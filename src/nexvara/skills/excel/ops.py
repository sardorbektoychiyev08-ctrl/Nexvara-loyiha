"""Excel operations over COM, each usable as a standalone agent tool.

Every function takes live COM objects (Range/Worksheet/Workbook) and keeps no
references after returning, so callers control lifetime. Strings passed to
Excel (formulas, number formats) are always the English/US forms, which Excel
translates for its own UI language and regional settings.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pythoncom
import win32com.client

from nexvara.skills.excel.table import (
    XL_CENTER,
    col_letter,
    excel_color,
    from_excel_value,
    is_date_format,
    localize_number_format,
    to_excel_value,
)

# Excel constants (late binding has no typelib constants).
XL_YES = 1
XL_ASCENDING = 1
XL_DESCENDING = 2
XL_SORT_ON_VALUES = 0
XL_CELL_VALUE = 1
XL_DATABASE = 1
XL_ROW_FIELD = 1
XL_COLUMN_FIELD = 2
XL_PAGE_FIELD = 3
XL_TYPE_PDF = 0

XL_SUM = -4157
XL_COUNT = -4112
XL_AVERAGE = -4106
XL_MAX = -4136
XL_MIN = -4139
AGGREGATES = {"sum": XL_SUM, "count": XL_COUNT, "average": XL_AVERAGE, "max": XL_MAX, "min": XL_MIN}

OPERATORS = {">": 5, "<": 6, ">=": 7, "<=": 8, "=": 3, "<>": 4}  # XlFormatConditionOperator

CHART_TYPES = {
    "column": 51,  # xlColumnClustered
    "bar": 57,  # xlBarClustered
    "line": 4,  # xlLine
    "line_markers": 65,  # xlLineMarkers
    "pie": 5,  # xlPie
    "doughnut": -4120,  # xlDoughnut
    "area": 1,  # xlArea
    "scatter": -4169,  # xlXYScatter
}

NUMBER_FORMATS = {
    "integer": "#,##0",
    "decimal": "#,##0.00",
    "percent": "0.0%",
    "date": "dd.mm.yyyy",
    "datetime": "dd.mm.yyyy hh:mm",
    "text": "@",
}

DEFAULT_CHUNK_ROWS = 5000


# ---------- reading ----------


def read_range(rng: Any) -> list[list[Any]]:
    """Values as a list of rows (a single cell becomes [[value]])."""
    v = rng.Value
    if not isinstance(v, tuple):
        return [[from_excel_value(v)]]
    return [[from_excel_value(x) for x in r] for r in v]


def used_table(ws: Any) -> tuple[list[Any], list[list[Any]]]:
    """(headers, rows) of the sheet's used range; first row is the header."""
    values = read_range(ws.UsedRange)
    if not values:
        return [], []
    return values[0], values[1:]


# ---------- writing ----------


def write_rows(
    ws: Any,
    rows: Sequence[Sequence[Any]],
    top: int = 1,
    left: int = 1,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
) -> Any:
    """Write a 2-D block in chunks so large tables don't hit COM marshalling limits.

    Returns the full written range.
    """
    if not rows:
        raise ValueError("nothing to write")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError("all rows must have the same length")
    right = col_letter(left + width - 1)
    for start in range(0, len(rows), chunk_rows):
        block = [[to_excel_value(v) for v in r] for r in rows[start : start + chunk_rows]]
        r0 = top + start
        ws.Range(f"{col_letter(left)}{r0}:{right}{r0 + len(block) - 1}").Value = block
    return ws.Range(f"{col_letter(left)}{top}:{right}{top + len(rows) - 1}")


def column_range(table: Any, col: int, include_header: bool = False) -> Any:
    """1-based column of a table range, without its header row by default."""
    ws = table.Worksheet
    first = table.Row + (0 if include_header else 1)
    last = table.Row + table.Rows.Count - 1
    c = table.Column + col - 1
    return ws.Range(ws.Cells(first, c), ws.Cells(last, c))


# ---------- cleaning / ordering ----------


def sort_table(table: Any, by: Sequence[tuple[int, bool]], header: bool = True) -> None:
    """Sort a table range. `by` = [(1-based column, ascending), ...] in priority order."""
    ws = table.Worksheet
    sorter = ws.Sort
    sorter.SortFields.Clear()
    for col, ascending in by:
        key = column_range(table, col, include_header=not header)
        sorter.SortFields.Add(
            Key=key,
            SortOn=XL_SORT_ON_VALUES,
            Order=XL_ASCENDING if ascending else XL_DESCENDING,
        )
    sorter.SetRange(table)
    sorter.Header = XL_YES if header else 2  # xlNo
    sorter.Apply()
    sorter.SortFields.Clear()


def autofilter(table: Any, column: int | None = None, criteria: str | None = None) -> None:
    """Turn on AutoFilter; optionally filter a 1-based column (criteria '>100', 'Toshkent')."""
    ws = table.Worksheet
    if ws.AutoFilterMode:
        ws.AutoFilterMode = False
    if column is None:
        table.AutoFilter()
    else:
        table.AutoFilter(Field=column, Criteria1=criteria)


def clear_filter(ws: Any) -> None:
    if ws.AutoFilterMode:
        ws.AutoFilterMode = False


def visible_row_count(table: Any) -> int:
    """Data rows (excluding header) currently visible after filtering."""
    count = 0
    for i in range(2, table.Rows.Count + 1):
        if not table.Rows(i).EntireRow.Hidden:
            count += 1
    return count


def remove_duplicates(table: Any, columns: Sequence[int], header: bool = True) -> int:
    """Remove rows duplicated on the given 1-based columns. Returns rows removed."""
    before = table.Rows.Count
    ws = table.Worksheet
    cols = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, list(columns))
    table.RemoveDuplicates(Columns=cols, Header=XL_YES if header else 2)
    # RemoveDuplicates leaves the range address unchanged; count what is left.
    last = ws.Cells(ws.Rows.Count, table.Column).End(-4162).Row  # xlUp
    after = max(last - table.Row + 1, 1)
    return before - after


def trim_text(table: Any) -> int:
    """Strip surrounding/double spaces in text cells. Returns cells changed."""
    values = read_range(table)
    changed = 0
    for r in values:
        for i, v in enumerate(r):
            if isinstance(v, str):
                clean = " ".join(v.split())
                if clean != v:
                    r[i] = clean
                    changed += 1
    if changed:
        table.Value = values
    return changed


# ---------- formatting ----------


def separators(app: Any) -> tuple[str, str]:
    """(decimal, thousands) separators Excel is actually using."""
    intl = app.International  # whole XlApplicationInternational array, 0-based here
    return intl[2], intl[3]


def local_format(app: Any, kind: str) -> str:
    """US code (or NUMBER_FORMATS key) -> code for NumberFormatLocal on this machine."""
    code = NUMBER_FORMATS.get(kind, kind)
    if is_date_format(code):
        return code
    return localize_number_format(code, *separators(app))


def set_number_format(rng: Any, kind: str) -> None:
    """kind: one of NUMBER_FORMATS keys, or a raw US-style format code.

    Numeric codes are localized and written via NumberFormatLocal (see table.py);
    date codes go through NumberFormat, which Excel handles correctly.
    """
    code = NUMBER_FORMATS.get(kind, kind)
    if is_date_format(code):
        rng.NumberFormat = code
    else:
        rng.NumberFormatLocal = local_format(rng.Application, code)


def center(rng: Any) -> None:
    rng.HorizontalAlignment = XL_CENTER
    rng.VerticalAlignment = XL_CENTER


def highlight_cells(rng: Any, operator: str, value: float, fill: str = "#FDE68A") -> None:
    """Conditional fill for cells compared to a number (e.g. '>', 1000000)."""
    if operator not in OPERATORS:
        raise ValueError(f"operator must be one of {sorted(OPERATORS)}")
    # Formula1 is parsed with the local decimal separator; an integer string is safe everywhere.
    if float(value) != int(value):
        raise ValueError("highlight_cells supports whole-number thresholds only")
    fc = rng.FormatConditions.Add(
        Type=XL_CELL_VALUE, Operator=OPERATORS[operator], Formula1=f"={int(value)}"
    )
    fc.Interior.Color = excel_color(fill)


def color_scale(rng: Any) -> None:
    """3-colour scale (low red -> high green)."""
    rng.FormatConditions.AddColorScale(ColorScaleType=3)


def data_bars(rng: Any, color: str = "#6366F1") -> None:
    bar = rng.FormatConditions.AddDatabar()
    bar.BarColor.Color = excel_color(color)


# ---------- charts ----------


def add_chart(
    ws: Any,
    source: Any,
    kind: str = "column",
    title: str = "",
    left: float | None = None,
    top: float | None = None,
    width: float = 480,
    height: float = 280,
) -> Any:
    """Embed a chart for `source` (header row = series names, first column = categories).

    Position defaults to the right of the used range. Returns the ChartObject.
    """
    if kind not in CHART_TYPES:
        raise ValueError(f"chart kind must be one of {sorted(CHART_TYPES)}")
    if left is None:
        used = ws.UsedRange
        left = ws.Cells(1, used.Column + used.Columns.Count + 1).Left
    if top is None:
        top = ws.Cells(2, 1).Top
    co = ws.ChartObjects().Add(left, top, width, height)
    chart = co.Chart
    chart.ChartType = CHART_TYPES[kind]
    chart.SetSourceData(Source=source)
    if title:
        chart.HasTitle = True
        chart.ChartTitle.Text = title
    return co


# ---------- pivot tables ----------


def add_pivot(
    wb: Any,
    source: Any,
    dest: Any,
    rows: Sequence[str],
    values: Sequence[tuple[str, str, str]],
    columns: Sequence[str] = (),
    filters: Sequence[str] = (),
    name: str = "NexvaraPivot",
) -> Any:
    """Create a PivotTable at `dest` (a cell Range).

    values = [(source field, aggregate, caption)], aggregate in AGGREGATES.
    Captions must differ from source field names (Excel rule).
    """
    cache = wb.PivotCaches().Create(SourceType=XL_DATABASE, SourceData=source)
    pt = cache.CreatePivotTable(TableDestination=dest, TableName=name)
    pt.ManualUpdate = True
    try:
        for f in rows:
            pt.PivotFields(f).Orientation = XL_ROW_FIELD
        for f in columns:
            pt.PivotFields(f).Orientation = XL_COLUMN_FIELD
        for f in filters:
            pt.PivotFields(f).Orientation = XL_PAGE_FIELD
        for field, agg, caption in values:
            if agg not in AGGREGATES:
                raise ValueError(f"aggregate must be one of {sorted(AGGREGATES)}")
            df = pt.AddDataField(pt.PivotFields(field), caption, AGGREGATES[agg])
            # PivotField has no NumberFormatLocal; the localized code is what Excel expects here.
            df.NumberFormat = local_format(wb.Application, "integer")
    finally:
        pt.ManualUpdate = False
    return pt


def pivot_values(pt: Any) -> list[list[Any]]:
    return read_range(pt.TableRange1)


# ---------- export ----------


def export_csv(rng: Any, path: str | Path) -> Path:
    """UTF-8 (with BOM, so Excel reopens Cyrillic/Uzbek text correctly) CSV of a range."""
    p = Path(path)
    if p.suffix.lower() != ".csv" or not p.is_absolute():
        raise ValueError(f"need an absolute .csv path: {p}")
    rows = read_range(rng)
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(["" if v is None else _csv_value(v) for v in r])
    return p


def _csv_value(v: Any) -> Any:
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return v


def export_pdf(target: Any, path: str | Path) -> Path:
    """Export a Workbook or Worksheet to PDF."""
    p = Path(path)
    if p.suffix.lower() != ".pdf" or not p.is_absolute():
        raise ValueError(f"need an absolute .pdf path: {p}")
    target.ExportAsFixedFormat(Type=XL_TYPE_PDF, Filename=str(p))
    return p
