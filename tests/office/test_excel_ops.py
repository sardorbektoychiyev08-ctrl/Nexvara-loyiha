"""Real-Excel tests for skills/excel/ops.py. Run with NEXVARA_RUN_OFFICE=1."""

import datetime as dt
import os
import time
from collections import defaultdict

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Excel",
    ),
]

HEADERS = ["Hudud", "Kategoriya", "Oy", "Soni", "Summa"]
REGIONS = ["Toshkent", "Samarqand", "Buxoro", "Farg'ona"]
CATEGORIES = ["Ofis", "Texnika", "Kanselyariya"]


def sales_rows(n: int) -> list[list[object]]:
    rows = []
    for i in range(n):
        qty = (i * 7) % 50 + 1
        rows.append(
            [
                REGIONS[i % len(REGIONS)],
                CATEGORIES[(i // 3) % len(CATEGORIES)],
                i % 12 + 1,
                qty,
                qty * ((i * 13) % 90 + 10) * 1000,
            ]
        )
    return rows


@pytest.fixture
def xl():
    from nexvara.skills.excel.bridge import ExcelSession

    with ExcelSession(visible=False) as session:
        yield session


@pytest.fixture
def sheet(xl):
    """A fresh sheet with a 60-row sales table at A1:E61."""
    from nexvara.skills.excel import ops

    wb = xl.new_workbook()
    ws = wb.Worksheets(1)
    ops.write_rows(ws, [HEADERS, *sales_rows(60)])
    yield ws
    wb.Close(SaveChanges=False)


def table(ws):
    return ws.Range("A1").CurrentRegion


def test_write_and_read_large_table_in_chunks(xl):
    from nexvara.skills.excel import ops

    rows = [HEADERS, *sales_rows(20000)]
    wb = xl.new_workbook()
    ws = wb.Worksheets(1)
    t0 = time.perf_counter()
    ops.write_rows(ws, rows, chunk_rows=5000)
    write_s = time.perf_counter() - t0
    headers, body = ops.used_table(ws)
    wb.Close(SaveChanges=False)

    assert headers == HEADERS
    assert len(body) == 20000
    assert body[12345][4] == rows[12346][4]
    assert write_s < 60, f"20k rows took {write_s:.1f}s"


def test_sort_descending_by_amount(sheet):
    from nexvara.skills.excel import ops

    ops.sort_table(table(sheet), [(5, False)])
    _, body = ops.used_table(sheet)
    amounts = [r[4] for r in body]
    assert amounts == sorted(amounts, reverse=True)
    assert len(body) == 60


def test_multi_key_sort(sheet):
    from nexvara.skills.excel import ops

    ops.sort_table(table(sheet), [(1, True), (4, False)])
    _, body = ops.used_table(sheet)
    keys = [(r[0], -r[3]) for r in body]
    assert keys == sorted(keys)


def test_autofilter_text_and_numeric(sheet):
    from nexvara.skills.excel import ops

    rows = sales_rows(60)
    ops.autofilter(table(sheet), 1, "Toshkent")
    assert ops.visible_row_count(table(sheet)) == sum(r[0] == "Toshkent" for r in rows)

    ops.autofilter(table(sheet), 5, ">500000")
    assert ops.visible_row_count(table(sheet)) == sum(r[4] > 500000 for r in rows)

    ops.clear_filter(sheet)
    assert ops.visible_row_count(table(sheet)) == 60


def test_remove_duplicates_and_trim(xl):
    from nexvara.skills.excel import ops

    wb = xl.new_workbook()
    ws = wb.Worksheets(1)
    data = [
        ["Ism", "Shahar"],
        ["  Ali  ", "Toshkent"],
        ["Vali", "Buxoro"],
        ["Ali", "Toshkent"],
        ["Vali", "Buxoro"],
        ["Sardor", "Samarqand"],
    ]
    ops.write_rows(ws, data)
    assert ops.trim_text(ws.Range("A1:B6")) == 1
    removed = ops.remove_duplicates(ws.Range("A1:B6"), [1, 2])
    _, body = ops.used_table(ws)
    wb.Close(SaveChanges=False)

    assert removed == 2
    assert body == [["Ali", "Toshkent"], ["Vali", "Buxoro"], ["Sardor", "Samarqand"]]


def test_number_formats_and_alignment(sheet):
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.table import XL_CENTER

    amounts = ops.column_range(table(sheet), 5)
    ops.set_number_format(amounts, "integer")
    ops.center(amounts)
    sheet.Range("G2").Value = 0.256
    ops.set_number_format(sheet.Range("G2"), "percent")

    dec, thou = ops.separators(sheet.Application)
    sheet.Range("G3").Value = 1234567.891
    ops.set_number_format(sheet.Range("G3"), "decimal")
    ops.write_rows(sheet, [[dt.datetime(2026, 10, 16, 14, 30)]], top=4, left=7)
    ops.set_number_format(sheet.Range("G4"), "datetime")
    sheet.Columns("G").AutoFit()

    assert amounts.Cells(1, 1).HorizontalAlignment == XL_CENTER
    assert sheet.Range("G2").Text == f"25{dec}6%"
    assert sheet.Range("G3").Text == f"1{thou}234{thou}567{dec}89"
    assert sheet.Range("G4").Text == "16.10.2026 14:30"
    assert ops.read_range(sheet.Range("G4")) == [[dt.datetime(2026, 10, 16, 14, 30)]]


def test_conditional_formatting(sheet):
    from nexvara.skills.excel import ops

    amounts = ops.column_range(table(sheet), 5)
    ops.highlight_cells(amounts, ">", 1000000)
    ops.color_scale(ops.column_range(table(sheet), 4))
    ops.data_bars(amounts)
    assert amounts.FormatConditions.Count == 2
    assert ops.column_range(table(sheet), 4).FormatConditions.Count == 1


def test_charts(sheet):
    from nexvara.skills.excel import ops

    sheet.Range("H1:I5").Value = [
        ["Hudud", "Summa"],
        *[[r, 100 * (i + 1)] for i, r in enumerate(REGIONS)],
    ]
    col = ops.add_chart(sheet, sheet.Range("H1:I5"), "column", "Hududlar bo'yicha")
    pie = ops.add_chart(sheet, sheet.Range("H1:I5"), "pie", "Ulush", top=400)

    assert sheet.ChartObjects().Count == 2
    assert col.Chart.ChartType == ops.CHART_TYPES["column"]
    assert pie.Chart.ChartType == ops.CHART_TYPES["pie"]
    assert col.Chart.SeriesCollection().Count == 1
    assert col.Chart.ChartTitle.Text == "Hududlar bo'yicha"
    assert list(col.Chart.SeriesCollection(1).Values) == [100, 200, 300, 400]


def test_pivot_table_matches_python(sheet):
    from nexvara.skills.excel import ops

    pivot_ws = sheet.Parent.Worksheets.Add()
    pt = ops.add_pivot(
        sheet.Parent,
        table(sheet),
        pivot_ws.Range("A3"),
        rows=["Hudud"],
        values=[("Summa", "sum", "Jami summa"), ("Soni", "sum", "Jami soni")],
    )
    got = {r[0]: (r[1], r[2]) for r in ops.pivot_values(pt)[1:] if r[0] is not None}

    expected: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for region, _cat, _m, qty, amount in sales_rows(60):
        expected[region][0] += amount
        expected[region][1] += qty
    grand = [sum(v[0] for v in expected.values()), sum(v[1] for v in expected.values())]

    for region, (amount, qty) in expected.items():
        assert got[region] == (amount, qty), region
    numeric = {k: v for k, v in got.items() if isinstance(v[0], float)}
    totals = [v for k, v in numeric.items() if k not in expected]
    assert totals == [tuple(grand)], "expected exactly one grand-total row"


def test_export_csv_utf8_and_pdf(sheet, tmp_path):
    from nexvara.skills.excel import ops

    sheet.Range("A2").Value = "Тошкент — O'zbekiston"
    csv_path = ops.export_csv(table(sheet), tmp_path / "out.csv")
    text = csv_path.read_text(encoding="utf-8-sig").splitlines()
    assert text[0] == ",".join(HEADERS)
    assert text[1].startswith("Тошкент — O'zbekiston,")
    assert len(text) == 61

    pdf = ops.export_pdf(sheet, tmp_path / "out.pdf")
    assert pdf.read_bytes()[:5] == b"%PDF-"
