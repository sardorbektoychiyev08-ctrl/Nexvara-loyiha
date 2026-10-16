"""NEXVARA desktop shell.

python -m nexvara.app.main            # open the app
python -m nexvara.app.main --smoke    # open, check the UI rendered, close (exit code 0/1)
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path

import webview

from nexvara import __version__
from nexvara.app.api import Api

UI_DIR = Path(__file__).parent / "ui"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nexvara")
    parser.add_argument("--smoke", action="store_true", help="open, verify the UI, close")
    parser.add_argument(
        "--selftest-excel",
        metavar="DIR",
        type=Path,
        help="smoke test, then press the real Excel button (drives Excel on screen)",
    )
    parser.add_argument("--debug", action="store_true", help="enable WebView dev tools")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    selftest = args.selftest_excel is not None
    if selftest:
        args.smoke = True
        args.selftest_excel.mkdir(parents=True, exist_ok=True)
        api = Api(output_dir=args.selftest_excel.resolve(), keep_office_open=False)
    else:
        api = Api()
    window = webview.create_window(
        "NEXVARA",
        url=str(UI_DIR / "index.html"),
        js_api=api,
        width=1320,
        height=820,
        min_size=(980, 620),
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
            print(f"SMOKE {'PASS' if ok else 'FAIL'}: nav_items={nav} version={version!r}")
            if ok and selftest:
                ok = excel_button_selftest(window)
            result["ok"] = ok
        finally:
            window.destroy()

    webview.start(smoke if args.smoke else None, debug=args.debug)
    return 0 if result["ok"] else 1


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
