"""Settings cards (Google account, updates) and section chat commands in a real window."""

import json
import os
import sys
import tempfile
import threading
import time

tmp = tempfile.mkdtemp(prefix="nexvara-ui-")
os.environ["NEXVARA_DATA"] = tmp

import webview  # noqa: E402

from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402

api = Api(persist=True)
win = webview.create_window(
    "NEXVARA-E2E", url=str(UI_DIR / "index.html"), js_api=api, width=1300, height=780
)
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {}


def wait_for(js, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = win.evaluate_js(js)
        if v:
            return v
        time.sleep(0.2)
    return None


def chat(text, expect):
    js = win.evaluate_js
    js(f"document.getElementById('chat-text').value={json.dumps(text)}")
    js("document.querySelector('#chat-form button[type=submit]').click()")
    return wait_for(
        f"[...document.querySelectorAll('.msg')].some(m => m.textContent.includes({json.dumps(expect)}))"
    )


def run():
    try:
        ready.wait(90)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')", 90)
        js = win.evaluate_js
        js("document.querySelector('.nav-item[data-page=settings]').click()")
        # No google_client.json in the throwaway folder: the card says BLOCKED, button disabled.
        res["account"] = wait_for("document.getElementById('account-info').textContent")
        res["login_disabled"] = js("document.getElementById('account-login').disabled")
        res["version"] = wait_for("document.getElementById('upd-info').textContent")
        js(
            "document.getElementById('upd-channel').value='"
            + tmp.replace("\\", "\\\\")
            + "\\\\yoq'"
        )
        js("document.querySelector('#upd-form button[type=submit]').click()")
        time.sleep(0.5)
        js("document.getElementById('upd-check').click()")
        res["update_error"] = wait_for(
            "!document.getElementById('upd-error').hidden && document.getElementById('upd-error').textContent"
        )
        res["channel_saved"] = api.get_settings()["update"]["channel"].endswith("yoq")
        # Section commands typed into the chat.
        js("document.querySelector('.nav-item[data-page=chat]').click()")
        res["theme_msg"] = chat("yorug‘ mavzuga o‘t", "Yorug‘ mavzu yoqildi")
        res["theme"] = js("document.documentElement.dataset.theme")
        res["history"] = chat("oxirgi vazifalarni ko‘rsat", "vazifa")
        res["workflows"] = chat("workflowlarni ko‘rsat", "workflow")
        chat("qorong‘i mavzu", "Qorong‘i mavzu yoqildi")
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = (
    "BLOCKED" in (res.get("account") or "")
    and res.get("login_disabled") is True
    and "0." in (res.get("version") or "")
    and "o‘qilmadi" in (res.get("update_error") or "")
    and res.get("channel_saved")
    and res.get("theme_msg")
    and res.get("theme") == "light"
    and res.get("history")
    and res.get("workflows")
    and not res.get("errors")
)
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
