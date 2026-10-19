# ruff: noqa: E501 - demo data
"""Screenshots of the desktop app for the illustrated user guide (scripts/make_guide.py).

    python scripts\\guide_shots.py <out folder>

A real window with demo data only (a temporary data folder, fake AI, demo files and chat) —
nothing of the owner's is shown and nothing on this PC is changed.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ctypes.windll.user32.SetProcessDPIAware()  # real pixels for the window rectangle
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "guide_shots")
OUT.mkdir(parents=True, exist_ok=True)
tmp = Path(tempfile.mkdtemp(prefix="nexvara-guide-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests" / "unit")]

import webview  # noqa: E402
import win32gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402
from test_ai_media import KEYS, make  # noqa: E402

from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402
from nexvara.core.task import TaskRunner  # noqa: E402
from nexvara.memory.store import MemoryStore  # noqa: E402
from nexvara.remote import DeviceStore  # noqa: E402

docs = tmp / "Hujjatlar"
docs.mkdir()
csv = docs / "Savdo.csv"
csv.write_text("Oy,Filial,Mahsulot,Summa\n" + "\n".join(
    f"2026-{m:02d}-01,{f},{p},{s}" for m in range(1, 7)
    for f, p, s in (("Chilonzor", "Daftar", 1200000 + m * 90000), ("Yunusobod", "Ruchka", 800000 + m * 60000),
                    ("Sergeli", "Kitob", 950000 + m * 40000))), encoding="utf-8")  # fmt: skip
for name in ("Baholar 7-A.xlsx", "Baholar 7-B.xlsx", "Oylik hisobot.docx", "Ota-onalar yig‘ilishi.pptx"):
    (docs / name).write_bytes(b"demo")

mem = MemoryStore(tmp / "app.db")
for role, text in (
    ("user", "Baholar 7-A.xlsx ni och, jadvalni formatla, Baho ustuni bo‘yicha sarala va PDF qil"),
    ("nexvara", "Bajarildi: jadval formatlandi, saralandi, PDF saqlandi — Baholar 7-A_NEXVARA.pdf"),
    ("user", "7-sinf fizika «Nyuton qonunlari» mavzusidan 20 ta test, 2 variant"),
    ("nexvara", "Test tayyor: 2 variant, 20 tadan savol, javoblar kaliti bilan (Word)."),
):
    mem.log_chat(role, text)

router = make(tmp, KEYS)
runner = TaskRunner()
api = Api(runner, overrides={"memory": mem, "ai_router": router, "onboarding_force": True,
                             "used_before": lambda: False,
                             "office_installed": lambda: {"excel": True, "word": True, "powerpoint": True},
                             "firewall_status": lambda a: {"tailscale": "", "needed": False},
                             "device_store": DeviceStore(tmp / "dev.db"), "remote_port": 0})  # fmt: skip


def demo_task(title, steps):
    def fn(task):
        for s in steps:
            with task.step(s):
                pass
        return {"report": [steps[-1]]}

    runner.start(title, fn).wait(5)


demo_task("Excel: Baholar 7-A.xlsx", ["Faylni ochish", "Jadvalni formatlash", "Saralash", "PDF qilib saqlash"])
demo_task("Test: 7-sinf fizika", ["Darslikdan mavzuni topish", "Savollar tuzish", "Word hujjat"])

win = webview.create_window("NEXVARA", url=str(UI_DIR / "index.html"), js_api=api,
                            width=1360, height=860, on_top=True)  # fmt: skip
ready = threading.Event()
win.events.loaded += lambda: ready.set()
shots: list[str] = []


def wait_for(js, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = win.evaluate_js(js)
        if v:
            return v
        time.sleep(0.2)
    return None


def snap(name: str) -> None:
    time.sleep(0.8)
    hwnd = win32gui.FindWindow(None, "NEXVARA")
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:  # noqa: BLE001 - Windows may refuse; the window is on top anyway
        pass
    time.sleep(0.3)
    left, t, r, b = win32gui.GetClientRect(hwnd)
    x, y = win32gui.ClientToScreen(hwnd, (0, 0))
    im = ImageGrab.grab(bbox=(x, y, x + r - left, y + b - t)).convert("RGB")
    px, w, bottom = im.load(), im.width, im.height
    while bottom > im.height // 2 and all(max(px[i, bottom - 1]) < 8 for i in range(0, w, 7)):
        bottom -= 1  # the empty black strip under the page
    im.crop((0, 0, w, bottom)).save(OUT / f"{name}.png")
    shots.append(name)


def page(name: str, shot: str, then: str = "") -> None:
    win.evaluate_js(f"show({json.dumps(name)})")
    if then:
        time.sleep(0.6)
        win.evaluate_js(then)
    snap(shot)


def run():
    js = win.evaluate_js
    try:
        ready.wait(90)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')", 90)
        wait_for("!document.getElementById('onboard').hidden")
        snap("01_yordamchi_1")
        js("document.getElementById('ob-next').click()")
        snap("02_yordamchi_2")
        js("document.getElementById('ob-skip').click()")
        page("home", "03_bosh_sahifa")
        page("chat", "04_suhbat")
        js("document.getElementById('chat-models').click()")
        wait_for("document.querySelectorAll('.caps-pop .cap-row').length")
        snap("05_ai_menyu")
        js("document.querySelector('.caps-pop .btn').click()")
        page("office", "06_office")
        page("library", "07_darsliklar")
        page("files", "08_fayllar", f"document.getElementById('f-query').value='Baholar';"
             f"document.getElementById('f-folder').value={json.dumps(str(docs))};"
             "document.getElementById('f-form').requestSubmit()")  # fmt: skip
        page("bi", "09_bi", f"biOpenSource({json.dumps(str(csv))})")
        time.sleep(2)
        snap("09_bi")
        page("cad", "10_chizma_bosh")
        for c in ("REC", "0,0", "120,70", "C", "60,35", "15", "DLI", "0,0", "120,0", "60,-12",
                  "DLI", "120,0", "120,70", "135,35", "ZE"):  # fmt: skip
            js(f"cad.exec({json.dumps(c)})")
        snap("10_chizma")
        page("workflows", "11_ish_jarayonlari")
        page("teach", "12_orgatish")
        page("memory", "13_xotira")
        page("history", "14_vazifalar")
        api.devices_start()
        page("devices", "15_qurilmalar")
        time.sleep(1.5)
        snap("15_qurilmalar")
        page("settings", "16_sozlamalar")
        js("document.querySelector('#page-settings').scrollTop = 0")
    except Exception as e:  # noqa: BLE001
        print("XATO:", repr(e))
    finally:
        api.devices_stop()
        win.destroy()


webview.start(run)
print(json.dumps(sorted(set(shots)), ensure_ascii=False))
