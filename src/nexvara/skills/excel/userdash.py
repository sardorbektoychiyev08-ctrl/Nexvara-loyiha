"""An Excel dashboard from the user's own table: «savdo jadvalidan Excelda dashboard yasa».

A new workbook (the source is not changed): the data sheet, and a Dashboard sheet with KPI
formulas (SUM per number column), a SUMIFS summary per category and charts over it. Reopened
and compared with the same sums computed in Python.
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from nexvara.core.task import Task, UserError

DATA_SHEET = "Ma'lumot"
DASH_SHEET = "Dashboard"
_TOTAL = re.compile(r"^\s*(jami|итого|всего|total|umumiy)\b", re.I)


def _total(header: str) -> str:
    return header if _TOTAL.match(header) else f"Jami {header}"


def split_table(values: list[list[Any]]) -> tuple[list[str], list[list[Any]], int, list[int]]:
    """(headers, rows, category column, number columns) — 0-based; a «Jami» row is dropped."""
    rows = [list(r) for r in values if any(v not in (None, "") for v in r)]
    if len(rows) < 3:
        raise UserError("Dashboard uchun kamida 2 qatorli jadval kerak")
    headers = [str(h if h not in (None, "") else f"Ustun {i + 1}") for i, h in enumerate(rows[0])]
    body = [r for r in rows[1:] if not (isinstance(r[0], str) and _TOTAL.match(r[0]))]

    def numeric(c: int) -> bool:
        vals = [r[c] for r in body if r[c] not in (None, "")]
        return bool(vals) and all(isinstance(v, int | float) and not isinstance(v, bool)
                                  for v in vals)  # fmt: skip

    nums = [c for c in range(len(headers)) if numeric(c)]
    texts = [c for c in range(len(headers)) if c not in nums]
    if not nums:
        raise UserError("Jadvalda son ustuni yo‘q — dashboard uchun raqamlar kerak")
    if not texts:
        raise UserError("Jadvalda nom/turkum ustuni yo‘q")

    # The category: the text column with the fewest distinct values, but more than one.
    def distinct(c: int) -> int:
        return len({str(r[c]) for r in body})

    cat = min(texts, key=lambda c: (distinct(c) < 2, distinct(c)))
    return headers, body, cat, nums


def expected(body: list[list[Any]], cat: int, nums: list[int]) -> dict[str, Any]:
    totals = {c: sum(float(r[c] or 0) for r in body) for c in nums}
    groups: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for r in body:
        for c in nums:
            groups[str(r[cat])][c] += float(r[c] or 0)
    return {"totals": totals, "groups": {k: dict(v) for k, v in groups.items()}}


def run_user_dashboard(task: Task, source: str | Path, *, keep_open: bool = True) -> dict[str, Any]:
    from nexvara.skills.excel.bridge import ExcelSession

    src = Path(source)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path.home() / "Documents" / "NEXVARA" / f"{src.stem} dashboard {stamp}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    with ExcelSession(visible=True, keep_open=keep_open) as xl:
        return _build(task, xl, src, out, keep_open)


def _build(task: Task, xl: Any, src: Path, out: Path, keep_open: bool) -> dict[str, Any]:
    # COM objects live only in this frame, so they are released before Excel quits.
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import format_table
    from nexvara.skills.excel.formulas import sheet_ref, sumifs
    from nexvara.skills.excel.table import TableSpec, col_letter

    with task.step(f"Jadvalni o‘qish: {src.name}") as s:
        target = str(src.resolve()).lower()
        already = [w for w in xl.app.Workbooks if str(w.FullName).lower() == target]
        wb_src = already[0] if already else xl.open_workbook(src)
        values = ops.read_range(wb_src.Worksheets(1).UsedRange)
        if not already:  # a workbook the user has open stays open
            wb_src.Close(False)
        del wb_src, already
        headers, body, cat, nums = split_table(values)
        s.detail = (f"{len(body)} qator; turkum: {headers[cat]}; "
                    f"sonlar: {', '.join(headers[c] for c in nums)}")  # fmt: skip

    with task.step("Ma'lumot varag‘i") as s:
        wb = xl.new_workbook()
        data = wb.Worksheets(1)
        data.Name = DATA_SHEET
        clean = [[("" if v is None else v) for v in r] for r in body]
        table = ops.write_rows(data, [headers, *clean])
        format_table(data, table, TableSpec(headers, clean, [c + 1 for c in nums]))
        ops.autofilter(table)
        s.detail = f"{len(body)} qator"
        xl.show()

    last = len(body) + 1
    L = col_letter  # noqa: N806

    def col(c: int) -> str:
        return sheet_ref(DATA_SHEET, f"${L(c + 1)}$2:${L(c + 1)}${last}")

    groups = list(dict.fromkeys(str(r[cat]) for r in body))
    with task.step("Ko‘rsatkichlar va formulalar") as s:
        dash = wb.Worksheets.Add(Before=data)
        dash.Name = DASH_SHEET
        dash.Activate()
        dash.Range("A1").Value = f"{src.stem} — dashboard"
        # KPIs: A3:B…
        kpis = [["Ko‘rsatkich", "Qiymat"], ["Yozuvlar soni", f"=COUNTA({col(cat)})"]]
        kpis += [[_total(headers[c]), f"=SUM({col(c)})"] for c in nums]
        kpi_rng = dash.Range(f"A3:B{2 + len(kpis)}")
        kpi_rng.Formula = kpis
        # Summary per category: D3…
        top, left = 3, 4
        width = 1 + len(nums)
        sum_rng = dash.Range(dash.Cells(top, left), dash.Cells(top + len(groups), left + width - 1))
        rows = [[headers[cat], *(headers[c] for c in nums)]]
        for i, g in enumerate(groups, start=1):
            ref = f"{L(left)}{top + i}"
            rows.append([g, *("=" + sumifs(col(c), (col(cat), ref)) for c in nums)])
        sum_rng.Formula = rows
        s.detail = f"{len(kpis) - 1} ta ko‘rsatkich, {len(groups)} ta {headers[cat]}"

    with task.step("Formatlash") as s:
        title = dash.Range("A1")
        title.Font.Size = 18
        title.Font.Bold = True
        for rng, numeric in ((kpi_rng, [2]), (sum_rng, list(range(2, width + 1)))):
            body_none = [[None] * rng.Columns.Count] * (rng.Rows.Count - 1)
            hdr = [str(v) for v in ops.read_range(rng.Rows(1))[0]]
            format_table(dash, rng, TableSpec(hdr, body_none, numeric), rng.Row, rng.Column)
        ops.set_number_format(dash.Range(f"B4:B{2 + len(kpis)}"), "integer")
        ops.set_number_format(
            dash.Range(
                dash.Cells(top + 1, left + 1), dash.Cells(top + len(groups), left + width - 1)
            ),
            "integer",
        )
        ops.data_bars(dash.Range(dash.Cells(top + 1, left + width - 1),
                                 dash.Cells(top + len(groups), left + width - 1)))  # fmt: skip
        dash.Columns("A:B").AutoFit()
        sum_rng.Columns.AutoFit()
        s.detail = "jadval uslubi, raqam formati, ma’lumot chiziqlari"

    with task.step("Grafiklar") as s:
        chart_top = dash.Cells(top + len(groups) + 3, 1).Top
        x0 = dash.Cells(1, 1).Left
        cats = dash.Range(dash.Cells(top, left), dash.Cells(top + len(groups), left))
        main = nums[-1]  # usually «Jami» / the amount
        main_col = left + 1 + nums.index(main)
        main_rng = dash.Range(dash.Cells(top, main_col), dash.Cells(top + len(groups), main_col))
        ops.add_chart(dash, xl.app.Union(cats, main_rng), "column",
                      f"{headers[main]} — {headers[cat]} bo‘yicha", left=x0, top=chart_top,
                      width=460, height=280)  # fmt: skip
        ops.add_chart(dash, xl.app.Union(cats, main_rng), "pie", f"{headers[main]} ulushi",
                      left=x0 + 470, top=chart_top, width=360, height=280)  # fmt: skip
        if len(nums) > 1:
            other = left + 1 + nums.index(nums[0])
            o_rng = dash.Range(dash.Cells(top, other), dash.Cells(top + len(groups), other))
            ops.add_chart(dash, xl.app.Union(cats, o_rng), "bar",
                          f"{headers[nums[0]]} — {headers[cat]} bo‘yicha", left=x0 + 840,
                          top=chart_top, width=420, height=280)  # fmt: skip
        s.detail = f"{dash.ChartObjects().Count} ta grafik"
        dash.Range("A1").Select()

    with task.step("Saqlash") as s:
        saved = xl.save_as(wb, out)
        s.detail = saved.name
        wb.Close(False)

    with task.step("Qayta ochib tekshirish") as s:
        wb2 = xl.open_workbook(saved)
        xl.show()
        d2 = wb2.Worksheets(DASH_SHEET)
        exp = expected(body, cat, nums)
        checks = []
        for i, c in enumerate(nums):
            got = d2.Cells(5 + i, 2).Value
            ok = isinstance(got, int | float) and abs(got - exp["totals"][c]) < 1e-6
            checks.append({"name": _total(headers[c]), "ok": ok, "detail": str(got)})
        bad = [
            g
            for i, g in enumerate(groups, start=1)
            if abs((d2.Cells(top + i, main_col).Value or 0) - exp["groups"][g][main]) > 1e-6
        ]
        checks.append({"name": f"{headers[cat]} bo‘yicha SUMIFS", "ok": not bad,
                       "detail": ", ".join(bad)})  # fmt: skip
        n_charts = d2.ChartObjects().Count
        checks.append({"name": "Grafiklar", "ok": n_charts >= 2, "detail": str(n_charts)})
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o‘tdi"
        d2.Activate()
        if failed:
            raise UserError("Tekshiruv o‘tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            wb2.Close(False)
    return {"path": str(saved), "source": str(src), "checks": checks,
            "report": [f"{saved.name} — Dashboard varag‘i ekranda ochiq"]}  # fmt: skip
