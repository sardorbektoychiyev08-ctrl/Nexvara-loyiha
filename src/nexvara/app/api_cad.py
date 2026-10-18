"""The «Chizmalar» page (mixed into app.api.Api): NEXVARA's own CAD editor, so nobody needs
AutoCAD installed. The page (app/ui/cad.js) edits a plain JSON drawing; this side opens and
saves real DXF files (AutoCAD 2010, mm) through nexvara/cad.py and exports PDF/PNG.

JSON drawing: {"layers": [{name, color (ACI), lineweight (1/100 mm), linetype, visible}],
"entities": [{type, layer, ...}], "units": "mm"} with model coordinates (y up, as in DXF):
  line: x1 y1 x2 y2 · polyline: points [[x, y, bulge]...], closed · circle: cx cy r ·
  arc: cx cy r start end (degrees, counter-clockwise) · ellipse: cx cy rx ry rot ·
  text: x y text h rot · dim: x1 y1 x2 y2 offset label
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

MAX_ENTITIES = 60000
KINDS = {"line", "polyline", "circle", "arc", "ellipse", "text", "dim", "ldim", "rdim", "hatch"}
LINETYPES = {"Continuous", "NX_SHTRIX", "NX_OQ"}


def _f(v: Any, lo: float = -1e7, hi: float = 1e7) -> float:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        raise ValueError("raqam kutilgan")
    if not lo <= float(v) <= hi:
        raise ValueError(f"qiymat chegaradan tashqarida: {v}")
    return float(v)


def _txt(v: Any, limit: int = 500) -> str:
    return "".join(c for c in str(v or "") if c.isprintable())[:limit]


# ---------------- DXF -> JSON ----------------
def doc_to_json(doc: Any) -> dict[str, Any]:
    """Model space as editable JSON. Blocks are exploded, splines become polylines; anything
    else (hatches, images, 3D) is counted in "skipped" and left out."""
    from collections import Counter

    layers = [{"name": ly.dxf.name, "color": abs(int(ly.dxf.color or 7)) or 7,
               "lineweight": int(ly.dxf.lineweight) if int(ly.dxf.lineweight) > 0 else 25,
               "linetype": str(ly.dxf.linetype or "Continuous"), "visible": ly.is_on(),
               "locked": ly.is_locked()}
              for ly in doc.layers]  # fmt: skip
    out: list[dict[str, Any]] = []
    skipped: Counter = Counter()

    def add(e: Any, depth: int = 0) -> None:
        if len(out) >= MAX_ENTITIES:
            skipped["juda ko‘p"] += 1
            return
        t = e.dxftype()
        layer = str(e.dxf.get("layer", "0"))
        try:
            if t == "LINE":
                s, en = e.dxf.start, e.dxf.end
                out.append({"type": "line", "layer": layer, "x1": s.x, "y1": s.y, "x2": en.x,
                            "y2": en.y})  # fmt: skip
            elif t == "LWPOLYLINE":
                pts = [[p[0], p[1], p[4]] for p in e.get_points("xyseb")]
                out.append({"type": "polyline", "layer": layer, "points": pts,
                            "closed": bool(e.closed)})  # fmt: skip
            elif t == "POLYLINE" and e.is_2d_polyline:
                pts = [[v.dxf.location.x, v.dxf.location.y, v.dxf.get("bulge", 0)]
                       for v in e.vertices]  # fmt: skip
                out.append({"type": "polyline", "layer": layer, "points": pts,
                            "closed": bool(e.is_closed)})  # fmt: skip
            elif t == "CIRCLE":
                c = e.dxf.center
                out.append({"type": "circle", "layer": layer, "cx": c.x, "cy": c.y,
                            "r": e.dxf.radius})  # fmt: skip
            elif t == "ARC":
                c = e.dxf.center
                out.append({"type": "arc", "layer": layer, "cx": c.x, "cy": c.y,
                            "r": e.dxf.radius, "start": e.dxf.start_angle,
                            "end": e.dxf.end_angle})  # fmt: skip
            elif t == "ELLIPSE":
                c, major = e.dxf.center, e.dxf.major_axis
                rx = math.hypot(major.x, major.y)
                full = abs((e.dxf.end_param - e.dxf.start_param) % (2 * math.pi)) < 1e-6
                if full:
                    out.append({"type": "ellipse", "layer": layer, "cx": c.x, "cy": c.y,
                                "rx": rx, "ry": rx * e.dxf.ratio,
                                "rot": math.degrees(math.atan2(major.y, major.x))})  # fmt: skip
                else:
                    pts = [[p.x, p.y, 0] for p in e.flattening(0.05)]
                    out.append({"type": "polyline", "layer": layer, "points": pts,
                                "closed": False})  # fmt: skip
            elif t in ("TEXT", "MTEXT"):
                p = e.dxf.insert
                text = e.plain_text() if t == "MTEXT" else e.dxf.text
                h = e.dxf.char_height if t == "MTEXT" else e.dxf.height
                rot = e.dxf.get("rotation", 0)
                out.append({"type": "text", "layer": layer, "x": p.x, "y": p.y,
                            "text": _txt(text), "h": h or 2.5, "rot": rot})  # fmt: skip
            elif t == "DIMENSION":
                out.extend(_dimension(e, layer))
            elif t == "HATCH":
                from ezdxf import path as ezpath

                rings = [[[v.x, v.y] for v in pth.flattening(0.05)]
                         for pth in ezpath.from_hatch(e)]  # fmt: skip
                rings = [r[:-1] if r[0] == r[-1] else r for r in rings]
                rings = [r for r in rings if len(r) >= 3]
                if rings:
                    solid = bool(e.dxf.solid_fill)
                    out.append({"type": "hatch", "layer": layer, "paths": rings,
                                "pattern": "SOLID" if solid else "ANSI31",
                                "scale": float(e.dxf.get("pattern_scale", 1) or 1)})  # fmt: skip
            elif t == "SPLINE":
                pts = [[p.x, p.y, 0] for p in e.flattening(0.05)]
                out.append({"type": "polyline", "layer": layer, "points": pts,
                            "closed": bool(e.closed)})  # fmt: skip
            elif t == "SOLID" or t == "TRACE":
                pts = [[v.x, v.y, 0] for v in e.vertices()]
                out.append({"type": "polyline", "layer": layer, "points": pts, "closed": True})
            elif t == "INSERT" and depth < 6:
                for sub in e.virtual_entities():
                    if not sub.dxf.hasattr("layer") or sub.dxf.layer == "0":
                        sub.dxf.layer = layer
                    add(sub, depth + 1)
            elif t == "POINT":
                p = e.dxf.location
                out.append({"type": "circle", "layer": layer, "cx": p.x, "cy": p.y, "r": 0.2})
            else:
                skipped[t] += 1
        except Exception:  # one odd entity from another program must not stop the file
            skipped[t] += 1

    for e in doc.modelspace():
        n = len(out)
        add(e)
        color = int(e.dxf.get("color", 256)) if e.dxf.hasattr("color") else 256
        if 1 <= color <= 255:  # an own colour instead of the layer's ("ByLayer" = 256)
            for item in out[n:]:
                item.setdefault("color", color)
    return {"units": "mm", "layers": layers, "entities": out, "skipped": dict(skipped)}


def _dimension(e: Any, layer: str) -> list[dict[str, Any]]:
    """AutoCAD dimensions -> the editor's dim (aligned), ldim (linear, rotated), rdim."""
    kind = int(e.dxf.dimtype) & 0x0F
    label = e.dxf.get("text", "")
    label = "" if label in ("", "<>", " ") else _txt(label, 40)
    base = e.dxf.defpoint
    if kind in (0, 1):
        d1, d2 = e.dxf.defpoint2, e.dxf.defpoint3
        if math.hypot(d2.x - d1.x, d2.y - d1.y) == 0:
            return []
        along = math.atan2(d2.y - d1.y, d2.x - d1.x)
        rot = math.radians(float(e.dxf.get("angle", 0)))
        if kind == 0 and abs(math.sin(along - rot)) > 1e-6:  # linear along "angle" (0/90…)
            return [{"type": "ldim", "layer": layer, "x1": d1.x, "y1": d1.y, "x2": d2.x,
                     "y2": d2.y, "bx": base.x, "by": base.y,
                     "rot": float(e.dxf.get("angle", 0)), "label": label}]  # fmt: skip
        length = math.hypot(d2.x - d1.x, d2.y - d1.y)
        nx, ny = -(d2.y - d1.y) / length, (d2.x - d1.x) / length
        off = (base.x - d2.x) * nx + (base.y - d2.y) * ny
        return [{"type": "dim", "layer": layer, "x1": d1.x, "y1": d1.y, "x2": d2.x,
                 "y2": d2.y, "offset": off, "label": label}]  # fmt: skip
    if kind in (3, 4):  # diameter: defpoint & defpoint4 on the circle; radius: centre & point
        p4 = e.dxf.defpoint4
        if kind == 3:
            cx, cy = (base.x + p4.x) / 2, (base.y + p4.y) / 2
        else:
            cx, cy = base.x, base.y
        r = math.hypot(p4.x - cx, p4.y - cy)
        if r == 0:
            return []
        ang = math.degrees(math.atan2(p4.y - cy, p4.x - cx))
        return [{"type": "rdim", "layer": layer, "cx": cx, "cy": cy, "r": r, "angle": ang,
                 "diameter": kind == 3, "label": label}]  # fmt: skip
    return []


# ---------------- JSON -> DXF ----------------
def json_to_doc(data: dict[str, Any]) -> Any:
    """A clean AutoCAD 2010 DXF (mm) from the editor's JSON; every value is validated."""
    from nexvara import cad

    if not isinstance(data, dict):
        raise ValueError("chizma noto‘g‘ri")
    ents = data.get("entities") or []
    if not isinstance(ents, list) or len(ents) > MAX_ENTITIES:
        raise ValueError("obyektlar ro‘yxati noto‘g‘ri yoki juda katta")
    doc = cad.new_document()
    for ly in data.get("layers") or []:
        name = _txt(ly.get("name"), 60).strip() or "0"
        if any(ch in name for ch in '<>/\\":;?*|=`'):
            raise ValueError(f"qatlam nomida taqiqlangan belgi: {name}")
        color = int(_f(ly.get("color", 7), 1, 255))
        lw = int(_f(ly.get("lineweight", 25), 0, 211))
        lt = str(ly.get("linetype") or "Continuous")
        lt = lt if lt in doc.linetypes else "Continuous"
        if name in doc.layers:
            layer = doc.layers.get(name)
            layer.color, layer.dxf.lineweight, layer.dxf.linetype = color, lw, lt
        else:
            layer = doc.layers.add(name, color=color, lineweight=lw, linetype=lt)
        if ly.get("visible") is False:
            layer.off()
        if ly.get("locked"):
            layer.lock()
    msp = doc.modelspace()
    for i, e in enumerate(ents, 1):
        if not isinstance(e, dict) or e.get("type") not in KINDS:
            raise ValueError(f"{i}-obyekt turi noma’lum")
        layer = _txt(e.get("layer"), 60) or "0"
        if layer not in doc.layers:
            doc.layers.add(layer)
        a: dict[str, Any] = {"layer": layer}
        if e.get("color") not in (None, "", 256):
            a["color"] = int(_f(e["color"], 1, 255))
        if e.get("linetype") in LINETYPES:
            a["linetype"] = e["linetype"]
        t = e["type"]
        try:
            if t == "line":
                msp.add_line((_f(e["x1"]), _f(e["y1"])), (_f(e["x2"]), _f(e["y2"])), dxfattribs=a)
            elif t == "polyline":
                pts = e.get("points") or []
                if not isinstance(pts, list) or not 2 <= len(pts) <= 100000:
                    raise ValueError("nuqtalar soni noto‘g‘ri")
                clean = [(_f(p[0]), _f(p[1]), _f(p[2] if len(p) > 2 else 0, -1e3, 1e3))
                         for p in pts]  # fmt: skip
                msp.add_lwpolyline(clean, format="xyb", close=bool(e.get("closed")),
                                   dxfattribs=a)  # fmt: skip
            elif t == "circle":
                msp.add_circle((_f(e["cx"]), _f(e["cy"])), _f(e["r"], 1e-6), dxfattribs=a)
            elif t == "arc":
                msp.add_arc((_f(e["cx"]), _f(e["cy"])), _f(e["r"], 1e-6),
                            _f(e["start"], -1e4, 1e4) % 360, _f(e["end"], -1e4, 1e4) % 360,
                            dxfattribs=a)  # fmt: skip
            elif t == "ellipse":
                rx, ry = _f(e["rx"], 1e-6), _f(e["ry"], 1e-6)
                rot = math.radians(_f(e.get("rot", 0), -1e4, 1e4))
                major, ratio = (rx, ry / rx) if rx >= ry else (ry, rx / ry)
                if ry > rx:
                    rot += math.pi / 2
                msp.add_ellipse((_f(e["cx"]), _f(e["cy"])),
                                major_axis=(major * math.cos(rot), major * math.sin(rot), 0),
                                ratio=ratio, dxfattribs=a)  # fmt: skip
            elif t == "text":
                txt = msp.add_text(_txt(e.get("text")), height=_f(e.get("h", 2.5), 0.01, 1e4),
                                   rotation=_f(e.get("rot", 0), -1e4, 1e4),
                                   dxfattribs={**a, "style": cad.TEXT_STYLE})  # fmt: skip
                txt.set_placement((_f(e["x"]), _f(e["y"])))
            elif t == "dim":
                p1, p2 = (_f(e["x1"]), _f(e["y1"])), (_f(e["x2"]), _f(e["y2"]))
                if math.dist(p1, p2) == 0:
                    continue
                label = _txt(e.get("label"), 40)
                dim = msp.add_aligned_dim(p1=p1, p2=p2, distance=_f(e.get("offset", 10)),
                                          dimstyle=cad.DIM_STYLE, text=label or "<>",
                                          dxfattribs=a)  # fmt: skip
                dim.render()
            elif t == "ldim":
                p1, p2 = (_f(e["x1"]), _f(e["y1"])), (_f(e["x2"]), _f(e["y2"]))
                label = _txt(e.get("label"), 40)
                dim = msp.add_linear_dim(base=(_f(e["bx"]), _f(e["by"])), p1=p1, p2=p2,
                                         angle=_f(e.get("rot", 0), -1e4, 1e4),
                                         dimstyle=cad.DIM_STYLE, text=label or "<>",
                                         dxfattribs=a)  # fmt: skip
                dim.render()
            elif t == "rdim":
                c, r = (_f(e["cx"]), _f(e["cy"])), _f(e["r"], 1e-6)
                ang = _f(e.get("angle", 45), -1e4, 1e4)
                label = _txt(e.get("label"), 40)
                make = msp.add_diameter_dim if e.get("diameter") else msp.add_radius_dim
                dim = make(center=c, radius=r, angle=ang, dimstyle=cad.DIM_STYLE,
                           text=label or "<>", dxfattribs=a)  # fmt: skip
                dim.render()
            elif t == "hatch":
                paths = e.get("paths") or []
                if not isinstance(paths, list) or not 1 <= len(paths) <= 200:
                    raise ValueError("shtrix chegarasi noto‘g‘ri")
                hatch = msp.add_hatch(dxfattribs=a)
                if (e.get("pattern") or "SOLID") == "SOLID":
                    hatch.set_solid_fill(color=a.get("color", 256))
                else:
                    hatch.set_pattern_fill(
                        "ANSI31", color=a.get("color", 256), scale=_f(e.get("scale", 1), 0.01, 1000)
                    )
                for ring in paths:
                    if not isinstance(ring, list) or not 2 <= len(ring) <= 100000:
                        raise ValueError("shtrix chegarasi noto‘g‘ri")
                    hatch.paths.add_polyline_path(
                        [(_f(q[0]), _f(q[1]), _f(q[2] if len(q) > 2 else 0, -1e3, 1e3))
                         for q in ring], is_closed=True)  # fmt: skip
        except (KeyError, TypeError, IndexError) as err:
            raise ValueError(f"{i}-obyekt ({t}) maydoni yetishmaydi: {err}") from err
    return doc


class CadApi:
    _overrides: dict

    def cad_open(self, path: str = "") -> dict[str, Any]:
        """Open a DXF (a file dialog when no path is given) as editable JSON."""
        from nexvara import cad
        from nexvara.core.task import UserError

        if not path:
            path = self._cad_dialog(save=False)
            if not path:
                return {"ok": False, "cancelled": True}
        try:
            data = doc_to_json(cad.read(Path(path)))
        except UserError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "path": str(path), "name": Path(path).name, "drawing": data}

    def cad_last_drawing(self) -> dict[str, Any]:
        """The newest DXF NEXVARA drew (chat "… chizib ber"), to continue it in the editor."""
        from nexvara import config

        folder = getattr(self, "_output_dir", None) or (config.data_dir() / "Chizmalar")
        files = sorted(Path(folder).glob("*.dxf"), key=lambda p: p.stat().st_mtime) if Path(
            folder).is_dir() else []  # fmt: skip
        if not files:
            return {"ok": False, "error": "Hali chizma yo‘q. Suhbatda «… chizib ber» deb yozing."}
        return self.cad_open(str(files[-1]))

    def cad_save(self, drawing: dict[str, Any], path: str = "") -> dict[str, Any]:
        """Save as DXF (a save dialog when no path is given); the file is re-read and audited."""
        from nexvara import cad
        from nexvara.agent.files import backup

        if not path:
            path = self._cad_dialog(save=True)
            if not path:
                return {"ok": False, "cancelled": True}
        target = Path(path)
        if target.suffix.lower() != ".dxf":
            target = target.with_suffix(".dxf")
        try:
            doc = json_to_doc(drawing)
        except ValueError as e:
            return {"ok": False, "error": f"Saqlab bo‘lmadi: {e}"}
        problems = cad.audit(doc)
        if problems:
            return {"ok": False, "error": "DXF tekshiruvdan o‘tmadi: " + "; ".join(problems[:3])}
        if target.is_file():
            backup(target)  # the previous version stays next to it
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".dxf.tmp")
        tmp.write_text(cad.to_string(doc), encoding="utf-8")
        tmp.replace(target)
        back = cad.summary(cad.read(target))
        return {"ok": True, "path": str(target), "name": target.name,
                "entities": back["entities"]}  # fmt: skip

    def cad_export(self, drawing: dict[str, Any], kind: str = "pdf",
                   path: str = "") -> dict[str, Any]:  # fmt: skip
        """PDF (vector, for printing) or PNG next to the drawing, or in Chizmalar."""
        import time

        from nexvara import cad, config

        if kind not in ("pdf", "png"):
            return {"ok": False, "error": "Faqat PDF yoki PNG"}
        try:
            doc = json_to_doc(drawing)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if not doc.modelspace().__len__():
            return {"ok": False, "error": "Chizma bo‘sh"}
        if path:
            out = Path(path).with_suffix("." + kind)
        else:
            folder = getattr(self, "_output_dir", None) or (config.data_dir() / "Chizmalar")
            Path(folder).mkdir(parents=True, exist_ok=True)
            out = Path(folder) / f"chizma_{time.strftime('%Y%m%d-%H%M%S')}.{kind}"
        cad.render(doc, out if kind == "pdf" else None, out if kind == "png" else None)
        opener = self._overrides.get("open_file")
        if opener:
            opener(str(out))
        return {"ok": True, "path": str(out), "name": out.name}

    def cad_ai_fix(self, drawing: dict[str, Any], note: str = "",
                   approved: bool = False) -> dict[str, Any]:  # fmt: skip
        """«AI bilan tuzatish»: the clean drawing the user meant. Without AI: an exact tidy-up."""
        from nexvara import cad_ai
        from nexvara.core.task import UserError

        if not isinstance(drawing, dict) or not drawing.get("entities"):
            return {"ok": False, "error": "Chizma bo‘sh — avval biror narsa chizing"}
        if not self._ai_ready():
            fixed, n = cad_ai.beautify(drawing)
            return {"ok": True, "drawing": fixed, "by": "offline", "fixes": n,
                    "reply": f"AI ulanmagan, shuning uchun o‘zim tekisladim: {n} ta tuzatish "
                    "(burchaklar, uchlar, o‘lchamlar). AI’ni ulasangiz (Sozlamalar → AI), "
                    "chizmangizni to‘liq qayta chizib beradi."}  # fmt: skip
        from nexvara.ai.router import NeedsConfirmation

        system, msgs = cad_ai.ai_messages(drawing, note)
        try:
            reply = self._router().complete("drawing", system, msgs, max_tokens=8000,
                                            expected_out=3000, approved=approved)  # fmt: skip
        except NeedsConfirmation as e:
            return {"ok": False, "confirm": e.estimate.describe()}
        except UserError as e:  # no money left, free limit reached, blocked privacy check...
            fixed, n = cad_ai.beautify(drawing)
            return {
                "ok": True,
                "drawing": fixed,
                "by": "offline",
                "fixes": n,
                "reply": f"AI ishlamadi ({e}). O‘zim tekisladim: {n} ta tuzatish.",
            }
        try:
            fixed = cad_ai.parse_reply(reply.text, drawing.get("layers"))
        except ValueError as e:
            return {"ok": False, "error": f"AI javobi chizma emas edi ({e}). Qayta urinib ko‘ring."}
        price = "bepul" if not reply.cost else f"≈${reply.cost:.3f}"
        return {
            "ok": True,
            "drawing": fixed,
            "by": "ai",
            "cost": reply.cost,
            "reply": f"AI chizmani qayta chizdi: {len(fixed['entities'])} ta obyekt ({price}).",
        }

    def _cad_dialog(self, save: bool) -> str:
        import webview

        if "cad_dialog" in self._overrides:
            return self._overrides["cad_dialog"](save)
        if not webview.windows:
            return ""
        kind = webview.SAVE_DIALOG if save else webview.OPEN_DIALOG
        chosen = webview.windows[0].create_file_dialog(
            kind, save_filename="chizma.dxf" if save else "",
            file_types=("AutoCAD chizma (*.dxf)", "Barcha fayllar (*.*)"),
        )  # fmt: skip
        if not chosen:
            return ""
        return str(chosen[0] if isinstance(chosen, list | tuple) else chosen)
