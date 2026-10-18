"""What each provider can do besides text, and how AUTO / MANUAL picks a model per direction.

Directions (each set separately in settings.json "ai" -> "capabilities"):
  text      chat, commands, questions (the tier router: cheap/balanced/powerful/special)
  vision    reading a photo: questions about it, OCR
  image     making and editing pictures
  stt       speech -> text (the microphone)
  tts       text -> speech (the speaker button)
  realtime  hands-free spoken conversation (NEXVARA chains stt -> chat -> tts turn by turn;
            the providers' streaming Realtime/Live APIs are not used)

Model ids and prices were checked against the official pages on 2026-10-18:
- OpenAI: developers.openai.com/api/docs/pricing, guides/image-generation, text-to-speech,
  speech-to-text (Image API: /v1/images/generations and /edits; /v1/audio/speech;
  /v1/audio/transcriptions);
- Gemini: ai.google.dev/gemini-api/docs/models, /pricing, /image-generation,
  /speech-generation (Interactions API; image models have no free tier, TTS and Flash do).
Anthropic and DeepSeek have no image, speech or voice models; DeepSeek does not read images.
A model is offered only if the key check found it in the account's own model list.
"""

from __future__ import annotations

from typing import Any

CAPABILITIES = ("text", "vision", "image", "stt", "tts", "realtime")
CAP_LABELS = {
    "text": "Matn va suhbat",
    "vision": "Rasmni ko‘rish (Vision/OCR)",
    "image": "Rasm yaratish va tahrirlash",
    "stt": "Ovoz → matn (STT)",
    "tts": "Matn → ovoz (TTS)",
    "realtime": "Jonli ovozli suhbat",
}

# provider -> direction -> models, cheapest first. "price": USD per unit (see `unit`);
# "free": the provider's official free tier covers it (Gemini only).
MEDIA: dict[str, dict[str, list[dict[str, Any]]]] = {
    "openai": {
        "image": [
            # per 1024x1024 image, medium quality (official per-image table)
            {"model": "gpt-image-1-mini", "price": 0.011, "unit": "image"},
            {"model": "gpt-image-2", "price": 0.053, "unit": "image"},
            # 2.5 has no per-image table yet: counted at the highest listed price
            {"model": "gpt-image-2.5-flare", "price": 0.25, "unit": "image"},
            {"model": "gpt-image-2.5-sunburst", "price": 0.25, "unit": "image"},
        ],
        "stt": [
            {"model": "gpt-4o-mini-transcribe", "price": 0.003, "unit": "minute"},
            {"model": "gpt-transcribe", "price": 0.0045, "unit": "minute"},
            {"model": "whisper-1", "price": 0.006, "unit": "minute"},
        ],
        # $12 per 1M audio tokens; ~1 000 characters ≈ 1 minute ≈ 1 250 audio tokens
        "tts": [{"model": "gpt-4o-mini-tts", "price": 0.016, "unit": "minute"}],
        "vision": [],  # the text tier models read photos
    },
    "gemini": {
        "image": [
            {"model": "gemini-3.1-flash-lite-image", "price": 0.0336, "unit": "image"},
            {"model": "gemini-nano-banana-2.1", "price": 0.0336, "unit": "image"},
            {"model": "gemini-3.1-flash-image", "price": 0.067, "unit": "image"},
            {"model": "gemini-3-pro-image", "price": 0.134, "unit": "image"},
        ],
        # speech is listened to by the free Flash models (audio in a normal request)
        "stt": [
            {"model": "gemini-3.5-flash-lite", "price": 0.0, "unit": "minute", "free": True},
            {"model": "gemini-3.8-flash", "price": 0.0, "unit": "minute", "free": True},
        ],
        "tts": [
            {"model": "gemini-3.8-flash-lite-tts", "price": 0.009, "unit": "minute", "free": True},
            {"model": "gemini-3.8-flash-tts", "price": 0.0135, "unit": "minute", "free": True},
        ],  # fmt: skip
        "vision": [],
    },
    "anthropic": {"vision": []},
    "deepseek": {},
}
VISION_PROVIDERS = ("openai", "gemini", "anthropic")
# Default voices (official lists): OpenAI recommends marin/cedar; Gemini has 30 named voices.
VOICES = {
    "openai": ["marin", "cedar", "alloy", "ash", "ballad", "coral", "echo", "fable", "nova",
               "onyx", "sage", "shimmer", "verse"],
    "gemini": ["Kore", "Puck", "Charon", "Zephyr", "Fenrir", "Leda", "Orus", "Aoede"],
}  # fmt: skip


def supports(provider: str, cap: str) -> bool:
    if cap == "text":
        return True
    if cap == "vision":
        return provider in VISION_PROVIDERS
    if cap == "realtime":  # a turn-by-turn conversation needs both ears and a voice
        return supports(provider, "stt") and supports(provider, "tts")
    return bool(MEDIA.get(provider, {}).get(cap))


def models_for(provider: str, cap: str, available: list[str] | None = None) -> list[dict]:
    """The direction's models this account has (all of them when the list is unknown)."""
    rows = MEDIA.get(provider, {}).get(cap) or []
    if not available:
        return list(rows)
    out = []
    for r in rows:
        hit = next((a for a in available if a == r["model"] or a.startswith(r["model"] + "-")),
                   None)  # fmt: skip
        if hit:
            out.append({**r, "model": hit})
    return out


def find(provider: str, cap: str, model: str) -> dict | None:
    for r in MEDIA.get(provider, {}).get(cap) or []:
        if model == r["model"] or model.startswith(r["model"] + "-"):
            return {**r, "model": model}
    return None


def cost(row: dict, units: float) -> float:
    return 0.0 if row.get("free") else round(float(row["price"]) * max(units, 0.0), 6)


def default_settings() -> dict[str, dict[str, str]]:
    return {c: {"mode": "auto", "provider": "", "model": ""} for c in CAPABILITIES}
