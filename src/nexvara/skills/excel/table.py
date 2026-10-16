"""Pure helpers for Excel tables. No COM here, so this module is unit-testable anywhere."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

# Excel constants (late binding has no typelib constants).
XL_CENTER = -4108
XL_CONTINUOUS = 1
XL_MAXIMIZED = -4137
XL_OPENXML_WORKBOOK = 51


def col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    if n < 1:
        raise ValueError(f"column index must be >= 1, got {n}")
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def excel_color(hex_color: str) -> int:
    """'#6366F1' -> Excel's BGR integer."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex_color!r}")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r + g * 256 + b * 65536


def validate_save_path(path: str | Path, overwrite: bool = False) -> Path:
    """Check an output path before Excel writes to it.

    Refuses relative paths, non-.xlsx files and silent overwrites.
    """
    p = Path(path)
    if not p.is_absolute():
        raise ValueError(f"save path must be absolute: {p}")
    if p.suffix.lower() != ".xlsx":
        raise ValueError(f"only .xlsx is supported for now: {p.name}")
    if p.exists() and not overwrite:
        raise FileExistsError(f"file already exists, refusing to overwrite: {p}")
    return p.resolve()


@dataclass
class TableSpec:
    headers: list[str]
    rows: list[list[object]]
    # 1-based column indexes (within the table) holding numbers.
    numeric_columns: list[int]

    @property
    def n_cols(self) -> int:
        return len(self.headers)

    def validate(self) -> None:
        if not self.headers:
            raise ValueError("table needs at least one header")
        for i, row in enumerate(self.rows):
            if len(row) != self.n_cols:
                raise ValueError(f"row {i} has {len(row)} cells, expected {self.n_cols}")
        for c in self.numeric_columns:
            if not 1 <= c <= self.n_cols:
                raise ValueError(f"numeric column {c} out of range")

    def address(self, top: int = 1, left: int = 1, extra_rows: int = 0) -> str:
        bottom = top + len(self.rows) + extra_rows
        right = left + self.n_cols - 1
        return f"{col_letter(left)}{top}:{col_letter(right)}{bottom}"


# ---------- locale-safe number formats ----------
# On some locales (seen: Excel 2016 + uz-Latn-UZ) Range.NumberFormat is NOT translated
# from US codes, so "#,##0" renders with ',' as the decimal mark. We therefore always
# write NumberFormatLocal with the separators Excel itself reports.

_DATE_TOKENS = set("dmyhsDMYHS")


def is_date_format(code: str) -> bool:
    """True if the US format code has date/time tokens outside quotes/escapes/brackets."""
    in_quote = escaped = in_bracket = False
    for ch in code:
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            in_quote = not in_quote
        elif in_quote:
            continue
        elif ch == "[":
            in_bracket = True
        elif ch == "]":
            in_bracket = False
        elif not in_bracket and ch in _DATE_TOKENS:
            return True
    return False


def localize_number_format(code: str, decimal: str, thousands: str) -> str:
    """Translate a US numeric format code ('#,##0.00') to local separators ('# ##0,00')."""
    out = []
    in_quote = escaped = False
    for ch in code:
        if escaped:
            out.append(ch)
            escaped = False
        elif ch == "\\":
            out.append(ch)
            escaped = True
        elif ch == '"':
            out.append(ch)
            in_quote = not in_quote
        elif in_quote:
            out.append(ch)
        elif ch == ",":
            out.append(thousands)
        elif ch == ".":
            out.append(decimal)
        else:
            out.append(ch)
    return "".join(out)


# ---------- dates ----------
# pywin32 shifts naive datetimes by the local UTC offset and rejects date objects,
# so dates go in as Excel serial numbers and come back as naive datetimes.

_EXCEL_EPOCH = _dt.datetime(1899, 12, 30)


def to_excel_value(v: object) -> object:
    if isinstance(v, _dt.datetime):
        return (v.replace(tzinfo=None) - _EXCEL_EPOCH).total_seconds() / 86400
    if isinstance(v, _dt.date):
        return float((v - _EXCEL_EPOCH.date()).days)
    return v


def from_excel_value(v: object) -> object:
    if isinstance(v, _dt.datetime):
        return _dt.datetime(v.year, v.month, v.day, v.hour, v.minute, v.second)
    return v
