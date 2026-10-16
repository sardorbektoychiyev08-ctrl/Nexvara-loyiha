"""Memory/Teach pages in a real window with a throwaway data folder."""

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


def run():
    try:
        ready.wait(30)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')")
        js = win.evaluate_js
        # Chat: teach a fact and a rule with the confirm buttons.
        js("document.querySelector('.nav-item[data-page=chat]').click()")
        js(
            "document.getElementById('chat-text').value='Eslab qol: men 12-maktabda fizika o‘qituvchisiman'"
        )
        js("document.querySelector('#chat-form button[type=submit]').click()")
        res["confirm_btn"] = wait_for("document.querySelectorAll('.confirm-row button').length")
        js("document.querySelector('.confirm-row .btn.primary').click()")
        res["saved_msg"] = wait_for(
            "[...document.querySelectorAll('.msg')].some(m => m.textContent.includes('Eslab qoldim'))"
        )
        # Teach page: preview + save a rule.
        js("document.querySelector('.nav-item[data-page=teach]').click()")
        js("document.getElementById('teach-text').value='jadvalni formatla va sarlavhani qotir'")
        js("document.getElementById('teach-check').click()")
        res["preview"] = wait_for("document.getElementById('teach-preview').textContent")
        js("document.querySelector('#teach-form button[type=submit]').click()")
        res["rules"] = wait_for("document.querySelectorAll('#teach-rules .ai-prov').length")
        # Memory page shows the fact, the chat and finds it by a suffixed word.
        js("document.querySelector('.nav-item[data-page=memory]').click()")
        res["facts"] = wait_for("document.querySelectorAll('#mem-facts .item-row').length")
        res["chat_lines"] = wait_for("document.querySelectorAll('#mem-chat .mem-line').length")
        js("document.getElementById('mem-search').value='maktabimizda'")
        js("document.querySelector('#mem-search-form button').click()")
        res["search"] = wait_for(
            "document.querySelectorAll('#mem-search-results .item-row').length"
        )
        js("document.getElementById('mem-export').click()")
        res["export"] = wait_for("document.getElementById('mem-backup-msg').textContent")
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = (
    res.get("confirm_btn")
    and res.get("saved_msg")
    and res.get("rules") == 1
    and res.get("facts") == 1
    and res.get("chat_lines") == 4
    and res.get("search")
    and "Saqlandi" in (res.get("export") or "")
    and not res.get("errors")
)
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
