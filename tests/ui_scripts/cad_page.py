"""Use the real Chizmalar window to draw, edit, save, open and export a DXF."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-cad-ui-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")

import webview

from nexvara import cad
from nexvara.app.api import Api
from nexvara.app.main import UI_DIR

target = tmp / "sinov.dxf"
api = Api(output_dir=tmp, overrides={"cad_dialog": lambda _save: str(target)})
win = webview.create_window(
    "NEXVARA Chizma sinovi", url=str(UI_DIR / "index.html"), js_api=api, width=1400, height=850
)
ready = threading.Event()
win.events.loaded += lambda: ready.set()
result = {}


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
        result["page"] = until("document.getElementById('page-cad').classList.contains('active')")
        for command in ("L", "0,0", "@100,0", "", "REC", "10,10", "@20,15", "C", "50,30", "@10,0"):
            js(f"cad.exec({json.dumps(command)})")
        result["entities"] = js("cad.doc.entities.length")
        result["types"] = json.loads(js("JSON.stringify(cad.doc.entities.map(e => e.type))"))
        js("document.querySelector('[data-cad=undo]').click()")
        result["undo"] = js("cad.doc.entities.length")
        js("document.querySelector('[data-cad=redo]').click()")
        result["redo"] = js("cad.doc.entities.length")
        js("document.querySelector('[data-cad=save]').click()")
        result["saved"] = until(
            "document.getElementById('cad-log').textContent.includes('Saqlandi:')"
        )
        js("document.querySelector('[data-cad=pdf]').click()")
        result["pdf"] = until("document.getElementById('cad-log').textContent.includes('Tayyor:')")
        js("document.querySelector('[data-cad=open]').click()")
        result["opened"] = until(
            "document.getElementById('cad-log').textContent.includes('sinov.dxf ochildi')"
        )
        result["reopened_count"] = js("cad.doc.entities.length")
        result["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
result["dxf_audit"] = cad.audit(cad.read(target)) if target.exists() else ["file missing"]
result["pdf_file"] = (tmp / "sinov.pdf").exists() or bool(list(tmp.glob("chizma_*.pdf")))
print(json.dumps(result, ensure_ascii=False, indent=1))
ok = (
    result.get("page")
    and result.get("entities") == 3
    and result.get("types") == ["line", "polyline", "circle"]
    and result.get("undo") == 2
    and result.get("redo") == 3
    and result.get("saved")
    and result.get("opened")
    and result.get("reopened_count") == 3
    and result.get("pdf")
    and result.get("pdf_file")
    and not result.get("dxf_audit")
    and not result.get("errors")
)
print("CAD E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
