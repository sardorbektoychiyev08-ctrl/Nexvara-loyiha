"""Mouse and keyboard of this PC from the paired phone ("Kompyuterni boshqarish").

Off by default: the owner turns it on in the PC window (Qurilmalar → «Telefon boshqarishi
mumkin»); the phone asks for its own fingerprint/PIN before control mode; the PC shows
«📱 Telefon boshqarmoqda» while it is used. Only these actions exist: click, double click,
right click, scroll, type text, a fixed list of keys — no shell, no files. Touchpad mode on
the phone: «nudge» moves the cursor by dx, dy pixels, «tap»/«tap_double»/«tap_right» click
where the cursor already is, «drag_start»/«drag_end» hold and release the left button.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

KEYS: dict[str, tuple[int, ...]] = {
    "enter": (0x0D,),
    "esc": (0x1B,),
    "tab": (0x09,),
    "backspace": (0x08,),
    "delete": (0x2E,),
    "up": (0x26,),
    "down": (0x28,),
    "left": (0x25,),
    "right": (0x27,),
    "home": (0x24,),
    "end": (0x23,),
    "pageup": (0x21,),
    "pagedown": (0x22,),
    "space": (0x20,),
    "win": (0x5B,),
    "ctrl+c": (0x11, 0x43),
    "ctrl+v": (0x11, 0x56),
    "ctrl+x": (0x11, 0x58),
    "ctrl+z": (0x11, 0x5A),
    "ctrl+y": (0x11, 0x59),
    "ctrl+s": (0x11, 0x53),
    "ctrl+a": (0x11, 0x41),
    "ctrl+p": (0x11, 0x50),
    "alt+tab": (0x12, 0x09),
    "alt+f4": (0x12, 0x73),
    "f5": (0x74,),
    "win+d": (0x5B, 0x44),
}

_MOUSE = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010)}
_WHEEL = 0x0800
_KEYUP, _UNICODE = 0x0002, 0x0004


class _KI(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MI(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _U(ctypes.Union):
    _fields_ = [("ki", _KI), ("mi", _MI), ("pad", ctypes.c_byte * 32)]


class _IN(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _send(*inputs: _IN) -> None:
    arr = (_IN * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(_IN))


def _key(vk: int = 0, scan: int = 0, flags: int = 0) -> _IN:
    return _IN(1, _U(ki=_KI(vk, scan, flags, 0, 0)))


def _mouse(flags: int, data: int = 0) -> _IN:
    return _IN(0, _U(mi=_MI(0, 0, data & 0xFFFFFFFF, flags, 0, 0)))


class _PT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def screen_size() -> tuple[int, int]:
    u = ctypes.windll.user32
    return u.GetSystemMetrics(0), u.GetSystemMetrics(1)


def act(
    action: str,
    x: float | None = None,
    y: float | None = None,
    dy: int = 0,
    text: str = "",
    key: str = "",
    dx: int = 0,
) -> None:
    """x, y are 0..1 of the primary screen (what the phone sees in «Kompyuter ekrani»)."""
    if action == "nudge":
        if not (-800 <= dx <= 800 and -800 <= dy <= 800):
            raise ValueError("Siljish juda katta")
        w, h = screen_size()
        pt = _PT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        nx, ny = max(0, min(w - 1, pt.x + dx)), max(0, min(h - 1, pt.y + dy))
        ctypes.windll.user32.SetCursorPos(nx, ny)
    elif action in ("tap", "tap_double", "tap_right"):
        down, up = _MOUSE["right" if action == "tap_right" else "left"]
        for _ in range(2 if action == "tap_double" else 1):
            _send(_mouse(down), _mouse(up))
            time.sleep(0.05)
    elif action == "drag_start":
        _send(_mouse(_MOUSE["left"][0]))
    elif action == "drag_end":
        _send(_mouse(_MOUSE["left"][1]))
    elif action in ("click", "double", "right", "move"):
        if x is None or y is None or not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("x, y 0..1 bo‘lsin")
        w, h = screen_size()
        ctypes.windll.user32.SetCursorPos(int(x * (w - 1)), int(y * (h - 1)))
        if action == "move":
            return
        down, up = _MOUSE["right" if action == "right" else "left"]
        for _ in range(2 if action == "double" else 1):
            _send(_mouse(down), _mouse(up))
            time.sleep(0.05)
    elif action == "scroll":
        _send(_mouse(_WHEEL, int(max(-15, min(15, dy))) * 120))
    elif action == "type":
        if not text or len(text) > 2000:
            raise ValueError("Matn 1–2000 belgi bo‘lsin")
        data = text.encode("utf-16-le")  # surrogate pairs become two units, as Windows wants
        for i in range(0, len(data), 2):
            code = data[i] | (data[i + 1] << 8)
            _send(_key(0, code, _UNICODE), _key(0, code, _UNICODE | _KEYUP))
    elif action == "key":
        combo = KEYS.get(key)
        if combo is None:
            raise ValueError("Noma’lum tugma")
        _send(*[_key(vk) for vk in combo], *[_key(vk, 0, _KEYUP) for vk in reversed(combo)])
    else:
        raise ValueError("Noma’lum amal")
