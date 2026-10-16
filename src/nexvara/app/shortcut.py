"""Desktop shortcut and the NEXVARA icon (drawn here, so no image file has to be shipped)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from nexvara import config

ACCENT = (0x63, 0x66, 0xF1)
ACCENT_2 = (0x06, 0xB6, 0xD4)


def icon_png(size: int = 256) -> bytes:
    """Rounded square with a diagonal brand gradient and a white "N"."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=size, height=size)
    steps = 48
    for i in range(steps):  # diagonal gradient made of thin bands
        t = i / (steps - 1)
        color = tuple((a + (b - a) * t) / 255 for a, b in zip(ACCENT, ACCENT_2, strict=True))
        y0, y1 = size * i / steps, size * (i + 1) / steps + 1
        page.draw_rect(pymupdf.Rect(0, y0, size, y1), color=None, fill=color)
    # Rounded corners: paint the outside of a rounded rectangle white-transparent later.
    s = size
    page.insert_text((s * 0.24, s * 0.80), "N", fontsize=s * 0.78, fontname="helv",
                     color=(1, 1, 1))  # fmt: skip
    pix = page.get_pixmap(alpha=True)
    # Cut rounded corners by clearing alpha outside a radius.
    r = size * 0.2
    samples = bytearray(pix.samples)
    n = pix.n
    for y in range(size):
        for x in range(size):
            dx = max(r - x, 0, x - (size - 1 - r))
            dy = max(r - y, 0, y - (size - 1 - r))
            if dx * dx + dy * dy > r * r:
                samples[(y * size + x) * n + n - 1] = 0
    out = pymupdf.Pixmap(pymupdf.csRGB, size, size, bytes(samples), True)
    return out.tobytes("png")


def write_icon(path: Path) -> Path:
    """A .ico holding one 256px PNG image (supported since Windows Vista)."""
    png = icon_png(256)
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 6 + 16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entry + png)
    return path


def icon_path() -> Path:
    path = config.data_dir() / "nexvara.ico"
    if not path.is_file():
        write_icon(path)
    return path


def create_desktop_shortcut() -> Path:
    """NEXVARA.lnk on the desktop: starts the app without a console window."""
    import win32com.client

    shell = win32com.client.Dispatch("WScript.Shell")
    desktop = Path(shell.SpecialFolders("Desktop"))
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    lnk = shell.CreateShortcut(str(desktop / "NEXVARA.lnk"))
    lnk.TargetPath = str(pythonw if pythonw.is_file() else exe)
    lnk.Arguments = "-m nexvara.app.main"
    lnk.WorkingDirectory = str(Path(__file__).resolve().parents[3])
    lnk.IconLocation = str(icon_path())
    lnk.Description = "NEXVARA — shaxsiy AI yordamchi"
    lnk.Save()
    return desktop / "NEXVARA.lnk"
