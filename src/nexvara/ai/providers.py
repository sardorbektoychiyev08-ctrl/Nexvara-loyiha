"""Provider adapters with one shape: complete(...) -> Reply, list_models() -> ids.

Anthropic goes through the official SDK. OpenAI, Gemini and DeepSeek all serve the
OpenAI "chat/completions" format, so one small HTTPS client covers the three.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from nexvara.core.task import UserError

TIMEOUT = 180.0


@dataclass
class Reply:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str = ""
    cost: float = 0.0
    provider: str = ""


class AiError(UserError):
    """A provider call failed; the message is shown to the user."""


class Provider:
    name = ""

    def complete(
        self,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        effort: str = "medium",
    ) -> Reply:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        raise NotImplementedError


# ---------------- Anthropic ----------------

# Opus/Sonnet 5.5 can hand a refused request to another model server-side.
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, key: str) -> None:
        import anthropic

        self._sdk = anthropic
        self.client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT, max_retries=2)

    def _errors(self, e: Exception) -> AiError:
        a = self._sdk
        if isinstance(e, a.AuthenticationError):
            return AiError("Anthropic API kaliti noto‘g‘ri yoki o‘chirilgan.")
        if isinstance(e, a.PermissionDeniedError):
            return AiError("Bu Anthropic kalitiga ruxsat yo‘q (hisobni tekshiring).")
        if isinstance(e, a.NotFoundError):
            return AiError("Anthropic: model topilmadi.")
        if isinstance(e, a.RateLimitError):
            return AiError("Anthropic: so‘rovlar chegarasi. Birozdan keyin qayta urinib ko‘ring.")
        if isinstance(e, a.BadRequestError):
            msg = str(getattr(e, "message", e))
            if "credit" in msg.lower() or "billing" in msg.lower():
                return AiError("Anthropic hisobida mablag‘ yetarli emas (Billing bo‘limi).")
            return AiError(f"Anthropic so‘rovni qabul qilmadi: {msg}")
        if isinstance(e, a.APIStatusError):
            return AiError(f"Anthropic serverida xato ({e.status_code}). Keyinroq urinib ko‘ring.")
        if isinstance(e, a.APIConnectionError):
            return AiError("Internetga ulanib bo‘lmadi (Anthropic).")
        return AiError(f"Anthropic: {e}")

    def complete(self, model, system, messages, max_tokens, effort="medium") -> Reply:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": effort},
        }
        try:
            if model in _FALLBACK_MODELS:
                r = self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                r = self.client.messages.create(**kwargs)
        except self._sdk.APIError as e:
            raise self._errors(e) from e
        if r.stop_reason == "refusal":
            raise AiError("AI bu so‘rovni bajarishdan bosh tortdi.")
        text = "".join(b.text for b in r.content if b.type == "text")
        u = r.usage
        tokens_in = (
            u.input_tokens
            + (getattr(u, "cache_creation_input_tokens", 0) or 0)
            + (getattr(u, "cache_read_input_tokens", 0) or 0)
        )
        return Reply(text, r.model, tokens_in, u.output_tokens, r.stop_reason or "", 0.0, self.name)

    def list_models(self) -> list[str]:
        try:
            return [m.id for m in self.client.models.list(limit=100)]
        except self._sdk.APIError as e:
            raise self._errors(e) from e


# ---------------- OpenAI-format providers ----------------

_BASE = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "deepseek": "https://api.deepseek.com",
}
_LABEL = {"openai": "OpenAI", "gemini": "Gemini", "deepseek": "DeepSeek"}


class ChatCompletionsProvider(Provider):
    def __init__(self, name: str, key: str, base_url: str | None = None, opener=None) -> None:
        self.name = name
        self.key = key
        self.base = (base_url or _BASE[name]).rstrip("/")
        self._open = opener or urllib.request.urlopen

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        label = _LABEL.get(self.name, self.name)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(3):
            req = urllib.request.Request(
                self.base + path,
                data=data,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                    "User-Agent": "NEXVARA",
                },
            )
            try:
                with self._open(req, timeout=TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = json.loads(e.read().decode("utf-8", "replace")).get("error", {})
                    detail = detail.get("message", "") if isinstance(detail, dict) else str(detail)
                except (ValueError, AttributeError, OSError):
                    pass
                if e.code in (401, 403):
                    raise AiError(f"{label} API kaliti noto‘g‘ri yoki ruxsat yo‘q.") from e
                if e.code == 402:
                    raise AiError(f"{label} hisobida mablag‘ yetarli emas.") from e
                if (e.code == 429 or e.code >= 500) and attempt < 2:
                    wait = e.headers.get("retry-after") if e.headers else None
                    try:
                        delay = min(float(wait), 30.0) if wait else 0.0
                    except ValueError:
                        delay = 0.0
                    time.sleep(delay or (2**attempt + random.random()))
                    continue
                if e.code == 429:
                    raise AiError(f"{label}: so‘rovlar chegarasi yoki kvota tugagan.") from e
                if e.code == 404:
                    raise AiError(f"{label}: model topilmadi. {detail}".strip()) from e
                raise AiError(f"{label} xatosi ({e.code}): {detail or e.reason}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise AiError(f"Internetga ulanib bo‘lmadi ({label}).") from e
        raise AiError(f"{label}: javob olinmadi")

    def complete(self, model, system, messages, max_tokens, effort="medium") -> Reply:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if self.name == "openai":
            body["max_completion_tokens"] = max_tokens
            body["reasoning_effort"] = {"max": "high", "xhigh": "high"}.get(effort, effort)
        else:
            body["max_tokens"] = max_tokens
        data = self._request("POST", "/chat/completions", body)
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as e:
            raise AiError("AI javobi tushunarsiz formatda keldi.") from e
        usage = data.get("usage") or {}
        return Reply(
            text,
            data.get("model", model),
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            choice.get("finish_reason") or "",
            0.0,
            self.name,
        )

    def list_models(self) -> list[str]:
        data = self._request("GET", "/models")
        ids = [m.get("id", "") for m in data.get("data", [])]
        return [i.removeprefix("models/") for i in ids if i]


def make_provider(name: str, key: str) -> Provider:
    if name == "anthropic":
        return AnthropicProvider(key)
    if name in _BASE:
        return ChatCompletionsProvider(name, key)
    raise ValueError(f"noma’lum provayder: {name}")
