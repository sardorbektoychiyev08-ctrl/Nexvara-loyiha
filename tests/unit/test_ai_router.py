"""Model Router v2 with fake providers only (no network, nothing paid): 4 tiers, checked
models, fallback, limits, warnings, dashboard, real balance, official pages, secrets."""

from __future__ import annotations

import io
import json
import logging
import urllib.error

import pytest

from nexvara.ai import models
from nexvara.ai.keys import MemoryKeyStore, RedactingFilter, redact
from nexvara.ai.providers import AiError, ChatCompletionsProvider, Provider, Reply, fetch_balance
from nexvara.ai.router import AiRouter, AiUnavailable, BudgetExceeded, Ledger, NeedsConfirmation
from nexvara.appdata import Settings


class Fake(Provider):
    def __init__(self, name, models_list=(), fail=None):
        self.name = name
        self.models_list = list(models_list)
        self.fail = fail  # AiError to raise from complete()
        self.calls = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append(model)
        if self.fail:
            raise self.fail
        return Reply("ok", model, 1000, 200)

    def list_models(self):
        return self.models_list


ALL = {
    "anthropic": ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"],
    "openai": ["gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "gpt-6-astra"],
    "gemini": ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-pro-preview"],
    "deepseek": ["deepseek-flash", "deepseek-v4-pro"],
}


@pytest.fixture
def make(tmp_path):
    fakes = {n: Fake(n, ALL[n]) for n in ALL}
    balances = []

    def build():
        r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(), Ledger(tmp_path / "l.db"),
                     factory=lambda n, k: fakes[n],
                     balance_fetch=lambda n, k: balances.append(n) or {
                         "supported": True, "available": True,
                         "balances": [{"currency": "USD", "total": 4.5, "granted": 0.5,
                                       "topped_up": 4.0}]})  # fmt: skip
        r.fakes, r.balances = fakes, balances
        return r

    return build


def test_four_tiers_with_uzbek_names():
    assert models.TIERS == ("cheap", "balanced", "powerful", "special")
    assert list(models.TIER_LABELS.values()) == ["Tejamkor", "Muvozanatli", "Kuchli", "Maxsus"]
    for p in models.PROVIDERS.values():
        assert set(p["tiers"]) == set(models.TIERS)
        for m in p["tiers"].values():
            assert any(m.startswith(k) for k in models.PRICES), m  # a known price


def test_official_pages_only():
    domains = {"openai": "platform.openai.com", "anthropic": "platform.claude.com",
               "gemini": "aistudio.google.com", "deepseek": "platform.deepseek.com"}  # fmt: skip
    for name, p in models.PROVIDERS.items():
        for key in ("key_url", "billing_url", "usage_url"):
            assert p[key].startswith(f"https://{domains[name]}/"), (name, key)
        assert "API" in p["subscription_note"] and p["free_tier"]
    assert models.PROVIDERS["deepseek"]["balance_api"] is True
    assert not any(models.PROVIDERS[n]["balance_api"] for n in ("openai", "anthropic", "gemini"))
    assert "bepul daraja bor" in models.PROVIDERS["gemini"]["free_tier"]


def test_missing_models_are_not_shown_as_working(make):
    r = make()
    r.fakes["gemini"].models_list = ["gemini-3.6-flash"]  # an account without most models
    info = r.save_key("gemini", "AIza-test-key-123456")
    assert info["models"]["balanced"] == "gemini-3.6-flash"  # alternative from the account
    assert info["models"]["cheap"] == "gemini-3.6-flash"
    assert "Kuchli" in info["missing"] and "Maxsus" in info["missing"]
    assert r.status()["providers"]["gemini"]["models"]["powerful"] is None
    with pytest.raises(AiUnavailable, match="mos model topilmadi"):
        r.estimate("powerful", "s", [{"role": "user", "content": "x"}], 100, "gemini")
    assert r.status()["providers"]["gemini"]["checked"]["models"] == 1


def test_tier_routing_and_special_needs_confirmation(make):
    r = make()
    r.save_key("anthropic", "sk-ant-test-1234567890")
    msg = [{"role": "user", "content": "salom"}]
    r.complete("classify", "s", msg, max_tokens=200)
    r.complete("plan", "s", msg, max_tokens=200)
    r.complete("analysis", "s", msg, max_tokens=200)
    assert r.fakes["anthropic"].calls == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-opus-5-5",
    ]
    with pytest.raises(NeedsConfirmation):
        r.complete("special", "s", msg, max_tokens=200)  # always asks, even when cheap
    r.complete("special", "s", msg, max_tokens=200, approved=True)
    assert r.fakes["anthropic"].calls[-1] == "claude-fable-5-1"


def test_fallback_to_another_provider(make):
    r = make()
    r.save_key("openai", "sk-test-openai-123456")
    r.save_key("deepseek", "sk-test-deepseek-123456")
    r.settings.update({"ai": {"provider": "openai"}})
    r.fakes["openai"].fail = AiError("OpenAI serverida xato (503)", retryable=True)
    reply = r.complete("plan", "s", [{"role": "user", "content": "x"}], max_tokens=200)
    assert reply.provider == "deepseek" and reply.fallback_from == "openai"
    assert r.ledger.recent(1)[0]["provider"] == "deepseek"  # cost recorded on who answered
    r.fakes["openai"].fail = AiError("OpenAI API kaliti noto‘g‘ri", retryable=False)
    with pytest.raises(AiError, match="kaliti"):  # a wrong key never silently switches
        r.complete("plan", "s", [{"role": "user", "content": "x"}], max_tokens=200)
    r.fakes["openai"].fail = AiError("busy", retryable=True)
    r.settings.update({"ai": {"fallback": False}})
    with pytest.raises(AiError, match="busy"):
        r.complete("plan", "s", [{"role": "user", "content": "x"}], max_tokens=200)


def test_limits_block_and_warn(make):
    r = make()
    r.save_key("anthropic", "sk-ant-test-1234567890")
    msg = [{"role": "user", "content": "x"}]
    r.settings.update({"ai": {"task_limit_usd": 0.0001}})
    with pytest.raises(BudgetExceeded, match="Bitta topshiriq"):
        r.complete("analysis", "s", msg, max_tokens=4000)
    r.settings.update({"ai": {"task_limit_usd": None,
                              "limits": {"anthropic": {"daily_usd": 0.001}}}})  # fmt: skip
    with pytest.raises(BudgetExceeded, match="Claude .*kunlik limit"):
        r.complete("analysis", "s", msg, max_tokens=4000)
    r.settings.update({"ai": {"limits": {"anthropic": {"daily_usd": None}},
                              "daily_budget_usd": 0.01}})  # fmt: skip
    r.ledger.record("anthropic", "claude-haiku-5-5", "chat", 0, 0, 0.0085)
    st = r.status()
    assert st["warnings"] and "85%" in st["warnings"][0] and not st["blocked"]
    r.ledger.record("anthropic", "claude-haiku-5-5", "chat", 0, 0, 0.002)
    st = r.status()
    assert st["blocked"] and "tugadi" in st["warnings"][0]
    with pytest.raises(BudgetExceeded, match="Kunlik AI limiti"):
        r.complete("classify", "s", msg, max_tokens=200)  # new paid calls are blocked


def test_dashboard_separates_limit_left_from_real_balance(make):
    r = make()
    r.save_key("deepseek", "sk-test-deepseek-123456")
    r.complete("plan", "s", [{"role": "user", "content": "x"}], max_tokens=200)
    d = r.dashboard()
    ds = d["providers"]["deepseek"]
    assert ds["has_key"] and ds["spent_month"] > 0 and d["estimated"] is True
    assert ds["left_month"] == pytest.approx(ds["monthly_limit"] - ds["spent_month"], abs=1e-3)
    assert ds["balance"] is None  # nothing fetched yet: never a made-up number
    assert len(d["series"]) == 30 and d["series"][-1]["total"] > 0
    assert d["history"][0]["purpose"] == "Rejalashtirish"
    assert sum(x["share"] for x in d["split"]) == pytest.approx(1.0)
    assert r.balance("openai") == {"supported": False}
    out = r.balance("deepseek")
    assert out["balances"][0]["total"] == 4.5 and r.dashboard()["providers"]["deepseek"]["balance"]
    assert d["providers"]["openai"]["has_key"] is False


def test_deepseek_balance_parsing_and_retryable_errors():
    body = {"is_available": True, "balance_infos": [
        {"currency": "USD", "total_balance": "10.50", "granted_balance": "0.50",
         "topped_up_balance": "10.00"}]}  # fmt: skip
    sent = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout):
        sent.append(req.full_url)
        return Resp(json.dumps(body).encode())

    out = fetch_balance("deepseek", "sk-test", opener=opener)
    assert sent == ["https://api.deepseek.com/user/balance"]
    assert out["balances"][0] == {"currency": "USD", "total": 10.5, "granted": 0.5,
                                  "topped_up": 10.0}  # fmt: skip
    assert fetch_balance("openai", "sk-test") == {"supported": False}

    def fail(code):
        def op(req, timeout):
            raise urllib.error.HTTPError(req.full_url, code, "x", {}, io.BytesIO(b"{}"))

        return op

    with pytest.raises(AiError) as e:
        ChatCompletionsProvider("openai", "k", opener=fail(401))._request("GET", "/models")
    assert e.value.retryable is False
    with pytest.raises(AiError) as e:
        ChatCompletionsProvider("openai", "k", opener=fail(400))._request("GET", "/models")
    assert e.value.retryable is False


def test_secrets_are_redacted_in_errors_and_logs(caplog):
    key = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    assert key not in redact(f"bad key {key}") and "yashirildi" in redact(key)
    assert "AIzaSy" not in redact("x AIzaSyA1234567890abcdefghijklmn")
    assert "abcdefghijklmnop" not in str(AiError(f"Provider said: {key}"))
    log = logging.getLogger("nexvara.test.redact")
    handler = logging.Handler()
    seen = []
    handler.emit = lambda rec: seen.append(rec.getMessage())
    handler.addFilter(RedactingFilter())
    log.addHandler(handler)
    try:
        log.warning("calling with %s", key)
    finally:
        log.removeHandler(handler)
    assert seen and key not in seen[0]


def test_planner_purpose_by_message():
    from nexvara.ai.features import plan_purpose

    assert plan_purpose("Hisobot.xlsx ni PDF qil") == "plan"
    assert plan_purpose("savdo natijalarini chuqur tahlil qilib ber") == "analysis"
    assert plan_purpose("eng kuchli model bilan yozib ber") == "special"


def test_api_limits_balance_and_background_office(tmp_path, monkeypatch, make):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    r = make()
    titles = []
    xlsx = tmp_path / "Hisobot.xlsx"
    xlsx.write_bytes(b"PK")
    api = Api(
        TaskRunner(), overrides={"ai_router": r, "command": lambda t: titles.append(t.title) or {}}
    )
    assert api.ai_save_limits("openai", "1.5", "")["ok"]
    assert r.config()["limits"]["openai"] == {"daily_usd": 1.5, "monthly_usd": None}
    assert api.ai_save_limits("openai", "-1", "")["ok"] is False
    assert api.ai_save_limits("yo‘q", 1, 1)["ok"] is False
    assert api.ai_balance("gemini") == {"supported": False}
    assert api.ai_dashboard()["providers"]["gemini"]["billing_url"].startswith("https://")
    out = api.chat(f"{xlsx} ni och va saqla, fonda bajar")
    assert out["task"]["title"].endswith("(fonda)") and "Tushunmadim" not in out["reply"]
    out = api.chat(f"{xlsx} ni och va saqla")
    assert not out["task"]["title"].endswith("(fonda)")  # visible Office by default


def test_keys_never_synced():
    from nexvara.sync import SYNC_SETTINGS

    assert not any(k.startswith(("ai.models", "ai.limits", "ai.enabled", "ai.provider"))
                   for k in SYNC_SETTINGS)  # fmt: skip
    assert all("key" not in k for k in SYNC_SETTINGS)
