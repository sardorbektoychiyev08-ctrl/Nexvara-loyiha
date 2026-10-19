"""A picture of the PC screen for the phone ("Kompyuter ekrani"), JPEG, view only.

Only a paired phone can ask for it (device token over the pinned HTTPS), the owner can turn it
off (settings.json → remote.screen_view), and the PC window shows "📱 Telefon ekranni ko‘rmoqda"
whenever it is being watched. Nothing is recorded or stored.
"""

from __future__ import annotations

import math


def _draw_cursor(hdc: int) -> None:
    """The mouse pointer on the picture (optional: a hidden or odd cursor is skipped)."""
    import win32gui

    try:
        flags, cursor, (x, y) = win32gui.GetCursorInfo()
        if not flags or not cursor:
            return
        _icon, hx, hy, mask, color = win32gui.GetIconInfo(cursor)
        for b in (mask, color):
            if b:
                win32gui.DeleteObject(b)
        win32gui.DrawIconEx(hdc, x - hx, y - hy, cursor, 0, 0, 0, None, 0x0003)  # DI_NORMAL
    except Exception:  # noqa: S110 - a picture without the pointer is still useful
        pass


def capture_jpeg(max_side: int = 1400, quality: int = 60) -> bytes:
    """The primary monitor as JPEG (GDI BitBlt; no extra libraries)."""
    import fitz  # PyMuPDF
    import win32api
    import win32con
    import win32gui
    import win32ui

    w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    desk = win32gui.GetDesktopWindow()
    hdc = win32gui.GetWindowDC(desk)
    src = win32ui.CreateDCFromHandle(hdc)
    mem = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    try:
        bmp.CreateCompatibleBitmap(src, w, h)
        mem.SelectObject(bmp)
        mem.BitBlt((0, 0), (w, h), src, (0, 0), win32con.SRCCOPY)
        _draw_cursor(mem.GetSafeHdc())  # BitBlt leaves it out; the touchpad needs to see it
        raw = bytearray(bmp.GetBitmapBits(True))  # BGRA, top-down
    finally:
        mem.DeleteDC()
        src.DeleteDC()
        win32gui.ReleaseDC(desk, hdc)
        win32gui.DeleteObject(bmp.GetHandle())
    raw[0::4], raw[2::4] = raw[2::4], raw[0::4]  # BGRA -> RGBA
    pix = fitz.Pixmap(fitz.csRGB, w, h, bytes(raw), True)
    pix = fitz.Pixmap(pix, 0)  # drop alpha
    side = max(w, h)
    if side > max_side:
        pix.shrink(math.ceil(math.log2(side / max_side)))
    return pix.tobytes("jpeg", jpg_quality=quality)
