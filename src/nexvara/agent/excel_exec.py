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
# Summary rows NEXVARA adds under the table ("o‘rtacha qatorini qo‘sh"): also footers.
STAT_LABELS = {"average": "O‘RTACHA", "max": "MAKSIMUM", "min": "MINIMUM", "count": "SONI",
               "median": "MEDIANA"}  # fmt: skip
STAT_FUNCS = {"average": "AVERAGE", "max": "MAX", "min": "MIN", "count": "COUNT",
              "median": "MEDIAN"}  # fmt: skip
_FOOTER_WORDS |= {fold(v).lower() for v in STAT_LABELS.values()}


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
        self.footers: list[str] = []  # labels of the footer rows, top to bottom
        while rows:
            label = next(
                (
                    fold(v).strip()
                    for v in rows[-1]
                    if isinstance(v, str) and fold(v).strip() in _FOOTER_WORDS
                ),
                None,
            )
            if label is None:
                break
            self.footers.insert(0, label)
            rows = rows[:-1]
        self.has_footer = bool(self.footers)
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
        if "jami" in t.footers:
            r += t.footers.index("jami")
        elif t.footers:  # summary rows already there: JAMI goes right under the data
            ws.Rows(r).Insert()
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

    if k in _EXTRA:
        return _EXTRA[k](a, xl, ws, t, ops, col_letter, check, nums, texts)

    raise CommandError(f"Excel uchun bu buyruq hali qo‘llanmaydi: «{a.text}»")


# ---------------- professional commands ----------------
def _abs_col(t: Table, c: int) -> int:
    return t.left + c - 1


def _body(ws: Any, t: Table, c: int, footers: bool = False) -> Any:
    """Data cells of table column c (1-based), optionally with the footer rows."""
    last = t.top + t.n_rows + (len(t.footers) if footers else 0)
    return ws.Range(ws.Cells(t.top + 1, _abs_col(t, c)), ws.Cells(last, _abs_col(t, c)))


def _number_column(t: Table, words: str | None, nums: list[int], what: str,
                   letter: str | None = None) -> int:  # fmt: skip
    col = t.find_column(words, letter) if (words or letter) else None
    if col in nums:
        return col
    if col is None and len(nums) == 1:
        return nums[0]
    names = ", ".join(t.headers[c - 1] for c in nums) or "yo‘q"
    if col is not None:
        raise CommandError(f"«{t.headers[col - 1]}» raqamli ustun emas. {what} uchun raqamli "
                           f"ustunni yozing: {names}")  # fmt: skip
    raise CommandError(f"{what}: qaysi ustun? Raqamli ustunlar: {names}")


def _strict_column(t: Table, words: str | None, letter: str | None = None) -> int | None:
    """A column the user really named (for deleting): its header shares the first word's stem."""
    if letter:
        return t.find_column(None, letter)
    col = t.find_column(words) if words else None
    if col is None:
        return None
    first = fold(re.findall(r"\w+", words or "")[0])
    head = re.findall(r"\w+", fold(t.headers[col - 1]))
    return col if any(h.startswith(_stem(first)) or first.startswith(h) for h in head) else None


def _ex_highlight(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    from nexvara.skills.excel.table import excel_color

    col = _number_column(t, a.args.get("words"), nums, "Belgilash", a.args.get("column"))
    body = _body(ws, t, col)
    name = t.headers[col - 1]
    mode = a.args.get("mode") or "cells"
    color = a.args.get("color") or "#FDE68A"
    before = int(body.FormatConditions.Count)
    vals = t.column(col)
    if mode == "scale":
        ops.color_scale(body)
        check("Rang shkalasi", body.FormatConditions.Count == before + 1)
        return f"«{name}»: rang shkalasi (kichik — qizil, katta — yashil)"
    if mode == "bars":
        ops.data_bars(body)
        check("Ma’lumot chiziqlari", body.FormatConditions.Count == before + 1)
        return f"«{name}»: katak ichida chiziqlar"
    if mode in ("top", "bottom"):
        n = max(1, min(int(a.args.get("top") or 3), t.n_rows))
        fc = body.FormatConditions.AddTop10()
        fc.TopBottom = 1 if mode == "top" else 0  # xlTop10Top / xlTop10Bottom
        fc.Rank = n
        fc.Percent = False
        fc.Interior.Color = excel_color(color)
        del fc
        numbers = sorted((v for v in vals if _is_num(v)), reverse=mode == "top")
        edge = numbers[n - 1] if len(numbers) >= n else None
        want = [_is_num(v) and edge is not None and (v >= edge if mode == "top" else v <= edge)
                for v in vals]  # fmt: skip
    else:
        crit = a.args.get("criteria")
        if not crit:
            raise CommandError("Qaysi qiymatlarni belgilash kerak? Masalan: «Summa 1000000 dan "
                               "katta kataklarni qizil bilan belgila»")  # fmt: skip
        m = re.match(r"(>=|<=|>|<|=)?(.+)", crit)
        op, num = m.group(1) or "=", float(m.group(2))
        dec = ops.separators(xl.app)[0]
        value = str(int(num)) if num.is_integer() else repr(num).replace(".", dec)
        fc = body.FormatConditions.Add(1, ops.OPERATORS[op], f"={value}")  # xlCellValue
        fc.Interior.Color = excel_color(color)
        del fc
        want = [_is_num(v) and _cmp(v, crit) for v in vals]
    target = excel_color(color)
    got = [int(body.Cells(i, 1).DisplayFormat.Interior.Color) == target
           for i in range(1, min(len(vals), 300) + 1)]  # fmt: skip
    check("Belgilangan kataklar", got == want[: len(got)], f"{sum(got)} ta")
    return f"«{name}»: {sum(want)} ta katak belgilandi"


def _ex_numfmt(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    kind = a.args.get("kind") or "decimal"
    dec = a.args.get("decimals")
    words = a.args.get("words")
    if kind == "date":
        col = t.find_column(words, a.args.get("column")) if words or a.args.get("column") else None
        if col is None:
            raise CommandError("Sana formati: qaysi ustun? Ustunlar: " + ", ".join(t.headers))
        import datetime as _dt

        vals = [v for v in t.column(col) if v not in (None, "")]
        if not vals or not all(isinstance(v, _dt.datetime) or _is_num(v) for v in vals):
            raise CommandError(f"«{t.headers[col - 1]}» ustunida sanalar matn sifatida yozilgan "
                               "— Excel ularni sana deb bilmaydi")  # fmt: skip
        code = "dd.mm.yyyy"
    else:
        col = _number_column(t, words, nums, "Raqam formati", a.args.get("column"))
        frac = "." + "0" * dec if dec else ""
        values = [v for v in t.column(col) if _is_num(v)]
        if kind == "money":
            code = f'#,##0{frac}" so‘m"'
        elif kind == "usd":
            code = f'"$"#,##0{frac or ".00"}'
        elif kind == "percent":
            pfrac = "." + "0" * (1 if dec is None else dec) if dec != 0 else ""
            # 0,15 is 15 %; but a column of 15, 40 already holds percents: show "15,0%" as is.
            already = values and max(abs(v) for v in values) > 1.5
            code = f'0{pfrac}"%"' if already else f"0{pfrac}%"
        elif kind == "integer":
            code = "#,##0"
        else:
            code = f"#,##0.{'0' * (2 if dec is None else max(dec, 1))}"
    rng = _body(ws, t, col, footers=True)
    ops.set_number_format(rng, code)
    ws.Columns(_abs_col(t, col)).AutoFit()
    shown = str(rng.Cells(1, 1).Text)
    marks = {"money": "so‘m", "usd": "$", "percent": "%"}
    ok = "#" not in shown and (kind not in marks or marks[kind] in shown)
    check("Raqam formati", ok, shown)
    return f"«{t.headers[col - 1]}»: masalan {shown}"


def _ex_autofit(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    last = t.top + t.n_rows + len(t.footers)
    full = ws.Range(ws.Cells(t.top, t.left), ws.Cells(last, t.left + len(t.headers) - 1))
    full.Columns.AutoFit()
    hidden = [t.headers[c - 1] for c in nums
              if any(str(_body(ws, t, c).Cells(i, 1).Text).startswith("#")
                     for i in range(1, min(t.n_rows, 200) + 1))]  # fmt: skip
    check("Raqamlar to‘liq ko‘rinadi", not hidden, ", ".join(hidden))
    return f"{len(t.headers)} ta ustun kengligi matnga moslandi"


def _ex_stats(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    import statistics

    if not nums:
        raise CommandError("Jadvalda raqamli ustun yo‘q")
    if 1 in nums:
        raise CommandError("Statistika qatori nomini yozish uchun birinchi ustun matnli bo‘lishi "
                           "kerak (masalan «Hudud»)")  # fmt: skip
    first, last = t.top + 1, t.top + t.n_rows
    footers = list(t.footers)
    done = []
    for fn in a.args.get("funcs") or ["average"]:
        label = STAT_LABELS[fn]
        key = fold(label).lower()
        r = (t.top + t.n_rows + 1 + footers.index(key)) if key in footers else (
            t.top + t.n_rows + 1 + len(footers))  # fmt: skip
        if key not in footers:
            footers.append(key)
        ws.Cells(r, t.left).Value = label
        for c in nums:
            letter = col_letter(_abs_col(t, c))
            cell = ws.Cells(r, _abs_col(t, c))
            cell.Formula = f"={STAT_FUNCS[fn]}({letter}{first}:{letter}{last})"
            if fn in ("average", "median"):
                ops.set_number_format(cell, "decimal")
            vals = [v for v in t.column(c) if _is_num(v)]
            want = {"average": statistics.fmean, "max": max, "min": min, "count": len,
                    "median": statistics.median}[fn](vals) if vals else 0  # fmt: skip
            got = cell.Value
            check(f"{label}: {t.headers[c - 1]}", _is_num(got) and abs(got - want) < 1e-6,
                  str(got))  # fmt: skip
        ws.Rows(r).Font.Italic = True
        ws.Cells(r, t.left).Font.Bold = True
        done.append(label.capitalize())
    return ", ".join(done) + " qatorlari: " + ", ".join(t.headers[c - 1] for c in nums)


_TOKEN = re.compile(r"\s*([-+*/()])\s*")


def _ex_formula(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    import ast

    name = str(a.args["name"]).strip()
    parts = [p.strip() for p in _TOKEN.split(a.args["expr"]) if p and p.strip()]
    first = t.top + 1
    excel, cols = [], []
    for p in parts:
        if p in "+-*/()":
            excel.append(p)
            cols.append(p)
            continue
        num = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(%)?", p)
        if num:
            v = float(num.group(1).replace(",", ".")) / (100 if num.group(2) else 1)
            excel.append(repr(v) if not v.is_integer() else str(int(v)))
            cols.append(excel[-1])
            continue
        c = t.find_column(p)
        if c is None or c not in nums:
            raise CommandError(
                f"Formulada «{p}» ustuni topilmadi yoki raqamli emas. Raqamli "
                "ustunlar: " + ", ".join(t.headers[i - 1] for i in nums)
            )
        excel.append(f"{col_letter(_abs_col(t, c))}{first}")
        cols.append(c)
    try:
        ast.parse("".join(str(x) if not isinstance(x, int) else "1" for x in cols), mode="eval")
    except SyntaxError as e:
        raise CommandError(f"Formulani tushunmadim: «{a.args['expr']}»") from e
    existing = next((i for i, h in enumerate(t.headers, 1) if fold(h) == fold(name)), None)
    if existing is not None and existing in nums and existing not in cols:
        c_new = existing  # "Foyda" again: recalculate the same column
    elif existing is not None:
        raise CommandError(f"«{name}» ustuni allaqachon bor")
    else:
        c_new = len(t.headers) + 1
        ws.Cells(t.top, _abs_col(t, c_new)).Value = name
        prev, head = ws.Cells(t.top, _abs_col(t, c_new) - 1), ws.Cells(t.top, _abs_col(t, c_new))
        head.Font.Bold = prev.Font.Bold
        if int(prev.Interior.ColorIndex) != -4142:  # xlColorIndexNone
            head.Interior.Color = prev.Interior.Color
            head.Font.Color = prev.Font.Color
        head.HorizontalAlignment = prev.HorizontalAlignment
    body = ws.Range(ws.Cells(first, _abs_col(t, c_new)),
                    ws.Cells(t.top + t.n_rows, _abs_col(t, c_new)))  # fmt: skip
    body.Formula = "=" + "".join(excel)  # relative references follow each row
    # Footer rows (JAMI, O‘RTACHA ...) get the same summary for the new column.
    for i, key in enumerate(t.footers):
        fn = (
            "SUM"
            if key == "jami"
            else next(
                (STAT_FUNCS[f] for f, lab in STAT_LABELS.items() if fold(lab).lower() == key), None
            )
        )
        if fn:
            letter = col_letter(_abs_col(t, c_new))
            ws.Cells(
                t.top + t.n_rows + 1 + i, _abs_col(t, c_new)
            ).Formula = f"={fn}({letter}{first}:{letter}{t.top + t.n_rows})"
    got = [r[0] for r in ops.read_range(body)]
    want: list[float | None] = []
    for row in t.rows:
        expr = []
        for x in cols:
            if isinstance(x, int):
                v = row[x - 1]
                expr.append(repr(float(v)) if _is_num(v) else "None")
            else:
                expr.append(str(x))
        try:
            want.append(_safe_eval("".join(expr)))
        except (ZeroDivisionError, TypeError, ValueError):
            want.append(None)
    bad = sum(
        1
        for g, w in zip(got, want, strict=False)
        if w is not None and not (_is_num(g) and abs(g - w) < 1e-6 * max(1, abs(w)))
    )
    check("Formula natijalari", bad == 0, f"{bad} ta qator mos emas")
    integer = all(float(w).is_integer() for w in want if w is not None)
    ops.set_number_format(_body(ws, t, c_new, footers=True), "integer" if integer else "decimal")
    if int(ws.Cells(first, _abs_col(t, c_new) - 1).Borders(9).LineStyle) != -4142:
        full = ws.Range(
            ws.Cells(t.top, _abs_col(t, c_new)),
            ws.Cells(t.top + t.n_rows + len(t.footers), _abs_col(t, c_new)),
        )
        full.Borders.LineStyle = 1
    ws.Columns(_abs_col(t, c_new)).AutoFit()
    return f"«{name}» = {a.args['expr']} ({t.n_rows} qator, Excel formulasi bilan)"


def _safe_eval(expr: str) -> float | None:
    """Arithmetic only (numbers, + - * /, brackets); None when a cell was not a number."""
    import ast
    import operator

    if "None" in expr:
        return None
    ops_ = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}  # fmt: skip

    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int | float):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in ops_:
            return ops_[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops_:
            return ops_[type(n.op)](ev(n.operand))
        raise ValueError("faqat arifmetika")

    return ev(ast.parse(expr, mode="eval"))


def _ex_rename_sheet(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    name = re.sub(r"[\[\]:*?/\\]", "-", str(a.args.get("name") or "")).strip(" '")[:31]
    if not name:
        raise CommandError("Varaq uchun yangi nomni «qo‘shtirnoq» ichida yozing")
    wb = ws.Parent
    taken = {str(wb.Worksheets(i).Name) for i in range(1, wb.Worksheets.Count + 1)} - {ws.Name}
    if name in taken:
        raise CommandError(f"«{name}» nomli varaq allaqachon bor")
    old = str(ws.Name)
    ws.Name = name
    check("Varaq nomi", str(ws.Name) == name, name)
    return f"«{old}» → «{name}»"


def _ex_delete_column(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    col = _strict_column(t, a.args.get("words"), a.args.get("column"))
    if col is None:
        raise CommandError(f"O‘chirish uchun ustun topilmadi: «{a.args.get('words')}». Ustunlar: "
                           + ", ".join(t.headers))  # fmt: skip
    if len(t.headers) < 2:
        raise CommandError("Jadvaldagi yagona ustunni o‘chirib bo‘lmaydi")
    name = t.headers[col - 1]
    last = t.top + t.n_rows + len(t.footers)
    ws.Range(ws.Cells(t.top, _abs_col(t, col)), ws.Cells(last, _abs_col(t, col))).Delete(-4159)
    t.refresh()
    check("Ustun o‘chirildi", name not in t.headers, name)
    return f"«{name}» ustuni o‘chirildi (asl fayl o‘zgarmaydi)"


def _ex_print_setup(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    try:
        ps = ws.PageSetup
        if a.args.get("landscape") is not None:
            ps.Orientation = 2 if a.args["landscape"] else 1  # xlLandscape / xlPortrait
        ps.Zoom = False
        ps.FitToPagesWide = 1
        ps.FitToPagesTall = False
        ps.PrintTitleRows = f"${t.top}:${t.top}"
        ps.CenterHorizontally = True
        orient = int(ps.Orientation)
        wide = int(ps.FitToPagesWide)
        del ps
    except Exception as e:  # PageSetup needs a printer driver (even "Microsoft Print to PDF")
        raise CommandError(
            "Chop etish sozlamalarini o‘zgartirib bo‘lmadi: Windows’da printer "
            "(masalan «Microsoft Print to PDF») o‘rnatilganini tekshiring"
        ) from e
    check("Bir sahifa eniga", wide == 1)
    if a.args.get("landscape") is not None:
        check("Sahifa yo‘nalishi", orient == (2 if a.args["landscape"] else 1))
    what = "albom, " if orient == 2 else ""
    return f"{what}eni bir sahifaga sig‘adi, sarlavha har sahifada takrorlanadi"


def _ex_font(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    if not a.args.get("name") and not a.args.get("size"):
        raise CommandError("Qaysi shrift yoki o‘lcham kerakligini yozing (masalan «Arial 12»)")
    last = t.top + t.n_rows + len(t.footers)
    rng = ws.Range(ws.Cells(t.top, t.left), ws.Cells(last, t.left + len(t.headers) - 1))
    if a.args.get("name"):
        rng.Font.Name = a.args["name"]
    if a.args.get("size"):
        rng.Font.Size = a.args["size"]
    rng.Columns.AutoFit()
    f = ws.Cells(t.top + 1, t.left).Font
    ok = (not a.args.get("name") or f.Name == a.args["name"]) and (
        not a.args.get("size") or abs(f.Size - a.args["size"]) < 0.01)  # fmt: skip
    check("Shrift", ok, f"{f.Name} {f.Size}")
    return " ".join(str(x) for x in (a.args.get("name"), a.args.get("size")) if x)


def _ex_replace(a, xl, ws, t, ops, col_letter, check, nums, texts) -> str:
    find, repl = str(a.args["find"]), str(a.args["replace"])
    used = ws.UsedRange

    def count() -> int:
        return sum(str(v).count(find) for row in ops.read_range(used) for v in row
                   if isinstance(v, str))  # fmt: skip

    before = count()
    if before == 0:
        raise CommandError(f"Jadvalda «{find}» matni topilmadi")
    used.Replace(find, repl, 2, 1, True)  # What, Replacement, xlPart, xlByRows, MatchCase
    left = count() if find not in repl else 0
    check("Almashtirildi", left == 0, f"{before} ta")
    return f"«{find}» → «{repl}»: {before} ta"


_EXTRA = {
    "highlight": _ex_highlight, "numfmt": _ex_numfmt, "autofit": _ex_autofit,
    "stats": _ex_stats, "formula": _ex_formula, "rename_sheet": _ex_rename_sheet,
    "delete_column": _ex_delete_column, "print_setup": _ex_print_setup, "font": _ex_font,
    "replace": _ex_replace,
}  # fmt: skip


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
