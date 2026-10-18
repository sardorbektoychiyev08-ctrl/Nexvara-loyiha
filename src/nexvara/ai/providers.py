"""Provider adapters with one shape: complete(...) -> Reply, list_models() -> ids.

Anthropic goes through the official SDK. OpenAI, Gemini and DeepSeek all serve the
OpenAI "chat/completions" format, so one small HTTPS client covers the three.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from nexvara.core.task import UserError

TIMEOUT = 180.0
VISION = ("openai", "gemini", "anthropic", "deepseek")


def _images(messages: list[dict[str, Any]]) -> bool:
    return any(m.get("images") for m in messages)


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
    """A provider call failed; the message is shown to the user (never contains the key).

    `retryable`: the provider was busy, down or unreachable — another provider may answer
    (the router's fallback). Wrong key, no credit or a bad request are not retryable."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        from nexvara.ai.keys import redact

        super().__init__(redact(message))  # a provider may echo part of the key back
        self.retryable = retryable


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
            return AiError(
                "Anthropic: so‘rovlar chegarasi. Birozdan keyin qayta urinib ko‘ring.",
                retryable=True,
            )
        if isinstance(e, a.BadRequestError):
            msg = str(getattr(e, "message", e))
            if "credit" in msg.lower() or "billing" in msg.lower():
                return AiError("Anthropic hisobida mablag‘ yetarli emas (Billing bo‘limi).")
            return AiError(f"Anthropic so‘rovni qabul qilmadi: {msg}")
        if isinstance(e, a.APIStatusError):
            return AiError(
                f"Anthropic serverida xato ({e.status_code}). Keyinroq urinib ko‘ring.",
                retryable=e.status_code >= 500,
            )
        if isinstance(e, a.APIConnectionError):
            return AiError("Internetga ulanib bo‘lmadi (Anthropic).", retryable=True)
        return AiError(f"Anthropic: {e}")

    def complete(self, model, system, messages, max_tokens, effort="medium") -> Reply:
        sdk_messages = []
        for m in messages:  # a photo goes as a base64 image block before the text
            if m.get("images"):
                blocks: list[dict[str, Any]] = [
                    {"type": "image", "source": {"type": "base64", "media_type": i["mime"],
                                                 "data": i["data"]}}
                    for i in m["images"]
                ]  # fmt: skip
                blocks.append({"type": "text", "text": m["content"]})
                sdk_messages.append({"role": m["role"], "content": blocks})
            else:
                sdk_messages.append({"role": m["role"], "content": m["content"]})
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": sdk_messages,
            "output_config": {"effort": effort},
        }
        try:
            # The provider's server-side fallback may silently change the selected
            # model. NEXVARA owns that decision, especially in MANUAL mode.
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
        return [m["id"] for m in self.list_model_details()]

    def list_model_details(self) -> list[dict[str, Any]]:
        try:
            # The SDK iterator traverses all pages; do not silently stop at 20/100.
            return [m.model_dump() for m in self.client.models.list(limit=100)]
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
                if e.code == 429 and "limit: 0" in detail:  # the model has no free tier
                    raise AiError(
                        f"{label}: bu model hisobingizning bepul darajasida (Free Tier) "
                        "ishlamaydi — limit 0. Pullik model uchun AI Studio → Billing kerak; "
                        "NEXVARA boshqa ulangan AI’dan foydalanishi mumkin.",
                        retryable=True,
                    ) from e
                if (e.code == 429 or e.code >= 500) and attempt < 2:
                    wait = e.headers.get("retry-after") if e.headers else None
                    try:
                        delay = min(float(wait), 30.0) if wait else 0.0
                    except ValueError:
                        delay = 0.0
                    time.sleep(delay or (2**attempt + random.random()))
                    continue
                if e.code == 429:
                    raise AiError(
                        f"{label}: so‘rovlar chegarasi yoki kvota tugagan.", retryable=True
                    ) from e
                if e.code == 404:
                    raise AiError(f"{label}: model topilmadi. {detail}".strip()) from e
                raise AiError(
                    f"{label} xatosi ({e.code}): {detail or e.reason}", retryable=e.code >= 500
                ) from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise AiError(f"Internetga ulanib bo‘lmadi ({label}).", retryable=True) from e
        raise AiError(f"{label}: javob olinmadi")

    def complete(self, model, system, messages, max_tokens, effort="medium") -> Reply:
        if _images(messages) and self.name not in VISION:
            label = _LABEL.get(self.name, self.name)
            raise AiError(
                f"{label} rasmni o‘qiy olmaydi: OpenAI, Gemini yoki Claude kalitini ulang."
            )
        if any(m.get("audio") for m in messages) and self.name != "gemini":
            raise AiError(
                f"{_LABEL.get(self.name, self.name)} ovozni tinglay olmaydi: Gemini kerak."
            )
        wire = []
        for m in messages:
            if m.get("audio"):  # Gemini (OpenAI-compatible endpoint): a spoken command
                a = m["audio"]
                fmt = "wav" if "wav" in a["mime"] else a["mime"].split("/")[-1]
                wire.append({"role": m["role"], "content": [
                    {"type": "text", "text": m["content"]},
                    {"type": "input_audio", "input_audio": {"data": a["data"], "format": fmt}},
                ]})  # fmt: skip
            elif m.get("images"):
                parts: list[dict[str, Any]] = [{"type": "text", "text": m["content"]}]
                parts += [{"type": "image_url",
                           "image_url": {"url": f"data:{i['mime']};base64,{i['data']}"}}
                          for i in m["images"]]  # fmt: skip
                wire.append({"role": m["role"], "content": parts})
            else:
                wire.append({"role": m["role"], "content": m["content"]})
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "system", "content": system}, *wire],
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
        ids = [m.get("id", m.get("name", "")) for m in self.list_model_details()]
        return [i.removeprefix("models/") for i in ids if i]

    def list_model_details(self) -> list[dict[str, Any]]:
        if self.name != "gemini":
            return [m for m in self._request("GET", "/models").get("data", [])
                    if isinstance(m, dict)]  # fmt: skip
        # The Gemini OpenAI-compatible endpoint does not expose the full native
        # model catalogue. Its native list endpoint is paginated and read-only.
        rows: list[dict[str, Any]] = []
        page = ""
        for _ in range(20):
            query = {"pageSize": "1000"}
            if page:
                query["pageToken"] = page
            url = "https://generativelanguage.googleapis.com/v1beta/models?" + (
                urllib.parse.urlencode(query)
            )
            req = urllib.request.Request(
                url, headers={"x-goog-api-key": self.key, "User-Agent": "NEXVARA"}
            )
            try:
                with self._open(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                raise AiError(
                    f"Gemini model ro‘yxati olinmadi ({e.code}).",
                    retryable=e.code == 429 or e.code >= 500,
                ) from e
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                raise AiError(
                    "Gemini model ro‘yxati olinmadi: internetni tekshiring.", retryable=True
                ) from e
            rows.extend(m for m in data.get("models", []) if isinstance(m, dict))
            page = str(data.get("nextPageToken") or "")
            if not page:
                return rows
        raise AiError("Gemini model ro‘yxati to‘liq olinmadi.")


def fetch_balance(name: str, key: str, opener=None) -> dict[str, Any]:
    """The provider's real account balance, only where an official endpoint exists for a
    normal API key (DeepSeek: GET /user/balance). Free: no model is called."""
    if name != "deepseek":
        return {"supported": False}
    data = ChatCompletionsProvider("deepseek", key, opener=opener)._request("GET", "/user/balance")
    infos = []
    for b in data.get("balance_infos") or []:
        try:
            infos.append({"currency": str(b.get("currency", "")),
                          "total": float(b.get("total_balance") or 0),
                          "granted": float(b.get("granted_balance") or 0),
                          "topped_up": float(b.get("topped_up_balance") or 0)})  # fmt: skip
        except (TypeError, ValueError):
            continue
    return {"supported": True, "available": bool(data.get("is_available")), "balances": infos,
            "checked_at": time.time()}  # fmt: skip


def make_provider(name: str, key: str) -> Provider:
    if name == "anthropic":
        return AnthropicProvider(key)
    if name in _BASE:
        return ChatCompletionsProvider(name, key)
    raise ValueError(f"noma’lum provayder: {name}")
