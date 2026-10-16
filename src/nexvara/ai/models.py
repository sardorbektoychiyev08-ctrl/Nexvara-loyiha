"""Providers, model tiers and prices (USD per 1M tokens: input, output).

Anthropic prices are the official list (2026-10). The others come from public price lists
and may drift; the user can override any price in settings.json ("ai" -> "prices").
"""

from __future__ import annotations

TIERS = ("cheap", "balanced", "powerful")
TIER_LABELS = {"cheap": "Arzon", "balanced": "O‘rtacha", "powerful": "Kuchli"}

PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "key_url": "https://console.anthropic.com/settings/keys",
        "key_hint": "sk-ant-...",
        "tiers": {
            "cheap": "claude-haiku-5-5",
            "balanced": "claude-sonnet-5-5",
            "powerful": "claude-opus-5-5",
        },
    },
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "key_url": "https://platform.openai.com/api-keys",
        "key_hint": "sk-...",
        "tiers": {"cheap": "gpt-5.4-nano", "balanced": "gpt-5.4", "powerful": "gpt-5.5"},
    },
    "gemini": {
        "label": "Google Gemini",
        "key_url": "https://aistudio.google.com/apikey",
        "key_hint": "AIza...",
        "tiers": {
            "cheap": "gemini-3.1-flash-lite",
            "balanced": "gemini-3.5-flash",
            "powerful": "gemini-3.1-pro",
        },
    },
    "deepseek": {
        "label": "DeepSeek",
        "key_url": "https://platform.deepseek.com/api_keys",
        "key_hint": "sk-...",
        "tiers": {
            "cheap": "deepseek-v4-flash",
            "balanced": "deepseek-v4-flash",
            "powerful": "deepseek-v4-pro",
        },
    },
}

PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-1": (10.00, 50.00),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.5": (5.00, 30.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3-flash": (0.50, 3.00),
    "gemini-3.1-pro": (2.00, 12.00),
    "deepseek-v4-flash": (0.14, 0.28),
    "deepseek-v4-pro": (0.55, 2.19),
}

# Unknown model: assume the provider's most expensive listed price (never under-count).
_FALLBACK = {
    "anthropic": (10.00, 50.00),
    "openai": (30.00, 180.00),
    "gemini": (4.00, 18.00),
    "deepseek": (0.55, 2.19),
}


def price(model: str, provider: str = "", overrides: dict | None = None) -> tuple[float, float]:
    """Per-1M prices; the longest known prefix wins ("gemini-3.1-pro-preview" -> gemini-3.1-pro)."""
    table = {**PRICES, **{k: tuple(v) for k, v in (overrides or {}).items()}}
    best = ""
    for name in table:
        if model.startswith(name) and len(name) > len(best):
            best = name
    if best:
        return table[best]  # type: ignore[return-value]
    return _FALLBACK.get(provider, (30.00, 180.00))


def cost(model: str, provider: str, input_tokens: int, output_tokens: int, overrides=None):
    p_in, p_out = price(model, provider, overrides)
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000


def pick_model(wanted: str, available: list[str]) -> str:
    """The wanted id, else its newest dated/preview variant ("gemini-3.1-pro-preview-06"),
    else the wanted id unchanged (the provider will say if it does not exist)."""
    if not available or wanted in available:
        return wanted
    variants = sorted(a for a in available if a.startswith(wanted))
    if variants:
        return variants[-1]
    return wanted


def estimate_tokens(text: str) -> int:
    """Uzbek Latin splits into more tokens than English; ~3 characters per token is safe."""
    return max(1, len(text) // 3)
