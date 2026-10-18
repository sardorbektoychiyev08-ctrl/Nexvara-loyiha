"""Spoken commands: only Gemini hears them, only after consent, and the text runs as a command.
Fake HTTP only: nothing is sent anywhere."""

from __future__ import annotations

import base64
import json

from test_privacy import Wire, chat_answer

from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import ChatCompletionsProvider
from nexvara.ai.router import AiRouter, Ledger
from nexvara.appdata import Settings

AUDIO = base64.b64encode(b"RIFF" + b"\0" * 32000).decode()


def _router(tmp_path, keys, answer):
    wires = {}

    def factory(name, key):
        wires.setdefault(name, Wire(chat_answer(answer)))
        return ChatCompletionsProvider(name, key, opener=wires[name])

    r = AiRouter(
        Settings(tmp_path / "s.json"),
        MemoryKeyStore(keys),
        Ledger(tmp_path / "l.db"),
        factory=factory,
    )
    r.settings.update({"ai": {"enabled": True}})
    return r, wires


def test_voice_needs_consent_then_goes_to_gemini_only(tmp_path):
    from nexvara.app.api import Api

    r, wires = _router(
        tmp_path,
        {"openai": "sk-test-openai-123456", "gemini": "AIza-test-gemini-1234567"},
        "Hisobot.xlsx ni och",
    )
    api = Api(overrides={"ai_router": r})
    first = api.voice_command(AUDIO)
    assert not first["ok"] and "Rozimisiz" in first["needs_consent"] and not wires
    out = api.voice_command(AUDIO, "audio/wav", consent=True)
    assert out == {"ok": True, "text": "Hisobot.xlsx ni och"}
    assert list(wires) == ["gemini"]  # never OpenAI, even with its key connected
    body = json.loads(wires["gemini"].bodies[0])
    part = body["messages"][1]["content"][1]
    assert part["type"] == "input_audio" and part["input_audio"]["format"] == "wav"
    assert api.voice_status()["consent"] is True  # remembered
    assert "qisqa" in api.voice_command(base64.b64encode(b"x").decode())["error"]


def test_voice_with_only_openai_uses_its_transcription(tmp_path):
    """No Gemini: the STT direction picks OpenAI's transcription endpoint (fake HTTP)."""
    from nexvara.ai.media import OpenAIMedia
    from nexvara.app.api import Api

    r, wires = _router(tmp_path, {"openai": "sk-test-openai-123456"}, "x")
    from test_ai_media import Net

    ears = Net({"/audio/transcriptions": {"text": "Savdo.xlsx ni och"}})
    r.media_factory = lambda name, key: OpenAIMedia(key, opener=ears)
    out = Api(overrides={"ai_router": r}).voice_command(AUDIO, consent=True)
    assert out == {"ok": True, "text": "Savdo.xlsx ni och"} and not wires
    assert (
        ears.urls[0].endswith("/audio/transcriptions")
        and b"gpt-4o-mini-transcribe" in ears.bodies[0]
    )
    assert r.ledger.recent()[0]["purpose"] == "Ovoz → matn"


def test_voice_without_any_listening_ai_explains(tmp_path):
    from nexvara.app.api import Api

    r, wires = _router(tmp_path, {"deepseek": "sk-test-deepseek-12345"}, "x")
    out = Api(overrides={"ai_router": r}).voice_command(AUDIO, consent=True)
    assert not out["ok"] and "kaliti kerak" in out["error"] and not wires
