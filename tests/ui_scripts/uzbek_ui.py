"""Every page of the real window, in dark and light theme: the visible text is Uzbek.

Collects what the user can see on each of the 12 sections (text, buttons, placeholders,
tooltips, select options) after the page has rendered, and reports the share of text pieces
without English words. PASS = 0 English pieces, no JS errors, both themes applied.
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
tmp = tempfile.mkdtemp(prefix="nexvara-ui-")
os.environ["NEXVARA_DATA"] = tmp

import webview  # noqa: E402
from tests.uzbek_check import english_words  # noqa: E402

from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402

api = Api(persist=True)
win = webview.create_window(
    "NEXVARA-E2E", url=str(UI_DIR / "index.html"), js_api=api, width=1300, height=780
)
ready = threading.Event()
win.events.loaded += lambda: ready.set()
res = {"pages": {}, "english": [], "pieces": 0}

COLLECT = """
(() => {
  const page = document.querySelector('.page.active');
  const out = [];
  const visible = (e) => e.offsetParent !== null || e.tagName === 'OPTION';
  for (const scope of [page, document.querySelector('.sidebar'), document.querySelector('.panel')]) {
    if (!scope) continue;
    (scope.innerText || '').split('\\n').map((s) => s.trim()).filter(Boolean).forEach((s) => out.push(s));
    scope.querySelectorAll('[placeholder],[title],[aria-label]').forEach((e) => {
      if (!visible(e)) return;
      ['placeholder', 'title', 'aria-label'].forEach((a) => { const v = e.getAttribute(a); if (v) out.push(v); });
    });
    scope.querySelectorAll('option').forEach((o) => out.push(o.textContent.trim()));
  }
  return JSON.stringify(out);
})()
"""


def run():
    try:
        ready.wait(90)
        end = time.monotonic() + 90
        while time.monotonic() < end and not str(win.evaluate_js(
                "document.getElementById('version').textContent")).startswith("NEXVARA v"):  # fmt: skip
            time.sleep(0.3)
        pages = json.loads(win.evaluate_js(
            "JSON.stringify([...document.querySelectorAll('.nav-item')].map(b => b.dataset.page))"))  # fmt: skip
        for theme in ("dark", "light"):
            win.evaluate_js(f"setTheme('{theme}', false)")
            res[f"theme_{theme}"] = win.evaluate_js("document.documentElement.dataset.theme")
            for page in pages:
                win.evaluate_js(f"document.querySelector('.nav-item[data-page={page}]').click()")
                time.sleep(1.2)  # let the page fill itself from the API
                pieces = json.loads(win.evaluate_js(COLLECT) or "[]")
                res["pages"][page] = len(pieces)
                res["pieces"] += len(pieces)
                for s in pieces:
                    bad = english_words(s)
                    if bad:
                        res["english"].append({"page": page, "theme": theme, "text": s[:160],
                                               "words": bad})  # fmt: skip
        res["errors"] = json.loads(win.evaluate_js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
unique = {(e["page"], e["text"]) for e in res["english"]}
total = max(1, res["pieces"])
res["uzbek_percent"] = round(100 * (1 - len(res["english"]) / total), 2)
print(json.dumps({k: v for k, v in res.items() if k != "english"}, ensure_ascii=False, indent=1))
for page, text in sorted(unique):
    print("INGLIZCHA:", page, "|", text)
ok = (not res["english"] and not res.get("errors") and res.get("theme_dark") == "dark"
      and res.get("theme_light") == "light" and len(res["pages"]) == 12)  # fmt: skip
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
