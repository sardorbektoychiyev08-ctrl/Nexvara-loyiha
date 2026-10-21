"""Official catalogue cache and spending decisions; network and billing are mocked."""

from __future__ import annotations

import io
import json
import time

import pytest

from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import AiError, ChatCompletionsProvider, Provider, Reply
from nexvara.ai.router import AiRouter, AiUnavailable, Ledger, NeedsConfirmation
from nexvara.appdata import Settings


class CatalogFake(Provider):
    def __init__(self, name: str, rows: list[dict]):
        self.name, self.rows, self.calls = name, rows, []
        self.fail_list = False
        self.fail_call = False

    def list_model_details(self):
        if self.fail_list:
            raise AiError("offline", retryable=True)
        return self.rows

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append(model)
        if self.fail_call:
            raise AiError("busy", retryable=True)
        return Reply("ok", model, 100, 50)


def make(tmp_path):
    fakes = {
        "openai": CatalogFake("openai", [{"id": "gpt-6-luna"}, {"id": "gpt-6-sol"}]),
        "gemini": CatalogFake("gemini", [{"name": "models/gemini-3.5-flash-lite"}]),
        "anthropic": CatalogFake("anthropic", [{"id": "claude-haiku-5-5"}]),
        "deepseek": CatalogFake("deepseek", [{"id": "deepseek-flash"}]),
    }
    keys = MemoryKeyStore({p: "test-key-123456789" for p in fakes})
    r = AiRouter(
        Settings(tmp_path / "settings.json"),
        keys,
        Ledger(tmp_path / "ledger.db"),
        factory=lambda p, _key: fakes[p],
    )
    r.settings.update({"ai": {"enabled": True, "free_mode": False}})
    return r, fakes


def test_refresh_records_lifecycle_and_keeps_verified_cache_offline(tmp_path):
    r, f = make(tmp_path)
    first = r.refresh_catalog(force=True)
    assert all(item["ok"] for item in first.values())
    checked = r.catalog_status()["openai"]["checked_at"]
    f["openai"].rows = [{"id": "gpt-6-sol", "deprecated": True}, {"id": "gpt-6.1-sol"}]
    second = r.refresh_catalog(force=True)["openai"]
    assert second["changes"]["added"] == ["gpt-6.1-sol"]
    assert second["changes"]["removed"] == ["gpt-6-luna"]
    assert second["changes"]["deprecated"] == ["gpt-6-sol"]
    assert "gpt-6-sol" not in r.catalog("openai")["text"]
    f["openai"].fail_list = True
    assert r.refresh_catalog(force=True)["openai"]["cached"]
    assert "gpt-6.1-sol" in r.catalog("openai")["text"]
    assert r.catalog_status()["openai"]["checked_at"] > checked
    state = r.config()["catalog_state"]["openai"]
    state["checked_at"] = time.time() - 90000
    r.settings.update({"ai": {"catalog_state": {"openai": state}}})
    assert r.catalog_status()["openai"]["stale"]


def test_auto_compares_all_connected_models_and_requires_paid_approval(tmp_path):
    r, f = make(tmp_path)
    r.refresh_catalog(force=True)
    msg = [{"role": "user", "content": "salom"}]
    choice = r.text_candidates("cheap", "s", msg, 50)[0]
    assert choice.provider in ("openai", "anthropic")
    r.settings.update({"ai": {"confirm_over_usd": 0.0}})  # paid above the limit: asks first
    with pytest.raises(NeedsConfirmation):
        r.complete("command", "s", msg)
    assert not any(fake.calls for fake in f.values())
    reply = r.complete("command", "s", msg, approved=True)
    assert reply.provider == choice.provider
    assert r.ledger.recent(1)[0]["model"] == reply.model


def test_manual_never_switches_and_unknown_price_is_blocked(tmp_path):
    r, f = make(tmp_path)
    f["openai"].rows.append({"id": "brand-new-unknown-model"})
    r.refresh_catalog(force=True)
    assert r.config()["catalog_state"]["openai"]["models"][0]["price_known"] is False
    with pytest.raises(AiUnavailable, match="narx"):
        r.estimate(
            "cheap",
            "s",
            [{"role": "user", "content": "x"}],
            50,
            "openai",
            "brand-new-unknown-model",
        )
    r.set_capability("text", "manual", "openai", "gpt-6-luna")
    f["openai"].fail_call = True
    r.settings.update({"ai": {"fallback": True}})
    with pytest.raises(AiError, match="busy"):
        r.complete("chat", "s", [{"role": "user", "content": "x"}], approved=True)
    assert not f["anthropic"].calls


def test_gemini_native_models_api_is_paginated_and_keeps_key_out_of_url():
    requests = []

    def opener(req, timeout):
        requests.append(req)
        data = (
            {"models": [{"name": "models/gemini-3.8-flash"}], "nextPageToken": "next"}
            if len(requests) == 1
            else {"models": [{"name": "models/gemini-3.5-flash-lite"}]}
        )

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Response(json.dumps(data).encode())

    provider = ChatCompletionsProvider("gemini", "private-test-key", opener=opener)
    assert provider.list_models() == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert len(requests) == 2 and "pageToken=next" in requests[1].full_url
    assert all("private-test-key" not in req.full_url for req in requests)
    assert all(req.get_header("X-goog-api-key") == "private-test-key" for req in requests)


def test_media_models_are_never_chat_models():
    from nexvara.ai.catalog import tier_of

    for p, m in (("gemini", "gemini-3.1-flash-lite-image"), ("gemini", "gemini-3.8-flash-tts"),
                 ("gemini", "gemini-3.8-flash-lite-tts"), ("gemini", "gemini-3.8-live"),
                 ("openai", "gpt-image-1-mini"), ("openai", "gpt-4o-mini-transcribe"),
                 ("openai", "gpt-realtime-mini")):  # fmt: skip
        assert tier_of(p, m) is None, m
    assert tier_of("gemini", "gemini-3.5-flash-lite") == "cheap"  # listens and chats
    assert tier_of("gemini", "gemini-3.8-flash") == "balanced"
    assert tier_of("openai", "gpt-6-luna") == "cheap"
