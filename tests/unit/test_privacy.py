"""Personal data is masked locally before any AI request and restored locally in the answer.

The OpenAI and Gemini cases go through the real HTTP adapter (ChatCompletionsProvider) with a
fake transport that records the exact bytes that would leave the PC — nothing is sent.
"""

from __future__ import annotations

import io
import json
import re

import pytest

from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.privacy import Guard, public
from nexvara.ai.providers import ChatCompletionsProvider, Provider, Reply
from nexvara.ai.router import AiRouter, Ledger, NeedsConfirmation
from nexvara.appdata import Settings

PERSON = (
    "O‘quvchi Aliyev Vali Karimovich, JSHSHIR 31234567890123, tel +998 90 123-45-67, "
    "pasport AA1234567, manzil: Chilonzor tumani, Bunyodkor ko‘chasi 12-uy, kv. 45, "
    "email vali.aliyev@mail.uz, karta 8600 1234 5678 9012, tug‘ilgan sanasi 05.03.2012"
)
SECRETS = ["Aliyev", "Vali", "Karimovich", "31234567890123", "123-45-67", "AA1234567",
           "Bunyodkor", "12-uy", "kv. 45", "vali.aliyev@mail.uz", "8600 1234 5678 9012",
           "05.03.2012"]  # fmt: skip


# ---------------- detection, restore, blocking ----------------


def test_every_kind_is_masked_and_restored():
    g = Guard()
    masked = g.mask(PERSON)
    for s in SECRETS:
        assert s not in masked, s
    for kind in ("ISM", "JSHSHIR", "TEL", "PASPORT", "MANZIL", "EMAIL", "KARTA", "SANA"):
        assert f"⟦{kind}_1⟧" in masked, kind
    assert g.restore(masked) == PERSON


@pytest.mark.parametrize("text,kind", [
    ("ismi Botirjon, familiyasi Qodirov", "ISM"),
    ("F.I.Sh.: Raximova Gulnoza Anvarovna", "ISM"),
    ("Sardorbek Toychiyev o‘g‘li uchun ariza", "ISM"),
    ("Nilufar uchun xat yoz", "ISM"),
    ("tel: 90 123 45 67", "TEL"),
    ("PINFL 5 1234 5678 9012 3", "JSHSHIR"),
    ("ID karta AD 1234567", "PASPORT"),
    ("STIR 123456789", "TEL"),  # 9 digits are hidden either way
])  # fmt: skip
def test_formats(text, kind):
    g = Guard()
    masked = g.mask(text)
    assert f"⟦{kind}_" in masked, masked
    assert g.restore(masked) == text


def test_same_value_same_token_and_model_variants_restored():
    g = Guard()
    m = g.mask("Vali Aliyev bilan Vali Aliyev ga xat")
    assert m.count("⟦ISM_1⟧") == 2 and "⟦ISM_2⟧" not in m
    assert g.restore("Hurmatli [ISM_1], «ISM_1» va ⟦ ISM_1 ⟧") == (
        "Hurmatli Vali Aliyev, Vali Aliyev va Vali Aliyev"
    )


@pytest.mark.parametrize("text", [
    "telefon raqami: 90-12",  # a phone keyword with a value in no known format
    "pasport: A 12-34",
    "JSHSHIR: 3123",
    "hujjat raqami 123456789012",  # an unknown long number
])  # fmt: skip
def test_unreliable_detection_is_hidden_not_blocked(text):
    """Unsure whether it is personal data: that part is hidden too, the request still goes."""
    g = Guard()
    masked = g.mask(text)
    assert "⟦MAXFIY_1⟧" in masked and not re.search(r"\d{2}", masked.replace("MAXFIY_1", ""))
    assert g.restore(masked) == text


@pytest.mark.parametrize("text", [
    "Hisobot.xlsx ni och, B ustun bo‘yicha saralab, PDF qilib saqla",
    "7-sinf fizika Nyuton qonunlari 20 ta test 2 variant",
    "Savdo 15 000 000 so‘m bo‘ldi, 2026-yil hisobotini tahlil qil",
    "Alisher Navoiy kim?",
    "Mirzo Ulug‘bek rasadxonasi haqida gapir",
    "«Savdo» panelida faqat Toshkent bo‘yicha natija",
    "telefon qilib eslatib qo‘y",
])  # fmt: skip
def test_ordinary_requests_pass_unchanged(text):
    assert Guard().mask(text) == text


def test_public_textbook_text_is_not_masked():
    g = Guard()
    out = g.mask("Savol: Vali so‘radi " + public("Abdulla Qodiriy 1894-yilda tug‘ilgan."))
    assert "⟦ISM_1⟧ so‘radi" in out and "Abdulla Qodiriy 1894" in out and "PUBLIC" not in out


# ---------------- through the router and the real HTTP adapter ----------------


class Wire:
    """A fake HTTPS transport: records request bodies, answers like the provider would."""

    def __init__(self, answer, status=200):
        self.bodies: list[str] = []
        self.answer = answer
        self.status = status

    def __call__(self, req, timeout):
        import urllib.error

        self.bodies.append(req.data.decode("utf-8") if req.data else "")
        if self.status != 200:
            raise urllib.error.HTTPError(req.full_url, self.status, "x", {}, io.BytesIO(b"{}"))

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R(json.dumps(self.answer).encode())


def chat_answer(text):
    return {"model": "m", "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20}}  # fmt: skip


@pytest.fixture
def wired(tmp_path):
    wires: dict[str, Wire] = {}

    def factory(name, key):
        return ChatCompletionsProvider(name, key, opener=wires[name])

    r = AiRouter(
        Settings(tmp_path / "s.json"),
        MemoryKeyStore({"openai": "sk-test-openai-123456", "gemini": "AIza-test-gemini-1234567"}),
        Ledger(tmp_path / "l.db"),
        factory=factory,
    )
    # Paid routing is tested here; Gemini's free mode (on by default) has its own tests.
    r.settings.update({"ai": {"enabled": True, "provider": "openai", "free_mode": False}})
    return r, wires


def _no_secret_left(bodies):
    # Check both the raw bytes and the decoded JSON (unicode may be \u-escaped on the wire).
    decoded = []
    for b in bodies:
        try:
            decoded += [m["content"] for m in json.loads(b).get("messages", [])]
        except ValueError:
            pass
    blob = "\n".join(bodies + decoded)
    for s in SECRETS:
        assert s not in blob, s
    return blob


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_provider_receives_only_placeholders(wired, provider):
    r, wires = wired
    r.set_capability(
        "text",
        "manual",
        provider,
        "gpt-6-luna" if provider == "openai" else "gemini-3.5-flash-lite",
    )
    wires[provider] = Wire(chat_answer("⟦ISM_1⟧ uchun ariza tayyor; tel ⟦TEL_1⟧."))
    reply = r.complete(
        "chat", "sys", [{"role": "user", "content": PERSON}], max_tokens=300, approved=True
    )
    blob = _no_secret_left(wires[provider].bodies)
    assert "⟦ISM_1⟧" in blob and "⟦JSHSHIR_1⟧" in blob
    assert reply.text == "Aliyev Vali Karimovich uchun ariza tayyor; tel +998 90 123-45-67."
    assert reply.masked >= 8 and r.last_masked == reply.masked


def test_fallback_provider_also_gets_masked_text(wired):
    r, wires = wired
    # off by default; the user turned it on. Above the «Ha» limit a dearer fallback asks.
    r.settings.update({"ai": {"fallback": True, "confirm_over_usd": 0.0}})
    wires["openai"] = Wire(chat_answer("x"), status=503)
    wires["gemini"] = Wire(chat_answer("Javob: ⟦ISM_1⟧"))
    with pytest.raises(NeedsConfirmation):  # a dearer fallback needs a fresh approval
        r.complete(
            "command", "sys", [{"role": "user", "content": PERSON}], max_tokens=300, approved=True
        )
    _no_secret_left(wires["openai"].bodies)
    assert wires["openai"].bodies and not wires["gemini"].bodies


def test_fallback_is_off_by_default(wired):
    r, wires = wired
    wires["openai"] = Wire(chat_answer("x"), status=503)
    wires["gemini"] = Wire(chat_answer("y"))
    with pytest.raises(Exception, match="503"):
        r.complete(
            "chat", "sys", [{"role": "user", "content": "salom"}], max_tokens=300, approved=True
        )
    assert wires["gemini"].bodies == []  # no paid fallback by itself


def test_unsure_value_never_leaves_the_pc(wired):
    r, wires = wired
    wires["openai"] = Wire(chat_answer("x"))
    r.complete("chat", "sys", [{"role": "user", "content": "pasport: A 12-34"}], max_tokens=300,
               approved=True)  # fmt: skip
    sent = " ".join(wires["openai"].bodies)
    assert sent and "12-34" not in sent and "MAXFIY" in sent


class Capture(Provider):
    def __init__(self, reply):
        self.reply = reply
        self.seen: list[str] = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.seen.append(system + "\n" + "\n".join(m["content"] for m in messages))
        return Reply(self.reply, model, 100, 20)

    def list_models(self):
        return []


def test_facts_history_context_and_plan_args_are_protected(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.memory.store import MemoryStore

    plan = {
        "kind": "tools",
        "say": "eslatma",
        "calls": [
            {"tool": "nexvara.command", "args": {"text": "Eslab qol: ⟦ISM_1⟧ telefoni ⟦TEL_1⟧"}}
        ],
    }
    cap = Capture(json.dumps(plan, ensure_ascii=False))
    keys = MemoryKeyStore({"anthropic": "sk-ant-x-1234567890"})
    r = AiRouter(Settings(tmp_path / "s.json"), keys, Ledger(tmp_path / "l.db"),
                 factory=lambda n, k: cap)  # fmt: skip
    r.settings.update({"ai": {"enabled": True}})
    budget = r.check_budget
    r.check_budget = lambda est, approved: budget(est, True)
    mem = MemoryStore(tmp_path / "app.db")
    mem.add_fact("Nilufar telefoni +998 91 765-43-21")
    api = Api(overrides={"memory": mem, "ai_router": r})
    api._context_file = str(tmp_path / "Aliyev Vali baholari.xlsx")
    out = api.chat(
        "Vali Aliyev ota-onasiga yig‘ilish haqida xabar matnini tayyorla, tel 90 123 45 67"
    )
    sent = "\n".join(cap.seen)
    for s in ("Vali", "Aliyev", "Nilufar", "765-43-21", "90 123 45 67"):
        assert s not in sent, s
    # The AI answered with placeholders only; the plan shown to the user has the real values
    # (restored on this PC) and still waits for "Ha".
    assert out.get("confirm") and "Aliyev Vali" in out["reply"] and "765-43-21" in out["reply"]
    assert "⟦" not in out["reply"] and out["privacy_masked"] >= 4
    assert re.search(r"yashirildi|AI’ga yuborilmadi", out["reply"])


def test_nexvara_file_names_with_timestamps_do_not_block():
    """Live check 2026-10-19: «rasm-20261019-025804.png» in the history blocked every request."""
    from nexvara.ai.privacy import Guard

    ok = (
        "Tayyor. Fayl: C:/Users/toych/AppData/Local/Temp/data/AI rasmlar/rasm-20261019-025804.png "
        "keyin kamera-20261019-031500.jpg va javob-20261019-031501.wav"
    )
    Guard().mask(ok)  # no PrivacyBlocked
    Guard().mask("Hisobot 20261019-025804 vaqtida tuzildi")
    Guard().mask("[2026-10-19] Foydalanuvchi: Ha [2026-10-19] NEXVARA: gpt-5.4-mini-2026-03-17")
    masked = Guard().mask("Mening hisob raqamim 2020 8000 1234 5678 9")  # still never sent
    assert "8000" not in masked and "⟦MAXFIY_1⟧" in masked


def test_phone_folder_path_does_not_block():
    r"""Live check 2026-10-22: «D:\NEXVARA\Telefondan\1000003519.jpg» (a photo sent from the
    phone) read as «telefon» + a number — every later request answered «So‘rov yuborilmadi»."""
    from nexvara.ai.privacy import Guard

    for ok in (
        r"Fayl: D:\NEXVARA\Telefondan\rasm-1792644054481_NEXVARA.xlsx",
        r"D:\NEXVARA\Telefondan\1000003519.jpg ni o‘qi",
        "telefondan 1000003519.jpg rasmini yubordim",
    ):
        Guard().mask(ok)  # no PrivacyBlocked
    assert "⟦TEL_1⟧" in Guard().mask("telefon raqamim 901234567")  # a real number still masked
