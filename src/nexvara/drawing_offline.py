"""Simple parts drawn exactly, without AI: "100x60 plastina, markazida 20 mm teshik chizib ber".

Recognised: rectangle/plate/square (rounded corners, a centre hole, holes in the corners),
circle/disc, ring/washer, triangle (three sides, or base + height), regular polygon (hexagon
nut...), ellipse. Sizes in mm (sm/m are converted). The result is the same validated spec the
AI would return, with centre lines and dimensions, so PDF/PNG/DXF come out identical in style.
Anything not understood returns None and the request goes to the AI (if connected).
"""

from __future__ import annotations

import math
import re
from typing import Any

from nexvara.knowledge.textnorm import fold

_NUM = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(?:\s*(mm|sm|cm|m)\b)?"

SHAPES = [
    ("ring", r"halqa|shayba|vtulka|quvur kesim"),
    ("polygon", r"(?:olti|besh|sakkiz|uch|tort|\d+)\s*burchakli|oltiburchak|gayka|kopburchak"),
    ("triangle", r"uchburchak"),
    ("ellipse", r"ellips|oval"),
    ("circle", r"doira|aylana|disk|gardish"),
    ("rect", r"tortburchak|plastina|plita|list|kvadrat|panel|taxta|lavha|detal"),
]
_N_SIDES = {"uch": 3, "tort": 4, "besh": 5, "olti": 6, "sakkiz": 8}


def _mm(value: str, unit: str | None) -> float:
    v = float(value.replace(",", "."))
    return v * {"sm": 10, "cm": 10, "m": 1000}.get((unit or "").lower(), 1)


def _find(f: str, *keys: str) -> float | None:
    """The number after (or right before) one of the key words: "radiusi 20", "20 mm radius".
    Words take suffixes ("radiusi"); one-letter marks (d, r, Ø) must stand alone ("d=40")."""
    for k in keys:
        tail = r"\w*" if len(k) > 2 else r"(?![a-z])"
        m = re.search(rf"(?<![a-z])(?:{k}){tail}\s*(?:=|:|-)?\s*{_NUM}{_UNIT}", f)
        if m:
            return _mm(m.group(1), m.group(2))
    for k in (k for k in keys if len(k) > 2):
        m = re.search(rf"{_NUM}{_UNIT}\s*(?:li\s+|lik\s+)?(?:{k})", f)
        if m:
            return _mm(m.group(1), m.group(2))
    return None


def _shape(f: str) -> str | None:
    return next((name for name, pat in SHAPES if re.search(rf"\b(?:{pat})", f)), None)


def parse(text: str, base: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Parameters of a simple part, or None. With `base` (the previous drawing's parameters),
    only the sizes mentioned in `text` change: "teshik 10 mm bo‘lsin"."""
    f = fold(text or "").replace("×", "x").replace("ø", "Ø")
    shape = _shape(f) or (base or {}).get("shape")
    if shape is None:
        return None
    p: dict[str, Any] = dict(base or {}) if (base or {}).get("shape") == shape else {}
    p["shape"] = shape
    if base is None or _shape(f):
        p["title"] = _title(text, shape)

    pair = re.search(rf"{_NUM}{_UNIT}\s*(?:x|\*|ga)\s*{_NUM}{_UNIT}", f)
    if pair:
        unit = pair.group(2) or pair.group(4)
        a, b = _mm(pair.group(1), unit), _mm(pair.group(3), pair.group(4) or unit)
    else:
        a = b = None
    dia = _find(f, "diametr", "Ø", "d")
    rad = _find(f, "radius", "r")
    hole = _hole(f)

    if shape == "rect":
        side = _find(f, "tomon", "kvadrat")
        if "kvadrat" in f and (side or a):
            p["w"] = p["h"] = side or a
        else:
            p["w"] = a or _find(f, "eni", "uzunlig", "kengli") or p.get("w")
            p["h"] = b or _find(f, "bo[‘’']?yi", "boyi", "balandlig") or p.get("h")
        corner = _find(f, "yumaloq", "radiusli burchak", "burchak radius", "burchaklari r")
        if corner is None and re.search(r"burchak\w* (?:yumaloq|r\s*\d)", f):
            corner = rad
        if corner is not None:
            p["corner_r"] = corner
        if hole is not None:
            p.update(hole)
        if not (p.get("w") and p.get("h")):
            return None
    elif shape == "circle":
        d = dia or (2 * rad if rad else None) or a or p.get("d")
        if not d:
            return None
        p["d"] = d
        if hole is not None and hole.get("center_hole"):
            p["center_hole"] = hole["center_hole"]
    elif shape == "ring":
        outer = _find(f, "tashqi diametr", "tashqi") or (a if a and b else None) or dia
        inner = _find(f, "ichki diametr", "ichki", "teshik") or (b if a and b else None)
        p["d"] = outer or p.get("d")
        p["d_in"] = inner or p.get("d_in")
        if not (p.get("d") and p.get("d_in")) or p["d_in"] >= p["d"]:
            return None
    elif shape == "triangle":
        sides = re.search(rf"tomon\w*\s*{_NUM}\s*,?\s*{_NUM}\s*,?\s*(?:va\s*)?{_NUM}{_UNIT}", f)
        if sides:
            unit = sides.group(4)
            p["sides"] = [_mm(sides.group(i), unit) for i in (1, 2, 3)]
        elif "teng tomonli" in f and (_find(f, "tomon") or a):
            s = _find(f, "tomon") or a
            p["sides"] = [s, s, s]
        else:
            base_len, height = _find(f, "asos"), _find(f, "balandlig")
            if base_len and height:
                p["base_h"] = [base_len, height]
        if not (p.get("sides") or p.get("base_h")):
            return None
        if p.get("sides"):
            s1, s2, s3 = sorted(p["sides"])
            if s1 + s2 <= s3:
                raise ValueError("Bunday uchburchak bo‘lmaydi: ikki tomon yig‘indisi uchinchisidan "
                                 "katta bo‘lishi kerak")  # fmt: skip
    elif shape == "polygon":
        m = re.search(r"(\d+)\s*burchak", f)
        word = next((n for w, n in _N_SIDES.items() if re.search(rf"\b{w}\s*burchak", f)), None)
        n = int(m.group(1)) if m else word or (6 if "gayka" in f else p.get("n", 6))
        if not 3 <= n <= 24:
            return None
        p["n"] = n
        flats = _find(f, "kalit olchami", "kalit", "tomonlar orasi", "s")
        side = _find(f, "tomon")
        if flats:
            p["r"] = flats / 2 / math.cos(math.pi / n)
        elif side:
            p["r"] = side / (2 * math.sin(math.pi / n))
        elif dia or a:
            p["r"] = (dia or a) / 2
        if not p.get("r"):
            return None
        if hole is not None and hole.get("center_hole"):
            p["center_hole"] = hole["center_hole"]
        elif "gayka" in f and "center_hole" not in p:
            p["center_hole"] = round(p["r"] * math.cos(math.pi / n) * 1.0, 1)  # thread ≈ flats/2
    elif shape == "ellipse":
        if a and b:
            p["rx"], p["ry"] = a / 2, b / 2
        elif not p.get("rx"):
            return None
    for key in ("w", "h", "d", "d_in", "r", "rx", "ry"):
        if key in p and not 0.5 <= p[key] <= 20000:
            raise ValueError("O‘lcham juda kichik yoki juda katta (0,5 mm … 20 m)")
    return p


def _hole(f: str) -> dict[str, Any] | None:
    """Holes: "markazida 20 mm teshik", "burchaklarida 4 ta 8 mm teshik", "teshik Ø10"."""
    if "teshik" not in f:
        return None
    m = re.search(rf"{_NUM}{_UNIT}\s*(?:li|lik)?\s*(?:diametrli\s+)?teshik", f)
    m = m or re.search(rf"teshik\w*\s*(?:diametri\s*)?(?:Ø|d|r)?\s*=?\s*{_NUM}{_UNIT}", f)
    if not m:
        return None
    size = _mm(m.group(1), m.group(2))
    if re.search(r"burchak\w*", f) and re.search(r"\b4\s*ta|tort\w* (?:ta )?teshik", f):
        return {"corner_holes": size}
    return {"center_hole": size}


def _title(text: str, shape: str) -> str:
    names = {"rect": "Plastina", "circle": "Disk", "ring": "Halqa (shayba)",
             "triangle": "Uchburchak", "polygon": "Ko‘pburchak", "ellipse": "Ellips"}  # fmt: skip
    if shape == "polygon" and "gayka" in fold(text):
        return "Gayka"
    if shape == "polygon":
        m = re.search(r"(\d+|olti|besh|sakkiz|uch|tort)\s*burchak", fold(text))
        words = {"6": "olti", "5": "besh", "8": "sakkiz", "3": "uch", "4": "to‘rt", "tort": "to‘rt"}
        if m:
            return f"{words.get(m.group(1), m.group(1)).capitalize()} burchakli detal"
    if shape == "rect" and "kvadrat" in fold(text):
        return "Kvadrat"
    return names[shape]


# ---------------- spec ----------------
_SCALES = [1, 2, 2.5, 4, 5, 10, 20, 25, 50, 100]


def _num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def build_spec(p: dict[str, Any]) -> dict[str, Any]:
    """The drawing (in sheet mm). Big parts are drawn at a reduced scale; the dimension labels
    always show the real size."""
    w_real, h_real = _extent(p)
    k = next((s for s in _SCALES if max(w_real, h_real) / s <= 260), _SCALES[-1])
    pad = 30.0
    width, height = w_real / k + 2 * pad, h_real / k + 2 * pad
    width, height = max(width, 200.0), max(height, 80.0)  # room for notes + title block
    cx, cy = width / 2, height / 2
    shapes: list[dict[str, Any]] = []
    notes: list[str] = []

    def dim(x1: float, y1: float, x2: float, y2: float, real: float, off: float = 10,
            prefix: str = "") -> None:  # fmt: skip
        shapes.append({"type": "dim", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "offset": off,
                       "label": prefix + _num(real)})  # fmt: skip

    def axes(x: float, y: float, rx: float, ry: float) -> None:
        e = 4
        shapes.append({"type": "line", "x1": x - rx - e, "y1": y, "x2": x + rx + e, "y2": y,
                       "style": "center", "w": 0.25})  # fmt: skip
        shapes.append({"type": "line", "x1": x, "y1": y - ry - e, "x2": x, "y2": y + ry + e,
                       "style": "center", "w": 0.25})  # fmt: skip

    def hole(x: float, y: float, d_real: float) -> None:
        r = d_real / 2 / k
        shapes.append({"type": "circle", "cx": x, "cy": y, "r": r, "w": 0.7})
        axes(x, y, r, r)

    t = p["shape"]
    if t == "rect":
        w, h = p["w"] / k, p["h"] / k
        x0, y0 = cx - w / 2, cy - h / 2
        shapes.append({"type": "rect", "x": x0, "y": y0, "width": w, "height": h,
                       "r": min(p.get("corner_r", 0) / k, w / 2, h / 2), "w": 0.7})  # fmt: skip
        dim(x0, y0 + h, x0 + w, y0 + h, p["w"], 12)
        dim(x0 + w, y0 + h, x0 + w, y0, p["h"], 12)
        if p.get("corner_r"):
            notes.append(f"Burchaklar radiusi R{_num(p['corner_r'])}")
        if p.get("center_hole"):
            hole(cx, cy, p["center_hole"])
            notes.append(f"Markaziy teshik Ø{_num(p['center_hole'])}")
        if p.get("corner_holes"):
            d = p["corner_holes"]
            inset = max(d, min(p["w"], p["h"]) * 0.12, 5.0)  # real mm from the edges
            if 2 * inset + d > min(p["w"], p["h"]):
                raise ValueError("Teshiklar sig‘maydi: plastina kichik yoki teshik katta")
            for sx in (-1, 1):
                for sy in (-1, 1):
                    hole(cx + sx * (w / 2 - inset / k), cy + sy * (h / 2 - inset / k), d)
            notes.append(f"4 ta teshik Ø{_num(d)}, chetdan {_num(inset)} mm")
            dim(x0, y0, x0 + inset / k, y0, inset, -8)
    elif t == "circle":
        r = p["d"] / 2 / k
        shapes.append({"type": "circle", "cx": cx, "cy": cy, "r": r, "w": 0.7})
        axes(cx, cy, r, r)
        dim(cx - r, cy + r, cx + r, cy + r, p["d"], 12, "Ø")
        if p.get("center_hole"):
            shapes.append({"type": "circle", "cx": cx, "cy": cy, "r": p["center_hole"] / 2 / k,
                           "w": 0.7})  # fmt: skip
            notes.append(f"Markaziy teshik Ø{_num(p['center_hole'])}")
    elif t == "ring":
        r, ri = p["d"] / 2 / k, p["d_in"] / 2 / k
        shapes += [{"type": "circle", "cx": cx, "cy": cy, "r": r, "w": 0.7},
                   {"type": "circle", "cx": cx, "cy": cy, "r": ri, "w": 0.7}]  # fmt: skip
        axes(cx, cy, r, r)
        dim(cx - r, cy + r, cx + r, cy + r, p["d"], 12, "Ø")
        dim(cx - ri, cy - r, cx + ri, cy - r, p["d_in"], -8, "Ø")
        notes.append(f"Devor qalinligi {_num((p['d'] - p['d_in']) / 2)} mm")
    elif t == "triangle":
        pts = _triangle(p)
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        ox = cx - (max(xs) + min(xs)) / 2 / k
        oy = cy + (max(ys) - min(ys)) / 2 / k  # base at the bottom, apex up (screen y down)
        sp = [(ox + x / k, oy - y / k) for x, y in pts]
        shapes.append({"type": "polygon", "points": [list(q) for q in sp], "w": 0.7})
        reals = [math.dist(pts[i], pts[(i + 1) % 3]) for i in range(3)]
        for i in range(3):
            a, b = sp[i], sp[(i + 1) % 3]
            dim(a[0], a[1], b[0], b[1], reals[i], 10)  # +offset = outside
        angles = _angles(reals)
        notes.append("Burchaklar: " + ", ".join(f"{_num(round(v, 1))}°" for v in angles))
    elif t == "polygon":
        n, r = p["n"], p["r"] / k
        start = -math.pi / 2 + (math.pi / n if n % 2 == 0 else 0)  # flat at the top and bottom
        pts = [[cx + r * math.cos(start + 2 * math.pi * i / n),
                cy + r * math.sin(start + 2 * math.pi * i / n)] for i in range(n)]  # fmt: skip
        shapes.append({"type": "polygon", "points": pts, "w": 0.7})
        axes(cx, cy, r, r)
        side = 2 * p["r"] * math.sin(math.pi / n)
        if n % 2:
            dim(pts[0][0], pts[0][1], pts[1][0], pts[1][1], side, -10)
        if n % 2 == 0:
            flats = 2 * p["r"] * math.cos(math.pi / n)
            ymin = min(q[1] for q in pts)
            ymax = max(q[1] for q in pts)
            dim(cx + r + 2, ymax, cx + r + 2, ymin, flats, 10)
            notes.append(f"Kalit o‘lchami S{_num(round(flats, 2))}, tomoni {_num(round(side, 2))}")
        dim(cx - r, cy + r, cx + r, cy + r, 2 * p["r"], 14, "Ø")
        if p.get("center_hole"):
            shapes.append({"type": "circle", "cx": cx, "cy": cy, "r": p["center_hole"] / 2 / k,
                           "w": 0.7})  # fmt: skip
            notes.append(f"Teshik Ø{_num(p['center_hole'])}")
    elif t == "ellipse":
        rx, ry = p["rx"] / k, p["ry"] / k
        shapes.append({"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry, "w": 0.7})
        axes(cx, cy, rx, ry)
        dim(cx - rx, cy + ry, cx + rx, cy + ry, 2 * p["rx"], 12)
        dim(cx + rx, cy + ry, cx + rx, cy - ry, 2 * p["ry"], 12)
    scale = "1:1" if k == 1 else f"1:{_num(k)}"
    return {"title": p.get("title") or "Chizma", "width": width, "height": height, "scale": scale,
            "notes": [*notes, "O‘lchamlar mm da."],
            "shapes": shapes}  # fmt: skip


def _extent(p: dict[str, Any]) -> tuple[float, float]:
    t = p["shape"]
    if t == "rect":
        return p["w"], p["h"]
    if t in ("circle", "ring"):
        return p["d"], p["d"]
    if t == "polygon":
        return 2 * p["r"], 2 * p["r"]
    if t == "ellipse":
        return 2 * p["rx"], 2 * p["ry"]
    pts = _triangle(p)
    return (max(q[0] for q in pts) - min(q[0] for q in pts),
            max(q[1] for q in pts) - min(q[1] for q in pts))  # fmt: skip


def _triangle(p: dict[str, Any]) -> list[tuple[float, float]]:
    """Vertices (real mm, y up): base on the x axis, the longest side as the base."""
    if p.get("base_h"):
        b, h = p["base_h"]
        return [(0.0, 0.0), (b, 0.0), (b / 2, h)]
    a, b, c = sorted(p["sides"], reverse=True)  # c... base = a (longest)
    x = (a * a + c * c - b * b) / (2 * a)
    y = math.sqrt(max(c * c - x * x, 0.0))
    return [(0.0, 0.0), (a, 0.0), (x, y)]


def _angles(s: list[float]) -> list[float]:
    out = []
    for i in range(3):
        a, b, c = s[i], s[(i + 1) % 3], s[(i + 2) % 3]
        cos = (b * b + c * c - a * a) / (2 * b * c)
        out.append(math.degrees(math.acos(max(-1.0, min(1.0, cos)))))
    return out


def describe(p: dict[str, Any]) -> str:
    t = p["shape"]
    if t == "rect":
        s = f"{_num(p['w'])}×{_num(p['h'])} mm"
    elif t in ("circle",):
        s = f"Ø{_num(p['d'])} mm"
    elif t == "ring":
        s = f"Ø{_num(p['d'])} / Ø{_num(p['d_in'])} mm"
    elif t == "polygon":
        s = f"{p['n']} burchakli, Ø{_num(round(2 * p['r'], 2))} mm"
    elif t == "ellipse":
        s = f"{_num(2 * p['rx'])}×{_num(2 * p['ry'])} mm"
    else:
        s = ("tomonlari " + ", ".join(_num(v) for v in p["sides"])) if p.get("sides") else (
            f"asosi {_num(p['base_h'][0])}, balandligi {_num(p['base_h'][1])}")  # fmt: skip
    return f"{p.get('title', 'Chizma')}: {s}"
