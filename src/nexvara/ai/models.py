"""Providers, model tiers, official pages and prices (USD per 1M tokens: input, output).

Checked against the providers' official docs on 2026-10-17:
- Anthropic: platform.claude.com/docs (models, pricing, console pages);
- OpenAI: developers.openai.com/api/docs/pricing;
- Gemini: ai.google.dev/gemini-api/docs/models, /pricing, /billing;
- DeepSeek: api-docs.deepseek.com (models, pricing, Get User Balance).
Prices drift; the user can override any price in settings.json ("ai" -> "prices"). Where a
provider has a promotional or off-peak price, the regular/peak price is used here so the
budget is never under-counted. A tier model is only shown as working after the key check
finds it in the account's own model list (see `pick_model`).
"""

from __future__ import annotations

import re

TIERS = ("cheap", "balanced", "powerful", "special")
TIER_LABELS = {
    "cheap": "Tejamkor",
    "balanced": "Muvozanatli",
    "powerful": "Kuchli",
    "special": "Maxsus",
}
TIER_HELP = {
    "cheap": "oddiy, arzon vazifalar (buyruqni tushunish, qisqa javob)",
    "balanced": "kundalik suhbat va Office ishlari",
    "powerful": "murakkab topshiriq, tahlil va rejalashtirish",
    "special": "eng kuchli yoki ixtisoslashgan model — faqat so‘ralganda, doim tasdiq bilan",
}

PROVIDERS: dict[str, dict] = {
    "openai": {
        "label": "OpenAI",
        "key_url": "https://platform.openai.com/api-keys",
        "billing_url": "https://platform.openai.com/settings/organization/billing/overview",
        "usage_url": "https://platform.openai.com/usage",
        "key_hint": "sk-...",
        "balance_api": False,
        "free_tier": "Rasmiy doimiy bepul API kvotasi e’lon qilinmagan: API oldindan to‘langan "
        "kredit bilan ishlaydi.",
        "subscription_note": "ChatGPT Plus/Pro obunasi API krediti emas: API uchun "
        "platform.openai.com da alohida kredit kerak.",
        "tiers": {
            "cheap": "gpt-6-luna",
            "balanced": "gpt-6-sol",
            "powerful": "gpt-6.1-sol",
            "special": "gpt-6-astra",
        },  # fmt: skip
        # If the account does not have the tier model, the first available one is used.
        "alternatives": {
            "cheap": ["gpt-5.6-luna", "gpt-5.4-nano", "gpt-5-nano"],
            "balanced": ["gpt-6.1-sol", "gpt-5.6-terra", "gpt-5.4"],
            "powerful": ["gpt-6-sol", "gpt-5.6-sol", "gpt-5.5"],
            "special": ["gpt-6.1-sol", "gpt-5.5"],
        },
    },
    "anthropic": {
        "label": "Claude (Anthropic)",
        "key_url": "https://platform.claude.com/settings/keys",
        "billing_url": "https://platform.claude.com/settings/billing",
        "usage_url": "https://platform.claude.com/usage",
        "key_hint": "sk-ant-...",
        "balance_api": False,
        "free_tier": "Rasmiy doimiy bepul API kvotasi e’lon qilinmagan: Claude Console’da kredit "
        "sotib olinadi.",
        "subscription_note": "Claude Pro/Max obunasi API krediti emas: API uchun Claude Console’da "
        "alohida kredit kerak.",
        "tiers": {
            "cheap": "claude-haiku-5-5",
            "balanced": "claude-sonnet-5-5",
            "powerful": "claude-opus-5-5",
            "special": "claude-fable-5-1",
        },  # fmt: skip
        "alternatives": {
            "cheap": ["claude-haiku-4-5"],
            "balanced": ["claude-sonnet-5", "claude-sonnet-4-6"],
            "powerful": ["claude-opus-5", "claude-opus-4-8"],
            "special": ["claude-fable-5", "claude-opus-5-5"],
        },
    },
    "gemini": {
        "label": "Google Gemini",
        "key_url": "https://aistudio.google.com/api-keys",
        "billing_url": "https://aistudio.google.com/billing",
        "usage_url": "https://aistudio.google.com/usage",
        "key_hint": "AIza...",
        "balance_api": False,
        "free_tier": "Rasmiy bepul daraja bor: yangi hisoblar Free Tier’da boshlaydi, ba’zi "
        "modellar (Flash, Flash-Lite) model chegaralari doirasida bepul; Pro modelida bepul "
        "daraja yo‘q.",
        "subscription_note": "Google One / Gemini Advanced obunasi Gemini API krediti emas: API "
        "to‘lovi AI Studio → Billing’da.",
        "tiers": {
            "cheap": "gemini-3.5-flash-lite",
            "balanced": "gemini-3.8-flash",
            "powerful": "gemini-3.1-pro-preview",
            "special": "gemini-3.1-pro-preview-customtools",
        },  # fmt: skip
        "alternatives": {
            "cheap": ["gemini-3.1-flash-lite", "gemini-3.6-flash"],
            "balanced": ["gemini-3.6-flash", "gemini-3-flash-preview"],
            "powerful": ["gemini-3.8-flash"],
            "special": ["gemini-3.1-pro-preview"],
        },
    },
    "deepseek": {
        "label": "DeepSeek",
        "key_url": "https://platform.deepseek.com/api_keys",
        "billing_url": "https://platform.deepseek.com/",
        "usage_url": "https://platform.deepseek.com/",
        "key_hint": "sk-...",
        "balance_api": True,  # GET https://api.deepseek.com/user/balance (official)
        "free_tier": "Doimiy bepul kvota e’lon qilinmagan; hisobda berilgan (granted) balans "
        "bo‘lsa, u rasmiy balans so‘rovida alohida ko‘rinadi.",
        "subscription_note": "DeepSeek suhbat ilovasidan foydalanish API balansi emas: API uchun "
        "platform.deepseek.com da balans to‘ldiriladi.",
        "tiers": {
            "cheap": "deepseek-flash",
            "balanced": "deepseek-flash",
            "powerful": "deepseek-v4-pro",
            "special": "deepseek-v4-pro",
        },  # fmt: skip
        "alternatives": {
            "cheap": [],
            "balanced": [],
            "powerful": ["deepseek-flash"],
            "special": ["deepseek-flash"],
        },  # fmt: skip
    },
}

PRICES: dict[str, tuple[float, float]] = {
    # Anthropic (official list)
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    # OpenAI (standard tier, short context)
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-astra": (10.00, 50.00),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5-nano": (0.05, 0.40),
    # Gemini (paid tier, prompts <= 200k). 3.8 Flash: the regular price after the promo.
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (1.50, 7.50),
    "gemini-3.6-flash": (1.50, 7.50),
    "gemini-3-flash-preview": (1.50, 7.50),
    "gemini-3.1-pro-preview": (2.00, 12.00),
    # DeepSeek (cache miss, peak hours)
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-flash": (0.30, 1.20),  # legacy name, served by deepseek-flash
    "deepseek-v4-pro": (1.32, 3.96),
}

# These are checked snapshots of the standard API rate, not an inferred price from
# GET /models. Providers do not expose a public per-model pricing API. A new model
# remains unpriced until this table is checked against its official page.
PRICE_SOURCES = {
    "openai": "https://developers.openai.com/api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing/",
}
PRICES_CHECKED_ON = "2026-10-18"


def price(
    model: str, provider: str = "", overrides: dict | None = None
) -> tuple[float, float] | None:
    """Reviewed exact rate, also for a dated variant of that same model."""
    table = {**PRICES, **{k: tuple(v) for k, v in (overrides or {}).items()}}
    best = ""
    for name in table:
        suffix = model.removeprefix(name + "-") if model.startswith(name + "-") else ""
        dated = bool(re.fullmatch(r"\d{2,4}(?:-\d{2}){0,2}", suffix))
        if (model == name or dated) and len(name) > len(best):
            best = name
    if best:
        return table[best]  # type: ignore[return-value]
    return None


def cost(model: str, provider: str, input_tokens: int, output_tokens: int, overrides=None):
    known = price(model, provider, overrides)
    if known is None:
        raise ValueError(f"«{model}» uchun tasdiqlangan narx yo‘q")
    p_in, p_out = known
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000


def pick_model(wanted: str, available: list[str]) -> str:
    """The wanted id, else its newest dated/preview variant ("gemini-3.1-pro-preview-06"),
    else the wanted id unchanged (no list to check against)."""
    if not available or wanted in available:
        return wanted
    variants = sorted(a for a in available if a.startswith(wanted))
    if variants:
        return variants[-1]
    return wanted


def pick_tier(provider: str, tier: str, available: list[str]) -> str | None:
    """The tier's model if the account has it, else the first available alternative,
    else None (the tier is shown as unavailable instead of a model that would fail).
    Without a model list (it could not be read) the configured id is kept."""
    info = PROVIDERS[provider]
    if not available:
        return info["tiers"][tier]
    for cand in (info["tiers"][tier], *info.get("alternatives", {}).get(tier, [])):
        hit = pick_model(cand, available)
        if hit in available:
            return hit
    return None


def estimate_tokens(text: str) -> int:
    """Uzbek Latin splits into more tokens than English; ~3 characters per token is safe."""
    return max(1, len(text) // 3)
