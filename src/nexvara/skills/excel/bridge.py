"""Live Excel session over COM (Office 2016+, any UI language).

The session starts its own Excel instance (DispatchEx), so workbooks the user
already has open are never touched. By default Excel is visible and maximized,
so the user watches the work happen.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any

import pythoncom
import pywintypes
import win32api
import win32com.client
import win32con
import win32gui

from nexvara.skills.excel.table import (
    XL_CENTER,
    XL_CONTINUOUS,
    XL_MAXIMIZED,
    XL_OPENXML_WORKBOOK,
    TableSpec,
    excel_color,
    validate_save_path,
)

log = logging.getLogger(__name__)

HEADER_FILL = "#6366F1"
HEADER_FONT = "#FFFFFF"
BORDER_COLOR = "#CBD5E1"


def bring_to_front(hwnd: int) -> bool:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        # Windows only lets the foreground process hand over focus; an Alt tap lifts that lock.
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32gui.SetForegroundWindow(hwnd)
    except pywintypes.error as e:
        log.warning("Could not bring Excel to front: %s", e)
        return False
    return True


class ExcelSession:
    """Context manager owning one Excel instance.

    keep_open=True leaves Excel running for the user when the block exits;
    otherwise every workbook is closed without saving and Excel quits.
    """

    def __init__(self, visible: bool = True, keep_open: bool = False) -> None:
        self.visible = visible
        self.keep_open = keep_open
        self.app: Any = None

    def __enter__(self) -> ExcelSession:
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.DispatchEx("Excel.Application")
            self.app.Visible = self.visible
        except Exception:
            pythoncom.CoUninitialize()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        try:
            if self.app is not None:
                if self.keep_open and self.visible:
                    self.app.UserControl = True
                else:
                    # Index access keeps no Python reference alive past Quit().
                    while self.app.Workbooks.Count:
                        self.app.Workbooks(1).Close(SaveChanges=False)
                    self.app.Quit()
        except Exception:
            log.exception("Error while closing Excel")
        finally:
            self.app = None
            pythoncom.CoUninitialize()

    @property
    def version(self) -> str:
        return str(self.app.Version)

    def show(self) -> None:
        if not self.visible:
            return
        self.app.WindowState = XL_MAXIMIZED
        bring_to_front(self.app.Hwnd)

    def new_workbook(self) -> Any:
        return self.app.Workbooks.Add()

    def open_workbook(self, path: str | Path) -> Any:
        return self.app.Workbooks.Open(str(Path(path).resolve()))

    def save_as(self, wb: Any, path: str | Path, overwrite: bool = False) -> Path:
        target = validate_save_path(path, overwrite=overwrite)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_name(f"{target.stem}.bak-{time.strftime('%Y%m%d-%H%M%S')}.xlsx")
            shutil.copy2(target, backup)
            log.info("Backed up %s -> %s", target, backup)
        # The overwrite decision was made above; keep Excel from blocking on its own prompt.
        self.app.DisplayAlerts = False
        try:
            wb.SaveAs(str(target), FileFormat=XL_OPENXML_WORKBOOK)
        finally:
            self.app.DisplayAlerts = True
        return target


def write_table(ws: Any, spec: TableSpec, top: int = 1, left: int = 1) -> Any:
    """Write headers + rows in one COM call; returns the written range."""
    spec.validate()
    values = [list(spec.headers), *[list(r) for r in spec.rows]]
    rng = ws.Range(spec.address(top, left))
    rng.Value = values
    return rng


def format_table(ws: Any, rng: Any, spec: TableSpec, top: int = 1, left: int = 1) -> None:
    """Professional default look: coloured header, borders, centred numbers, fitted columns."""
    n_rows = rng.Rows.Count

    header = rng.Rows(1)
    header.Font.Bold = True
    header.Font.Color = excel_color(HEADER_FONT)
    header.Interior.Color = excel_color(HEADER_FILL)
    header.HorizontalAlignment = XL_CENTER

    rng.VerticalAlignment = XL_CENTER
    rng.Borders.LineStyle = XL_CONTINUOUS
    rng.Borders.Color = excel_color(BORDER_COLOR)

    for c in spec.numeric_columns:
        body = ws.Range(ws.Cells(top + 1, left + c - 1), ws.Cells(top + n_rows - 1, left + c - 1))
        body.HorizontalAlignment = XL_CENTER
        body.NumberFormat = "#,##0"

    rng.Rows.RowHeight = 20
    rng.Columns.AutoFit()
    for i in range(1, rng.Columns.Count + 1):
        col = rng.Columns(i)
        col.ColumnWidth = col.ColumnWidth + 3


def freeze_header(app: Any, row: int = 1) -> None:
    win = app.ActiveWindow
    if win is None:
        return
    win.FreezePanes = False
    win.SplitColumn = 0
    win.SplitRow = row
    win.FreezePanes = True
