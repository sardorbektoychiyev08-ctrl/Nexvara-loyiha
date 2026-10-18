"""Desktop shortcut and the NEXVARA mark, drawn for the installer."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from nexvara import config

ACCENT = (0x63, 0x66, 0xF1)
ACCENT_2 = (0x06, 0xB6, 0xD4)


def icon_png(size: int = 256) -> bytes:
    """Anti-aliased gradient tile and the same geometric N as the UI and phone."""
    from io import BytesIO

    from PIL import Image, ImageDraw

    scale = 4
    s = size * scale
    gradient = Image.new("RGBA", (s, s))
    pixels = gradient.load()
    for y in range(s):
        for x in range(s):
            t = min(1.0, max(0.0, (x + y) / (2 * s)))
            pixels[x, y] = tuple(
                round(a * (1 - t) + b * t) for a, b in zip(ACCENT, ACCENT_2, strict=True)
            ) + (255,)
    mask = Image.new("L", (s, s))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=s * 0.21, fill=255)
    gradient.putalpha(mask)
    draw = ImageDraw.Draw(gradient)
    points = [(63, 190), (63, 66), (82, 66), (174, 166), (174, 66),
              (193, 66), (193, 190), (174, 190), (82, 90), (82, 190)]  # fmt: skip
    draw.polygon([(x * s / 256, y * s / 256) for x, y in points], fill="white")
    draw.ellipse((199 * s / 256, 47 * s / 256, 217 * s / 256, 65 * s / 256),
                 fill=(171, 243, 255, 255))  # fmt: skip
    gradient = gradient.resize((size, size), Image.Resampling.LANCZOS)
    out = BytesIO()
    gradient.save(out, format="PNG")
    return out.getvalue()


def write_icon(path: Path) -> Path:
    """A .ico holding one 256px PNG image (supported since Windows Vista)."""
    png = icon_png(256)
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 6 + 16)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entry + png)
    return path


def icon_path() -> Path:
    path = config.data_dir() / "nexvara-2.ico"
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
    if getattr(sys, "frozen", False):  # installed NEXVARA.exe (PyInstaller build)
        lnk.TargetPath = str(exe)
        lnk.WorkingDirectory = str(exe.parent)
    else:
        lnk.TargetPath = str(pythonw if pythonw.is_file() else exe)
        lnk.Arguments = "-m nexvara.app.main"
        lnk.WorkingDirectory = str(Path(__file__).resolve().parents[3])
    lnk.IconLocation = str(icon_path())
    lnk.Description = "NEXVARA — shaxsiy AI yordamchi"
    lnk.Save()
    return desktop / "NEXVARA.lnk"
