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
    parser.add_argument("--debug", action="store_true", help="enable WebView dev tools")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

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
            result["ok"] = ok
        finally:
            window.destroy()

    webview.start(smoke if args.smoke else None, debug=args.debug)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
