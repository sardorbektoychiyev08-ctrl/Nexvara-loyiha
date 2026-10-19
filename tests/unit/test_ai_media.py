"""Multi-AI directions: AUTO / MANUAL per direction (text, vision, image, stt, tts, realtime),
fallback, API errors and budget rules — fake HTTP and fake providers only, nothing is paid."""

from __future__ import annotations

import base64
import io
import json
import urllib.error

import pytest

from nexvara.ai import capabilities as caps
from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.media import GeminiMedia, OpenAIMedia
from nexvara.ai.providers import AiError, Provider, Reply
from nexvara.ai.router import AiRouter, AiUnavailable, BudgetExceeded, Ledger, NeedsConfirmation
from nexvara.appdata import Settings


def _png() -> bytes:
    import fitz

    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8), False)
    pix.clear_with(200)
    return pix.tobytes("png")


PNG = _png()
WAV = b"RIFF" + b"\0" * 40


class Net:
    """A fake HTTPS transport: answers per URL suffix, records url, headers and raw body."""

    def __init__(self, answers: dict[str, object], status: int = 200):
        self.answers, self.status = answers, status
        self.urls: list[str] = []
        self.bodies: list[bytes] = []
        self.headers: list[dict] = []

    def __call__(self, req, timeout):
        self.urls.append(req.full_url)
        self.bodies.append(req.data or b"")
        self.headers.append(dict(req.header_items()))
        if self.status != 200:
            body = json.dumps({"error": {"message": "busy"}}).encode()
            raise urllib.error.HTTPError(req.full_url, self.status, "x", {}, io.BytesIO(body))
        ans = next(v for k, v in self.answers.items() if req.full_url.endswith(k))
        raw = ans if isinstance(ans, bytes) else json.dumps(ans).encode()

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R(raw)


class TextFake(Provider):
    def __init__(self, name):
        self.name, self.calls = name, []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append({"model": model, "messages": messages})
        return Reply(f"{self.name}:{model}", model, 500, 50)

    def list_models(self):
        return []


class MediaFake:
    def __init__(self, name, log, fail=None):
        self.name, self.log, self.fail = name, log, fail

    def _go(self, what, model):
        self.log.append((self.name, what, model))
        if self.fail:
            raise self.fail
        return PNG if "image" in what else WAV

    def generate_image(self, model, prompt, size="1024x1024", quality="medium"):
        return self._go("image", model)

    def edit_image(self, model, prompt, image, mime, size="1024x1024", quality="medium"):
        return self._go("image_edit", model)

    def speak(self, model, text, voice=""):
        return self._go("tts", model)

    def transcribe(self, model, audio, mime="audio/wav", prompt=""):
        self._go("stt", model)
        return "salom"

    def web_search(self, model, question):
        self._go("web", model)
        self.log.append(("question", question))
        return {"text": "Toshkentda ertaga +18°C ⟦TEL_1⟧",
                "sources": [{"url": "https://meteo.uz/x", "title": "Meteo"}]}  # fmt: skip


def make(tmp_path, keys, **ai):
    texts: dict[str, TextFake] = {}
    log: list = []
    fails: dict[str, Exception] = {}
    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(keys), Ledger(tmp_path / "l.db"),
                 factory=lambda n, k: texts.setdefault(n, TextFake(n)),
                 media_factory=lambda n, k: MediaFake(n, log, fails.get(n)))  # fmt: skip
    r.settings.update({"ai": {"enabled": True, "free_tier_confirmed": "gemini" in keys, **ai}})
    r.texts, r.log, r.fails = texts, log, fails
    return r


KEYS = {"openai": "sk-test-openai-123456", "gemini": "AIza-test-gemini-1234567",
        "anthropic": "sk-ant-test-1234567890", "deepseek": "sk-test-deepseek-12345"}  # fmt: skip


# ---------------- registry ----------------


def test_registry_matches_official_capabilities():
    assert caps.supports("openai", "image") and caps.supports("gemini", "image")
    assert not caps.supports("anthropic", "image") and caps.supports("deepseek", "vision")
    assert caps.supports("anthropic", "vision") and not caps.supports("anthropic", "tts")
    assert caps.supports("gemini", "realtime") and caps.supports("openai", "realtime")
    assert not caps.supports("deepseek", "stt")
    # only models the account really has
    have = ["gpt-image-2", "gpt-4o-mini-tts", "gpt-5.4"]
    assert [r["model"] for r in caps.models_for("openai", "image", have)] == ["gpt-image-2"]
    assert caps.models_for("openai", "stt", have) == []
    assert caps.cost({"price": 0.05, "free": False}, 2) == 0.1
    assert caps.cost({"price": 0.05, "free": True}, 2) == 0.0


def test_key_check_stores_the_accounts_media_models(tmp_path):
    class Lister(TextFake):
        def list_models(self):
            return ["gpt-6-luna", "gpt-6-sol", "gpt-image-1-mini", "gpt-4o-mini-tts",
                    "gpt-4o-mini-transcribe", "dall-e-3"]  # fmt: skip

    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(), Ledger(tmp_path / "l.db"),
                 factory=lambda n, k: Lister(n))  # fmt: skip
    r.save_key("openai", "sk-test-openai-123456")
    cat = r.catalog("openai")
    assert cat["image"] == ["gpt-image-1-mini"] and cat["tts"] == ["gpt-4o-mini-tts"]
    assert cat["stt"] == ["gpt-4o-mini-transcribe"] and "gpt-6-luna" in cat["text"]
    assert "dall-e-3" not in cat["image"]  # not in the checked list: never offered


# ---------------- AUTO ----------------


def test_auto_prefers_free_then_cheapest(tmp_path):
    r = make(tmp_path, KEYS)
    assert r.candidates("tts")[0][0] == "gemini" and r.candidates("tts")[0][1]["free"]
    assert r.candidates("stt")[0][0] == "gemini"
    img = r.candidates("image")
    assert img[0][1]["model"] == "gpt-image-1-mini"  # $0.011 < Gemini $0.0336
    assert [p for p, _ in img].count("gemini") >= 1  # the fallback list
    r.settings.update({"ai": {"free_mode": False}})
    assert r.candidates("tts")[0][0] == "openai"


def test_auto_image_asks_first_then_runs_and_records(tmp_path):
    r = make(tmp_path, KEYS)
    with pytest.raises(NeedsConfirmation) as e:
        r.media("image", 1, lambda c, m: c.generate_image(m, "olma"), confirm_always=True)
    assert "gpt-image-1-mini" in e.value.estimate.describe() and r.log == []
    out, est = r.media("image", 1, lambda c, m: c.generate_image(m, "olma"), approved=True)
    assert out == PNG and est.cost == pytest.approx(0.011)
    assert r.ledger.recent()[0]["purpose"] == "Rasm yaratish"
    assert r.ledger.today("openai") == pytest.approx(0.011)


def test_auto_falls_back_when_provider_is_busy_not_when_key_is_wrong(tmp_path):
    r = make(tmp_path, KEYS)
    r.settings.update({"ai": {"fallback": True}})
    r.fails["openai"] = AiError("band", retryable=True)
    with pytest.raises(NeedsConfirmation):
        r.media("image", 1, lambda c, m: c.generate_image(m, "x"), approved=True)
    assert [x[0] for x in r.log] == ["openai"]
    r.log.clear()
    r.fails["openai"] = AiError("kalit noto‘g‘ri")
    with pytest.raises(AiError, match="kalit"):
        r.media("image", 1, lambda c, m: c.generate_image(m, "x"), approved=True)
    assert [x[0] for x in r.log] == ["openai"]


def test_budget_blocks_paid_media_before_any_call(tmp_path):
    r = make(tmp_path, KEYS, daily_budget_usd=0.005)
    with pytest.raises(BudgetExceeded):
        r.media("image", 1, lambda c, m: c.generate_image(m, "x"), approved=True)
    assert r.log == []
    out, est = r.media("tts", 0.5, lambda c, m: c.speak(m, "salom"))  # free Gemini TTS
    assert est.free and est.cost == 0.0 and out == WAV


def test_no_provider_for_a_direction_says_what_is_needed(tmp_path):
    r = make(tmp_path, {"deepseek": KEYS["deepseek"], "anthropic": KEYS["anthropic"]})
    with pytest.raises(AiUnavailable, match="OpenAI yoki Google Gemini"):
        r.candidates("image")
    with pytest.raises(AiUnavailable):
        r.candidates("tts")


# ---------------- MANUAL ----------------


def test_manual_media_is_never_swapped(tmp_path):
    r = make(tmp_path, KEYS)
    r.set_capability("image", "manual", "gemini", "gemini-3-pro-image")
    assert r.candidates("image") == [("gemini", {**caps.find("gemini", "image",
                                                               "gemini-3-pro-image"),
                                                 "free": False})]  # fmt: skip
    r.fails["gemini"] = AiError("band", retryable=True)
    with pytest.raises(AiError):  # MANUAL: no fallback to OpenAI
        r.media("image", 1, lambda c, m: c.generate_image(m, "x"), approved=True)
    assert [x[0] for x in r.log] == ["gemini"]
    r.set_capability("image", "auto")
    assert r.candidates("image")[0][0] == "openai"


def test_manual_choice_is_validated(tmp_path):
    r = make(tmp_path, KEYS)
    with pytest.raises(ValueError, match="imkoniyati yo‘q"):
        r.set_capability("image", "manual", "anthropic", "claude-opus-5-5")
    with pytest.raises(ValueError, match="topilmadi"):
        r.set_capability("tts", "manual", "openai", "gpt-image-2")
    with pytest.raises(ValueError):
        r.set_capability("telepatiya", "auto")
    r.set_capability("realtime", "manual", "gemini", "")
    assert r.cap_settings()["realtime"]["model"] == "stt+tts"


def test_manual_provider_without_key_explains(tmp_path):
    r = make(tmp_path, {"gemini": KEYS["gemini"]})
    r.settings.update({"ai": {"capabilities": {"tts": {"mode": "manual", "provider": "openai",
                                                       "model": "gpt-4o-mini-tts"}}}})  # fmt: skip
    with pytest.raises(AiUnavailable, match="kaliti kiritilmagan"):
        r.candidates("tts")


def test_manual_text_and_vision_models_are_used_as_chosen(tmp_path):
    r = make(tmp_path, KEYS)
    r.set_capability("text", "manual", "openai", "gpt-6-sol")
    reply = r.complete("chat", "s", [{"role": "user", "content": "salom"}], approved=True)
    assert reply.text == "openai:gpt-6-sol" and reply.provider == "openai"
    r.set_capability("vision", "manual", "anthropic", "claude-sonnet-5-5")
    pic = [
        {"role": "user", "content": "nima bor?", "images": [{"mime": "image/png", "data": "AA"}]}
    ]
    assert r.complete("vision", "s", pic, approved=True).text == "anthropic:claude-sonnet-5-5"
    r.set_capability("text", "manual", "deepseek", "deepseek-flash")
    r.set_capability("vision", "auto")
    with pytest.raises(AiUnavailable, match="katalogda mavjud emas"):
        r.settings.update({"ai": {"capabilities": {**r.cap_settings(), "vision": {
            "mode": "manual", "provider": "deepseek", "model": "removed-model"}}}})  # fmt: skip
        r.complete("vision", "s", pic, approved=True)


def test_auto_text_escalates_when_the_answer_is_not_usable(tmp_path):
    r = make(tmp_path, {"anthropic": KEYS["anthropic"]})
    ok = r.complete("chat", "s", [{"role": "user", "content": "x"}], approved=True,
                    accept=lambda t: "sonnet" in t)  # fmt: skip
    assert ok.text == "anthropic:claude-haiku-5-5"  # no dearer retry on first approval
    assert len(r.texts["anthropic"].calls) == 1
    r.set_capability("text", "manual", "anthropic", "claude-haiku-5-5")
    kept = r.complete("chat", "s", [{"role": "user", "content": "x"}], approved=True,
                      accept=lambda t: "sonnet" in t)  # fmt: skip
    assert kept.text == "anthropic:claude-haiku-5-5"  # MANUAL: never swapped


def test_free_text_prefers_stronger_model_at_same_cost(tmp_path):
    r = make(tmp_path, {"gemini": KEYS["gemini"]})
    reply = r.complete(
        "chat",
        "s",
        [{"role": "user", "content": "x"}],
        accept=lambda text: "gemini-3.8-flash" in text,
    )
    assert reply.model == "gemini-3.8-flash" and reply.cost == 0
    assert [c["model"] for c in r.texts["gemini"].calls] == ["gemini-3.8-flash"]


def test_status_for_the_menu(tmp_path):
    r = make(tmp_path, {"gemini": KEYS["gemini"]})
    st = r.capabilities_status()["capabilities"]
    assert set(st) == set(caps.CAPABILITIES)
    assert st["tts"]["auto_pick"]["provider"] == "gemini" and st["tts"]["auto_pick"]["free"]
    assert st["image"]["offers"]["openai"]["connected"] is False
    assert "anthropic" not in st["image"]["offers"]


# ---------------- HTTP shapes (official endpoints) ----------------


def test_openai_media_requests():
    net = Net({"/images/generations": {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
               "/images/edits": {"data": [{"b64_json": base64.b64encode(PNG).decode()}]},
               "/audio/speech": WAV, "/audio/transcriptions": {"text": "Привет"}})  # fmt: skip
    m = OpenAIMedia("sk-test-openai-123456", opener=net)
    assert m.generate_image("gpt-image-1-mini", "olma") == PNG
    body = json.loads(net.bodies[0])
    assert body["model"] == "gpt-image-1-mini" and body["size"] == "1024x1024"
    assert m.edit_image("gpt-image-2", "fonini oq qil", PNG, "image/png") == PNG
    assert b'name="image[]"' in net.bodies[1] and net.urls[1].endswith("/v1/images/edits")
    assert m.speak("gpt-4o-mini-tts", "salom", "marin") == WAV
    assert json.loads(net.bodies[2])["response_format"] == "wav"
    assert m.transcribe("gpt-4o-mini-transcribe", WAV) == "Привет"
    assert all("sk-test" not in json.dumps(h.get("Content-type", "")) for h in net.headers)


def test_gemini_media_requests():
    net = Net({"/interactions": {"steps": [{"type": "model_output", "content": [
        {"type": "image", "data": base64.b64encode(PNG).decode()}]}]}})  # fmt: skip
    g = GeminiMedia("AIza-test-gemini-1234567", opener=net)
    assert g.generate_image("gemini-3.1-flash-image", "olma", "1536x1024") == PNG
    body = json.loads(net.bodies[0])
    assert (
        body["response_format"]["type"] == "image"
        and body["response_format"]["aspect_ratio"] == "3:2"
    )
    assert net.headers[0]["X-goog-api-key"] == "AIza-test-gemini-1234567"
    assert "key=" not in net.urls[0]  # the key never goes into the URL (logs)
    pcm = b"\x01\x00" * 100
    audio = {"type": "audio", "data": base64.b64encode(pcm).decode()}
    net2 = Net({"/interactions": {"steps": [{"content": [audio]}]}})
    wav = GeminiMedia("AIza-test-gemini-1234567", opener=net2).speak(
        "gemini-3.8-flash-tts", "salom"
    )
    assert wav[:4] == b"RIFF" and wav.endswith(pcm)  # raw PCM wrapped as WAV
    assert json.loads(net2.bodies[0])["generation_config"]["speech_config"] == [{"voice": "Kore"}]


def test_media_api_errors_are_clear():
    for status, word in ((401, "kaliti"), (402, "mablag‘"), (404, "topilmadi")):
        with pytest.raises(AiError, match=word):
            OpenAIMedia("sk-test-x-123456", opener=Net({}, status)).speak("gpt-4o-mini-tts", "x")
    with pytest.raises(AiError) as e:
        GeminiMedia("AIza-test-1234567", opener=Net({"/interactions": {"steps": []}})).speak(
            "gemini-3.8-flash-tts", "x"
        )
    assert "ovoz qaytarmadi" in str(e.value)


# ---------------- the app: ✨ 🔊 🖼️ 📷 🧠 ----------------


def _api(tmp_path, monkeypatch, keys=KEYS, **ai):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    r = make(tmp_path, keys, **ai)
    return Api(overrides={"ai_router": r}), r


def test_chat_image_generation_asks_price_then_saves(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch)
    ask = api.chat("rasm yarat: qishloq maktabi, qishki manzara")
    assert ask.get("confirm") and "gpt-image-1-mini" in ask["reply"] and r.log == []
    done = api.confirm_ai(ask["confirm"], True)
    assert done["image"].endswith(".png") and done["image_data"].startswith("data:image/png")
    assert r.log == [("openai", "image", "gpt-image-1-mini")]
    # the new picture is "shu rasm": edit it
    ask2 = api.chat("shu rasmni fonini ko‘k qilib o‘zgartir")
    assert ask2.get("confirm") and "tahrirlayman" in ask2["reply"]
    api.confirm_ai(ask2["confirm"], True)
    assert r.log[-1][1] == "image_edit"


def test_chat_question_about_a_photo_uses_vision(tmp_path, monkeypatch):
    from test_drawing import _jpeg_with_gps

    api, r = _api(tmp_path, monkeypatch, {"anthropic": KEYS["anthropic"]})
    photo = tmp_path / "doska.jpg"
    photo.write_bytes(_jpeg_with_gps())
    api.set_context_file(str(photo))
    ask = api.chat("bu rasmda nima yozilgan?")
    assert ask.get("confirm") and "📷" in ask["reply"]
    ans = api.confirm_ai(ask["confirm"], True)
    assert ans["reply"].startswith("anthropic:")
    sent = r.texts["anthropic"].calls[-1]["messages"][0]["images"][0]["data"]
    assert sent and "GPS" not in base64.b64decode(sent)[:4000].decode("latin-1")


def test_speak_hides_personal_data_and_uses_free_tts(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch)
    out = api.ai_speak("Javob: **tayyor**. JSHSHIR 31234567890123 yozildi.")
    assert out["ok"] and base64.b64decode(out["audio"]) == WAV and out["provider"] == "gemini"
    assert out["cost"] == 0.0


def test_speak_with_paid_tts_respects_budget(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch, {"openai": KEYS["openai"]}, daily_budget_usd=0.0001)
    out = api.ai_speak("salom " * 300)
    assert not out["ok"] and "limit" in out["error"].lower() and r.log == []


def test_capability_menu_api(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch)
    st = api.ai_capabilities()
    assert st["enabled"] and set(st["capabilities"]) == set(caps.CAPABILITIES)
    bad = api.ai_set_capability("image", "manual", "deepseek", "x")
    assert not bad["ok"] and "yo‘q" in bad["error"]
    good = api.ai_set_capability("tts", "manual", "openai", "gpt-4o-mini-tts")
    assert good["ok"] and good["capabilities"]["tts"]["mode"] == "manual"
    assert api.ai_speak("salom", approved=True)["provider"] == "openai"


def test_camera_photo_becomes_the_chat_photo(tmp_path, monkeypatch):
    api, _ = _api(tmp_path, monkeypatch)
    out = api.save_camera_photo("data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8x").decode())
    assert out["ok"] and api.get_context_file() == out["path"]
    assert not api.save_camera_photo("javascript:alert(1)")["ok"]


def test_without_ai_media_explains(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    out = Api().chat("rasm yarat: olma")
    assert "AI kerak" in out["reply"]


def test_picture_requests_are_not_confused_with_office_work():
    from nexvara.app.api_media import _MAKE

    for yes in (
        "rasm yarat: olma",
        "maktab logotipini yasa",
        "AI bilan surat tayyorla",
        "create an image of a school",
    ):
        assert _MAKE.search(yes), yes
    for no in (
        "rasmli taqdimot yarat",
        "rasm qo‘shib hujjat yarat",
        "7-sinf test yarat",
        "Hisobot.xlsx dan diagramma yarat",
    ):
        assert not _MAKE.search(no), no


def test_fallback_off_or_free_mode_never_moves_to_another_paid_provider(tmp_path):
    r = make(tmp_path, KEYS)  # fallback off (default)
    r.fails["openai"] = AiError("band", retryable=True)
    with pytest.raises(AiError, match="band"):
        r.media("image", 1, lambda c, m: c.generate_image(m, "x"), approved=True)
    assert {x[0] for x in r.log} == {"openai"}
    r = make(tmp_path / "b", KEYS, fallback=True)  # free Gemini TTS busy, free mode on
    r.fails["gemini"] = AiError("chegara", retryable=True)
    with pytest.raises(AiError):
        r.media("tts", 0.2, lambda c, m: c.speak(m, "salom"))
    assert [x[0] for x in r.log] == ["gemini", "gemini"]  # both free Gemini voices, no OpenAI


def test_gemini_picture_is_jpeg_and_saved_as_jpg(tmp_path, monkeypatch):
    """Live check 2026-10-19: Gemini image models accept only response mime image/jpeg."""
    jpg = b"\xff\xd8\xff\xe0" + b"\0" * 32
    net = Net({"/interactions": {"steps": [{"content": [
        {"type": "image", "data": base64.b64encode(jpg).decode()}]}]}})  # fmt: skip
    out = GeminiMedia("AIza-test-gemini-1234567", opener=net).generate_image(
        "gemini-3.1-flash-lite-image", "x"
    )
    assert json.loads(net.bodies[0])["response_format"]["mime_type"] == "image/jpeg"
    api, r = _api(tmp_path, monkeypatch)
    r.set_capability("image", "manual", "gemini", "gemini-3.1-flash-lite-image")
    r.media_factory = lambda n, k: type("M", (), {"generate_image": lambda self, m, p: out})()
    ask = api.chat("rasm yarat: olma")
    done = api.confirm_ai(ask["confirm"], True)
    assert done["image"].endswith(".jpg") and done["image_data"].startswith("data:image/jpeg")


def test_model_without_free_tier_gets_a_clear_message():
    """Live check 2026-10-19: a Free Tier key gets 429 «limit: 0» for Gemini image models."""

    class Limit0(Net):
        def __call__(self, req, timeout):
            self.urls.append(req.full_url)
            msg = "Rate limit exceeded for model x (limit: 0 input tokens per minute on Free Tier)."
            body = json.dumps({"error": {"message": msg}}).encode()
            raise urllib.error.HTTPError(req.full_url, 429, "x", {}, io.BytesIO(body))

    net = Limit0({})
    with pytest.raises(AiError, match="bepul darajasida") as e:
        GeminiMedia("AIza-test-gemini-1234567", opener=net).generate_image(
            "gemini-3.1-flash-image", "x"
        )
    assert e.value.retryable and len(net.urls) == 1  # no pointless retries


def test_chat_answers_have_no_markdown_stars(tmp_path):
    """Live check 2026-10-19: a vision answer came as «**NEXVARA 2026**» — shown as stars."""
    r = make(tmp_path, {"anthropic": KEYS["anthropic"]})

    class Bold(TextFake):
        def complete(self, model, system, messages, max_tokens, effort="medium"):
            return Reply("Rasmda **NEXVARA 2026** va __qizil__ shakl bor.", model, 10, 10)

    r.factory = lambda n, k: Bold(n)
    out = r.complete("vision", "s", [{"role": "user", "content": "nima?"}], approved=True)
    assert out.text == "Rasmda NEXVARA 2026 va qizil shakl bor."
    plan = r.complete("plan", "s", [{"role": "user", "content": "x"}], approved=True)
    assert "**" in plan.text  # JSON/plans are left untouched


def test_openai_transcription_gets_the_uzbek_hint(tmp_path, monkeypatch):
    """Live check 2026-10-19: without a hint OpenAI wrote Uzbek speech in Kyrgyz-like Cyrillic."""
    api, r = _api(tmp_path, monkeypatch, {"openai": KEYS["openai"]})
    seen = {}

    class Ear(MediaFake):
        def transcribe(self, model, audio, mime="audio/wav", prompt=""):
            seen["prompt"] = prompt
            return "Бугун соат тўққизда дарс бор"

    r.media_factory = lambda n, k: Ear(n, [])
    text = api._transcribe(base64.b64encode(WAV * 100).decode(), "audio/wav", "x", approved=True)
    assert "lotin" in seen["prompt"] and text.startswith("Bugun soat to")


def test_streamed_wav_gets_real_sizes_for_android():
    """Live check 2026-10-19: OpenAI's WAV said 0xFFFFFFFF sizes; Android MediaPlayer refused it."""
    import struct

    from nexvara.ai.media import fix_wav_sizes, wav_from_pcm

    good = wav_from_pcm(b"\x01\x00" * 50)
    bad = bytearray(good)
    struct.pack_into("<I", bad, 4, 0xFFFFFFFF)
    struct.pack_into("<I", bad, 40, 0xFFFFFFFF)
    assert fix_wav_sizes(bytes(bad)) == good
    net = Net({"/audio/speech": bytes(bad)})
    assert OpenAIMedia("sk-test-openai-123456", opener=net).speak("gpt-4o-mini-tts", "x") == good


# ---------------- 🌐 internetdan qidirish ----------------


def test_web_search_requests_and_sources():
    cite = {"type": "url_citation", "url": "https://uzhydromet.uz/p", "title": "Gidromet",
            "start_index": 0, "end_index": 5}  # fmt: skip
    net = Net({"/responses": {"output": [
        {"type": "web_search_call", "status": "completed", "action": {"type": "search"}},
        {"type": "message", "content": [{"type": "output_text", "text": "Ertaga +18°C.",
                                         "annotations": [cite, cite]}]}]}})  # fmt: skip
    out = OpenAIMedia("sk-test-openai-123456", opener=net).web_search("gpt-5.4", "ob-havo")
    body = json.loads(net.bodies[0])
    assert net.urls[0].endswith("/v1/responses") and body["tools"] == [{"type": "web_search"}]
    assert out == {"text": "Ertaga +18°C.", "sources": [{"url": "https://uzhydromet.uz/p",
                                                         "title": "Gidromet"}]}  # fmt: skip
    net = Net({"/interactions": {"steps": [
        {"type": "google_search_call", "arguments": {"queries": ["ob-havo"]}},
        {"type": "google_search_result", "result": {"search_suggestions": "<div/>"}},
        {"type": "model_output", "content": [{"type": "text", "text": "Ertaga iliq.",
                                              "annotations": [cite]}]}]}})  # fmt: skip
    g = GeminiMedia("AIza-test-gemini-1234567", opener=net)
    assert g.web_search("gemini-3.5-flash-lite", "ob-havo")["sources"][0]["title"] == "Gidromet"
    assert json.loads(net.bodies[0])["tools"] == [{"type": "google_search"}]
    with pytest.raises(AiError, match="internetdan javob"):
        GeminiMedia("AIza-test-1234567", opener=Net({"/interactions": {"steps": []}})).web_search(
            "gemini-3.5-flash-lite", "x"
        )


def test_chat_web_search_free_gemini_runs_at_once_with_sources(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch)
    out = api.chat("internetdan qidir: Toshkentda ertaga ob-havo qanday? 90 123 45 67 ga yoz")
    assert not out.get("confirm") and ("gemini", "web", "gemini-3.5-flash-lite") in r.log
    sent = next(x[1] for x in r.log if x[0] == "question")
    assert "90 123 45 67" not in sent and "⟦TEL_1⟧" in sent  # personal data stays here
    assert "Toshkentda ertaga" in sent and "internetdan qidir" not in sent
    assert "90 123 45 67" in out["reply"]  # restored in the answer on this PC
    assert "Manbalar:" in out["reply"] and "https://meteo.uz/x" in out["reply"]
    assert "bepul" in out["reply"]


def test_chat_web_search_paid_asks_first(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch, keys={"openai": KEYS["openai"]})
    ask = api.chat("internetda eng yangi Python versiyasini top")
    assert ask.get("confirm") and "gpt-5.4" in ask["reply"] and r.log == []
    assert api.confirm_ai(ask["confirm"], False).get("reply")  # «Yo‘q»: nothing is called
    assert r.log == []
    ask = api.chat("so‘nggi yangiliklar: maktab ta’limi")
    done = api.confirm_ai(ask["confirm"], True)
    assert ("openai", "web", "gpt-5.4") in r.log and "Manbalar:" in done["reply"]
    assert r.ledger.today() > 0  # recorded in the cost ledger


def test_web_words_do_not_catch_office_work(tmp_path, monkeypatch):
    api, r = _api(tmp_path, monkeypatch)
    for text in ("Baholar.xlsx ni och", "word hujjat yarat", "rasm yarat: olma"):
        api.chat(text)
    assert not any(x[1] == "web" for x in r.log if len(x) > 2)
