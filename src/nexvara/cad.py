"""AutoCAD files: a NEXVARA drawing as a proper DXF, and any DXF shown as PDF/PNG.

The DXF is what an engineer expects when it opens in AutoCAD:
- R2010 (AutoCAD 2010+ opens it directly; Unicode text, so «o‘», «ғ», «Ø» survive);
- units millimetres ($INSUNITS=4, metric), y pointing up, the drawing at its real size;
- layers by line purpose (contour, thin, hidden, axis, dimensions, text, frame), each with
  its own colour, line weight and an ISO-like line type in mm;
- real entities: LWPOLYLINE (rounded corners as bulges), CIRCLE, ARC, ELLIPSE, TEXT and true
  associative-looking DIMENSIONs (AutoCAD can edit their value and style);
- the sheet frame and title block, as on the PDF.
Everything is built from the validated spec (nexvara.drawing.validate), never from AI text.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
from typing import Any

# name: (ACI colour, line weight in 1/100 mm, line type)
LAYERS = {
    "KONTUR": (7, 70, "Continuous"),  # main visible contour
    "INGICHKA": (8, 25, "Continuous"),  # thin lines
    "YASHIRIN": (5, 35, "NX_SHTRIX"),  # hidden edges
    "SHTRIX": (4, 35, "NX_SHTRIX"),  # dashed (non-hidden) lines
    "OQ_CHIZIQ": (1, 25, "NX_OQ"),  # axes, centre lines
    "OLCHAM": (3, 18, "Continuous"),  # dimensions and arrows
    "MATN": (7, 25, "Continuous"),
    "RAMKA": (7, 50, "Continuous"),  # sheet frame and title block
}
LINETYPES = {  # in mm, as on a printed sheet (GOST 2.303: dashes 2-8, gaps 1-2)
    "NX_SHTRIX": ("Shtrix chiziq ____ ____", [6.0, 4.0, -2.0]),
    "NX_OQ": ("Shtrix-punktir (o‘q) ____ . ____", [17.0, 12.0, -2.0, 0.5, -2.5]),
}
_WEIGHTS = (13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158)
TEXT_STYLE = "NEXVARA"
DIM_STYLE = "NEXVARA"


def _layer_for(c: dict[str, Any]) -> str:
    style = c.get("style", "solid")
    if c["type"] in ("dim", "arrow"):
        return "OLCHAM"
    if c["type"] == "text":
        return "MATN"
    if style == "hidden":
        return "YASHIRIN"
    if style == "dashed":
        return "SHTRIX"
    if style == "center":
        return "OQ_CHIZIQ"
    if style == "thin" or c.get("w", 0.5) < 0.45:
        return "INGICHKA"
    return "KONTUR"


def _weight(w_mm: float) -> int:
    want = round(w_mm * 100)
    return min(_WEIGHTS, key=lambda v: abs(v - want))


def new_document() -> Any:
    """An empty R2010 drawing in mm with NEXVARA's layers, line types and styles."""
    import ezdxf
    from ezdxf import units

    doc = ezdxf.new("R2010", setup=False, units=units.MM)
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 0
    doc.header["$LWDISPLAY"] = 1  # show line weights, as on paper
    doc.header["$DIMSTYLE"] = DIM_STYLE
    doc.header["$TEXTSTYLE"] = TEXT_STYLE
    for name, (desc, pattern) in LINETYPES.items():
        doc.linetypes.add(name, pattern=pattern, description=desc)
    for name, (color, lw, lt) in LAYERS.items():
        doc.layers.add(name, color=color, lineweight=lw, linetype=lt)
    doc.styles.add(TEXT_STYLE, font="arial.ttf")
    ds = doc.dimstyles.new(DIM_STYLE)
    ds.dxf.dimtxsty = TEXT_STYLE
    ds.dxf.dimtxt = 3.5  # text height, mm
    ds.dxf.dimasz = 2.5  # arrow size
    ds.dxf.dimexe = 2.0  # extension line beyond the dimension line
    ds.dxf.dimexo = 0.0  # extension lines start at the object (as on the PDF)
    ds.dxf.dimgap = 1.0
    ds.dxf.dimtad = 1  # text above the line
    ds.dxf.dimdec = 1
    ds.dxf.dimzin = 8  # no trailing zeros: 100, 12,5
    ds.dxf.dimdsep = ord(",")  # Uzbek/GOST decimal comma
    ds.dxf.dimlunit = 2  # decimal
    ds.dxf.dimclrd = 3
    ds.dxf.dimclre = 3
    ds.dxf.dimclrt = 3
    ds.dxf.dimlwd = 18
    ds.dxf.dimlwe = 18
    ds.dxf.dimtih = 0  # text aligned with the dimension line, as on the PDF
    ds.dxf.dimtoh = 0
    return doc


def _rounded_rect(x: float, y: float, w: float, h: float, r: float) -> list[tuple]:
    """Corner points with bulges for a rounded rectangle (y already flipped, y up, x,y = lower
    left). A bulge of tan(90°/4) makes a quarter circle."""
    r = min(r, w / 2, h / 2)
    if r <= 0:
        return [(x, y, 0), (x + w, y, 0), (x + w, y + h, 0), (x, y + h, 0)]
    b = math.tan(math.radians(22.5))
    return [
        (x + r, y, 0), (x + w - r, y, b), (x + w, y + r, 0), (x + w, y + h - r, b),
        (x + w - r, y + h, 0), (x + r, y + h, b), (x, y + h - r, 0), (x, y + r, b),
    ]  # fmt: skip


def build(spec: dict[str, Any], frame: bool = True) -> Any:
    """The ezdxf document for a validated drawing spec."""
    from nexvara.drawing import MARGIN, TITLE_H, validate

    s = validate(spec)
    doc = new_document()
    msp = doc.modelspace()
    hgt = s["height"]

    def flip(x: float, y: float) -> tuple[float, float]:
        return (x, hgt - y)

    def attrs(c: dict[str, Any], layer: str | None = None) -> dict[str, Any]:
        layer = layer or _layer_for(c)
        a: dict[str, Any] = {"layer": layer}
        lw = _weight(c.get("w", 0.5))
        if lw != LAYERS[layer][1]:
            a["lineweight"] = lw
        return a

    def arrow_head(tip: tuple[float, float], frm: tuple[float, float], size: float,
                   layer: str) -> None:  # fmt: skip
        a = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
        p1 = (tip[0] - size * math.cos(a - 0.35), tip[1] - size * math.sin(a - 0.35))
        p2 = (tip[0] - size * math.cos(a + 0.35), tip[1] - size * math.sin(a + 0.35))
        msp.add_solid([tip, p1, p2], dxfattribs={"layer": layer})

    def text(x: float, y: float, value: str, size: float, layer: str = "MATN",
             align: str = "LEFT", angle: float = 0.0) -> None:  # fmt: skip
        # SVG font-size is the em size; AutoCAD text height is the capital height (~0.7 em).
        t = msp.add_text(value, height=round(size * 0.7, 3), rotation=angle,
                         dxfattribs={"layer": layer, "style": TEXT_STYLE})  # fmt: skip
        t.set_placement((x, y), align={"LEFT": None, "CENTER": "BOTTOM_CENTER"}.get(align))

    for c in s["shapes"]:
        t = c["type"]
        if t == "line":
            msp.add_line(flip(c["x1"], c["y1"]), flip(c["x2"], c["y2"]), dxfattribs=attrs(c))
        elif t == "arrow":
            a, b = flip(c["x1"], c["y1"]), flip(c["x2"], c["y2"])
            msp.add_line(a, b, dxfattribs=attrs(c))
            arrow_head(b, a, 3.0, attrs(c)["layer"])
        elif t in ("polyline", "polygon"):
            pts = [flip(x, y) for x, y in c["points"]]
            msp.add_lwpolyline(pts, close=t == "polygon", dxfattribs=attrs(c))
        elif t == "rect":
            x, y = flip(c["x"], c["y"] + c["height"])  # lower-left corner once y points up
            pts = _rounded_rect(x, y, c["width"], c["height"], c["r"])
            msp.add_lwpolyline(pts, format="xyb", close=True, dxfattribs=attrs(c))
        elif t == "circle":
            msp.add_circle(flip(c["cx"], c["cy"]), c["r"], dxfattribs=attrs(c))
        elif t == "ellipse":
            rx, ry = c["rx"], c["ry"]
            major = (rx, 0, 0) if rx >= ry else (0, ry, 0)
            ratio = min(rx, ry) / max(rx, ry)
            msp.add_ellipse(flip(c["cx"], c["cy"]), major_axis=major, ratio=ratio,
                            dxfattribs=attrs(c))  # fmt: skip
        elif t == "arc":
            # SVG angles turn clockwise on screen (y down); DXF counter-clockwise (y up).
            msp.add_arc(flip(c["cx"], c["cy"]), c["r"], (-c["end"]) % 360, (-c["start"]) % 360,
                        dxfattribs=attrs(c))  # fmt: skip
        elif t == "text":
            text(*flip(c["x"], c["y"]), c["text"], c["size"])
        elif t == "dim":
            p1, p2 = flip(c["x1"], c["y1"]), flip(c["x2"], c["y2"])
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) == 0:
                continue
            # The spec's offset is to the left of p1->p2 on screen (y down) = to the right once
            # y points up, and ezdxf measures "distance" to the left: hence the minus.
            distance = -c["offset"]
            ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
            if not -90 < ang <= 90:  # measure left-to-right / bottom-up so the text is readable
                p1, p2, distance = p2, p1, -distance
            dim = msp.add_aligned_dim(p1=p1, p2=p2, distance=distance, dimstyle=DIM_STYLE,
                                      text=c["label"] or "<>",
                                      dxfattribs={"layer": "OLCHAM"})  # fmt: skip
            dim.render()

    if frame:
        # The sheet as on the PDF: the frame around the drawing and the title block, bottom right.
        x0, x1 = -MARGIN / 2, s["width"] + MARGIN / 2
        y_top, y_bot = MARGIN / 2, -(MARGIN / 2 + TITLE_H)  # relative to the drawing, y up
        msp.add_lwpolyline([(x0, hgt + y_top), (x1, hgt + y_top), (x1, y_bot), (x0, y_bot)],
                           close=True, dxfattribs={"layer": "RAMKA"})  # fmt: skip
        bx = s["width"] - 90
        by_top, by_bot = -MARGIN / 2, -(MARGIN / 2 + TITLE_H)
        msp.add_lwpolyline([(bx, by_top), (bx + 90, by_top), (bx + 90, by_bot), (bx, by_bot)],
                           close=True, dxfattribs={"layer": "RAMKA", "lineweight": 50})  # fmt: skip
        text(bx + 3, by_top - 6.5, s["title"], 4.5)
        import time

        info = f"Masshtab {s['scale']} · {time.strftime('%d.%m.%Y')} · NEXVARA"
        text(bx + 3, by_bot + 3, info, 3.0)
        for i, n in enumerate(s["notes"][:2]):
            text(x0 + MARGIN / 2 + 2, by_top - 4 - 4 * (i + 1), n, 2.8)
    doc.set_modelspace_vport(height=max(s["height"], s["width"] * 0.6) + 40,
                             center=(s["width"] / 2, s["height"] / 2 - TITLE_H / 2))  # fmt: skip
    doc.header["$EXTMIN"] = (-MARGIN, -(MARGIN + TITLE_H), 0)
    doc.header["$EXTMAX"] = (s["width"] + MARGIN, hgt + MARGIN, 0)
    return doc


def to_string(doc: Any) -> str:
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue()


def audit(doc: Any) -> list[str]:
    """Problems AutoCAD would complain about (empty list = a clean file)."""
    auditor = doc.audit()
    return [str(e.message) for e in auditor.errors]


# ---------------- any DXF (or DWG via ODA) -> PDF / PNG ----------------
MAX_DXF_BYTES = 60 * 1024 * 1024


def read(path: Path) -> Any:
    """Open a DXF tolerantly (files from other CAD programs are often slightly broken)."""
    from nexvara.core.task import UserError

    path = Path(path)
    if not path.is_file():
        raise UserError(f"Fayl topilmadi: {path}")
    if path.stat().st_size > MAX_DXF_BYTES:
        raise UserError("DXF fayl juda katta (60 MB gacha)")
    if path.suffix.lower() == ".dwg":
        raise UserError(
            "DWG — AutoCAD’ning yopiq formati. AutoCAD’da «Save As → DXF» qilib yuboring, "
            "NEXVARA DXF’ni o‘qiydi va PDF/PNG qiladi."
        )
    from ezdxf import recover
    from ezdxf.lldxf.const import DXFStructureError

    try:
        doc, _auditor = recover.readfile(str(path))
    except (OSError, DXFStructureError) as e:
        raise UserError(f"DXF faylni o‘qib bo‘lmadi: {e}") from e
    return doc


def summary(doc: Any) -> dict[str, Any]:
    """What is inside: entity counts by type, layers, size of the drawing (in drawing units)."""
    from collections import Counter

    from ezdxf import bbox

    msp = doc.modelspace()
    kinds = Counter(e.dxftype() for e in msp)
    box = bbox.extents(msp, fast=True)
    size = (round(box.size.x, 2), round(box.size.y, 2)) if box.has_data else (0.0, 0.0)
    units = {0: "", 1: "dyuym", 4: "mm", 5: "sm", 6: "m"}.get(int(doc.units), "")
    return {"entities": sum(kinds.values()), "types": dict(kinds.most_common()),
            "layers": [ly.dxf.name for ly in doc.layers], "size": size,
            "units": units}  # fmt: skip


def render(doc: Any, pdf: Path | None = None, png: Path | None = None,
           dpi: int = 150) -> dict[str, str]:  # fmt: skip
    """Model space -> PDF (vector) and PNG on white paper, black lines, real line weights."""
    from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, pymupdf

    backend = pymupdf.PyMuPdfBackend()
    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.BLACK,
        lineweight_policy=config.LineweightPolicy.ABSOLUTE,
    )
    Frontend(RenderContext(doc), backend, config=cfg).draw_layout(doc.modelspace(), finalize=True)
    page = layout.Page(0, 0, layout.Units.mm, margins=layout.Margins.all(5))
    out: dict[str, str] = {}
    if pdf is not None:
        pdf.write_bytes(backend.get_pdf_bytes(page))
        out["pdf"] = str(pdf)
    if png is not None:
        png.write_bytes(backend.get_pixmap_bytes(page, fmt="png", dpi=dpi))
        out["png"] = str(png)
    return out
