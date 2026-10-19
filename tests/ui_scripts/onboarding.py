"""First-start guide in a real window: shown on a new PC, 4 steps, finished once and remembered.
Nothing on this PC is changed (autostart unticked, no phone server, temporary data folder)."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-ui-onboard-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")

import webview  # noqa: E402

from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402

office = {"excel": True, "word": True, "powerpoint": False}
api = Api(overrides={"onboarding_force": True, "used_before": lambda: False,
                     "office_installed": lambda: office,
                     "firewall_status": lambda a: {"tailscale": "", "needed": False}})  # fmt: skip
win = webview.create_window("NEXVARA onboarding", url=str(UI_DIR / "index.html"), js_api=api,
                            width=1200, height=800)  # fmt: skip
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {}


def wait_for(js, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = win.evaluate_js(js)
        if v:
            return v
        time.sleep(0.2)
    return None


def run():
    try:
        ready.wait(90)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')", 90)
        js = win.evaluate_js
        js(
            "window.__errors = []; window.addEventListener('error', e => __errors.push(String(e.message)))"
        )
        res["shown"] = wait_for("!document.getElementById('onboard').hidden")
        res["office"] = json.loads(js("JSON.stringify([...document.querySelectorAll('#ob-office li')]"
                                      ".map(li => li.className))"))  # fmt: skip
        steps = []
        for _ in range(3):
            js("document.getElementById('ob-next').click()")
            time.sleep(0.4)
            steps.append(js("document.getElementById('ob-step').textContent"))
        res["steps"] = steps
        res["last_button"] = js("document.getElementById('ob-next').textContent")
        js("document.getElementById('ob-autostart').checked = false")  # never touch Windows here
        js("document.getElementById('ob-next').click()")
        res["closed"] = wait_for("document.getElementById('onboard').hidden")
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    except Exception as e:  # noqa: BLE001
        res["exception"] = repr(e)
    finally:
        win.destroy()


webview.start(run)
res["remembered"] = api.get_settings()["onboarding"]["done"]
res["not_again"] = api.onboarding_status() == {"show": False}
print(json.dumps(res, ensure_ascii=False, indent=1))
checks = {
    "shown": bool(res.get("shown")),
    "office": res.get("office") == ["ok", "ok", "bad"],
    "steps": res.get("steps") == ["2 / 4", "3 / 4", "4 / 4"]
    and res.get("last_button") == "Boshlash",
    "closed_and_remembered": bool(res.get("closed"))
    and res.get("remembered")
    and res.get("not_again"),
    "no_js_errors": not res.get("errors") and "exception" not in res,
}
print(json.dumps(checks, indent=1))
print("ONBOARDING", "PASS" if all(checks.values()) else "FAIL")
sys.exit(0 if all(checks.values()) else 1)
