"""Execute a parsed Excel plan live in Excel, verifying every step.

The original file is never modified unless the user explicitly says "ustiga saqla"
(then a backup copy is made first). Results go to "<name>_NEXVARA.xlsx".
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from nexvara.agent import files
from nexvara.agent.parse import Action, Plan
from nexvara.core.task import Task, UserError
from nexvara.knowledge.textnorm import fold

_FOOTER_WORDS = {"jami", "jami:", "итого", "itogo", "total", "всего", "hammasi"}


class CommandError(UserError):
    """A step that cannot be done as asked; the message is shown to the user."""


def _is_num(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _stem(w: str) -> str:
    return w[: max(3, len(w) - 3)] if len(w) > 4 else w


class Table:
    """The data block on the active sheet: header row + body, re-read after every change."""

    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.refresh()

    def refresh(self) -> None:
        from nexvara.skills.excel import ops

        used = self.ws.UsedRange
        values = ops.read_range(used)
        top = used.Row
        # Header = first row with at least two filled cells.
        for i, row in enumerate(values):
            if sum(v not in (None, "") for v in row) >= 2:
                top = used.Row + i
                break
        first_col = used.Column
        full = self.ws.Cells(top, first_col).CurrentRegion
        vals = ops.read_range(full)
        self.headers = [str(h).strip() if h is not None else "" for h in vals[0]]
        self.top = full.Row
        self.left = full.Column
        rows = vals[1:]
        # A trailing "JAMI" row is a footer, not data: sorting, filters, charts and pivots
        # must not treat it as one more record.
        self.has_footer = bool(rows) and any(
            isinstance(v, str) and fold(v).strip() in _FOOTER_WORDS for v in rows[-1]
        )
        if self.has_footer:
            rows = rows[:-1]
        self.rows = rows
        last = self.top + len(rows)
        self.range = self.ws.Range(
            self.ws.Cells(self.top, self.left),
            self.ws.Cells(last, self.left + len(self.headers) - 1),
        )

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    def column(self, idx: int) -> list[Any]:
        return [r[idx - 1] for r in self.rows]

    def numeric_columns(self) -> list[int]:
        out = []
        for i in range(1, len(self.headers) + 1):
            vals = [v for v in self.column(i) if v not in (None, "")]
            if vals and sum(_is_num(v) for v in vals) / len(vals) >= 0.8:
                out.append(i)
        return out

    def text_columns(self) -> list[int]:
        nums = set(self.numeric_columns())
        return [i for i in range(1, len(self.headers) + 1) if i not in nums]

    def find_column(self, words: str | None, letter: str | None = None) -> int | None:
        """Column by letter ("B") or by header words ("summa", "hududlar" -> "Hudud")."""
        if letter:
            from nexvara.skills.excel.table import col_letter

            for i in range(1, len(self.headers) + 1):
                if col_letter(self.left + i - 1) == letter.upper():
                    return i
        if not words:
            return None
        best, best_score = None, 0.0
        tokens = [fold(t) for t in re.findall(r"\w+", words)]
        for i, h in enumerate(self.headers, start=1):
            hf = fold(h)
            if not hf:
                continue
            htoks = re.findall(r"\w+", hf)
            score = sum(1 for t in tokens if any(ht.startswith(_stem(t)) or t.startswith(ht)
                                                 for ht in htoks))  # fmt: skip
            score = score / max(len(htoks), 1)
            if score > best_score:
                best, best_score = i, score
        return best if best_score > 0 else None

    def find_value(self, word: str, cols: list[int]) -> tuple[int, str] | None:
        """('Toshkentni' -> (col, 'Toshkent')) by matching against the real cell values."""
        w = fold(word)
        for c in cols:
            values = {str(v) for v in self.column(c) if isinstance(v, str) and v.strip()}
            for v in sorted(values, key=len, reverse=True):
                fv = fold(v)
                if fv == w or (len(fv) >= 3 and w.startswith(fv)) or fv.startswith(w):
                    return c, v
        return None


def run_excel_plan(
    task: Task,
    plan: Plan,
    source: Path,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
) -> dict[str, Any]:
    from nexvara.skills.excel.bridge import ExcelSession

    if plan.app != "excel":
        raise CommandError("Bu reja Excel uchun emas")
    overwrite = any(a.kind == "save" and a.args.get("overwrite") for a in plan.actions)
    out = source if overwrite and source.suffix.lower() == ".xlsx" else files.output_path(
        source, ".xlsx"
    )  # fmt: skip
    with ExcelSession(visible=visible, keep_open=keep_open) as xl:
        return _execute(task, xl, plan, source, out, overwrite, visible, pause, keep_open)


def _execute(
    task: Task,
    xl: Any,
    plan: Plan,
    source: Path,
    out: Path,
    overwrite: bool,
    visible: bool,
    pause: float,
    keep_open: bool,
) -> dict[str, Any]:
    # COM objects live only in this frame, so they are released before Excel quits.
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import format_table, freeze_header
    from nexvara.skills.excel.table import TableSpec, col_letter

    report: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise CommandError(f"{name}: {detail}")

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with task.step(f"Faylni ochish: {source.name}") as s:
        wb = xl.open_workbook(source)
        ws = wb.ActiveSheet
        xl.show()
        t = Table(ws)
        if len(t.headers) < 1 or t.n_rows < 1:
            raise CommandError("Faylda jadval topilmadi (sarlavha va kamida bitta qator kerak)")
        s.detail = f"{ws.Name}: {t.n_rows} qator, ustunlar: {', '.join(t.headers)}"
        report.append(s.detail)
    beat()

    pdf_path = csv_path = None
    for action in plan.actions:
        if action.kind in ("open", "save"):
            continue
        with task.step(_title(action)) as s:
            s.detail = _do(action, xl, ws, t, ops, format_table, freeze_header, TableSpec,
                           col_letter, check, visible)  # fmt: skip
            report.append(f"{_title(action)}: {s.detail}")
            t.refresh()
        if action.kind == "pdf":
            pdf_path = out.with_suffix(".pdf")
        if action.kind == "csv":
            csv_path = out.with_suffix(".csv")
        beat()

    with task.step("Saqlash") as s:
        saved = xl.save_as(wb, out, overwrite=overwrite)  # backs up the original when overwriting
        if overwrite:
            report.append("Asl fayl ustiga saqlandi (oldin .bak nusxasi olindi)")
        if pdf_path:
            pdf_path = files.output_path(source, ".pdf") if not overwrite else pdf_path
            ops.export_pdf(ws, pdf_path)
        if csv_path:
            csv_path = files.output_path(source, ".csv") if not overwrite else csv_path
            ops.export_csv(t.range, csv_path)
        s.detail = saved.name
        rows_before_close, headers_before = t.n_rows, t.headers
        wb.Close(SaveChanges=False)
        del ws, t
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        wb2 = xl.open_workbook(saved)
        t2 = Table(wb2.ActiveSheet)
        checks.append({"name": "Fayl ochiladi", "ok": True, "detail": saved.name})
        checks.append(
            {
                "name": "Jadval saqlangan",
                "ok": t2.headers == headers_before and t2.n_rows == rows_before_close,
                "detail": f"{t2.n_rows} qator",
            }
        )
        if pdf_path:
            ok = pdf_path.is_file() and pdf_path.read_bytes()[:5] == b"%PDF-"
            checks.append({"name": "PDF", "ok": ok, "detail": pdf_path.name})
        if csv_path:
            checks.append({"name": "CSV", "ok": csv_path.is_file(), "detail": csv_path.name})
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o‘tdi"
        del t2
        if failed:
            raise CommandError("Tekshiruv o‘tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            wb2.Close(SaveChanges=False)
        else:
            xl.show()

    return {
        "path": str(saved),
        "source": str(source),
        "pdf": str(pdf_path) if pdf_path else "",
        "csv": str(csv_path) if csv_path else "",
        "report": report,
        "checks": checks,
        "unknown": plan.unknown,
    }


def _title(a: Action) -> str:
    from nexvara.agent.parse import DESCRIBE

    return DESCRIBE.get(a.kind, a.kind)


def _do(a, xl, ws, t, ops, format_table, freeze_header, TableSpec, col_letter, check, visible):  # noqa: N803
    """Run one action; returns a short result text. Raises CommandError if impossible."""
    k = a.kind
    nums, texts = t.numeric_columns(), t.text_columns()

    if k == "dedupe":
        col = t.find_column(a.args.get("words"))
        cols = [col] if col else list(range(1, len(t.headers) + 1))
        before = t.n_rows
        removed = ops.remove_duplicates(t.range, cols)
        t.refresh()
        check("Dublikatlar", t.n_rows == before - removed, f"{removed} ta o‘chirildi")
        return f"{removed} ta takroriy qator o‘chirildi ({t.n_rows} qoldi)"

    if k == "clean":
        changed = ops.trim_text(t.range)
        empty = 0
        for r in range(t.top + t.n_rows, t.top, -1):
            row = ws.Range(ws.Cells(r, t.left), ws.Cells(r, t.left + len(t.headers) - 1))
            if all(v in (None, "") for v in ops.read_range(row)[0]):
                ws.Rows(r).Delete()
                empty += 1
        return f"{changed} ta katak tozalandi, {empty} ta bo‘sh qator o‘chirildi"

    if k == "sort":
        col = t.find_column(a.args.get("column"), _letter(a.args.get("column")))
        if col is None:
            raise CommandError(f"Ustun topilmadi: «{a.args.get('column')}». Ustunlar: "
                               f"{', '.join(t.headers)}")  # fmt: skip
        desc = bool(a.args.get("descending"))
        ops.sort_table(t.range, [(col, not desc)])
        t.refresh()
        vals = [v for v in t.column(col) if v not in (None, "")]
        key = (lambda v: (0, v)) if col in nums else (lambda v: (1, fold(str(v))))
        sorted_ok = [key(v) for v in vals] == sorted((key(v) for v in vals), reverse=desc)
        check("Saralash", sorted_ok, t.headers[col - 1])
        return f"«{t.headers[col - 1]}» bo‘yicha {'kamayish' if desc else 'o‘sish'} tartibida"

    if k == "clear_filter":
        ops.clear_filter(ws)
        return "filtr olib tashlandi"

    if k == "filter":
        words = (a.args.get("words") or "").split()
        col = t.find_column(" ".join(words), a.args.get("column"))
        value = a.args.get("value")
        crit = a.args.get("criteria")
        if crit:
            if col is None or col not in nums:
                col = col if col in nums else (nums[0] if len(nums) == 1 else None)
            if col is None:
                raise CommandError("Qaysi raqamli ustun bo‘yicha filtrlash kerakligini yozing")
            criteria = crit
            expect = sum(1 for v in t.column(col) if _is_num(v) and _cmp(v, crit))
        else:
            cand_words = [value] if value else [
                w for w in words if t.find_column(w) != col or col is None
            ]  # fmt: skip
            found = None
            for w in cand_words:
                found = t.find_value(w, [col] if col else texts)
                if found:
                    break
            if not found:
                raise CommandError(f"Filtr uchun qiymat topilmadi: «{' '.join(words)}»")
            col, criteria = found
            expect = sum(
                1 for v in t.column(col) if isinstance(v, str) and fold(v) == fold(criteria)
            )
        ops.autofilter(t.range, col, criteria)
        shown = ops.visible_row_count(t.range)
        check("Filtr", shown == expect, f"{shown} qator (kutilgan {expect})")
        return f"«{t.headers[col - 1]}» = {criteria}: {shown} ta qator ko‘rinadi"

    if k == "format":
        spec = TableSpec(t.headers, t.rows, nums)
        format_table(ws, t.range, spec, t.top, t.left)
        for c in nums:
            body = ops.column_range(t.range, c)
            integer = all(float(v).is_integer() for v in t.column(c) if _is_num(v))
            ops.set_number_format(body, "integer" if integer else "decimal")
        if visible:
            freeze_header(xl.app, t.top)
        cell = ws.Cells(t.top + 1, t.left + nums[0] - 1) if nums else None
        if cell is not None:
            check("Raqamlar markazda", cell.HorizontalAlignment == -4108)
        return f"sarlavha, chegaralar, {len(nums)} ta raqamli ustun markazda va formatda"

    if k == "total":
        if not nums:
            raise CommandError("Jadvalda raqamli ustun yo‘q")
        r = t.top + t.n_rows + 1
        first, last = t.top + 1, t.top + t.n_rows
        if 1 not in nums:
            ws.Cells(r, t.left).Value = "JAMI"
        for c in nums:
            letter = col_letter(t.left + c - 1)
            ws.Cells(r, t.left + c - 1).Formula = f"=SUM({letter}{first}:{letter}{last})"
        ws.Rows(r).Font.Bold = True
        for c in nums:
            got = ws.Cells(r, t.left + c - 1).Value
            want = sum(v for v in t.column(c) if _is_num(v))
            check(f"Jami: {t.headers[c - 1]}", abs((got or 0) - want) < 1e-6, str(got))
        return "jami: " + ", ".join(t.headers[c - 1] for c in nums)

    if k == "chart":
        words = a.args.get("words") or ""
        val = t.find_column(words)
        val = val if val in nums else (nums[-1] if nums else None)  # amount is usually last
        cat = next((c for c in texts if t.find_column(words) == c), texts[0] if texts else None)
        if val is None or cat is None:
            raise CommandError("Diagramma uchun matnli va raqamli ustun kerak")
        cats = [v for v in t.column(cat)]
        before = ws.ChartObjects().Count
        if len(set(cats)) == len(cats) and len(cats) <= 30:
            c1, c2 = col_letter(t.left + cat - 1), col_letter(t.left + val - 1)
            last = t.top + t.n_rows
            src = ws.Range(f"{c1}{t.top}:{c1}{last},{c2}{t.top}:{c2}{last}")
        else:
            src = _summary(ws, t, cat, val, col_letter)
        title = f"{t.headers[val - 1]} — {t.headers[cat - 1]} bo‘yicha"
        ops.add_chart(ws, src, a.args.get("kind") or "column", title)
        check("Diagramma", ws.ChartObjects().Count == before + 1)
        return f"{a.args.get('kind') or 'column'}: {title}"

    if k == "pivot":
        words = a.args.get("words") or ""
        tokens = words.split()
        row_col = next((t.find_column(w) for w in tokens if t.find_column(w) in texts), None)
        row_col = row_col or (texts[0] if texts else None)
        vals = [c for c in (t.find_column(w) for w in tokens) if c in nums] or nums[:3]
        if row_col is None or not vals:
            raise CommandError("Pivot uchun matnli va raqamli ustun kerak")
        sheet = ws.Parent.Worksheets.Add(After=ws)
        sheet.Name = _unique_sheet_name(ws.Parent, "Pivot")
        values = [
            (t.headers[c - 1], "sum", f"Jami {t.headers[c - 1]}") for c in dict.fromkeys(vals)
        ]
        pt = ops.add_pivot(
            ws.Parent, t.range, sheet.Range("A3"), rows=[t.headers[row_col - 1]],
            values=values, name=sheet.Name.replace(" ", ""),
        )  # fmt: skip
        rng = pt.TableRange1
        grand = rng.Cells(rng.Rows.Count, 2).Value
        want = sum(v for v in t.column(vals[0]) if _is_num(v))
        check("Pivot jami", abs((grand or 0) - want) < 1e-6, str(grand))
        ws.Activate()
        return f"«{sheet.Name}» varag‘ida: {t.headers[row_col - 1]} bo‘yicha"

    if k == "freeze":
        if visible:
            freeze_header(xl.app, t.top)
        return "sarlavha qatori qotirildi"

    if k in ("pdf", "csv"):
        return "saqlashda yaratiladi"

    raise CommandError(f"Excel uchun bu buyruq hali qo‘llanmaydi: «{a.text}»")


def _letter(text: str | None) -> str | None:
    return text if text and re.fullmatch(r"[A-Z]{1,2}", text) else None


def _cmp(v: float, crit: str) -> bool:
    m = re.match(r"(>=|<=|>|<|=)?(.+)", crit)
    op, num = m.group(1) or "=", float(m.group(2))
    return {">": v > num, "<": v < num, ">=": v >= num, "<=": v <= num, "=": v == num}[op]


def _unique_sheet_name(wb: Any, base: str) -> str:
    names = {wb.Worksheets(i).Name for i in range(1, wb.Worksheets.Count + 1)}
    if base not in names:
        return base
    i = 2
    while f"{base} {i}" in names:
        i += 1
    return f"{base} {i}"


def _summary(ws: Any, t: Table, cat: int, val: int, col_letter) -> Any:
    """Unique categories + SUMIFS next to the table, for a readable chart of repeated rows."""
    cats = list(dict.fromkeys(v for v in t.column(cat) if v not in (None, "")))[:30]
    left = t.left + len(t.headers) + 1
    c1, c2 = col_letter(left), col_letter(left + 1)
    cat_l, val_l = col_letter(t.left + cat - 1), col_letter(t.left + val - 1)
    first, last = t.top + 1, t.top + t.n_rows
    ws.Cells(t.top, left).Value = t.headers[cat - 1]
    ws.Cells(t.top, left + 1).Value = t.headers[val - 1]
    for i, c in enumerate(cats, start=1):
        ws.Cells(t.top + i, left).Value = c
        val_rng = f"${val_l}${first}:${val_l}${last}"
        cat_rng = f"${cat_l}${first}:${cat_l}${last}"
        ws.Cells(t.top + i, left + 1).Formula = f"=SUMIFS({val_rng},{cat_rng},{c1}{t.top + i})"
    return ws.Range(f"{c1}{t.top}:{c2}{t.top + len(cats)}")
