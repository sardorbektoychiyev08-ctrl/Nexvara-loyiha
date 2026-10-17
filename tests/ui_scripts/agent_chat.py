"""Chat drives Files, NEXVARA BI, Workflows and Settings in a real window (throwaway data)."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="nexvara-ui-")
os.environ["NEXVARA_DATA"] = tmp

import webview  # noqa: E402

from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402

work = Path(tmp) / "Ish"
work.mkdir()
(work / "savdo.csv").write_text(
    "Sana;Filial;Daromad\n05.01.2026;Toshkent;100\n03.02.2026;Buxoro;250\n", encoding="utf-8"
)
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


def chat(text, expect):
    js = win.evaluate_js
    js("document.querySelector('.nav-item[data-page=chat]').click()")
    before = js("document.querySelectorAll('.msg').length")
    js(f"document.getElementById('chat-text').value={json.dumps(text)}")
    js("document.querySelector('#chat-form button[type=submit]').click()")
    # Only messages that appeared after this one was sent count (an earlier reply may
    # contain the same word).
    return wait_for(
        f"[...document.querySelectorAll('.msg')].slice({before})"
        f".some(m => m.textContent.includes({json.dumps(expect)}))"
    )


def run():
    try:
        ready.wait(90)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')", 90)
        js = win.evaluate_js
        arxiv = work / "Arxiv"
        res["copy"] = chat(f"{work / 'savdo.csv'} ni {arxiv} papkasiga nusxala", "nusxalandi")
        res["copied"] = (arxiv / "savdo.csv").is_file()
        res["bi"] = chat(
            f"{work / 'savdo.csv'} dan dashboard yarat va «Savdo» deb saqla", "saqlandi"
        )
        res["bi_page"] = wait_for(
            "document.getElementById('page-bi').classList.contains('active') && "
            "document.getElementById('bi-msg').textContent.includes('Savdo')"
        )
        res["summary"] = chat("«Savdo» dashboardi ko‘rsatkichlarini ayt", "2 ta qator")
        res["wf"] = chat(
            "«Ertalab» workflow yarat: oxirgi vazifalarni ko‘rsat. Har kuni soat 08:00 da",
            "saqlandi",
        )
        res["wf_saved"] = api.wf_list()[0]["trigger"] == {"type": "daily", "time": "08:00"}
        res["setting"] = chat("savollar soni 15 bo‘lsin", "(sukut): 15")
        res["setting_saved"] = api.get_settings()["test_count"] == 15
        js("document.querySelector('.nav-item[data-page=settings]').click()")
        res["sync_card"] = wait_for("document.getElementById('sync-msg').textContent")
        res["import_btn"] = js("!!document.getElementById('account-import')")
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = all(res.get(k) for k in ("copy", "copied", "bi", "bi_page", "summary", "wf", "wf_saved",
                              "setting", "setting_saved", "sync_card", "import_btn"))  # fmt: skip
ok = ok and not res.get("errors")
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
