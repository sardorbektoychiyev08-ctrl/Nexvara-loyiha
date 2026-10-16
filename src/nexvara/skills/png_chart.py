"""Dependency-free PNG bar chart, used to put pictures into Word/PowerPoint."""

from __future__ import annotations

import struct
import zlib
from collections.abc import Sequence
from pathlib import Path


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def bar_chart_png(
    values: Sequence[float],
    path: str | Path,
    width: int = 800,
    height: int = 400,
    bar: str = "#6366F1",
    accent: str = "#06B6D4",
    background: str = "#FFFFFF",
) -> Path:
    """Write a simple vertical bar chart (bars alternate two brand colours). Returns the path."""
    if not values or min(values) < 0:
        raise ValueError("values must be non-empty and non-negative")
    pad = 30
    top = max(values) or 1
    n = len(values)
    slot = (width - 2 * pad) / n
    bg, colors = _hex(background), (_hex(bar), _hex(accent))
    pixels = [[bg] * width for _ in range(height)]
    for i, v in enumerate(values):
        x0 = int(pad + i * slot + slot * 0.15)
        x1 = int(pad + (i + 1) * slot - slot * 0.15)
        y0 = int(height - pad - (height - 2 * pad) * v / top)
        for y in range(y0, height - pad):
            row = pixels[y]
            for x in range(x0, x1):
                row[x] = colors[i % 2]
    axis = _hex("#94A3B8")
    for x in range(pad, width - pad):
        pixels[height - pad][x] = axis
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in pixels)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    p = Path(path)
    p.write_bytes(png)
    return p
