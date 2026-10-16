"""NEXVARA BI in a real window: chat opens a dashboard from an Excel file, drill-down,
date filter, a new widget, an ETL step, save and every export format.

Set NEXVARA_SHOT=<folder> to also save screenshots of the window."""

import datetime as dt
import json
import os
import random
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-bi-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")

import openpyxl

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Sana", "Filial", "Mahsulot", "Daromad", "Xarajat"])
rng = random.Random(7)
for i in range(120):
    d = dt.datetime(2026, 1, 1) + dt.timedelta(days=i * 2)
    f = rng.choice(["Toshkent", "Samarqand", "Buxoro", "Andijon"])
    m = rng.choice(["Daftar", "Ruchka", "Kitob"])
    rev = rng.randint(200, 900) * 1000
    ws.append([d, f, m, rev, int(rev * rng.uniform(0.4, 0.8))])
src = tmp / "Savdo 2026.xlsx"
wb.save(src)

import webview

from nexvara.app.api import Api
from nexvara.app.main import UI_DIR

api = Api(persist=True)
win = webview.create_window(
    "NEXVARA-E2E", url=str(UI_DIR / "index.html"), js_api=api, width=1320, height=860
)
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {}
SHOTS = os.environ.get("NEXVARA_SHOT")


def shot(name):
    if not SHOTS:
        return
    import ctypes

    import pymupdf
    import win32con
    import win32gui
    import win32ui

    del win32con
    hwnd = win32gui.FindWindow(None, "NEXVARA-E2E")
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    src_dc = win32gui.GetWindowDC(hwnd)
    dc = win32ui.CreateDCFromHandle(src_dc)
    mem = dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(dc, w, h)
    mem.SelectObject(bmp)
    # PW_RENDERFULLCONTENT (2): also captures GPU-drawn content such as WebView2.
    ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)
    bmp_path = Path(SHOTS) / f"{name}.bmp"
    bmp.SaveBitmapFile(mem, str(bmp_path))
    pix = pymupdf.Pixmap(str(bmp_path))
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    pix.save(str(bmp_path.with_suffix(".png")))
    bmp_path.unlink()
    mem.DeleteDC()
    dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, src_dc)
    win32gui.DeleteObject(bmp.GetHandle())


def wait_for(js, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = win.evaluate_js(js)
        if v:
            return v
        time.sleep(0.25)
    return None


def run():
    try:
        ready.wait(30)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')")
        js = win.evaluate_js
        js("window.confirm = () => true; window.prompt = () => 'Ikkinchi';")
        js("document.querySelector('.nav-item[data-page=chat]').click()")
        js(
            f"document.getElementById('chat-text').value = {json.dumps(f'«{src}» dan dashboard yarat')}"
        )
        js("document.querySelector('#chat-form button[type=submit]').click()")
        res["widgets"] = wait_for("document.querySelectorAll('#bi-board .bi-widget').length")
        res["on_bi_page"] = js("document.getElementById('page-bi').classList.contains('active')")
        res["kpi_profit"] = js(
            "[...document.querySelectorAll('.bi-kpi .card-label')].some(x => x.textContent.includes('Sof foyda'))"
        )
        res["growth_shown"] = js("document.querySelectorAll('.bi-growth').length > 0")
        time.sleep(0.5)
        shot("bi-1-overview")
        js("document.querySelector('.content').scrollTop = 760")
        time.sleep(0.4)
        shot("bi-1b-charts")
        js("document.querySelector('.content').scrollTop = 0")
        js("document.querySelector('[data-bi-export=png]').click()")
        res["export_png_page1"] = wait_for(
            "document.getElementById('bi-msg').textContent.startsWith('Saqlandi')", timeout=30
        )
        rows_before = js("document.getElementById('bi-rows').textContent")
        js(
            "document.querySelector('.bi-bar .bi-hit').dispatchEvent(new MouseEvent('click', {bubbles: true}))"
        )
        res["drill_chip"] = wait_for("document.querySelectorAll('#bi-chips .chip').length === 1")
        res["rows_changed"] = js("document.getElementById('bi-rows').textContent") != rows_before
        js("document.getElementById('bi-clear').click()")
        wait_for("document.querySelectorAll('#bi-chips .chip').length === 0")
        js(
            "const d = document.querySelector('#bi-filters input[type=date]'); d.value = '2026-03-01';"
            "d.dispatchEvent(new Event('change'))"
        )
        res["date_chip"] = wait_for(
            "document.getElementById('bi-chips').textContent.includes('2026-03-01')"
        )
        js("document.getElementById('bi-clear').click()")
        # new widget: average revenue by product (bar)
        count = js("document.querySelectorAll('#bi-board .bi-widget').length")
        js("document.getElementById('bi-add-widget').click()")
        js(
            "const f = document.getElementById('bi-wform'); const s = f.querySelectorAll('select');"
            "s[1].value = 'Mahsulot'; [...s[2].options].forEach(o => o.selected = o.value === 'Daromad');"
            "s[3].value = 'avg'; f.querySelector('.btn.primary').click()"
        )
        res["widget_added"] = wait_for(
            f"document.querySelectorAll('#bi-board .bi-widget').length === {count + 1}"
        )
        # ETL: a calculated column
        js("document.getElementById('bi-etl-toggle').click()")
        wait_for("document.querySelectorAll('#bi-etl-body select').length > 0")
        js(
            "const b = document.getElementById('bi-etl-body'); const s = b.querySelector('select');"
            "s.value = 'calc'; s.dispatchEvent(new Event('change'));"
            "const inputs = [...b.querySelectorAll('input')];"
            "inputs.find(i => i.closest('label').textContent.startsWith('Yangi nom')).value = 'Marja';"
            "inputs.find(i => i.closest('label').textContent.startsWith('Formula')).value = '[Daromad] / [Xarajat]';"
            "[...b.querySelectorAll('button')].find(x => x.textContent === 'Bosqich qo‘shish').click()"
        )
        res["etl_step"] = wait_for(
            "document.getElementById('bi-etl-body').textContent.includes('Marja')"
        )
        # page 2 and a new page
        js("document.querySelectorAll('#bi-tabs button')[1].click()")
        res["page2"] = wait_for("document.querySelector('.bi-scatter') !== null")
        shot("bi-2-details")
        js(
            "[...document.querySelectorAll('#bi-tabs button')].find(b => b.textContent === '+ Sahifa').click()"
        )
        res["page3"] = wait_for("document.querySelectorAll('#bi-tabs button').length === 4")
        js("document.getElementById('bi-name').value = 'Savdo paneli'")
        js("document.getElementById('bi-save').click()")
        res["saved"] = wait_for(
            "document.getElementById('bi-msg').textContent.includes('Saqlandi')"
        )
        for kind in ("png", "xlsx", "csv", "pdf"):
            js("document.getElementById('bi-msg').textContent = ''")
            js(f"document.querySelector('[data-bi-export={kind}]').click()")
            res[f"export_{kind}"] = wait_for(
                "document.getElementById('bi-msg').textContent.startsWith('Saqlandi')", timeout=30
            )
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
exports = sorted(p.suffix for p in (tmp / "data" / "BI" / "Eksport").glob("*"))
res["export_files"] = exports
res["saved_files"] = [p.name for p in (tmp / "data" / "BI").glob("*.json")]
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = (
    (res.get("widgets") or 0) >= 6
    and all(res.get(k) for k in ("on_bi_page", "kpi_profit", "growth_shown", "drill_chip",
                                  "rows_changed", "date_chip", "widget_added", "etl_step",
                                  "page2", "page3", "saved", "export_png", "export_xlsx",
                                  "export_csv", "export_pdf"))
    and exports == [".csv", ".pdf", ".png", ".png", ".xlsx"]
    and res["saved_files"] == ["Savdo_paneli.json"]
    and not res.get("errors")
)  # fmt: skip
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
