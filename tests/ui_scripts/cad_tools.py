"""Chizmalar in a real window: the professional tools (trim, extend, fillet, chamfer, offset,
hatch, dimensions, array, scale, rotate, explode, layers), a clean AutoCAD DXF, PDF and Word."""

import json
import math
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-cad-tools-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")

import webview

from nexvara import cad
from nexvara.app.api import Api
from nexvara.app.main import UI_DIR

target = tmp / "asboblar.dxf"
api = Api(output_dir=tmp, overrides={"cad_dialog": lambda _save: str(target)})
win = webview.create_window(
    "NEXVARA Chizma asboblari", url=str(UI_DIR / "index.html"), js_api=api, width=1500, height=900
)
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {}


def until(js, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = win.evaluate_js(js)
        if value:
            return value
        time.sleep(0.2)
    return None


def run():
    try:
        ready.wait(90)
        js = win.evaluate_js
        until(
            "window.cad && document.getElementById('version').textContent.startsWith('NEXVARA v')",
            90,
        )
        js("document.querySelector('.nav-item[data-page=cad]').click()")
        until("document.getElementById('page-cad').classList.contains('active')")

        def ex(*cmds):
            for c in cmds:
                js(f"cad.exec({json.dumps(c)})")

        def doc():
            return json.loads(js("JSON.stringify(cad.doc.entities)"))

        # 1) two crossing lines, trim the right half of the horizontal one
        ex("L", "0,0", "100,0", "")
        ex("L", "50,-20", "50,20", "")
        ex("TR")
        js("cad.pick(80, 0)")
        lines = [e for e in doc() if e["type"] == "line"]
        res["trim"] = sorted((e["x1"], e["x2"]) for e in lines if e["y1"] == e["y2"] == 0)
        js("cad.setTool('select')")

        # 2) extend: a short line up to a vertical wall
        ex("L", "0,40", "30,40", "")
        ex("L", "80,30", "80,60", "")
        ex("EX")
        js("cad.pick(29, 40)")
        res["extend"] = [e["x2"] for e in doc() if e["type"] == "line" and e["y1"] == e["y2"] == 40]
        js("cad.setTool('select')")

        # 3) fillet R5 between two lines meeting at a corner
        ex("L", "200,0", "260,0", "")
        ex("L", "200,0", "200,60", "")
        ex("F", "R 5")
        js("cad.pick(240, 0)")
        js("cad.pick(200, 40)")
        arcs = [e for e in doc() if e["type"] == "arc"]
        res["fillet"] = (
            [round(arcs[-1]["r"], 3), round(arcs[-1]["cx"], 3), round(arcs[-1]["cy"], 3)]
            if arcs
            else None
        )
        js("cad.setTool('select')")

        # 4) chamfer 4 mm
        ex("L", "300,0", "360,0", "")
        ex("L", "300,0", "300,60", "")
        ex("CHA", "D 4")
        js("cad.pick(340, 0)")
        js("cad.pick(300, 40)")
        res["chamfer"] = any(
            e["type"] == "line"
            and abs(math.hypot(e["x2"] - e["x1"], e["y2"] - e["y1"]) - 4 * math.sqrt(2)) < 1e-3
            for e in doc()
        )
        js("cad.setTool('select')")

        # 5) circle + hatch inside a rectangle (the circle becomes a hole)
        ex("REC", "0,100", "@80,50", "C", "40,125", "10")
        js("cad.setTool('hatch')")
        js("cad.pick(5, 105)")
        hatch = [e for e in doc() if e["type"] == "hatch"]
        res["hatch_paths"] = len(hatch[0]["paths"]) if hatch else 0
        js("cad.setTool('select')")

        # 6) dimensions: linear (horizontal), radius
        ex("DIM", "0,100", "80,100", "40,90")
        ex("DRA")
        js("cad.pick(50, 125)")
        res["dims"] = sorted(e["type"] for e in doc() if e["type"] in ("ldim", "rdim", "dim"))
        js("cad.setTool('select')")

        # 7) offset a line 10 mm upwards
        n = len(doc())
        ex("L", "0,200", "100,200", "", "O", "10")
        js("cad.pick(50, 200)")
        js("cad.pick(50, 230)")
        res["offset"] = [e["y1"] for e in doc()[n:] if e["type"] == "line"]
        js("cad.setTool('select')")

        # 8) select the last line, array 2 x 3, then scale and rotate a copy
        last = len(doc()) - 1
        js(f"cad.select([{last}])")
        ex("AR", "2", "3", "15", "120")
        res["array_added"] = len(doc()) - last - 1
        # 9) explode a rectangle into 4 lines
        rect = next(i for i, e in enumerate(doc()) if e["type"] == "polyline")
        js(f"cad.select([{rect}])")
        before = len(doc())
        ex("X")
        res["explode"] = len(doc()) - before  # -1 polyline +4 lines = 3
        # 10) undo everything back once and redo
        js("document.querySelector('[data-cad=undo]').click()")
        js("document.querySelector('[data-cad=redo]').click()")
        res["count"] = len(doc())
        # 10b) a template: an M10x50 bolt from the list
        until("document.querySelectorAll('#cad-template option').length > 3")
        before_tpl = len(doc())
        js("window.prompt = () => 'M10x50'")
        js(
            "const s = document.getElementById('cad-template'); s.value = 'bolt'; "
            "s.dispatchEvent(new Event('change'))"
        )
        res["template"] = (
            until(f"cad.doc.entities.length > {before_tpl}") and len(doc()) - before_tpl
        )
        # 10c) 3D view: the rectangle + circle become a plate with a hole
        js("window.prompt = () => '12'")
        js("document.querySelector('[data-cad=view3d]').click()")
        res["view3d"] = until("window.cad3dFaces > 6 && document.querySelector('.cad3d canvas')")
        js("document.querySelector('.cad3d button').click()")
        # 11) «AI bilan tuzatish» without a key: NEXVARA tidies the sketch itself; zoom; compact
        js("window.prompt = () => ''; window.confirm = () => true;")
        js("document.querySelector('[data-cad=ai]').click()")
        res["ai_fix"] = until(
            "document.getElementById('cad-log').textContent.includes('tekisladim')"
        )
        for b in ("zoomin", "zoomout", "compact", "compact"):
            js(f"document.querySelector('[data-cad={b}]').click()")
        # 12) colours: «COLOR 1» for new objects, the palette recolours the selection
        ex("COLOR 1", "L", "0,-80", "60,-80", "")
        last = len(doc()) - 1
        res["color_new"] = doc()[last].get("color")
        js(f"cad.select([{last}])")
        js("document.getElementById('cad-color').click()")
        res["palette"] = js("document.querySelectorAll('.cad-palette .cad-pal-sw').length")
        js("document.querySelector('.cad-palette [data-aci=\"30\"]').click()")
        res["color_pick"] = doc()[last].get("color")
        js("cad.select([])")
        ex("COLOR BYLAYER")  # with nothing selected: only the colour of new objects
        js("document.querySelector('[data-cad=save]').click()")
        res["saved"] = until("document.getElementById('cad-log').textContent.includes('Saqlandi:')")
        # 13) PDF and Word buttons: files next to the drawing (Word: the drawing on an A4 page)
        for kind, ext in (("pdf", ".pdf"), ("word", ".docx")):
            js(f"document.querySelector('[data-cad={kind}]').click()")
            res[f"export_{kind}"] = until(
                f"document.getElementById('cad-log').textContent.includes('{ext}')", 40
            )
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
        res["log"] = js("document.getElementById('cad-log').textContent")[-600:]
        res["doc"] = js("JSON.stringify(cad.doc)")
    finally:
        win.destroy()


webview.start(run)
if target.exists():
    d = cad.read(target)
    res["dxf_audit"] = cad.audit(d)
    res["dxf_types"] = cad.summary(d)["types"]
    res["dxf_colors"] = sorted({e.dxf.color for e in d.modelspace() if e.dxf.hasattr("color")})
else:
    res["dxf_audit"] = ["file missing"]
docx = sorted(tmp.glob("chizma_*.docx"))
res["docx_ok"] = bool(docx) and docx[-1].read_bytes()[:2] == b"PK"
res["pdf_ok"] = any(p.read_bytes()[:5] == b"%PDF-" for p in tmp.glob("chizma_*.pdf"))
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = res.get("trim") == [(0.0, 50.0)] or res.get("trim") == [[0, 50]]
checks = {
    "trim": res.get("trim") in ([[0, 50]], [(0, 50)]),
    "extend": res.get("extend") == [80],
    "fillet": res.get("fillet") == [5, 205, 5],
    "chamfer": res.get("chamfer") is True,
    "hatch": res.get("hatch_paths") == 2,
    "dims": res.get("dims") == ["ldim", "rdim"],
    "offset": res.get("offset") == [200, 210],
    "array": res.get("array_added") == 5,
    "explode": res.get("explode") == 3,
    "saved": bool(res.get("saved")),
    "dxf": res.get("dxf_audit") == [] and "HATCH" in res.get("dxf_types", {}),
    "ai_fix": bool(res.get("ai_fix")),
    "view3d": bool(res.get("view3d")),
    "template": (res.get("template") or 0) >= 10,
    "colors": res.get("color_new") == 1
    and res.get("color_pick") == 30
    and (res.get("palette") or 0) >= 255
    and 30 in res.get("dxf_colors", []),
    "pdf_word": bool(res.get("export_pdf"))
    and bool(res.get("export_word"))
    and res.get("pdf_ok")
    and res.get("docx_ok"),
    "no_js_errors": not res.get("errors"),
}
print(json.dumps(checks, indent=1))
print("CAD TOOLS", "PASS" if all(checks.values()) else "FAIL")
sys.exit(0 if all(checks.values()) else 1)
