"""NEXVARA desktop shell.

python -m nexvara.app.main            # open the app
python -m nexvara.app.main --smoke    # open, check the UI rendered, close (exit code 0/1)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from pathlib import Path

import webview

from nexvara import __version__
from nexvara.app.api import Api

UI_DIR = Path(__file__).parent / "ui"
WANTED_SIZE = (1320, 820)
MIN_SIZE = (900, 560)


def work_area() -> tuple[int, int, int, int] | None:
    """Usable desktop (without the taskbar) in the logical pixels pywebview uses."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
        return None
    try:
        scale = ctypes.windll.user32.GetDpiForSystem() / 96
    except AttributeError:
        scale = 1.0
    # The rectangle is physical when the process is DPI aware, logical otherwise.
    aware = bool(ctypes.windll.user32.IsProcessDPIAware())
    s = scale if aware else 1.0
    return (round(rect.left / s), round(rect.top / s),
            round((rect.right - rect.left) / s), round((rect.bottom - rect.top) / s))  # fmt: skip


def window_geometry(area: tuple[int, int, int, int] | None) -> dict[str, int]:
    """Fit the window inside the screen (a 125% laptop has only ~816 px of height), centered."""
    w, h = WANTED_SIZE
    if area is None:
        return {"width": w, "height": h}
    x0, y0, aw, ah = area
    w = max(min(w, aw - 24), MIN_SIZE[0])
    h = max(min(h, ah - 24), MIN_SIZE[1])
    return {"width": w, "height": h, "x": x0 + (aw - w) // 2, "y": y0 + (ah - h) // 2}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexvara")
    parser.add_argument("--smoke", action="store_true", help="open, verify the UI, close")
    parser.add_argument(
        "--selftest-excel",
        metavar="DIR",
        type=Path,
        help="smoke test, then press the real Excel button (drives Excel on screen)",
    )
    parser.add_argument(
        "--selftest-library",
        metavar="DIR",
        type=Path,
        help="smoke test, then index the textbook folder and make a test from the UI form",
    )
    parser.add_argument(
        "--selftest-chat",
        metavar="FILE",
        type=Path,
        help="smoke test, then type an Office command about FILE into the chat and wait",
    )
    parser.add_argument(
        "--selftest-installed",
        metavar="DIR",
        type=Path,
        help="check an installed copy with the real data (read-only) + Office/BI demos in DIR",
    )
    parser.add_argument("--debug", action="store_true", help="enable WebView dev tools")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    from nexvara.ai.keys import RedactingFilter

    for handler in logging.getLogger().handlers:  # API keys never reach a log
        handler.addFilter(RedactingFilter())

    selftest = args.selftest_excel is not None
    selftest_dir = args.selftest_excel or args.selftest_library
    if args.selftest_chat is not None or args.selftest_installed is not None:
        args.smoke = True
    if args.selftest_installed is not None:
        args.selftest_installed.mkdir(parents=True, exist_ok=True)
        api = Api(persist=True)  # the real data, only read (no watchers, no update step)
    elif selftest_dir is not None:
        args.smoke = True
        selftest_dir.mkdir(parents=True, exist_ok=True)
        api = Api(output_dir=selftest_dir.resolve(), keep_office_open=False)
    elif args.selftest_chat is not None:
        api = Api(keep_office_open=False)
    else:
        api = Api(persist=True)  # history and settings survive restarts
        if not args.smoke:
            api.start_background()  # workflow folder watchers and daily schedules
            try:
                api.update_after_start()  # did an update started last time succeed?
            except Exception:  # noqa: BLE001 - never block the app from opening
                logging.getLogger(__name__).exception("update check after start failed")

            def resume_google() -> None:  # saved Google session, checked without a browser
                try:
                    api.account_resume()
                except Exception:  # noqa: BLE001 - the Settings card shows the state
                    logging.getLogger(__name__).exception("Google session check failed")

            threading.Thread(target=resume_google, name="google-resume", daemon=True).start()
    window = webview.create_window(
        "NEXVARA",
        url=str(UI_DIR / "index.html"),
        js_api=api,
        **window_geometry(work_area()),
        min_size=MIN_SIZE,
        background_color="#0B1020",
    )

    result = {"ok": not args.smoke}
    ready = threading.Event()
    window.events.loaded += lambda: ready.set()

    def smoke() -> None:
        try:
            if not ready.wait(30):
                print("SMOKE FAIL: window did not load in 30s")
                return
            nav = window.evaluate_js("document.querySelectorAll('.nav-item').length")
            # The UI fills #version from api.get_info() once the JS bridge is ready,
            # so seeing it proves the JS -> Python round trip works.
            version = ""
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and not version.startswith("NEXVARA v"):
                time.sleep(0.2)
                version = window.evaluate_js("document.getElementById('version').textContent")
            ok = bool(nav) and nav >= 11 and version == f"NEXVARA v{__version__}"
            # Settings page: the AI card lists every provider (reads keys, sends nothing).
            window.evaluate_js("document.querySelector('.nav-item[data-page=settings]').click()")
            providers = 0
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not providers:
                time.sleep(0.2)
                providers = window.evaluate_js("document.querySelectorAll('.ai-prov').length")
            # Every page opens, none is a placeholder, and no script error happened.
            pages = json.loads(window.evaluate_js(
                "JSON.stringify([...document.querySelectorAll('.nav-item')]"
                ".map(b => b.dataset.page))"
            ))  # fmt: skip
            placeholders = []
            for page in pages:
                window.evaluate_js(f"document.querySelector('.nav-item[data-page={page}]').click()")
                time.sleep(0.4)
                if window.evaluate_js(
                    "document.querySelector('#page-placeholder.active') !== null"
                ):
                    placeholders.append(page)
            window.evaluate_js("document.querySelector('.nav-item[data-page=home]').click()")
            time.sleep(0.5)
            errors = json.loads(window.evaluate_js("JSON.stringify(window.__errors)"))
            ok = ok and providers == 4 and not errors
            print(
                f"SMOKE {'PASS' if ok else 'FAIL'}: nav_items={nav} version={version!r} "
                f"ai_providers={providers} not_ready={placeholders} js_errors={errors}"
            )
            if ok and selftest:
                ok = excel_button_selftest(window)
            if ok and args.selftest_library is not None:
                ok = library_selftest(window)
            if ok and args.selftest_chat is not None:
                ok = chat_selftest(window, args.selftest_chat)
            if args.selftest_installed is not None:
                ok = installed_selftest(api, args.selftest_installed, smoke_ok=ok)
            result["ok"] = ok
        finally:
            window.destroy()

    webview.start(smoke if args.smoke else None, debug=args.debug)
    return 0 if result["ok"] else 1


def installed_selftest(api: Api, out: Path, smoke_ok: bool) -> bool:
    """After an install or update: are the accounts, sync, AI settings and Office still fine?
    Only reads the real data; Office/BI demos write into `out`. Report: out/report.json
    (no e-mail, token or key is written — only yes/no and counts)."""
    from nexvara import config
    from nexvara.sync import unseal

    rep: dict = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)),
                 "exe": sys.executable, "data_dir": str(config.data_dir()),
                 "smoke_12_pages": smoke_ok}  # fmt: skip
    g = api.account_status()
    rep["google"] = {"configured": g["configured"], "signed_in": g["signed_in"],
                     "owner_set": g["owner_set"], "session": g["session"]}  # fmt: skip
    s = api.sync_status()
    folder = Path(s.get("folder") or "")
    files = sorted((folder / "NEXVARA-sync").glob("*.nxsync")) if s.get("folder") else []
    pw = api._sync_keys().load("passphrase") or ""
    opened = 0
    for f in files:
        try:
            opened += isinstance(unseal(f.read_bytes(), pw), dict)
        except Exception:  # noqa: BLE001 - counted as not opened
            pass
    rep["sync"] = {"folder_set": bool(s.get("folder")), "folder_exists": folder.is_dir(),
                   "has_passphrase": s["has_passphrase"], "files": len(files),
                   "decrypted": opened}  # fmt: skip
    ai = api.ai_status()
    dash = api.ai_dashboard()
    rep["ai"] = {"providers": len(ai["providers"]), "enabled": ai.get("enabled"),
                 "keys": sum(bool(p["has_key"]) for p in ai["providers"].values()),
                 "dashboard_rows": len(dash.get("providers") or [])}  # fmt: skip
    u = api.update_status()
    rep["update"] = {"current": u["current"], "channel_set": bool(u["channel"]),
                     "kept": u["kept"]}  # fmt: skip
    work = Api(output_dir=out.resolve(), keep_office_open=False)
    office = {}
    demos = [("excel", work.run_excel_demo), ("excel_dashboard", work.run_excel_dashboard),
             ("word", work.run_word_report), ("powerpoint", work.run_presentation)]  # fmt: skip
    for name, start in demos:
        snap = start()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline and snap["status"] in ("pending", "running"):
            time.sleep(1)
            snap = work.get_task(snap["id"]) or snap
        office[name] = snap["status"]
    rep["office"] = office
    csv = out / "bi_sinov.csv"
    csv.write_text("Oy,Hudud,Savdo\n" + "\n".join(
        f"2026-{m:02d}-01,{h},{m * 100 + i * 7}" for m in range(1, 7)
        for i, h in enumerate(("Toshkent", "Samarqand", "Buxoro"))), "utf-8")  # fmt: skip
    bi = work.bi_auto(str(csv))
    pages = (bi.get("config") or {}).get("pages") or []
    rep["bi"] = {"ok": bi.get("ok"), "widgets": sum(len(pg["widgets"]) for pg in pages)}
    ok = (smoke_ok and rep["ai"]["providers"] == 4
          and all(v == "succeeded" for v in office.values())
          and bool(bi.get("ok")) and rep["bi"]["widgets"] > 0)  # fmt: skip
    rep["ok"] = ok
    (out / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), "utf-8")
    print("INSTALLED", "PASS" if ok else "FAIL", json.dumps(rep, ensure_ascii=False))
    return ok


def chat_selftest(window: webview.Window, file: Path) -> bool:
    """Type a multi-step command into the chat and wait for the final "Tayyor" message."""
    js = window.evaluate_js
    js("document.querySelector('.nav-item[data-page=chat]').click()")
    command = f"«{file.resolve()}» ni och, formatla, jami qo‘sh va saqla"
    js(f"document.getElementById('chat-text').value = {json.dumps(command)}")
    js("document.getElementById('chat-form').requestSubmit()")
    last = ""
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        time.sleep(0.5)
        last = js("(document.querySelector('#chat-log .msg:last-child')||{}).textContent") or ""
        if last.startswith(("Tayyor", "Bajarilmadi", "Bekor")):
            break
    ok = last.startswith("Tayyor ✓") and "Tekshiruv:" in last
    print(f"SELFTEST {'PASS' if ok else 'FAIL'} [chat]: {last.splitlines()[0] if last else ''!r}")
    return ok


def library_selftest(window: webview.Window) -> bool:
    """Index the textbook folder and build a test through the real "Darsliklar" page."""
    js = window.evaluate_js
    js("document.querySelector('.nav-item[data-page=library]').click()")
    time.sleep(1)
    ok = _click_and_watch(window, "lib-index", "Darsliklarni indekslash", steps=2, checks=0)
    time.sleep(1.5)  # the page re-renders the catalog after the task
    first_grade = js(
        "(document.querySelector('#t-grade option[value]:not([value=\"\"])')||{}).value"
    )
    js(f"document.getElementById('t-grade').value = '{first_grade}'")
    js("document.getElementById('t-grade').dispatchEvent(new Event('change'))")
    subject = js("(document.querySelector('#t-subject option[value]:not([value=\"\"])')||{}).value")
    js(f"document.getElementById('t-subject').value = {subject!r}")
    js("document.getElementById('t-topic').value = 'bosim'")
    shown = _click_and_watch(window, "t-topic-show", "Mavzu: bosim", steps=5, checks=4)
    js("document.getElementById('t-topic').value = 'kuch massa bosim'")
    js("document.getElementById('t-count').value = '6'")
    title = f"Test: {first_grade}-sinf {subject} · kuch massa bosim"
    made = _click_and_watch(window, "t-make", title, steps=6, checks=6)
    print(f"SELFTEST library: grade={first_grade!r} subject={subject!r}")
    return ok and shown and made


def excel_button_selftest(window: webview.Window) -> bool:
    """Click each real Office Agent button and watch the task panel until it finishes."""
    window.evaluate_js("document.querySelector('.nav-item[data-page=office]').click()")
    ok = _click_and_watch(window, "run-excel", "Excel: 10 qatorli jadval", steps=6, checks=7)
    dash = _click_and_watch(window, "run-dashboard", "Excel: savdo dashboardi", steps=8, checks=14)
    word = _click_and_watch(window, "run-word", "Word: rasmiy hisobot", steps=8, checks=15)
    ppt = _click_and_watch(window, "run-ppt", "PowerPoint: taqdimot", steps=8, checks=11)
    return ok and dash and word and ppt


def _click_and_watch(
    window: webview.Window, button: str, title: str, steps: int, checks: int
) -> bool:
    js = window.evaluate_js
    # Wait until the button is enabled (a previous task may still be finishing).
    deadline = time.monotonic() + 30
    while js(f"document.getElementById('{button}').disabled") and time.monotonic() < deadline:
        time.sleep(0.3)
    js(f"document.getElementById('{button}').click()")
    status = ""
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        time.sleep(0.5)
        status = js("document.getElementById('task-status').className") or ""
        shown = js("document.getElementById('task-title').textContent") or ""
        if shown == title and any(s in status for s in ("succeeded", "failed", "cancelled")):
            break
    steps_ok = js("document.querySelectorAll('#task-steps li.succeeded').length")
    checks_ok = js("document.querySelectorAll('#task-result .check.ok').length")
    checks_bad = js("document.querySelectorAll('#task-result .check.bad').length")
    error = js("document.getElementById('task-error').textContent")
    ok = "succeeded" in status and steps_ok == steps and checks_ok == checks and checks_bad == 0
    print(
        f"SELFTEST {'PASS' if ok else 'FAIL'} [{button}]: status={status!r} steps_ok={steps_ok} "
        f"checks_ok={checks_ok} checks_bad={checks_bad} error={error!r}"
    )
    return ok


if __name__ == "__main__":
    sys.exit(main())
