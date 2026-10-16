"""AI router, providers and features with fake providers: no network, no paid calls."""

from __future__ import annotations

import io
import json
import os
import urllib.error
from types import SimpleNamespace

import pytest

from nexvara.ai import features, models
from nexvara.ai.keys import KeyStore, MemoryKeyStore, mask
from nexvara.ai.providers import (
    AiError,
    AnthropicProvider,
    ChatCompletionsProvider,
    Provider,
    Reply,
)
from nexvara.ai.router import AiRouter, BudgetExceeded, Ledger, NeedsConfirmation
from nexvara.appdata import Settings


class FakeProvider(Provider):
    def __init__(self, replies=None, models_list=None):
        self.replies = list(replies or [])
        self.models_list = models_list or []
        self.calls = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append({"model": model, "system": system, "messages": messages,
                           "max_tokens": max_tokens, "effort": effort})  # fmt: skip
        text = self.replies.pop(0) if self.replies else "{}"
        return Reply(text, model, 1000, 500)

    def list_models(self):
        return self.models_list


@pytest.fixture
def router(tmp_path):
    fake = FakeProvider(models_list=["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"])
    r = AiRouter(
        Settings(tmp_path / "settings.json"),
        MemoryKeyStore(),
        Ledger(tmp_path / "app.db"),
        factory=lambda name, key: fake,
    )
    r.fake = fake
    return r


def test_prices_and_model_picking():
    assert models.price("claude-opus-5-5") == (4.00, 20.00)
    assert models.price("gemini-3.1-pro-preview-06", "gemini") == (2.00, 12.00)
    assert models.price("mystery-model", "openai") == (30.00, 180.00)  # never under-count
    assert models.price("gpt-5.4", "openai", {"gpt-5.4": [1, 2]}) == (1, 2)
    assert models.cost("claude-haiku-5-5", "anthropic", 1_000_000, 1_000_000) == pytest.approx(0.6)
    avail = ["gemini-3.1-pro-preview", "gemini-3.1-pro-preview-06", "gemini-3.5-flash"]
    assert models.pick_model("gemini-3.1-pro", avail) == "gemini-3.1-pro-preview-06"
    assert models.pick_model("gemini-3.5-flash", avail) == "gemini-3.5-flash"
    assert models.pick_model("x", []) == "x"
    assert mask("sk-ant-api03-abcdefgh1234") == "sk-a…1234"


def test_not_ready_without_key(router):
    assert not router.ready()
    assert router.provider_name() is None
    with pytest.raises(Exception, match="o‘chirilgan"):
        router.complete("qa", "s", [{"role": "user", "content": "x"}])


def test_save_key_turns_ai_on(router):
    info = router.save_key("anthropic", "sk-ant-test-1234567890")
    assert info["models"]["powerful"] == "claude-opus-5-5"
    assert router.ready() and router.provider_name() == "anthropic"
    st = router.status()
    assert st["providers"]["anthropic"]["has_key"]
    assert "1234567890" not in json.dumps(st)  # the key itself never reaches the UI
    with pytest.raises(ValueError):
        router.save_key("anthropic", "short")
    router.delete_key("anthropic")
    assert not router.ready()


def test_complete_records_cost_and_tiers(router):
    router.save_key("anthropic", "sk-ant-test-1234567890")
    router.fake.replies = ["salom"]
    r = router.complete("classify", "sys", [{"role": "user", "content": "hi"}], max_tokens=100)
    assert r.text == "salom" and r.provider == "anthropic"
    assert router.fake.calls[-1]["model"] == "claude-haiku-5-5"  # classify -> cheap tier
    assert r.cost == pytest.approx((1000 * 0.10 + 500 * 0.50) / 1e6)
    assert router.ledger.today() == pytest.approx(r.cost)
    assert router.ledger.recent()[0]["purpose"] == "Buyruqni tushunish"


def test_budget_and_confirmation(router):
    router.save_key("anthropic", "sk-ant-test-1234567890")
    big = [{"role": "user", "content": "x" * 60000}]  # ~20k tokens on the balanced tier
    with pytest.raises(NeedsConfirmation) as e:
        router.complete("qa", "s", big, max_tokens=8000)
    assert "taxminan $" in e.value.estimate.describe()
    assert router.fake.calls == []  # nothing was sent
    router.complete("qa", "s", big, max_tokens=8000, approved=True)
    router.settings.update({"ai": {"daily_budget_usd": 0.01}})
    with pytest.raises(BudgetExceeded, match="Kunlik"):
        router.complete("qa", "s", big, max_tokens=8000, approved=True)


def test_classify_reads_fenced_json(router):
    router.save_key("anthropic", "sk-ant-test-1234567890")
    router.fake.replies = [
        '```json\n{"kind": "test", "command": "7-sinf fizika 10 ta test", "grade": "7"}\n```'
    ]
    intent = features.classify(router, "fizikadan 7 sinfga 10ta savol kerak")
    assert intent.kind == "test" and intent.grade == 7
    assert router.fake.calls[-1]["effort"] == "low"
    router.fake.replies = ['{"kind": "weird"}']
    assert features.classify(router, "x").kind == "chat"
    router.fake.replies = ["not json at all"]
    with pytest.raises(AiError):
        features.classify(router, "x")


def test_parse_questions_validates():
    data = [
        {"q": "Kuch birligi?", "options": ["N", "J", "W", "Pa"], "answer": 0, "page": 12},
        {"q": "Uch variant", "options": ["a", "b", "c"], "answer": 0},
        {"q": "Takror", "options": ["a", "a", "b", "c"], "answer": 1},
        {"q": "Javob yo'q", "options": ["a", "b", "c", "d"], "answer": 7},
        {"q": "Harfli", "options": ["A) bir", "B) ikki", "C) uch", "D) to'rt"], "answer": "2"},
    ]
    qs = features.parse_questions(data)
    assert [q.text for q in qs] == ["Kuch birligi?", "Harfli"]
    assert qs[0].answer == "A" and qs[0].source == "12-bet"
    assert qs[1].options[0] == "bir" and qs[1].answer == "C"


def test_ai_quizzes_variants(router, monkeypatch):
    from nexvara.knowledge import service
    from nexvara.knowledge.store import Book

    book = Book(1, "x.pdf", "Fizika", 7, "Fizika", 2022, 100, "ok", "")
    monkeypatch.setattr(service, "topic_material", lambda req: (book, [(5, "matn " * 50)], "Kuch"))
    monkeypatch.setattr(service, "make_quizzes", lambda req: (book, "Kuch", []))
    router.save_key("anthropic", "sk-ant-test-1234567890")
    pool = [
        {
            "q": f"Savol {i}?",
            "options": [f"t{i}", f"x{i}", f"y{i}", f"z{i}"],
            "answer": 0,
            "page": 5,
        }
        for i in range(8)
    ]
    router.fake.replies = [json.dumps(pool)]
    req = service.TestRequest(7, "Fizika", "Kuch", count=4, variants=2)
    b, topic, quizzes, cost = features.make_ai_quizzes(router, req, approved=True)
    assert topic == "Kuch" and len(quizzes) == 2 and cost > 0
    assert all(len(q.questions) == 4 for q in quizzes)
    for q in quizzes[1].questions:  # shuffled options still point at the right answer
        assert q.options["ABCD".index(q.answer)].startswith("t")
    assert {q.text for q in quizzes[0].questions} != {q.text for q in quizzes[1].questions}
    assert "[5-bet]" in router.fake.calls[-1]["messages"][0]["content"]


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_chat_completions_provider(monkeypatch):
    sent = []
    answers = [
        urllib.error.HTTPError("u", 429, "busy", {"retry-after": "0"}, io.BytesIO(b"{}")),
        _Resp(json.dumps({
            "model": "gpt-5.4",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        }).encode()),
    ]  # fmt: skip

    def opener(req, timeout):
        sent.append(req)
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr("nexvara.ai.providers.time.sleep", lambda s: None)
    p = ChatCompletionsProvider("openai", "sk-test", opener=opener)
    r = p.complete("gpt-5.4", "sys", [{"role": "user", "content": "hi"}], 100, "low")
    assert (r.text, r.input_tokens, r.output_tokens) == ("ok", 12, 3)
    body = json.loads(sent[-1].data)
    assert body["max_completion_tokens"] == 100 and body["reasoning_effort"] == "low"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert sent[-1].get_header("Authorization") == "Bearer sk-test"

    def denied(req, timeout):
        raise urllib.error.HTTPError(
            "u", 401, "no", {}, io.BytesIO(b'{"error": {"message": "bad"}}')
        )

    with pytest.raises(AiError, match="kaliti noto"):
        ChatCompletionsProvider("deepseek", "k", opener=denied).list_models()


def test_anthropic_provider_shape():
    p = AnthropicProvider("sk-ant-test")
    captured = {}

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(
            stop_reason="end_turn", model=kw["model"],
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text="javob")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=4, cache_creation_input_tokens=0,
                                  cache_read_input_tokens=None),
        )  # fmt: skip

    p.client = SimpleNamespace(
        messages=SimpleNamespace(create=create),
        beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
    )
    r = p.complete("claude-opus-5-5", "s", [{"role": "user", "content": "x"}], 500, "high")
    assert r.text == "javob" and r.input_tokens == 10
    assert captured["fallbacks"] == "default" and captured["output_config"] == {"effort": "high"}
    captured.clear()
    p.complete("claude-haiku-5-5", "s", [{"role": "user", "content": "x"}], 500)
    assert "fallbacks" not in captured


def test_api_chat_with_ai(router, monkeypatch):
    from nexvara.app.api import Api

    monkeypatch.setattr(features, "find_passages", lambda *a, **k: [])
    router.save_key("anthropic", "sk-ant-test-1234567890")
    api = Api(overrides={"ai_router": router})
    assert api.get_info()["ai_connected"]
    router.fake.replies = ['{"kind": "question"}', "Nyutonning birinchi qonuni — inersiya."]
    out = api.chat("inersiya nima o'zi")
    assert "inersiya" in out["reply"]
    # An expensive answer waits for "Ha".
    router.settings.update({"ai": {"confirm_over_usd": 0.0}})
    out = api.chat("yana bir narsani bilmoqchiman")
    assert "Davom etaymi" in out["reply"] and out["confirm"]
    calls = len(router.fake.calls)
    assert "Bekor" in api.confirm_ai(out["confirm"], False)["reply"]
    assert len(router.fake.calls) == calls  # nothing sent after "Yo‘q"
    out = api.chat("yana bir narsani bilmoqchiman")
    router.fake.replies = ['{"kind": "chat"}', "Salom!"]
    assert api.confirm_ai(out["confirm"])["reply"] == "Salom!"
    assert "eskirgan" in api.confirm_ai(out["confirm"])["reply"]


def test_ai_word_is_not_part_of_the_topic():
    from nexvara.app.api import _wants_ai
    from nexvara.knowledge.service import parse_test_request

    req = parse_test_request("AI bilan 7-sinf fizika kuch 6 ta test tuz")
    assert (req.topic, req.count) == ("kuch", 6)
    assert _wants_ai("sun'iy intellekt yordamida 8-sinf tarix Amir Temur 10 ta test")
    assert parse_test_request("sun'iy intellekt yordamida 8-sinf tarix Amir Temur test").topic == (
        "amir temur"
    )
    assert not _wants_ai("7-sinf fizika Nyuton qonunlari 20 ta test")


@pytest.mark.skipif(os.name != "nt", reason="Windows Credential Manager")
def test_credential_manager_roundtrip():
    store = KeyStore(prefix="NEXVARA-TEST/ai/")
    store.save("openai", "sk-test-roundtrip-123")
    try:
        assert store.load("openai") == "sk-test-roundtrip-123"
    finally:
        store.delete("openai")
    assert store.load("openai") is None
