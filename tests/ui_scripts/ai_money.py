"""Home "AI balans va xarajatlar" panel and the AI provider rows in Settings, real window.

Fake usage rows are written to a throwaway app.db (no AI call). Clicking a payment button
must ask for the provider's official page; the browser is not opened in this test.
"""

import json
import os
import sys
import tempfile
import threading
import time

tmp = tempfile.mkdtemp(prefix="nexvara-ui-")
os.environ["NEXVARA_DATA"] = tmp

import webview  # noqa: E402

from nexvara.ai.router import Ledger  # noqa: E402
from nexvara.app.api import Api  # noqa: E402
from nexvara.app.main import UI_DIR  # noqa: E402

led = Ledger()
led.record("deepseek", "deepseek-flash", "plan", 1200, 300, 0.0012)
led.record("anthropic", "claude-haiku-5-5", "classify", 900, 100, 0.0004)

api = Api(persist=True)
opened = []
api.open_url = lambda url: opened.append(url) or True  # never opens a browser here
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


def run():
    try:
        ready.wait(90)
        wait_for("document.getElementById('version').textContent.startsWith('NEXVARA v')", 90)
        js = win.evaluate_js
        res["cards"] = wait_for("document.querySelectorAll('#ai-money-cards .ai-card').length")
        res["labels"] = json.loads(
            js(
                "JSON.stringify([...document.querySelectorAll('#ai-money-cards h3')].map(h => h.firstChild.textContent))"
            )
        )
        res["deepseek_month"] = js(
            "[...document.querySelectorAll('#ai-money-cards .ai-card')].find(c => c.textContent.includes('DeepSeek')).textContent.includes('$0.0012')"
        )
        res["no_balance_api"] = js(
            "document.getElementById('ai-money-cards').textContent.split('Haqiqiy balansni avtomatik olish imkoni yo‘q').length - 1"
        )
        res["history_rows"] = js("document.querySelectorAll('#ai-money-history tr').length")
        res["chart"] = js("document.querySelectorAll('#ai-money-chart rect').length")
        res["estimated_note"] = js(
            "document.getElementById('ai-money').textContent.includes('taxminiy sarf')"
        )
        js(
            "[...document.querySelectorAll('#ai-money-cards .ai-card')].find(c => c.textContent.includes('Gemini')).querySelector('button').click()"
        )
        time.sleep(0.5)
        js("document.querySelector('.nav-item[data-page=settings]').click()")
        res["rows"] = wait_for("document.querySelectorAll('.ai-prov').length")
        res["pay_buttons"] = js(
            "[...document.querySelectorAll('.ai-prov button')].filter(b => b.textContent.startsWith('To‘lov / Balans')).length"
        )
        res["key_buttons"] = js(
            "[...document.querySelectorAll('.ai-prov button')].filter(b => b.textContent.startsWith('API kalitini olish')).length"
        )
        res["subscription_text"] = js(
            "document.getElementById('ai-card').textContent.includes('API krediti bilan bir xil emas')"
        )
        js(
            "[...[...document.querySelectorAll('.ai-prov')].find(r => r.textContent.includes('OpenAI')).querySelectorAll('button')].find(b => b.textContent.startsWith('To‘lov / Balans')).click()"
        )
        time.sleep(0.5)
        res["errors"] = json.loads(js("JSON.stringify(window.__errors)"))
    finally:
        win.destroy()


webview.start(run)
res["opened"] = opened
print(json.dumps(res, ensure_ascii=False, indent=1))
ok = (
    res.get("cards") == 4
    and res.get("labels") == ["OpenAI", "Claude (Anthropic)", "Google Gemini", "DeepSeek"]
    and res.get("deepseek_month")
    and res.get("no_balance_api") == 3
    and res.get("history_rows") == 3
    and res.get("chart") == 30
    and res.get("estimated_note")
    and res.get("rows") == 4
    and res.get("pay_buttons") == 4
    and res.get("key_buttons") == 4
    and res.get("subscription_text")
    and opened
    == [
        "https://aistudio.google.com/billing",
        "https://platform.openai.com/settings/organization/billing/overview",
    ]
    and not res.get("errors")
)
print("E2E", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
