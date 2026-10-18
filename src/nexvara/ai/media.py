"""Pictures and speech through the providers' official HTTPS APIs (no SDKs, no local models).

OpenAI: POST /v1/images/generations and /v1/images/edits (base64 in data[0].b64_json),
        POST /v1/audio/speech (audio bytes), POST /v1/audio/transcriptions (JSON "text").
Gemini: POST /v1beta/interactions (x-goog-api-key) — images (response_format "image") and
        speech (response_format "audio", WAV 24 kHz mono 16-bit); the base64 data is in a
        `steps[].content[]` block of type image/audio (or `output_image` / `output_audio`).
Listening with Gemini stays in providers.py (audio inside a normal Flash request).
Every error becomes an AiError with a short Uzbek message; the key is never in it.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from nexvara.ai.providers import TIMEOUT, AiError

OPENAI = "https://api.openai.com/v1"
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _http(opener, url: str, headers: dict[str, str], data: bytes | None, label: str) -> bytes:
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={**headers, "User-Agent": "NEXVARA"})  # fmt: skip
        try:
            with opener(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                err = json.loads(e.read().decode("utf-8", "replace")).get("error", {})
                detail = err.get("message", "") if isinstance(err, dict) else str(err)
            except (ValueError, AttributeError, OSError):
                pass
            if e.code in (401, 403):
                raise AiError(f"{label} API kaliti noto‘g‘ri yoki bu modelga ruxsat yo‘q. "
                              f"{detail}".strip()) from e  # fmt: skip
            if e.code == 402:
                raise AiError(f"{label} hisobida mablag‘ yetarli emas.") from e
            if (e.code == 429 or e.code >= 500) and attempt < 2:
                time.sleep(2**attempt)
                continue
            if e.code == 429:
                raise AiError(f"{label}: so‘rovlar chegarasi yoki kvota tugagan.",
                              retryable=True) from e  # fmt: skip
            if e.code == 404:
                raise AiError(f"{label}: model topilmadi. {detail}".strip()) from e
            if e.code == 400 and ("safety" in detail.lower() or "policy" in detail.lower()):
                raise AiError(f"{label} bu so‘rovni xavfsizlik qoidasi bo‘yicha rad etdi.") from e
            raise AiError(f"{label} xatosi ({e.code}): {detail or e.reason}",
                          retryable=e.code >= 500) from e  # fmt: skip
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 2:
                time.sleep(2**attempt)
                continue
            raise AiError(f"Internetga ulanib bo‘lmadi ({label}).", retryable=True) from e
    raise AiError(f"{label}: javob olinmadi")


def _json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise AiError(f"{label} javobi tushunarsiz formatda keldi.") from e


def _multipart(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]):
    """(body, content-type) for multipart/form-data; files: (field, filename, mime, bytes)."""
    boundary = "nexvara" + uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                f"{v}\r\n").encode()  # fmt: skip
    for field, name, mime, blob in files:
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
                f"filename=\"{name}\"\r\nContent-Type: {mime}\r\n\r\n").encode()  # fmt: skip
        out += blob + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def wav_from_pcm(pcm: bytes, rate: int = 24000) -> bytes:
    import struct

    head = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(pcm))
    )
    return head + pcm


class OpenAIMedia:
    label = "OpenAI"

    def __init__(self, key: str, opener=None, base: str = OPENAI) -> None:
        self.key, self.base = key, base.rstrip("/")
        self._open = opener or urllib.request.urlopen

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.key}"}

    def _image_out(self, raw: bytes) -> bytes:
        data = _json(raw, self.label)
        try:
            b64 = data["data"][0]["b64_json"]
        except (KeyError, IndexError, TypeError) as e:
            raise AiError("OpenAI rasm qaytarmadi.") from e
        return base64.b64decode(b64)

    def generate_image(self, model: str, prompt: str, size: str = "1024x1024",
                       quality: str = "medium") -> bytes:  # fmt: skip
        body = {"model": model, "prompt": prompt, "n": 1, "size": size, "quality": quality,
                "output_format": "png"}  # fmt: skip
        raw = _http(self._open, self.base + "/images/generations",
                    {**self._auth(), "Content-Type": "application/json"},
                    json.dumps(body).encode("utf-8"), self.label)  # fmt: skip
        return self._image_out(raw)

    def edit_image(self, model: str, prompt: str, image: bytes, mime: str,
                   size: str = "1024x1024", quality: str = "medium") -> bytes:  # fmt: skip
        ext = "png" if "png" in mime else "jpg"
        body, ctype = _multipart(
            {"model": model, "prompt": prompt, "size": size, "quality": quality},
            [("image[]", f"rasm.{ext}", mime, image)],
        )
        raw = _http(self._open, self.base + "/images/edits",
                    {**self._auth(), "Content-Type": ctype}, body, self.label)  # fmt: skip
        return self._image_out(raw)

    def speak(self, model: str, text: str, voice: str = "marin") -> bytes:
        body = {"model": model, "input": text, "voice": voice, "response_format": "wav"}
        return _http(self._open, self.base + "/audio/speech",
                     {**self._auth(), "Content-Type": "application/json"},
                     json.dumps(body).encode("utf-8"), self.label)  # fmt: skip

    def transcribe(self, model: str, audio: bytes, mime: str = "audio/wav",
                   prompt: str = "") -> str:  # fmt: skip
        fields = {"model": model, "response_format": "json"}
        if prompt:
            fields["prompt"] = prompt
        body, ctype = _multipart(fields, [("file", "ovoz.wav", mime, audio)])
        raw = _http(self._open, self.base + "/audio/transcriptions",
                    {**self._auth(), "Content-Type": ctype}, body, self.label)  # fmt: skip
        return str(_json(raw, self.label).get("text") or "").strip()


def _find_block(data: Any, kind: str) -> dict | None:
    """The last {"type": kind, "data": base64} block anywhere in an Interactions response."""
    found = None
    if isinstance(data, dict):
        if data.get("type") == kind and isinstance(data.get("data"), str):
            found = data
        for k, v in data.items():
            if k == f"output_{kind}" and isinstance(v, dict) and isinstance(v.get("data"), str):
                found = v
            hit = _find_block(v, kind)
            if hit is not None:
                found = hit
    elif isinstance(data, list):
        for v in data:
            hit = _find_block(v, kind)
            if hit is not None:
                found = hit
    return found


class GeminiMedia:
    label = "Gemini"

    def __init__(self, key: str, opener=None, base: str = GEMINI) -> None:
        self.key, self.base = key, base.rstrip("/")
        self._open = opener or urllib.request.urlopen

    def _interact(self, body: dict) -> dict:
        raw = _http(self._open, self.base + "/interactions",
                    {"x-goog-api-key": self.key, "Content-Type": "application/json"},
                    json.dumps(body).encode("utf-8"), self.label)  # fmt: skip
        return _json(raw, self.label)

    def _image(self, model: str, parts: list[dict], aspect: str = "1:1") -> bytes:
        data = self._interact({
            "model": model, "input": parts,
            "response_format": {"type": "image", "mime_type": "image/png", "aspect_ratio": aspect,
                                "image_size": "1K"},
        })  # fmt: skip
        block = _find_block(data, "image")
        if block is None:
            raise AiError("Gemini rasm qaytarmadi (so‘rov rad etilgan bo‘lishi mumkin).")
        return base64.b64decode(block["data"])

    def generate_image(self, model: str, prompt: str, size: str = "1024x1024",
                       quality: str = "medium") -> bytes:  # fmt: skip
        return self._image(model, [{"type": "text", "text": prompt}], _aspect(size))

    def edit_image(self, model: str, prompt: str, image: bytes, mime: str,
                   size: str = "1024x1024", quality: str = "medium") -> bytes:  # fmt: skip
        parts = [
            {"type": "text", "text": prompt},
            {"type": "image", "mime_type": mime, "data": base64.b64encode(image).decode()},
        ]
        return self._image(model, parts, _aspect(size))  # fmt: skip

    def speak(self, model: str, text: str, voice: str = "Kore") -> bytes:
        data = self._interact({
            "model": model,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice}]},
        })  # fmt: skip
        block = _find_block(data, "audio")
        if block is None:
            raise AiError("Gemini ovoz qaytarmadi.")
        audio = base64.b64decode(block["data"])
        if audio[:4] != b"RIFF":  # raw PCM (audio/l16) — wrap it so any player can open it
            audio = wav_from_pcm(audio)
        return audio


def _aspect(size: str) -> str:
    try:
        w, h = (int(x) for x in size.lower().split("x"))
    except ValueError:
        return "1:1"
    return "1:1" if w == h else ("3:2" if w > h else "2:3")


def media_client(provider: str, key: str, opener=None):
    if provider == "openai":
        return OpenAIMedia(key, opener)
    if provider == "gemini":
        return GeminiMedia(key, opener)
    raise AiError("Bu provayderda rasm/ovoz modeli yo‘q.")
