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


def file_in_use(path) -> bool:
    """True while another program (an open Word/Excel window) holds the file locked."""
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return False
    try:
        with open(p, "r+b"):
            return False
    except PermissionError:
        return True
    except OSError:
        return False


def pdf_opens_in_word() -> bool:
    """Windows opens .pdf with Word on some PCs: Word then waits behind an invisible «convert
    this PDF?» question (live 2026-10-24) — show a picture of the result instead."""
    import ctypes

    buf = ctypes.create_unicode_buffer(520)
    size = ctypes.c_ulong(len(buf))
    try:  # ASSOCF_NONE, ASSOCSTR_EXECUTABLE = 2
        hr = ctypes.windll.shlwapi.AssocQueryStringW(0, 2, ".pdf", None, buf, ctypes.byref(size))
    except (AttributeError, OSError):
        return False
    exe = buf.value.lower() if hr == 0 else ""
    return "winword" in exe or "pdfreflow" in exe
