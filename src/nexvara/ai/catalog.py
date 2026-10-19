"""Account model discovery and conservative, reviewed routing metadata.

Model IDs and lifecycle come from each provider's Models API. Prices and the
quality/capability labels that those APIs do not supply are reviewed snapshots;
unrecognised models are visible in the catalogue but never billed by AUTO.
"""

from __future__ import annotations

import time
from typing import Any

from nexvara.ai import capabilities as caps
from nexvara.ai import models

REFRESH_SECONDS = 24 * 60 * 60
PROVIDERS_API = {
    "openai": "https://developers.openai.com/api/reference/resources/models/methods/list",
    "gemini": "https://ai.google.dev/api/models",
    "anthropic": "https://platform.claude.com/docs/en/api/models/list",
    "deepseek": "https://api-docs.deepseek.com/api/list-models/",
}
QUALITY = {"cheap": 1, "balanced": 2, "powerful": 3, "special": 4}


_MEDIA_ONLY = ("-image", "-tts", "-transcribe", "-realtime", "-audio", "-live", "-embedding",
               "image-", "tts-", "whisper", "dall-e", "-search", "-moderation")  # fmt: skip


def tier_of(provider: str, model: str) -> str | None:
    # «gemini-3.1-flash-lite-image» starts like a chat model but only makes pictures;
    # TTS, transcription, realtime and embedding ids never answer a chat either.
    if any(caps.find(provider, c, model) for c in ("image", "stt", "tts")) and not any(
        model == r["model"] for r in caps.MEDIA.get(provider, {}).get("stt", [])
    ):
        return None
    if any(tag in model for tag in _MEDIA_ONLY):
        return None
    if provider == "deepseek" and model == "deepseek-flash":
        return "balanced"  # the same reviewed model is listed for cheap and balanced
    info = models.PROVIDERS[provider]
    # A canonical model may also appear as an older tier's fallback. Its own
    # quality label wins over that fallback entry.
    for tier in models.TIERS:
        name = info["tiers"][tier]
        if model == name or model.startswith(name + "-"):
            return tier
    for tier in models.TIERS:
        names = info.get("alternatives", {}).get(tier, [])
        if any(model == name or model.startswith(name + "-") for name in names):
            return tier
    return None


def directions(provider: str, model: str, detail: dict[str, Any] | None = None) -> list[str]:
    """Only features backed by the API metadata or a reviewed provider mapping."""
    detail = detail or {}
    offered = {c for c in ("image", "stt", "tts") if caps.find(provider, c, model)}
    if tier_of(provider, model) is not None:
        offered.add("text")
        modalities = detail.get("input_modalities")
        if isinstance(modalities, list):
            if "image" in modalities:
                offered.add("vision")
        elif provider in ("openai", "gemini", "anthropic") or (
            provider == "deepseek" and model == "deepseek-flash"
        ):
            offered.add("vision")
    return sorted(offered)


def normalize(provider: str, raw: list[str | dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in raw:
        detail = {"id": item} if isinstance(item, str) else dict(item)
        name = str(detail.get("id") or detail.get("name") or "").removeprefix("models/")
        if not name or len(name) > 160:
            continue
        lifecycle = str(detail.get("lifecycle") or detail.get("status") or "active")
        if detail.get("deprecated") is True:
            lifecycle = "deprecated"
        if lifecycle not in ("active", "deprecated", "retired"):
            lifecycle = "active"
        rows.append(
            {
                "id": name,
                "lifecycle": lifecycle,
                "directions": directions(provider, name, detail),
                "price_known": models.price(name, provider) is not None
                or any(
                    (found := caps.find(provider, cap, name)) is not None
                    and found.get("price") is not None
                    for cap in ("image", "stt", "tts")
                ),
            }
        )
    return sorted({r["id"]: r for r in rows}.values(), key=lambda r: r["id"])


def changed(previous: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    old = {r["id"] for r in previous.get("models") or [] if isinstance(r, dict) and r.get("id")}
    now = {r["id"] for r in rows}
    return {
        "added": sorted(now - old),
        "removed": sorted(old - now),
        "deprecated": sorted(r["id"] for r in rows if r["lifecycle"] != "active"),
    }


def stale(state: dict[str, Any], now: float | None = None) -> bool:
    return (now or time.time()) - float(state.get("checked_at") or 0) >= REFRESH_SECONDS


def by_direction(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    out = {c: [] for c in caps.CAPABILITIES}
    for row in rows:
        if row["lifecycle"] != "active":
            continue
        for cap in row["directions"]:
            out[cap].append(row["id"])
    out["realtime"] = ["stt+tts"] if out["stt"] and out["tts"] else []
    return out
