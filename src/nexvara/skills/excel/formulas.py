"""Formula builders with Office-version fallbacks.

Formulas are always English (Range.Formula); Excel shows them localized.
"""

from __future__ import annotations

from typing import Any

# Excel returns this for #NAME? when reading .Value of an errored cell.
XL_ERR_NAME = -2146826259

_xlookup_cache: dict[int, bool] = {}


def supports_xlookup(app: Any) -> bool:
    """Probe once per Excel instance: Office 2016/2019 lack XLOOKUP, 365/2021 have it."""
    key = int(app.Hwnd)
    if key not in _xlookup_cache:
        wb = app.Workbooks.Add()
        try:
            cell = wb.Worksheets(1).Range("A1")
            cell.Formula = "=XLOOKUP(1,{1},{2})"
            _xlookup_cache[key] = cell.Value == 2
            del cell
        finally:
            wb.Close(SaveChanges=False)
            del wb
    return _xlookup_cache[key]


def lookup(value: str, lookup_range: str, return_range: str, xlookup: bool) -> str:
    """Exact-match lookup expression (no leading '=')."""
    if xlookup:
        return f'XLOOKUP({value},{lookup_range},{return_range},"")'
    return f'IFERROR(INDEX({return_range},MATCH({value},{lookup_range},0)),"")'


def sumifs(sum_range: str, *criteria: tuple[str, str]) -> str:
    """SUMIFS(sum_range, crit_range1, crit1, ...) (no leading '=')."""
    if not criteria:
        raise ValueError("sumifs needs at least one (range, criterion) pair")
    parts = [sum_range]
    for rng, crit in criteria:
        parts += [rng, crit]
    return f"SUMIFS({','.join(parts)})"


def growth(current: str, previous: str) -> str:
    """Period-over-period growth, blank when there is no previous value."""
    return f'IF(OR({previous}="",{previous}=0),"",{current}/{previous}-1)'


def sheet_ref(sheet: str, address: str) -> str:
    """'Ma'lumot'!$A$2:$A$100 with quotes escaped as Excel requires."""
    return "'" + sheet.replace("'", "''") + "'!" + address
