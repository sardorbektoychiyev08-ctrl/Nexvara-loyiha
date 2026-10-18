"""Chat tools in a real window with fake AI providers (nothing leaves the PC, nothing is paid):
🧠 AUTO/MANUAL menu, ✨ picture after «Ha», 🔊 spoken answers, 🖼️ photo pick, 🎧/🎤/📷 present."""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="nexvara-ui-media-"))
os.environ["NEXVARA_DATA"] = str(tmp / "data")
sys.path.insert(0, str(Path(__file__).parents[1] / "unit"))

import webview  # noqa: E402
from test_ai_media import KEYS, PNG, make  # noqa: E402

from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402

router = make(tmp, KEYS)
api = Api(overrides={"ai_router": router})
photo = tmp / "doska.png"
photo.write_bytes(PNG)
api.pick_image = lambda: (api.set_context_file(str(photo)), {"path": str(photo)})[1]
win = webview.create_window("NEXVARA media", url=str(UI_DIR / "index.html"), js_api=api,
                            width=1300, height=820)  # fmt: skip
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {}


def wait_for(js, timeout=20):
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
        js("document.querySelector('.nav-item[data-page=chat]').click()")
        ids = ["chat-mic", "chat-speak", "chat-image", "chat-camera", "chat-gen", "chat-live",
               "chat-models"]  # fmt: skip
        probe = (
            "JSON.stringify(IDS.map(i => { const b = document.getElementById(i); "
            "return !!b && b.offsetParent !== null; }))"
        ).replace("IDS", json.dumps(ids))
        res["buttons"] = json.loads(js(probe))
        # 🧠 menu: six directions; switch TTS to OpenAI by hand
        js("document.getElementById('chat-models').click()")
        res["rows"] = wait_for("document.querySelectorAll('.caps-pop .cap-row').length >= 7 && "
                               "document.querySelectorAll('.caps-pop .cap-row').length")  # fmt: skip
        js("""(() => { const row = [...document.querySelectorAll('.caps-pop .cap-row')]
              .find(r => r.textContent.includes('Matn → ovoz'));
              const [mode, prov, model] = row.querySelectorAll('select');
              mode.value = 'manual'; mode.dispatchEvent(new Event('change'));
              prov.value = 'openai'; prov.dispatchEvent(new Event('change')); })()""")
        time.sleep(1.5)
        res["tts_manual"] = router.cap_settings()["tts"]
        js("document.querySelector('.caps-pop .btn').click()")
        # 🔊 on, then a chat answer is spoken through the chosen TTS (paid: «Ha» to the price)
        js("window.confirm = () => true")
        js("document.getElementById('chat-speak').click()")
        time.sleep(0.8)
        res["speak_saved"] = router.config().get("speak_replies")
        js(
            "document.getElementById('chat-text').value = 'salom'; document.getElementById('chat-form').requestSubmit()"
        )
        res["spoken"] = wait_for("true") and any(x[1] == "tts" for x in _wait_log("tts"))
        # ✨ picture: price first, then «Ha», then the picture in the chat
        js("document.getElementById('chat-speak').click()")
        js("window.confirm = () => false; document.getElementById('chat-text').value = 'qishki maktab hovlisi';"
           "document.getElementById('chat-gen').click()")  # fmt: skip
        res["log_after_gen"] = js("document.getElementById('chat-log').innerText.slice(-600)")
        res["asked"] = wait_for("document.querySelector('.confirm-row .btn.primary') !== null")
        res["no_call_before_yes"] = not any(x[1] == "image" for x in router.log)
        js("[...document.querySelectorAll('.confirm-row .btn.primary')].pop().click()")
        res["image_shown"] = wait_for("document.querySelector('.ai-image img') && "
                                      "document.querySelector('.ai-image img').src.startsWith('data:image/png')")  # fmt: skip
        # 🖼️ photo from the PC becomes the chat's file
        js("document.getElementById('chat-image').click()")
        res["photo"] = wait_for(
            "document.getElementById('chat-file').textContent.endsWith('doska.png')"
        )
        res["settings_caps"] = wait_for(
            "document.querySelectorAll('#ai-caps-settings .cap-row').length"
        )
        res["errors"] = json.loads(js("JSON.stringify(window.__errors || [])"))
    except Exception as e:  # noqa: BLE001
        res["exception"] = repr(e)
    finally:
        win.destroy()


def _wait_log(kind, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if any(x[1] == kind for x in router.log):
            break
        time.sleep(0.2)
    return router.log


webview.start(run)
print(json.dumps(res, ensure_ascii=False, indent=1))
checks = {
    "seven_buttons": res.get("buttons") == [True] * 7,
    "menu_rows": (res.get("rows") or 0) >= 7,
    "tts_manual": (res.get("tts_manual") or {}).get("provider") == "openai",
    "speak": bool(res.get("speak_saved")) and bool(res.get("spoken")),
    "image_after_yes": bool(res.get("asked"))
    and res.get("no_call_before_yes")
    and bool(res.get("image_shown")),
    "photo": bool(res.get("photo")),
    "settings_caps": (res.get("settings_caps") or 0) >= 7,
    "no_js_errors": not res.get("errors") and "exception" not in res,
}
print(json.dumps(checks, indent=1))
print("MEDIA TOOLS", "PASS" if all(checks.values()) else "FAIL")
sys.exit(0 if all(checks.values()) else 1)
