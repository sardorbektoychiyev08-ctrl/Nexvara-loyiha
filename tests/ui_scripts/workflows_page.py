"""Workflows page in a real window: build one from a template, run it, approve, see history."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-wf-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")

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
        js("window.confirm = () => true;")
        js("document.querySelector('.nav-item[data-page=workflows]').click()")
        res["templates"] = wait_for("document.querySelectorAll('#wf-template option').length > 3")
        # Template 3: approval + test command. Replace the command with a harmless one.
        js(
            "const t = document.getElementById('wf-template'); t.value = '2';"
            "t.dispatchEvent(new Event('change'))"
        )
        res["loaded"] = wait_for("document.getElementById('wf-name').value.includes('Haftalik')")
        res["folder_fields_hidden"] = js(
            "document.querySelector('label[data-trig=folder]').offsetParent === null"
        )
        js(
            "const i = document.querySelectorAll('#wf-steps input')[1]; i.value = 'nimalarni eslab qolding';"
            "i.dispatchEvent(new Event('input'))"
        )
        js("document.querySelector('#wf-form button[type=submit]').click()")
        res["saved"] = wait_for("document.querySelectorAll('#wf-list .ai-prov').length === 1")
        js("document.querySelector('#wf-list .btn.primary').click()")  # run
        res["waiting"] = wait_for(
            "document.getElementById('wf-active').textContent.includes('tasdiq')"
        )
        js(
            "[...document.querySelectorAll('#wf-active button')].find(b => b.textContent === 'Tasdiqlash').click()"
        )
        res["done"] = wait_for(
            "document.getElementById('wf-active-card').hidden === true", timeout=20
        )
        time.sleep(1.5)
        js(
            "[...document.querySelectorAll('#wf-list button')].find(b => b.textContent === 'Tarix').click()"
        )
        res["history"] = wait_for(
            "document.getElementById('wf-runs').textContent.includes('Bajarildi')"
        )
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = all(res.get(k) for k in ("templates", "loaded", "folder_fields_hidden", "saved", "waiting",
                              "done", "history")) and not res.get("errors")  # fmt: skip
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
