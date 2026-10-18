"""Ready drawing templates for the «Chizmalar» editor (PC and phone), as editor JSON (mm, Y up).

- A4 / A3 sheet with the frame and the main title block (GOST 2.301 formats, GOST 2.104 frame:
  20 mm binding margin on the left, 5 mm elsewhere; title block 185 x 55 mm, simplified).
- Hexagon bolt (side view), nut, washer (top views), deep-groove ball bearing (front view).
  Sizes from the usual tables: bolts/nuts ISO 4014/4032 (s, k, m), washers ISO 7089, bearings
  of series 62xx (d, D, B). Only common sizes are listed; anything else is a clear error.
"""

from __future__ import annotations

import math
import re
from typing import Any

# d: (across flats s, head height k, nut height m, washer d1, washer D, washer h)
METRIC = {
    6: (10, 4.0, 5.2, 6.4, 12, 1.6),
    8: (13, 5.3, 6.8, 8.4, 16, 1.6),
    10: (16, 6.4, 8.4, 10.5, 20, 2.0),
    12: (18, 7.5, 10.8, 13.0, 24, 2.5),
    16: (24, 10.0, 14.8, 17.0, 30, 3.0),
    20: (30, 12.5, 18.0, 21.0, 37, 3.0),
    24: (36, 15.0, 21.5, 25.0, 44, 4.0),
}
# bearing: (d, D, B)
BEARINGS = {
    "6200": (10, 30, 9),
    "6201": (12, 32, 10),
    "6202": (15, 35, 11),
    "6203": (17, 40, 12),
    "6204": (20, 47, 14),
    "6205": (25, 52, 15),
    "6206": (30, 62, 16),
    "6207": (35, 72, 17),
    "6208": (40, 80, 18),
}
SHEETS = {"A4": (210, 297), "A3": (420, 297)}

CATALOG = [
    {"id": "A4", "title": "A4 varaq: ramka va shtamp", "ask": ""},
    {"id": "A3", "title": "A3 varaq: ramka va shtamp", "ask": ""},
    {"id": "bolt", "title": "Bolt (yondan ko‘rinish)", "ask": "Rezba va uzunlik, masalan M10x50"},
    {"id": "nut", "title": "Gayka (ustidan)", "ask": "Rezba, masalan M12"},
    {"id": "washer", "title": "Shayba (ustidan)", "ask": "Rezba, masalan M10"},
    {"id": "bearing", "title": "Podshipnik (oldidan)", "ask": "Raqami, masalan 6204"},
]


def _n(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _line(x1: float, y1: float, x2: float, y2: float, layer: str = "KONTUR") -> dict[str, Any]:
    return {"type": "line", "layer": layer, "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _rect(x: float, y: float, w: float, h: float, layer: str = "KONTUR") -> dict[str, Any]:
    return {
        "type": "polyline",
        "layer": layer,
        "closed": True,
        "points": [[x, y, 0], [x + w, y, 0], [x + w, y + h, 0], [x, y + h, 0]],
    }


def _text(x: float, y: float, s: str, h: float = 2.5, layer: str = "MATN") -> dict[str, Any]:
    return {"type": "text", "layer": layer, "x": x, "y": y, "text": s, "h": h, "rot": 0}


def _circle(cx: float, cy: float, r: float, layer: str = "KONTUR") -> dict[str, Any]:
    return {"type": "circle", "layer": layer, "cx": cx, "cy": cy, "r": r}


def _ldim(x1, y1, x2, y2, bx, by, rot, label="") -> dict[str, Any]:  # noqa: ANN001
    return {
        "type": "ldim",
        "layer": "OLCHAM",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "bx": bx,
        "by": by,
        "rot": rot,
        "label": label,
    }


LAYERS = [
    {"name": "0", "color": 7, "lineweight": 25, "linetype": "Continuous", "visible": True},
    {"name": "KONTUR", "color": 7, "lineweight": 70, "linetype": "Continuous", "visible": True},
    {"name": "INGICHKA", "color": 8, "lineweight": 25, "linetype": "Continuous", "visible": True},
    {"name": "OQ_CHIZIQ", "color": 1, "lineweight": 25, "linetype": "NX_OQ", "visible": True},
    {"name": "OLCHAM", "color": 3, "lineweight": 18, "linetype": "Continuous", "visible": True},
    {"name": "MATN", "color": 7, "lineweight": 25, "linetype": "Continuous", "visible": True},
    {"name": "RAMKA", "color": 7, "lineweight": 50, "linetype": "Continuous", "visible": True},
]


def _metric(size: str) -> tuple[int, float | None]:
    m = re.search(r"m?\s*(\d+)(?:\s*[x×*]\s*(\d+(?:[.,]\d+)?))?", (size or "").lower())
    if not m or int(m.group(1)) not in METRIC:
        raise ValueError("Rezba: M6, M8, M10, M12, M16, M20 yoki M24 (masalan M10x50)")
    length = float(m.group(2).replace(",", ".")) if m.group(2) else None
    return int(m.group(1)), length


def sheet(fmt: str) -> list[dict[str, Any]]:
    w, h = SHEETS[fmt]
    out = [_rect(0, 0, w, h, "INGICHKA"), _rect(20, 5, w - 25, h - 10, "RAMKA")]
    x0, y0 = w - 5 - 185, 5  # title block, bottom right inside the frame
    out.append(_rect(x0, y0, 185, 55, "RAMKA"))
    for y in (5, 10, 15, 20, 25, 30, 35, 40, 45, 50):  # left part: 5 mm rows
        out.append(_line(x0, y0 + y, x0 + 65, y0 + y, "INGICHKA"))
    for x in (7, 17, 40, 55, 65, 135):
        out.append(_line(x0 + x, y0, x0 + x, y0 + 55, "RAMKA" if x in (65, 135) else "INGICHKA"))
    out += [
        _line(x0 + 135, y0 + 40, x0 + 185, y0 + 40, "RAMKA"),
        _line(x0 + 135, y0 + 20, x0 + 185, y0 + 20, "RAMKA"),
        _line(x0 + 65, y0 + 15, x0 + 135, y0 + 15, "RAMKA"),
    ]
    labels = [
        (1, 22, "Chizdi"),
        (1, 17, "Tekshirdi"),
        (1, 12, "T. nazorat"),
        (1, 7, "N. nazorat"),
        (1, 2, "Tasdiqladi"),
        (18, 27, "Familiya"),
        (41, 27, "Imzo"),
        (56, 27, "Sana"),
    ]
    out += [_text(x0 + x, y0 + y, s, 2.0) for x, y, s in labels]
    out += [
        _text(x0 + 70, y0 + 32, "Chizma nomi", 5.0),
        _text(x0 + 137, y0 + 46, "Massa", 2.5),
        _text(x0 + 162, y0 + 46, "Masshtab", 2.5),
        _text(x0 + 167, y0 + 42, "1:1", 3.5),
        _text(x0 + 137, y0 + 25, "Varaq 1", 2.5),
        _text(x0 + 162, y0 + 25, "Varaqlar 1", 2.5),
        _text(x0 + 70, y0 + 6, "Material", 3.5),
        _text(x0 + 140, y0 + 8, "Tashkilot", 3.5),
    ]
    return out


def _hexagon(cx: float, cy: float, s: float) -> dict[str, Any]:
    r = s / math.sqrt(3)  # across corners / 2
    pts = [
        [
            round(cx + r * math.cos(math.radians(30 + 60 * i)), 3),
            round(cy + r * math.sin(math.radians(30 + 60 * i)), 3),
            0,
        ]
        for i in range(6)
    ]
    return {"type": "polyline", "layer": "KONTUR", "closed": True, "points": pts}


def bolt(size: str) -> list[dict[str, Any]]:
    d, length = _metric(size)
    length = length or 5 * d
    if not d <= length <= 300:
        raise ValueError("Bolt uzunligi rezbadan katta va 300 mm gacha bo‘lsin")
    s, k = METRIC[d][0], METRIC[d][1]
    e = s / math.cos(math.radians(30))  # across corners: the head's visible height from the side
    thread = min(length, 2 * d + 6)
    c = 0.1 * d  # end chamfer
    out = [
        _rect(-k, -e / 2, k, e),
        _line(-k, -s / 2, 0, -s / 2, "INGICHKA"),
        _line(-k, s / 2, 0, s / 2, "INGICHKA"),  # flats seen from the side
        {
            "type": "polyline",
            "layer": "KONTUR",
            "closed": True,
            "points": [
                [0, -d / 2, 0],
                [length - c, -d / 2, 0],
                [length, -d / 2 + c, 0],
                [length, d / 2 - c, 0],
                [length - c, d / 2, 0],
                [0, d / 2, 0],
            ],
        },
        _line(length - thread, -0.425 * d, length, -0.425 * d, "INGICHKA"),
        _line(length - thread, 0.425 * d, length, 0.425 * d, "INGICHKA"),
        _line(length - thread, -d / 2, length - thread, d / 2),
        _line(-k - 3, 0, length + 3, 0, "OQ_CHIZIQ"),
        _ldim(0, d / 2, length, d / 2, length / 2, e / 2 + 8, 0),
        _ldim(-k, e / 2, 0, e / 2, -k / 2, e / 2 + 8, 0),
        _ldim(length, -d / 2, length, d / 2, length + 10, 0, 90, f"M{d}"),
        _text(0, -e / 2 - 10, f"Bolt M{d}×{length:g} (ISO 4014)", 3.5),
    ]
    return out


def nut(size: str) -> list[dict[str, Any]]:
    d, _ = _metric(size)
    s, m = METRIC[d][0], METRIC[d][2]
    return [
        _hexagon(0, 0, s),
        _circle(0, 0, 0.85 * d / 2),
        {"type": "arc", "layer": "INGICHKA", "cx": 0, "cy": 0, "r": d / 2, "start": 0, "end": 270},
        _circle(0, 0, s / 2, "INGICHKA"),
        _line(-s / 2 - 4, 0, s / 2 + 4, 0, "OQ_CHIZIQ"),
        _line(0, -s / 2 - 4, 0, s / 2 + 4, "OQ_CHIZIQ"),
        _ldim(
            -s / 2,
            -s / math.sqrt(3),
            s / 2,
            -s / math.sqrt(3),
            0,
            -s / math.sqrt(3) - 8,
            0,
            f"S{s}",
        ),
        _text(-s / 2, s / math.sqrt(3) + 6, f"Gayka M{d} (ISO 4032), balandligi {_n(m)} mm", 3.0),
    ]


def washer(size: str) -> list[dict[str, Any]]:
    d, _ = _metric(size)
    d1, big, h = METRIC[d][3], METRIC[d][4], METRIC[d][5]
    return [
        _circle(0, 0, big / 2),
        _circle(0, 0, d1 / 2),
        _line(-big / 2 - 4, 0, big / 2 + 4, 0, "OQ_CHIZIQ"),
        _line(0, -big / 2 - 4, 0, big / 2 + 4, "OQ_CHIZIQ"),
        {
            "type": "rdim",
            "layer": "OLCHAM",
            "cx": 0,
            "cy": 0,
            "r": big / 2,
            "angle": 45,
            "diameter": True,
            "label": "",
        },
        {
            "type": "rdim",
            "layer": "OLCHAM",
            "cx": 0,
            "cy": 0,
            "r": d1 / 2,
            "angle": 135,
            "diameter": True,
            "label": "",
        },
        _text(-big / 2, big / 2 + 6, f"Shayba {d} (ISO 7089), qalinligi {_n(h)} mm", 3.0),
    ]


def bearing(size: str) -> list[dict[str, Any]]:
    code = re.sub(r"\D", "", size or "")
    if code not in BEARINGS:
        raise ValueError("Podshipnik: 6200 … 6208 (masalan 6204)")
    d, big, width = BEARINGS[code]
    pitch = (d + big) / 4  # ball circle radius
    ball = (big - d) * 0.3 / 2
    out = [
        _circle(0, 0, big / 2),
        _circle(0, 0, d / 2),
        _circle(0, 0, pitch + ball * 0.8, "INGICHKA"),
        _circle(0, 0, pitch - ball * 0.8, "INGICHKA"),
        _circle(0, 0, pitch, "OQ_CHIZIQ"),
    ]
    n = max(6, int(2 * math.pi * pitch / (2.4 * ball)))
    out += [
        _circle(
            round(pitch * math.cos(2 * math.pi * i / n), 3),
            round(pitch * math.sin(2 * math.pi * i / n), 3),
            ball,
        )
        for i in range(n)
    ]
    out += [
        {
            "type": "rdim",
            "layer": "OLCHAM",
            "cx": 0,
            "cy": 0,
            "r": big / 2,
            "angle": 30,
            "diameter": True,
            "label": "",
        },
        {
            "type": "rdim",
            "layer": "OLCHAM",
            "cx": 0,
            "cy": 0,
            "r": d / 2,
            "angle": 210,
            "diameter": True,
            "label": "",
        },
        _text(-big / 2, big / 2 + 6, f"Podshipnik {code}: d={d}, D={big}, B={width} mm", 3.0),
    ]
    return out


def make(name: str, size: str = "") -> dict[str, Any]:
    """Editor drawing for a template; ValueError with an Uzbek message on a bad size."""
    if name in SHEETS:
        ents = sheet(name)
    elif name == "bolt":
        ents = bolt(size)
    elif name == "nut":
        ents = nut(size)
    elif name == "washer":
        ents = washer(size)
    elif name == "bearing":
        ents = bearing(size)
    else:
        raise ValueError("Bunday shablon yo‘q")
    for e in ents:
        for k, v in list(e.items()):
            if isinstance(v, float):
                e[k] = round(v, 3)
    return {"units": "mm", "layers": LAYERS, "entities": ents}
