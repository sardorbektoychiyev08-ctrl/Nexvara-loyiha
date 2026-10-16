"""Helpers shared by the Office skills."""

from __future__ import annotations

import logging

import pywintypes
import win32api
import win32con
import win32gui

log = logging.getLogger(__name__)


def bring_to_front(hwnd: int, maximize: bool = True) -> bool:
    """Show an Office window and make it the foreground window so the user sees the work."""
    try:
        hwnd = int(hwnd)  # PowerPoint returns HWND as a non-int COM value
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE if maximize else win32con.SW_RESTORE)
        # Windows only lets the foreground process hand over focus; an Alt tap lifts that lock.
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32gui.SetForegroundWindow(hwnd)
    except (pywintypes.error, TypeError, ValueError) as e:
        log.warning("Could not bring window %s to front: %s", hwnd, e)
        return False
    return True


def validate_output_path(path, suffixes: tuple[str, ...], overwrite: bool = False):
    """Absolute path with an allowed suffix; refuses silent overwrite. Returns resolved Path."""
    from pathlib import Path

    p = Path(path)
    if not p.is_absolute():
        raise ValueError(f"path must be absolute: {p}")
    if p.suffix.lower() not in suffixes:
        raise ValueError(f"expected one of {suffixes}: {p.name}")
    if p.exists() and not overwrite:
        raise FileExistsError(f"file already exists, refusing to overwrite: {p}")
    return p.resolve()
