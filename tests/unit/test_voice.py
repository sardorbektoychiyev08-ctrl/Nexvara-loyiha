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


def test_voice_without_gemini_key_explains(tmp_path):
    from nexvara.app.api import Api

    r, wires = _router(tmp_path, {"openai": "sk-test-openai-123456"}, "x")
    out = Api(overrides={"ai_router": r}).voice_command(AUDIO, consent=True)
    assert not out["ok"] and "Gemini kaliti kerak" in out["error"] and not wires
