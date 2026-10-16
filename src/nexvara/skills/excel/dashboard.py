"""Excel sales dashboard built live: data sheet, formula summaries, KPIs, charts, pivot.

Every number on the dashboard is an Excel formula over the data sheet, and the
result is reopened and compared against the same figures computed in Python.
"""

from __future__ import annotations

import datetime as dt
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from nexvara.core.task import Task
from nexvara.skills.excel.formulas import growth, lookup, sheet_ref, sumifs
from nexvara.skills.excel.table import validate_save_path

DATA_SHEET = "Ma'lumot"
DASH_SHEET = "Dashboard"
PIVOT_SHEET = "Pivot"

MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
          "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"]  # fmt: skip
REGIONS = {"Toshkent": 52_000_000, "Samarqand": 31_000_000, "Buxoro": 22_000_000,
           "Farg'ona": 27_000_000}  # fmt: skip
CATEGORIES = {"Ofis jihozlari": 1.0, "Texnika": 1.6, "Kanselyariya": 0.45}
DATA_HEADERS = ["Sana", "Oy", "Hudud", "Kategoriya", "Daromad", "Xarajat"]
LOSS_MONTH = 2  # February runs at a loss so COUNTIF has something to find

# Dashboard layout (1-based rows/cols)
KPI_TOP = 3
MONTH_TOP, MONTH_LEFT = 3, 4  # D3: Oy | Daromad | Xarajat | Foyda | O'sish
REGION_TOP, REGION_LEFT = 3, 10  # J3: Hudud | Daromad | Ulush
CAT_TOP = REGION_TOP + len(REGIONS) + 3  # under the region table


def data_rows(year: int = 2026) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for m in range(1, 13):
        for ri, (region, base) in enumerate(REGIONS.items()):
            for ci, (cat, mult) in enumerate(CATEGORIES.items()):
                revenue = round(
                    base * mult * (1 + 0.03 * m) * (0.9 + ((m * 7 + ri * 5 + ci * 3) % 21) / 100)
                )
                ratio = 1.12 if m == LOSS_MONTH else 0.58 + ((m * 3 + ri * 7 + ci) % 25) / 100
                cost = round(revenue * ratio)
                rows.append([dt.date(year, m, 1), MONTHS[m - 1], region, cat, revenue, cost])
    return rows


def expected_figures(rows: list[list[Any]]) -> dict[str, Any]:
    by_month: dict[str, list[int]] = {m: [0, 0] for m in MONTHS}
    by_region: dict[str, int] = defaultdict(int)
    by_cat: dict[str, int] = defaultdict(int)
    for _d, month, region, cat, rev, cost in rows:
        by_month[month][0] += rev
        by_month[month][1] += cost
        by_region[region] += rev
        by_cat[cat] += rev
    revenue = sum(r[4] for r in rows)
    cost = sum(r[5] for r in rows)
    monthly_rev = [by_month[m][0] for m in MONTHS]
    growths = [monthly_rev[i] / monthly_rev[i - 1] - 1 for i in range(1, 12)]
    return {
        "revenue": revenue,
        "cost": cost,
        "profit": revenue - cost,
        "margin": (revenue - cost) / revenue,
        "avg_growth": sum(growths) / len(growths),
        "best_region": max(by_region, key=by_region.__getitem__),
        "loss_months": sum(1 for m in MONTHS if by_month[m][0] < by_month[m][1]),
        "by_month": by_month,
        "by_region": dict(by_region),
        "by_cat": dict(by_cat),
    }


def default_output_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.home() / "Documents" / "NEXVARA" / f"nexvara-dashboard-{stamp}.xlsx"


class VerificationError(Exception):
    pass


def run_dashboard(
    task: Task,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.4,
) -> dict[str, Any]:
    from nexvara.skills.excel.bridge import ExcelSession

    out = Path(out_path) if out_path else default_output_path()
    validate_save_path(out)

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with ExcelSession(visible=visible, keep_open=keep_open) as xl:
        saved, checks, xlookup = _build_and_verify(task, xl, out, beat, keep_open)
    return {"path": str(saved), "checks": checks, "xlookup": xlookup}


def _build_and_verify(
    task: Task, xl: Any, out: Path, beat: Any, keep_open: bool
) -> tuple[Path, list[dict[str, Any]], bool]:
    # COM objects live only in this frame, so they are released before Excel quits.
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import format_table
    from nexvara.skills.excel.formulas import supports_xlookup
    from nexvara.skills.excel.table import TableSpec, col_letter

    rows = data_rows()
    n = len(rows)

    with task.step("Excel'ni ochish") as s:
        xl.show()
        xlookup = supports_xlookup(xl.app)
        s.detail = f"Excel {xl.version}, XLOOKUP {'bor' if xlookup else 'yo`q → INDEX/MATCH'}"
    beat()

    with task.step("Ma'lumot varag'i") as s:
        wb = xl.new_workbook()
        data = wb.Worksheets(1)
        data.Name = DATA_SHEET
        table = ops.write_rows(data, [DATA_HEADERS, *rows])
        spec = TableSpec(DATA_HEADERS, rows, numeric_columns=[5, 6])
        format_table(data, table, spec)
        ops.set_number_format(ops.column_range(table, 1), "date")
        ops.autofilter(table)
        s.detail = f"{n} qator, {table.Address}"
        xl.show()
    beat()

    last = n + 1

    def col(c: int) -> str:
        letter = col_letter(c)
        return sheet_ref(DATA_SHEET, f"${letter}$2:${letter}${last}")

    month_col, region_col, cat_col, rev_col, cost_col = col(2), col(3), col(4), col(5), col(6)

    with task.step("Hisob-kitob formulalari") as s:
        dash = wb.Worksheets.Add(Before=data)
        dash.Name = DASH_SHEET
        dash.Activate()
        dash.Range("A1").Value = "NEXVARA — Savdo dashboardi 2026"

        # Monthly summary: SUMIFS + growth
        m0, c0 = MONTH_TOP, MONTH_LEFT
        L = col_letter  # noqa: N806
        mc, rc, cc, pc, gc = (L(c0 + i) for i in range(5))
        dash.Range(f"{mc}{m0}:{gc}{m0}").Value = [["Oy", "Daromad", "Xarajat", "Foyda", "O'sish"]]
        dash.Range(f"{mc}{m0 + 1}:{mc}{m0 + 12}").Value = [[m] for m in MONTHS]
        month_formulas = []
        for i in range(12):
            r = m0 + 1 + i
            month_formulas.append(
                [
                    "=" + sumifs(rev_col, (month_col, f"{mc}{r}")),
                    "=" + sumifs(cost_col, (month_col, f"{mc}{r}")),
                    f"={rc}{r}-{cc}{r}",
                    '=""' if i == 0 else "=" + growth(f"{rc}{r}", f"{rc}{r - 1}"),
                ]
            )
        dash.Range(f"{rc}{m0 + 1}:{gc}{m0 + 12}").Formula = month_formulas
        month_rng = dash.Range(f"{mc}{m0}:{gc}{m0 + 12}")

        # Region + category summaries
        r0, k0 = REGION_TOP, REGION_LEFT
        hc, dc, uc = L(k0), L(k0 + 1), L(k0 + 2)
        nr = len(REGIONS)
        dash.Range(f"{hc}{r0}:{uc}{r0}").Value = [["Hudud", "Daromad", "Ulush"]]
        dash.Range(f"{hc}{r0 + 1}:{hc}{r0 + nr}").Value = [[r] for r in REGIONS]
        dash.Range(f"{dc}{r0 + 1}:{uc}{r0 + nr}").Formula = [
            [
                "=" + sumifs(rev_col, (region_col, f"{hc}{r}")),
                f"={dc}{r}/SUM(${dc}${r0 + 1}:${dc}${r0 + nr})",
            ]
            for r in range(r0 + 1, r0 + nr + 1)
        ]
        region_rng = dash.Range(f"{hc}{r0}:{uc}{r0 + nr}")

        t0, ncat = CAT_TOP, len(CATEGORIES)
        dash.Range(f"{hc}{t0}:{dc}{t0}").Value = [["Kategoriya", "Daromad"]]
        dash.Range(f"{hc}{t0 + 1}:{hc}{t0 + ncat}").Value = [[c] for c in CATEGORIES]
        dash.Range(f"{dc}{t0 + 1}:{dc}{t0 + ncat}").Formula = [
            ["=" + sumifs(rev_col, (cat_col, f"{hc}{r}"))] for r in range(t0 + 1, t0 + ncat + 1)
        ]
        cat_rng = dash.Range(f"{hc}{t0}:{dc}{t0 + ncat}")

        # KPIs
        k = KPI_TOP
        reg_vals = f"${dc}${r0 + 1}:${dc}${r0 + nr}"
        reg_names = f"${hc}${r0 + 1}:${hc}${r0 + nr}"
        kpis = [
            ("Ko'rsatkich", "Qiymat"),
            ("Jami daromad", f"=SUM({rev_col})"),
            ("Jami xarajat", f"=SUM({cost_col})"),
            ("Sof foyda", f"=B{k + 1}-B{k + 2}"),
            ("Foyda marjasi", f'=IF(B{k + 1}=0,"",B{k + 3}/B{k + 1})'),
            ("O'rtacha oylik o'sish", f"=AVERAGE({gc}{m0 + 2}:{gc}{m0 + 12})"),
            ("Eng yaxshi hudud", "=" + lookup(f"MAX({reg_vals})", reg_vals, reg_names, xlookup)),
            ("Zarar ko'rgan oylar", f'=COUNTIF({pc}{m0 + 1}:{pc}{m0 + 12},"<0")'),
        ]
        dash.Range(f"A{k}:A{k + len(kpis) - 1}").Value = [[a] for a, _ in kpis]
        dash.Range(f"B{k}:B{k + len(kpis) - 1}").Formula = [[b] for _, b in kpis]
        kpi_rng = dash.Range(f"A{k}:B{k + len(kpis) - 1}")
        s.detail = "SUMIFS, IF, COUNTIF, AVERAGE, " + ("XLOOKUP" if xlookup else "INDEX/MATCH")
    beat()

    with task.step("Formatlash"):
        title = dash.Range("A1")
        title.Font.Size = 18
        title.Font.Bold = True
        for rng, numeric in ((kpi_rng, []), (month_rng, [2, 3, 4, 5]), (region_rng, [2, 3]),
                             (cat_rng, [2])):  # fmt: skip
            hdr = [str(v) for v in ops.read_range(rng.Rows(1))[0]]
            body = [[None] * len(hdr)] * (rng.Rows.Count - 1)
            format_table(dash, rng, TableSpec(hdr, body, numeric), rng.Row, rng.Column)
        ops.set_number_format(dash.Range(f"B{k + 1}:B{k + 3}"), "integer")
        ops.set_number_format(dash.Range(f"B{k + 4}:B{k + 5}"), "percent")
        ops.center(dash.Range(f"B{k + 1}:B{k + len(kpis) - 1}"))
        ops.set_number_format(dash.Range(f"{gc}{m0 + 1}:{gc}{m0 + 12}"), "percent")
        ops.set_number_format(dash.Range(f"{uc}{r0 + 1}:{uc}{r0 + nr}"), "percent")
        ops.color_scale(dash.Range(f"{pc}{m0 + 1}:{pc}{m0 + 12}"))
        ops.data_bars(dash.Range(f"{dc}{r0 + 1}:{dc}{r0 + nr}"))
        dash.Columns("A").AutoFit()
        dash.Columns("B").ColumnWidth = 22
        xl.show()
    beat()

    with task.step("Grafiklar") as s:
        chart_top = dash.Cells(m0 + 15, 1).Top
        ops.add_chart(dash, dash.Range(f"{mc}{m0}:{cc}{m0 + 12}"), "line_markers",
                      "Oylik daromad va xarajat", left=dash.Cells(1, 1).Left, top=chart_top,
                      width=520, height=280)  # fmt: skip
        ops.add_chart(dash, dash.Range(f"{hc}{r0}:{dc}{r0 + nr}"), "column",
                      "Hududlar bo'yicha daromad", left=dash.Cells(1, 1).Left + 530,
                      top=chart_top, width=380, height=280)  # fmt: skip
        ops.add_chart(dash, cat_rng, "doughnut", "Kategoriyalar ulushi",
                      left=dash.Cells(1, 1).Left + 920, top=chart_top, width=320,
                      height=280)  # fmt: skip
        s.detail = f"{dash.ChartObjects().Count} ta grafik"
    beat()

    with task.step("PivotTable") as s:
        pivot_ws = wb.Worksheets.Add(After=dash)
        pivot_ws.Name = PIVOT_SHEET
        pt = ops.add_pivot(wb, table, pivot_ws.Range("A3"), rows=["Hudud"],
                           columns=["Kategoriya"], values=[("Daromad", "sum", "Jami daromad")],
                           name="HududKategoriya")  # fmt: skip
        s.detail = pt.TableRange1.Address
        dash.Activate()
        dash.Range("A1").Select()
    beat()

    with task.step("Saqlash") as s:
        saved = xl.save_as(wb, out)
        s.detail = str(saved)
        wb.Close(SaveChanges=False)
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        wb2 = xl.open_workbook(saved)
        xl.show()
        checks = verify_dashboard(wb2, expected_figures(rows))
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o'tdi"
        if failed:
            raise VerificationError("Tekshiruv o'tmadi: " + ", ".join(c["name"] for c in failed))
        wb2.Worksheets(DASH_SHEET).Activate()
        if not keep_open:
            wb2.Close(SaveChanges=False)
    return saved, checks, xlookup


def _close(a: Any, b: float, rel: float = 1e-9) -> bool:
    return isinstance(a, int | float) and abs(a - b) <= rel * max(1.0, abs(b))


def verify_dashboard(wb: Any, exp: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    dash = wb.Worksheets(DASH_SHEET)
    k = KPI_TOP
    kpi = {dash.Cells(r, 1).Value: dash.Cells(r, 2).Value for r in range(k + 1, k + 8)}
    check("Jami daromad", _close(kpi["Jami daromad"], exp["revenue"]), str(kpi["Jami daromad"]))
    check("Jami xarajat", _close(kpi["Jami xarajat"], exp["cost"]), str(kpi["Jami xarajat"]))
    check("Sof foyda", _close(kpi["Sof foyda"], exp["profit"]), str(kpi["Sof foyda"]))
    check("Foyda marjasi", _close(kpi["Foyda marjasi"], exp["margin"]), str(kpi["Foyda marjasi"]))
    check(
        "O'rtacha oylik o'sish",
        _close(kpi["O'rtacha oylik o'sish"], exp["avg_growth"]),
        str(kpi["O'rtacha oylik o'sish"]),
    )
    check(
        "Eng yaxshi hudud", kpi["Eng yaxshi hudud"] == exp["best_region"], kpi["Eng yaxshi hudud"]
    )
    check("Zarar ko'rgan oylar", kpi["Zarar ko'rgan oylar"] == exp["loss_months"])

    bad = []
    for i, m in enumerate(MONTHS):
        r = MONTH_TOP + 1 + i
        rev = dash.Cells(r, MONTH_LEFT + 1).Value
        cost = dash.Cells(r, MONTH_LEFT + 2).Value
        if not (_close(rev, exp["by_month"][m][0]) and _close(cost, exp["by_month"][m][1])):
            bad.append(m)
    check("Oylik SUMIFS", not bad, ", ".join(bad))

    reg = {
        dash.Cells(r, REGION_LEFT).Value: dash.Cells(r, REGION_LEFT + 1).Value
        for r in range(REGION_TOP + 1, REGION_TOP + 1 + len(REGIONS))
    }
    check("Hududlar", all(_close(reg[r], v) for r, v in exp["by_region"].items()))
    cats = {
        dash.Cells(r, REGION_LEFT).Value: dash.Cells(r, REGION_LEFT + 1).Value
        for r in range(CAT_TOP + 1, CAT_TOP + 1 + len(CATEGORIES))
    }
    check("Kategoriyalar", all(_close(cats[c], v) for c, v in exp["by_cat"].items()))

    formula = dash.Cells(MONTH_TOP + 1, MONTH_LEFT + 1).Formula
    check("Formulalar saqlangan", formula.startswith("=SUMIFS("), formula)
    check("3 ta grafik", dash.ChartObjects().Count == 3, str(dash.ChartObjects().Count))

    pivot_ws = wb.Worksheets(PIVOT_SHEET)
    ok_pivot = pivot_ws.PivotTables().Count == 1
    grand = None
    if ok_pivot:
        rng = pivot_ws.PivotTables(1).TableRange1
        grand = rng.Cells(rng.Rows.Count, rng.Columns.Count).Value
    check("PivotTable jami", ok_pivot and _close(grand, exp["revenue"]), str(grand))

    from nexvara.skills.excel.ops import separators

    _dec, thou = separators(wb.Application)
    shown = dash.Cells(k + 1, 2).Text
    want = f"{exp['revenue']:,}".replace(",", thou)
    check("Raqam formati ekranda", shown == want, f"{shown!r} (kutilgan {want!r})")
    return checks
