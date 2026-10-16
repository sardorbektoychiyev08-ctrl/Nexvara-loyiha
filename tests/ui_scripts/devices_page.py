"""Devices: the desktop page turns phone access on; a second window plays the phone
(pairs with the code, sends a command, sees tasks). TLS is off here only because a test
browser cannot accept the PC's own certificate; the unit tests cover HTTPS."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-dev-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")

import webview

from nexvara.app.api import Api
from nexvara.app.main import UI_DIR

api = Api(persist=True, overrides={"remote_tls": False, "remote_port": 0})
desk = webview.create_window(
    "NEXVARA-E2E", url=str(UI_DIR / "index.html"), js_api=api, width=1300, height=800
)
ready = threading.Event()
desk.events.loaded += lambda: ready.set()
res = {}


def wait_for(win, js, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            v = win.evaluate_js(js)
        except Exception:
            v = None
        if v:
            return v
        time.sleep(0.25)
    return None


def run():
    phone = None
    try:
        ready.wait(90)
        wait_for(desk, "document.getElementById('version').textContent.startsWith('NEXVARA v')", 90)
        desk.evaluate_js("window.confirm = () => true;")
        desk.evaluate_js("document.querySelector('.nav-item[data-page=devices]').click()")
        desk.evaluate_js("document.getElementById('dev-toggle').click()")
        res["qr"] = wait_for(desk, "document.querySelector('#dev-qr svg') !== null")
        code = desk.evaluate_js("document.getElementById('dev-code').textContent")
        url = desk.evaluate_js("document.getElementById('dev-url').textContent")
        res["code_ok"] = len(code) == 6 and code.isdigit()
        url = url.replace(url.split("//")[1].split(":")[0], "127.0.0.1")
        loaded = threading.Event()
        phone = webview.create_window("NEXVARA-PHONE", url=f"{url}#p={code}", width=420, height=780)
        phone.events.loaded += lambda: loaded.set()
        loaded.wait(20)
        res["code_prefilled"] = wait_for(
            phone, f"document.getElementById('code').value === '{code}'"
        )
        phone.evaluate_js("document.getElementById('dname').value = 'Test telefon'")
        phone.evaluate_js("document.getElementById('pair-btn').click()")
        res["paired"] = wait_for(phone, "!document.getElementById('nav').hidden")
        res["listed"] = wait_for(
            desk, "document.getElementById('dev-list').textContent.includes('Test telefon')"
        )
        phone.evaluate_js("document.getElementById('text').value = 'Eslab qol: telefondan salom'")
        phone.evaluate_js("document.getElementById('send').click()")
        res["confirm"] = wait_for(
            phone, "document.querySelectorAll('#msgs .row .btn.primary').length > 0"
        )
        phone.evaluate_js("document.querySelector('#msgs .row .btn.primary').click()")
        res["saved"] = wait_for(
            phone,
            "[...document.querySelectorAll('.msg')].some(m => m.textContent.includes('Eslab qoldim'))",
        )
        res["phone_msgs"] = phone.evaluate_js(
            "[...document.querySelectorAll('#msgs > *')].map(m => m.className + ': ' + m.textContent).join(' | ')"
        )
        res["fact_on_pc"] = [f["text"] for f in api.memory_facts()] == ["telefondan salom"]
        phone.evaluate_js("document.querySelector('nav [data-tab=tasks]').click()")
        res["tasks_tab"] = wait_for(phone, "document.getElementById('tasks').children.length > 0")
        # Revoke from the PC: the phone is sent back to pairing.
        desk.evaluate_js("document.querySelector('#dev-list .btn.danger').click()")
        wait_for(desk, "document.getElementById('dev-list').textContent.includes('Hali qurilma')")
        phone.evaluate_js("document.querySelector('nav [data-tab=tasks]').click()")
        res["revoked"] = wait_for(phone, "!document.getElementById('pair').hidden")
        res["errors"] = json.loads(desk.evaluate_js("JSON.stringify(window.__errors)"))
        desk.evaluate_js("document.getElementById('dev-toggle').click()")
        res["stopped"] = wait_for(
            desk, "document.getElementById('dev-state').textContent === 'O‘chiq'"
        )
    finally:
        if phone is not None:
            phone.destroy()
        desk.destroy()


webview.start(run)
print(json.dumps(res, ensure_ascii=False, indent=1))
keys = ("qr", "code_ok", "code_prefilled", "paired", "listed", "confirm", "saved", "fact_on_pc",
        "tasks_tab", "revoked", "stopped")  # fmt: skip
ok = all(res.get(k) for k in keys) and not res.get("errors")
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
