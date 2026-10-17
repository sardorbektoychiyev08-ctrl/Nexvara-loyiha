"""Drawings ("chizma"): "shuni chizib ber", or a photo of a hand-drawn, unfinished sketch made
clean and complete.

Safety by design:
- the AI never writes SVG or code. It returns a small JSON *spec* (lines, circles, arcs, text,
  dimensions...) which is validated here against a strict whitelist with numeric bounds, and
  NEXVARA draws the SVG itself (text is XML-escaped). A bad or hostile reply cannot inject
  anything; it is rejected.
- a photo is re-encoded locally before it leaves the PC: EXIF (GPS location, phone model,
  time) is dropped and it is downscaled. Images cannot be masked like text, so every request
  with a picture asks the user first (Api._chat_drawing).
Output: SVG (exact), PDF (print) and PNG (phone preview), via PyMuPDF.
"""

from __future__ import annotations

import base64
import json
import math
import re
import time
from html import escape
from pathlib import Path
from typing import Any

from nexvara.core.task import UserError

MAX_SHAPES = 400
MAX_SIDE_MM = 2000.0
STYLES = {"solid": None, "dashed": "6,3", "hidden": "3,2", "center": "12,3,2,3", "thin": None}
KINDS = {"line", "polyline", "polygon", "rect", "circle", "ellipse", "arc", "text", "arrow", "dim"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024

_REQUEST = re.compile(
    r"\bchiz(ib|ib ber|ing|gin|masini|mani|ma|madan)?\b|\bchizma\w*|\bsxema\w*|\beskiz\w*",
    re.IGNORECASE,
)
_FROM_PHOTO = re.compile(
    r"\b(rasm\w*|surat\w*|foto\w*|shu|bu|ushbu|qo[‘’']?lda|chala|tugallanmagan)\b", re.IGNORECASE
)


def is_drawing_request(text: str) -> bool:
    return bool(_REQUEST.search(text or ""))


def wants_photo(text: str) -> bool:
    return bool(_FROM_PHOTO.search(text or ""))


def is_image(path: str | None) -> bool:
    return bool(path) and Path(str(path)).suffix.lower() in IMAGE_EXT and Path(str(path)).is_file()


# ---------------- validation ----------------
def _num(v: Any, lo: float = -MAX_SIDE_MM, hi: float = MAX_SIDE_MM) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise ValueError("raqam kutilgan")
    if not lo <= float(v) <= hi:
        raise ValueError(f"qiymat chegaradan tashqarida: {v}")
    return float(v)


def _pts(v: Any, n_min: int) -> list[tuple[float, float]]:
    if not isinstance(v, list) or not n_min <= len(v) <= 500:
        raise ValueError("nuqtalar ro‘yxati noto‘g‘ri")
    return [(_num(p[0]), _num(p[1])) for p in v if isinstance(p, list | tuple) and len(p) == 2]


def _text(v: Any, limit: int = 120) -> str:
    s = str(v if v is not None else "")
    s = "".join(c for c in s if c.isprintable())
    return s[:limit]


def validate(spec: Any) -> dict[str, Any]:
    """A clean copy of the spec, or ValueError. Unknown keys are dropped."""
    if not isinstance(spec, dict):
        raise ValueError("chizma JSON obyekt bo‘lishi kerak")
    out: dict[str, Any] = {
        "title": _text(spec.get("title") or "Chizma", 80),
        "width": _num(spec.get("width", 297), 10, MAX_SIDE_MM),
        "height": _num(spec.get("height", 210), 10, MAX_SIDE_MM),
        "scale": _text(spec.get("scale") or "1:1", 12),
        "notes": [_text(n, 200) for n in (spec.get("notes") or [])[:10]],
        "shapes": [],
    }
    shapes = spec.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        raise ValueError("chizmada shakl yo‘q")
    if len(shapes) > MAX_SHAPES:
        raise ValueError(f"shakllar juda ko‘p ({len(shapes)})")
    for i, s in enumerate(shapes, 1):
        if not isinstance(s, dict) or s.get("type") not in KINDS:
            raise ValueError(f"{i}-shakl turi noma’lum")
        t = s["type"]
        style = s.get("style") if s.get("style") in STYLES else "solid"
        c: dict[str, Any] = {"type": t, "style": style, "w": _num(s.get("w", 0.5), 0.1, 3.0)}
        try:
            if t in ("line", "arrow", "dim"):
                c.update(x1=_num(s["x1"]), y1=_num(s["y1"]), x2=_num(s["x2"]), y2=_num(s["y2"]))
                if t == "dim":
                    c["offset"] = _num(s.get("offset", 8), -200, 200)
                    c["label"] = _text(s.get("label") or "", 30)
            elif t in ("polyline", "polygon"):
                c["points"] = _pts(s.get("points"), 2 if t == "polyline" else 3)
            elif t == "rect":
                c.update(x=_num(s["x"]), y=_num(s["y"]), width=_num(s["width"], 0.1),
                         height=_num(s["height"], 0.1), r=_num(s.get("r", 0), 0, 500))  # fmt: skip
            elif t == "circle":
                c.update(cx=_num(s["cx"]), cy=_num(s["cy"]), r=_num(s["r"], 0.1))
            elif t == "ellipse":
                c.update(cx=_num(s["cx"]), cy=_num(s["cy"]), rx=_num(s["rx"], 0.1),
                         ry=_num(s["ry"], 0.1))  # fmt: skip
            elif t == "arc":
                c.update(cx=_num(s["cx"]), cy=_num(s["cy"]), r=_num(s["r"], 0.1))
                c.update(start=_num(s["start"], -720, 720), end=_num(s["end"], -720, 720))
            elif t == "text":
                c.update(x=_num(s["x"]), y=_num(s["y"]), text=_text(s.get("text")),
                         size=_num(s.get("size", 5), 1, 60))  # fmt: skip
        except (KeyError, TypeError, IndexError) as e:
            raise ValueError(f"{i}-shakl ({t}) maydoni yetishmaydi: {e}") from e
        out["shapes"].append(c)
    return out


def parse_reply(text: str) -> dict[str, Any]:
    """The JSON object inside the AI's reply (code fences tolerated), validated."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise UserError("AI chizma ma’lumotini qaytarmadi. Qaytadan urinib ko‘ring.")
    try:
        return validate(json.loads(m.group(0)))
    except ValueError as e:  # json.JSONDecodeError is a ValueError
        raise UserError(f"AI chizmasi tekshiruvdan o‘tmadi: {e}") from e


# ---------------- rendering (our own SVG; nothing from the AI is copied verbatim) ----------------
MARGIN = 10.0  # mm around the drawing area
TITLE_H = 16.0


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _el(tag: str, text: str | None = None, **attrs: Any) -> str:
    """One SVG element; every attribute and the text are escaped (a_b -> a-b)."""
    a = " ".join(f'{k.rstrip("_").replace("_", "-")}="{escape(str(v), quote=True)}"'
                 for k, v in attrs.items() if v is not None)  # fmt: skip
    return f"<{tag} {a}>{escape(text)}</{tag}>" if text is not None else f"<{tag} {a}/>"


def _stroke(c: dict[str, Any]) -> dict[str, Any]:
    return {"stroke": "#111827", "stroke_width": _f(c["w"]), "fill": "none",
            "stroke_linecap": "round"}  # fmt: skip


def _line(x1: float, y1: float, x2: float, y2: float, c: dict[str, Any]) -> str:
    return _el("line", x1=_f(x1), y1=_f(y1), x2=_f(x2), y2=_f(y2), **_stroke(c))


def _arrow_head(x1: float, y1: float, x2: float, y2: float, size: float = 3.0) -> str:
    a = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - size * math.cos(a - 0.35), y2 - size * math.sin(a - 0.35))
    p2 = (x2 - size * math.cos(a + 0.35), y2 - size * math.sin(a + 0.35))
    pts = f"{_f(x2)},{_f(y2)} {_f(p1[0])},{_f(p1[1])} {_f(p2[0])},{_f(p2[1])}"
    return _el("polygon", points=pts, fill="#111827")


def _label(x: float, y: float, text: str, size: float, angle: float = 0.0) -> str:
    rot = f"rotate({_f(angle)} {_f(x)} {_f(y)})" if angle else None
    return _el("text", text, x=_f(x), y=_f(y), font_size=_f(size), text_anchor="middle",
               font_family="Arial, sans-serif", fill="#111827", transform=rot)  # fmt: skip


def _outline(c: dict[str, Any]) -> tuple[list[tuple[float, float]], bool] | None:
    """The shape as points (closed?) — used to draw dashed lines segment by segment, because
    PDF/PNG renderers do not all honour stroke-dasharray."""
    t = c["type"]
    if t in ("line", "arrow"):
        return [(c["x1"], c["y1"]), (c["x2"], c["y2"])], False
    if t in ("polyline", "polygon"):
        return list(c["points"]), t == "polygon"
    if t == "rect":
        x, y, w, h = c["x"], c["y"], c["width"], c["height"]
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True
    if t in ("circle", "ellipse", "arc"):
        rx, ry = (c["r"], c["r"]) if t != "ellipse" else (c["rx"], c["ry"])
        a0, a1 = (
            (math.radians(c["start"]), math.radians(c["end"])) if t == "arc" else (0, 2 * math.pi)
        )
        if t == "arc" and a1 <= a0:
            a1 += 2 * math.pi
        n = max(24, int(abs(a1 - a0) / (2 * math.pi) * 96))
        pts = [(c["cx"] + rx * math.cos(a0 + (a1 - a0) * i / n),
                c["cy"] + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]  # fmt: skip
        return pts, False
    return None


def _dashed(c: dict[str, Any]) -> str | None:
    pattern = STYLES.get(c.get("style", "solid"))
    shape = _outline(c) if pattern else None
    if not shape:
        return None
    pts, closed = shape
    if closed:
        pts = [*pts, pts[0]]
    dash = [float(v) * max(0.6, c["w"] / 0.5) for v in pattern.split(",")]
    d, k, left, on = [], 0, dash[0], True
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while seg > 0 and pos < seg:
            step = min(left, seg - pos)
            if on:
                ax, ay = x0 + (x1 - x0) * pos / seg, y0 + (y1 - y0) * pos / seg
                bx, by = x0 + (x1 - x0) * (pos + step) / seg, y0 + (y1 - y0) * (pos + step) / seg
                d.append(f"M{_f(ax)} {_f(ay)}L{_f(bx)} {_f(by)}")
            pos += step
            left -= step
            if left <= 1e-9:
                k = (k + 1) % len(dash)
                left, on = dash[k], not on
    solid = {**c, "style": "solid"}
    out = _el("path", d="".join(d) or "M0 0", **_stroke(solid))
    if c["type"] == "arrow":
        out += _arrow_head(c["x1"], c["y1"], c["x2"], c["y2"])
    return out


def _shape_svg(c: dict[str, Any]) -> str:
    t = c["type"]
    dashed = _dashed(c)
    if dashed is not None:
        return dashed
    if t == "line":
        return _line(c["x1"], c["y1"], c["x2"], c["y2"], c)
    if t == "arrow":
        head = _arrow_head(c["x1"], c["y1"], c["x2"], c["y2"])
        return _line(c["x1"], c["y1"], c["x2"], c["y2"], c) + head
    if t in ("polyline", "polygon"):
        pts = " ".join(f"{_f(x)},{_f(y)}" for x, y in c["points"])
        return _el(t, points=pts, **_stroke(c))
    if t == "rect":
        return _el("rect", x=_f(c["x"]), y=_f(c["y"]), width=_f(c["width"]),
                   height=_f(c["height"]), rx=_f(c["r"]), **_stroke(c))  # fmt: skip
    if t == "circle":
        return _el("circle", cx=_f(c["cx"]), cy=_f(c["cy"]), r=_f(c["r"]), **_stroke(c))
    if t == "ellipse":
        return _el("ellipse", cx=_f(c["cx"]), cy=_f(c["cy"]), rx=_f(c["rx"]), ry=_f(c["ry"]),
                   **_stroke(c))  # fmt: skip
    if t == "arc":
        a0, a1 = math.radians(c["start"]), math.radians(c["end"])
        x0, y0 = c["cx"] + c["r"] * math.cos(a0), c["cy"] + c["r"] * math.sin(a0)
        x1, y1 = c["cx"] + c["r"] * math.cos(a1), c["cy"] + c["r"] * math.sin(a1)
        large = 1 if (c["end"] - c["start"]) % 360 > 180 else 0
        r = _f(c["r"])
        d = f"M {_f(x0)} {_f(y0)} A {r} {r} 0 {large} 1 {_f(x1)} {_f(y1)}"
        return _el("path", d=d, **_stroke(c))
    if t == "text":
        return _el("text", c["text"], x=_f(c["x"]), y=_f(c["y"]), font_size=_f(c["size"]),
                   font_family="Arial, sans-serif", fill="#111827")  # fmt: skip
    if t == "dim":  # a dimension: extension lines, a line with two arrows, the value
        x1, y1, x2, y2, off = c["x1"], c["y1"], c["x2"], c["y2"], c["offset"]
        length = math.hypot(x2 - x1, y2 - y1)
        if length == 0:
            return ""
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length
        a = (x1 + nx * off, y1 + ny * off)
        b = (x2 + nx * off, y2 + ny * off)
        thin = {**c, "w": 0.25, "style": "solid"}
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        if ang > 90 or ang < -90:
            ang += 180
        th = math.radians(ang)  # the text sits on the side its letters grow to, clear of the line
        mx = (a[0] + b[0]) / 2 + math.sin(th) * 1.0
        my = (a[1] + b[1]) / 2 - math.cos(th) * 1.0
        return "".join([
            _line(x1, y1, a[0] + nx * 2, a[1] + ny * 2, thin),
            _line(x2, y2, b[0] + nx * 2, b[1] + ny * 2, thin),
            _line(a[0], a[1], b[0], b[1], thin),
            _arrow_head(b[0], b[1], a[0], a[1], 2.5),
            _arrow_head(a[0], a[1], b[0], b[1], 2.5),
            _label(mx, my, c["label"] or _f(round(length, 1)), 3.5, ang),
        ])  # fmt: skip
    return ""


def render_svg(spec: dict[str, Any]) -> str:
    """A finished sheet: frame, the drawing, a title block (name, scale, date)."""
    s = validate(spec)
    w, h = s["width"], s["height"]
    W, H = w + 2 * MARGIN, h + 2 * MARGIN + TITLE_H  # noqa: N806
    body = "\n".join(_shape_svg(c) for c in s["shapes"])
    date = time.strftime("%d.%m.%Y")
    notes = "".join(
        f'<text x="{_f(MARGIN + 2)}" y="{_f(H - TITLE_H + 4 + 4 * (i + 1))}" font-size="2.8" '
        f'font-family="Arial, sans-serif" fill="#374151">{escape(n)}</text>'
        for i, n in enumerate(s["notes"][:2])
    )
    tx = W - MARGIN - 90
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{_f(W)}mm" height="{_f(H)}mm" viewBox="0 0 {_f(W)} {_f(H)}">
<rect x="0" y="0" width="{_f(W)}" height="{_f(H)}" fill="#ffffff"/>
<rect x="{_f(MARGIN / 2)}" y="{_f(MARGIN / 2)}" width="{_f(W - MARGIN)}" height="{_f(H - MARGIN)}" fill="none" stroke="#111827" stroke-width="0.7"/>
<g transform="translate({_f(MARGIN)} {_f(MARGIN)})">
{body}
</g>
<rect x="{_f(tx)}" y="{_f(H - TITLE_H - MARGIN / 2)}" width="90" height="{_f(TITLE_H)}" fill="none" stroke="#111827" stroke-width="0.5"/>
<text x="{_f(tx + 3)}" y="{_f(H - TITLE_H - MARGIN / 2 + 6.5)}" font-size="4.5" font-weight="bold" font-family="Arial, sans-serif" fill="#111827">{escape(s["title"])}</text>
<text x="{_f(tx + 3)}" y="{_f(H - MARGIN / 2 - 3)}" font-size="3" font-family="Arial, sans-serif" fill="#374151">Masshtab {escape(s["scale"])} · {date} · NEXVARA</text>
{notes}
</svg>"""  # noqa: E501


def to_dxf(spec: dict[str, Any]) -> str:
    """The same drawing as AutoCAD R12 DXF (mm; y flipped because DXF y grows upwards)."""
    s = validate(spec)
    hgt = s["height"]
    out: list[str] = ["0", "SECTION", "2", "ENTITIES"]

    def ent(kind: str, *pairs: tuple[int, Any]) -> None:
        out.extend([("0"), kind, "8", "0"])
        for code, val in pairs:
            out.extend([str(code), _f(val) if isinstance(val, float | int) else str(val)])

    def line(x1: float, y1: float, x2: float, y2: float) -> None:
        ent("LINE", (10, x1), (20, hgt - y1), (11, x2), (21, hgt - y2))

    def text(x: float, y: float, value: str, size: float) -> None:
        clean = "".join(ch if ord(ch) < 128 else "?" for ch in value)  # R12 is ASCII
        ent("TEXT", (10, x), (20, hgt - y), (40, size), (1, clean))

    for c in s["shapes"]:
        t = c["type"]
        if t == "circle":
            ent("CIRCLE", (10, c["cx"]), (20, hgt - c["cy"]), (40, c["r"]))
        elif t == "arc":  # SVG angles run clockwise on screen; DXF counter-clockwise
            ent("ARC", (10, c["cx"]), (20, hgt - c["cy"]), (40, c["r"]),
                (50, (-c["end"]) % 360), (51, (-c["start"]) % 360))  # fmt: skip
        elif t == "text":
            text(c["x"], c["y"], c["text"], c["size"])
        elif t == "dim":
            x1, y1, x2, y2, off = c["x1"], c["y1"], c["x2"], c["y2"], c["offset"]
            length = math.hypot(x2 - x1, y2 - y1)
            if length:
                nx, ny = -(y2 - y1) / length, (x2 - x1) / length
                ax, ay, bx, by = x1 + nx * off, y1 + ny * off, x2 + nx * off, y2 + ny * off
                line(x1, y1, ax, ay)
                line(x2, y2, bx, by)
                line(ax, ay, bx, by)
                text((ax + bx) / 2, (ay + by) / 2 - 1, c["label"] or _f(round(length, 1)), 3.5)
        else:
            shape = _outline(c)
            if shape:
                pts, closed = shape
                if closed:
                    pts = [*pts, pts[0]]
                for (xa, ya), (xb, yb) in zip(pts, pts[1:], strict=False):
                    line(xa, ya, xb, yb)
    out.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(out) + "\n"


def export(spec: dict[str, Any], folder: Path, name: str = "") -> dict[str, str]:
    """Write SVG, PDF, PNG and DXF; returns their paths."""
    import fitz  # PyMuPDF

    svg = render_svg(spec)
    folder.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^\w‘’' -]", "", name or spec.get("title") or "chizma").strip()[:50] or "chizma"
    stem = f"{base.replace(' ', '_')}_{time.strftime('%Y%m%d-%H%M%S')}"
    svg_p, pdf_p, png_p = (folder / f"{stem}{ext}" for ext in (".svg", ".pdf", ".png"))
    svg_p.write_text(svg, encoding="utf-8")
    dxf_p = folder / f"{stem}.dxf"
    dxf_p.write_text(to_dxf(spec), encoding="ascii")
    doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    try:
        pdf_p.write_bytes(doc.convert_to_pdf())
        page = doc[0]
        zoom = min(4.0, 2400 / max(page.rect.width, page.rect.height))
        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(str(png_p))
    finally:
        doc.close()
    return {"svg": str(svg_p), "pdf": str(pdf_p), "png": str(png_p), "dxf": str(dxf_p)}


# ---------------- the photo ----------------
def clean_image(path: Path, max_side: int = 1600) -> tuple[str, str]:
    """(mime, base64) of the photo re-encoded locally: no EXIF/GPS, at most `max_side` px."""
    import fitz

    data = Path(path).read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        raise UserError("Rasm juda katta (15 MB gacha)")
    try:
        pix = fitz.Pixmap(data)
    except Exception as e:  # not an image PyMuPDF can read
        raise UserError("Rasmni o‘qib bo‘lmadi (JPG yoki PNG yuboring)") from e
    if pix.alpha or pix.n > 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    side = max(pix.width, pix.height)
    if side > max_side:
        f = math.ceil(math.log2(side / max_side))
        pix.shrink(f)  # halves the size f times
    out = pix.tobytes("jpeg", jpg_quality=85)  # a fresh JPEG: the original metadata is gone
    return "image/jpeg", base64.b64encode(out).decode("ascii")


PROMPT = """You are a precise technical draftsman. Produce ONE JSON object describing a clean,
complete drawing. No prose, no SVG, no code: only JSON with this schema (all lengths in mm,
origin top-left, y grows downwards, the drawing area is width x height):
{"title": str (Uzbek), "width": number, "height": number, "scale": "1:1", "notes": [str],
 "shapes": [
  {"type":"line","x1","y1","x2","y2","style":"solid|dashed|hidden|center|thin","w":0.25..1},
  {"type":"polyline"|"polygon","points":[[x,y],...]},
  {"type":"rect","x","y","width","height","r"},
  {"type":"circle","cx","cy","r"}, {"type":"ellipse","cx","cy","rx","ry"},
  {"type":"arc","cx","cy","r","start":deg,"end":deg},
  {"type":"arrow","x1","y1","x2","y2"},
  {"type":"dim","x1","y1","x2","y2","offset","label"},
  {"type":"text","x","y","text","size"}]}
Rules: straight lines straight, right angles exact, symmetric parts symmetric, circles round;
main contours w=0.7, hidden lines "hidden", axes "center", dimensions with "dim". Labels and
notes in Uzbek (Latin). At most 300 shapes."""


_EDIT = re.compile(
    r"\b(oxirgi|shu|bu)?\s*chizma\w*.*\b(o[‘’']?zgartir|tuzat|qo[‘’']?sh|olib tashla|"
    r"kattalashtir|kichraytir|almashtir|uzaytir|qisqartir|o[‘’']?chir)\w*",
    re.IGNORECASE,
)


def is_edit_request(text: str) -> bool:
    """ "Oxirgi chizmani o‘zgartir: teshik 10 mm bo‘lsin" (needs a previous drawing)."""
    return bool(_EDIT.search(text or "")) and "chizib ber" not in (text or "").lower()


Messages = list[dict[str, Any]]


def ai_messages(request: str, image: tuple[str, str] | None,
                previous: dict[str, Any] | None = None) -> tuple[str, Messages]:  # fmt: skip
    """(system, messages) for AiRouter.complete. The user text is masked by the router."""
    if previous is not None:
        task = ("Here is the current drawing JSON. Apply the user's change and return the whole "
                f"new drawing JSON. Change: {request}\nCurrent: "
                + json.dumps(previous, ensure_ascii=False))  # fmt: skip
        return PROMPT, [{"role": "user", "content": task}]
    if image is None:
        task = f"Draw: {request}"
    else:
        task = ("The photo shows a hand-drawn, possibly unfinished sketch. Redraw it as a clean, "
                "complete technical drawing: keep its shapes, proportions and any written sizes, "
                "complete obviously missing symmetric parts, fix wobbly lines. User's words: "
                f"{request}")  # fmt: skip
    msg: dict[str, Any] = {"role": "user", "content": task}
    if image is not None:
        msg["images"] = [{"mime": image[0], "data": image[1]}]
    return PROMPT, [msg]
