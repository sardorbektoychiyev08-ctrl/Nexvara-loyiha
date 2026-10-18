"""AutoCAD DXF output, DXF -> PDF/PNG, and simple parts drawn exactly without AI."""

from __future__ import annotations

import math

import pytest

from nexvara import cad, drawing, drawing_offline

SPEC = {
    "title": "Plastina Ø30 — o‘zbekcha ғ",
    "width": 120,
    "height": 80,
    "notes": ["Material: po‘lat"],
    "shapes": [
        {"type": "rect", "x": 10, "y": 10, "width": 100, "height": 60, "w": 0.7, "r": 6},
        {"type": "circle", "cx": 60, "cy": 40, "r": 15},
        {"type": "line", "x1": 60, "y1": 5, "x2": 60, "y2": 75, "style": "center"},
        {"type": "line", "x1": 20, "y1": 20, "x2": 100, "y2": 20, "style": "hidden"},
        {"type": "dim", "x1": 10, "y1": 70, "x2": 110, "y2": 70, "offset": 8},
        {"type": "dim", "x1": 110, "y1": 10, "x2": 110, "y2": 70, "offset": -8, "label": "60"},
        {"type": "arc", "cx": 60, "cy": 40, "r": 20, "start": 0, "end": 90},
        {"type": "ellipse", "cx": 30, "cy": 40, "rx": 8, "ry": 4},
        {"type": "arrow", "x1": 80, "y1": 30, "x2": 95, "y2": 20},
        {"type": "text", "x": 12, "y": 8, "text": "Teshik\n0\nEOF", "size": 4},
    ],
}


def test_dxf_is_a_clean_autocad_2010_file_in_mm(tmp_path):
    doc = cad.build(SPEC)
    assert cad.audit(doc) == []
    assert doc.dxfversion == "AC1024" and doc.header["$INSUNITS"] == 4
    p = tmp_path / "a.dxf"
    p.write_text(drawing.to_dxf(SPEC), encoding="utf-8")
    back = cad.read(p)
    info = cad.summary(back)
    assert info["units"] == "mm"
    assert {"KONTUR", "YASHIRIN", "OQ_CHIZIQ", "OLCHAM", "MATN", "RAMKA"} <= set(info["layers"])
    t = info["types"]
    assert t["DIMENSION"] == 2 and t["CIRCLE"] == 1 and t["ARC"] == 1 and t["ELLIPSE"] == 1
    msp = back.modelspace()
    layer_of = {e.dxftype() + ":" + e.dxf.layer for e in msp}
    assert "LINE:OQ_CHIZIQ" in layer_of and "LINE:YASHIRIN" in layer_of
    assert back.layers.get("YASHIRIN").dxf.linetype == "NX_SHTRIX"
    texts = [e.dxf.text for e in msp.query("TEXT")]
    assert SPEC["title"] in texts  # Unicode survives (R12 used to turn it into "?")
    assert "Teshik0EOF" in texts  # a line break cannot inject DXF group codes
    # The rounded rectangle is one closed polyline with quarter-circle bulges.
    rect = next(e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "KONTUR")
    assert rect.closed and sum(1 for *_xy, b in rect.get_points("xyb") if b) == 4


def test_dimensions_measure_real_size_and_read_upright():
    msp = cad.build(SPEC).modelspace()
    dims = list(msp.query("DIMENSION"))
    assert sorted(round(d.get_measurement(), 3) for d in dims) == [60.0, 100.0]
    for d in dims:
        p2, p3 = d.dxf.defpoint2, d.dxf.defpoint3
        ang = math.degrees(math.atan2(p3.y - p2.y, p3.x - p2.x))
        assert -90 < ang <= 90  # left-to-right or bottom-up: never upside down
    horizontal = next(d for d in dims if round(d.get_measurement()) == 100)
    assert horizontal.dxf.defpoint.y == pytest.approx(2.0)  # below the part, as on the PDF
    vertical = next(d for d in dims if round(d.get_measurement()) == 60)
    assert vertical.dxf.defpoint.x == pytest.approx(118.0)  # right of the part


def test_any_dxf_becomes_pdf_and_png(tmp_path):
    p = tmp_path / "chizma.dxf"
    p.write_text(drawing.to_dxf(SPEC), encoding="utf-8")
    out = cad.render(cad.read(p), tmp_path / "c.pdf", tmp_path / "c.png")
    assert open(out["pdf"], "rb").read(5) == b"%PDF-"
    assert open(out["png"], "rb").read(4) == b"\x89PNG"
    broken = tmp_path / "buzuq.dxf"
    broken.write_text("bu dxf emas", encoding="utf-8")
    from nexvara.core.task import UserError

    with pytest.raises(UserError):
        cad.read(broken)
    with pytest.raises(UserError, match="DWG"):
        (tmp_path / "x.dwg").write_bytes(b"AC1032")
        cad.read(tmp_path / "x.dwg")


# ---------------- simple parts without AI ----------------
@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("100x60 plastina, markazida 20 mm teshik chizib ber",
         {"shape": "rect", "w": 100, "h": 60, "center_hole": 20}),
        ("120 ga 80 to‘rtburchak plastina burchaklarida 4 ta 10 mm teshik, burchaklari R8 "
         "yumaloq chiz", {"shape": "rect", "w": 120, "h": 80, "corner_holes": 10, "corner_r": 8}),
        ("kvadrat 50 mm chiz", {"shape": "rect", "w": 50, "h": 50}),
        ("2 m ga 1,2 m taxta chizmasini chiz", {"shape": "rect", "w": 2000, "h": 1200}),
        ("Diametri 50 mm doira chiz", {"shape": "circle", "d": 50}),
        ("radiusi 3 sm aylana chizib ber", {"shape": "circle", "d": 60}),
        ("Shayba chiz: tashqi diametri 40, ichki diametri 21",
         {"shape": "ring", "d": 40, "d_in": 21}),
        ("Uchburchak chiz tomonlari 30, 40 va 50", {"shape": "triangle", "sides": [30, 40, 50]}),
        ("teng tomonli uchburchak tomoni 60 chiz", {"shape": "triangle", "sides": [60, 60, 60]}),
        ("olti burchakli detal kalit o‘lchami 24 chiz", {"shape": "polygon", "n": 6}),
        ("ellips 80x40 chiz", {"shape": "ellipse", "rx": 40, "ry": 20}),
    ],
)  # fmt: skip
def test_simple_parts_are_understood(text, want):
    p = drawing_offline.parse(text)
    assert p is not None
    for k, v in want.items():
        assert p[k] == pytest.approx(v) if isinstance(v, int | float) else p[k] == v
    spec = drawing_offline.build_spec(p)
    assert cad.audit(cad.build(spec)) == []
    labels = {s["label"] for s in spec["shapes"] if s["type"] == "dim"}
    assert labels  # every part is dimensioned with its real size


def test_hexagon_across_flats_and_big_parts_are_scaled():
    p = drawing_offline.parse("M12 gayka chizmasi kalit 19")
    assert p["title"] == "Gayka" and 2 * p["r"] * math.cos(math.pi / 6) == pytest.approx(19)
    big = drawing_offline.build_spec(drawing_offline.parse("2 m ga 1,2 m taxta chiz"))
    assert big["scale"] == "1:10" and {"2000", "1200"} <= {
        s["label"] for s in big["shapes"] if s["type"] == "dim"
    }  # drawn smaller, labelled with the real size


def test_impossible_or_unknown_parts():
    with pytest.raises(ValueError, match="uchburchak"):
        drawing_offline.parse("uchburchak tomonlari 1, 2, 10 chiz")
    with pytest.raises(ValueError, match="sig‘maydi"):
        drawing_offline.build_spec(drawing_offline.parse("20x20 plastina, burchaklarida 4 ta "
                                                         "15 mm teshik"))  # fmt: skip
    for text in ("Velosiped g‘ildiragi chizmasini chizib ber", "Uy chizmasini chizib ber",
                 "Gayka chizmasini chizib ber"):  # fmt: skip
        assert drawing_offline.parse(text) is None  # these go to the AI


def test_edit_changes_only_what_is_said():
    base = drawing_offline.parse("100x60 plastina, markazida 20 mm teshik chiz")
    p = drawing_offline.parse("oxirgi chizmani o‘zgartir: teshik 10 mm bo‘lsin", base)
    assert (p["w"], p["h"], p["center_hole"]) == (100, 60, 10)
    p = drawing_offline.parse("oxirgi chizmani o‘zgartir: eni 150 bo‘lsin", base)
    assert (p["w"], p["h"], p["center_hole"]) == (150, 60, 20)


# ---------------- in chat ----------------
def _api(tmp_path):
    from nexvara.app.api import Api

    return Api(output_dir=tmp_path / "out")


def _done(api, out):
    t = api._runner.get(out["task"]["id"])
    assert t.wait(30) and t.status == "succeeded", t.error
    return t


def test_chat_draws_a_simple_part_without_ai_and_edits_it(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    api = _api(tmp_path)
    out = api.chat("100x60 plastina, markazida 20 mm teshik chizib ber")
    assert "AI’siz" in out["reply"] and not out.get("confirm")
    t = _done(api, out)
    res = t.result
    for k in ("png", "pdf", "dxf"):
        assert res["path" if k == "png" else k]
    assert cad.audit(cad.read(res["dxf"])) == []
    circles = [s for s in api._last_drawing["shapes"] if s["type"] == "circle"]
    assert circles[0]["r"] == pytest.approx(10)
    out = api.chat("Oxirgi chizmani o‘zgartir: teshik 10 mm bo‘lsin")
    _done(api, out)
    circles = [s for s in api._last_drawing["shapes"] if s["type"] == "circle"]
    assert circles[0]["r"] == pytest.approx(5)
    out = api.chat("Oxirgi chizmani o‘zgartir: chiroyliroq qil")
    assert "tushunmadim" in out["reply"] and "task" not in out
    out = api.chat("uchburchak chiz, tomonlari 1, 2 va 10")
    assert "Chizib bo‘lmaydi" in out["reply"]


def test_chat_turns_a_dxf_into_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    p = tmp_path / "Loyiha chizma.dxf"
    p.write_text(drawing.to_dxf(SPEC), encoding="utf-8")
    api = _api(tmp_path)
    out = api.chat(f"«{p}» ni PDF qil")
    t = _done(api, out)
    assert t.result["pdf"].endswith(".pdf") and open(t.result["pdf"], "rb").read(4) == b"%PDF"
    api.set_context_file(str(p))
    t = _done(api, api.chat("shu DXF faylni ko‘rsat"))
    assert "obyekt" in t.result["report"][0]
    (tmp_path / "eski.dwg").write_bytes(b"AC1032")
    api.set_context_file(str(tmp_path / "eski.dwg"))
    assert "DXF" in api.chat("shu dwg faylni PDF qil")["reply"]
