"""Files page in a real window: search a folder, inspect, ZIP, back up, rename, recycle."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-files-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")
work = tmp / "ish"
work.mkdir()
(work / "Hisobot yanvar.txt").write_text("1", encoding="utf-8")
(work / "Hisobot fevral.txt").write_text("2", encoding="utf-8")
(work / "boshqa.txt").write_text("3", encoding="utf-8")

import webview

from nexvara.app.api import Api
from nexvara.app.main import UI_DIR

api = Api(persist=True)
win = webview.create_window(
    "NEXVARA-E2E", url=str(UI_DIR / "index.html"), js_api=api, width=1300, height=780
)
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {}


def wait_for(js, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = win.evaluate_js(js)
        if v:
            return v
        time.sleep(0.2)
    return None


def run():
    try:
        ready.wait(30)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')")
        js = win.evaluate_js
        js("window.confirm = () => true; window.prompt = (m, d) => 'Oylik_{n}';")
        js("document.querySelector('.nav-item[data-page=files]').click()")
        js(f"document.getElementById('f-folder').value = {json.dumps(str(work))}")
        js("document.getElementById('f-query').value = 'hisobot'")
        js("document.querySelector('#f-form button[type=submit]').click()")
        res["rows"] = wait_for("document.querySelectorAll('#f-table tr.clickable').length")
        js("document.querySelector('#f-table tr.clickable').click()")
        res["info_has_hash"] = wait_for(
            "document.getElementById('f-info').textContent.includes('SHA-256')"
        )
        js("document.querySelector('#f-table th input').click()")  # select all
        res["selected"] = wait_for(
            "document.getElementById('f-count').textContent.includes('tanlangan: 2')"
        )
        js("document.querySelector('[data-fa=zip]').click()")
        res["zip"] = wait_for("document.getElementById('f-msg').textContent.startsWith('Arxiv:')")
        js("document.querySelector('[data-fa=backup]').click()")
        res["backup"] = wait_for("document.getElementById('f-msg').textContent.includes('zaxira')")
        js("document.querySelector('[data-fa=rename]').click()")  # 2 files -> batch with the prompt
        res["renamed"] = wait_for(
            "document.getElementById('f-msg').textContent.includes('qayta nomlandi')"
        )
        res["names"] = sorted(p.name for p in work.iterdir() if p.suffix == ".txt")
        # Search again for the renamed files and send one to the Recycle Bin.
        js("document.getElementById('f-query').value = 'oylik_1'")
        js("document.querySelector('#f-form button[type=submit]').click()")
        wait_for("document.querySelectorAll('#f-table tr.clickable').length === 1")
        js("document.querySelector('#f-table tr.clickable input').click()")
        js("document.querySelector('[data-fa=recycle]').click()")
        res["recycled"] = wait_for(
            "document.getElementById('f-msg').textContent.includes('Savatga')"
        )
        res["log_rows"] = wait_for("document.querySelectorAll('#f-log tr').length")
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
res["left"] = sorted(p.name for p in work.iterdir() if p.suffix == ".txt")
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = (
    res.get("rows") == 2
    and res.get("info_has_hash")
    and res.get("selected")
    and res.get("zip")
    and res.get("backup")
    and res.get("names") == ["Oylik_1.txt", "Oylik_2.txt", "boshqa.txt"]
    and res.get("recycled")
    and res.get("left") == ["Oylik_2.txt", "boshqa.txt"]
    and (res.get("log_rows") or 0) >= 4
    and not res.get("errors")
)
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
