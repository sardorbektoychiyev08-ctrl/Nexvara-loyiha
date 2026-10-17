"""First real AI test for one provider — synthetic texts only, NEXVARA's own limits apply.

    .venv\\Scripts\\python.exe scripts\\ai_live_test.py openai              # dry run: estimate only
    .venv\\Scripts\\python.exe scripts\\ai_live_test.py gemini
    .venv\\Scripts\\python.exe scripts\\ai_live_test.py openai --run --i-approve   # real, paid

The dry run sends nothing. A real run needs both flags, a key saved in NEXVARA Settings → AI
and "AI yoqilgan"; it never turns AI on, never uses fallback (one provider only) and stops at
the first error. The texts contain no personal data (the privacy guard must find none). The
limits are NEXVARA's own (settings.json), not the provider's real spending cap.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nexvara.ai import features, models  # noqa: E402
from nexvara.ai.privacy import Guard  # noqa: E402
from nexvara.ai.router import AiRouter  # noqa: E402

# Synthetic, no names, numbers or addresses of real people.
TESTS = [
    ("chat", "cheap", "Salom! Bir jumlada o‘zingni tanishtir."),
    ("plan", "balanced", "Hisobot.xlsx ni PDF qilib saqla, keyin uni Arxiv papkasiga ko‘chir"),
    ("plan", "balanced", "sinov fayllari papkasidagi excel fayllarni top"),
    ("qa", "balanced", "Fotosintez nima? Ikki jumlada o‘zbekcha tushuntir."),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("provider", choices=["openai", "gemini", "anthropic", "deepseek"])
    ap.add_argument("--run", action="store_true", help="really call the provider (paid)")
    ap.add_argument("--i-approve", action="store_true", help="the owner approved the spend")
    a = ap.parse_args()
    r = AiRouter()
    cfg = r.config()
    for _purpose, _tier, text in TESTS:
        g = Guard()
        g.mask(text)
        if g.count:
            print("XATO: sinov matnida shaxsiy ma’lumot topildi — to‘xtatildi")
            return 2
    total = 0.0
    print(f"Provayder: {models.PROVIDERS[a.provider]['label']}")
    for purpose, tier, text in TESTS:
        model = (cfg.get("models") or {}).get(a.provider, {}).get(tier) \
            or models.PROVIDERS[a.provider]["tiers"][tier]  # fmt: skip
        est_in = models.estimate_tokens(text) + (2000 if purpose == "plan" else 300)
        c = models.cost(model, a.provider, est_in, 400, cfg.get("prices"))
        total += c
        print(f"  {purpose:5} {model:28} ≈ ${c:.4f}  «{text[:50]}»")
    lim = (cfg.get("limits") or {}).get(a.provider) or {}
    print(f"Jami taxmin: ≈ ${total:.4f}. NEXVARA limitlari: kunlik "
          f"${lim.get('daily_usd') or cfg['daily_budget_usd']}, bitta topshiriq "
          f"${lim.get('task_usd') or cfg['task_limit_usd']} "
          "(provayderdagi haqiqiy chegara emas).")  # fmt: skip
    if not a.run:
        print("Quruq rejim: hech narsa yuborilmadi.")
        return 0
    if not a.i_approve:
        print("Haqiqiy sinov uchun egasining ruxsati kerak: --i-approve")
        return 3
    if not r.keys.load(a.provider):
        print("Kalit yo‘q: NEXVARA → Sozlamalar → AI → «Kalitni tekshirish va saqlash».")
        return 4
    if not cfg.get("enabled"):
        print("AI o‘chiq: Sozlamalar → AI → «AI yoqilgan» ni o‘zingiz yoqing.")
        return 5
    r.settings.update({"ai": {"provider": a.provider}})
    cfg_fb = r.config().get("fallback")
    if cfg_fb:
        print("Fallback yoqilgan — birinchi sinov uchun o‘chiring (Sozlamalar → AI).")
        return 6
    spent0 = r.ledger.today(a.provider)
    for purpose, _tier, text in TESTS:
        t0 = time.monotonic()
        if purpose == "plan":
            from nexvara.agent import tools

            p = features.plan(r, text, tools.catalog(), {}, [], approved=False)
            out = f"reja: {[c.get('tool') for c in p.calls] or p.kind}"
        elif purpose == "qa":
            out = r.complete("qa", "Qisqa javob ber.", [{"role": "user", "content": text}],
                             max_tokens=600).text  # fmt: skip
        else:
            out = r.complete("chat", "Qisqa javob ber.", [{"role": "user", "content": text}],
                             max_tokens=300).text  # fmt: skip
        row = r.ledger.recent(1)[0]
        print(f"  ✓ {purpose:5} {row['model']} {row['input_tokens']}+{row['output_tokens']} token, "
              f"${row['cost']:.4f}, {time.monotonic() - t0:.1f} s → {out[:90]!r}")  # fmt: skip
    print(f"Bugun shu provayderga (taxminiy): ${r.ledger.today(a.provider) - spent0:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
