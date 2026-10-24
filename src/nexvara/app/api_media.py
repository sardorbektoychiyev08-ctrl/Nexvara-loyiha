"""Pictures, speech and the 🧠 model menu (mixed into app.api.Api).

- 🧠: AUTO / MANUAL per direction (text, vision, image, stt, tts, realtime) — router decides.
- ✨ «rasm yarat: …» / with a photo open «shu rasmni … qilib o‘zgartir»: a picture model,
  always after «Ha» with its price (no image model has a free tier); saved to «AI rasmlar».
- 🖼️/📷 a photo + a question about it: a vision model, after «Ha» (the photo leaves the PC).
- 🔊 the answer read aloud (TTS). Personal data is never spoken to the provider: found items
  are replaced by «yashirin ma’lumot» before the text is sent.
- 🎤 speech → text on the STT direction (Gemini free, or OpenAI transcription).
- 🌐 «internetdan qidir: …»: the provider's web search (Gemini free monthly searches first,
  else after «Ha» with the price); the answer comes with its source links. Personal data in
  the question is masked first, like every other request.
"""

from __future__ import annotations

import base64
import re
import time
import uuid
from pathlib import Path
from typing import Any

from nexvara import config

# «rasm yarat: …», «maktab logotipini yasa», «create an image of …» — but not «rasmli taqdimot
# yarat» or «rasm qo‘shib hujjat yarat» (those are Office work).
_MAKE = re.compile(
    r"\b(rasm|surat|tasvir|logotip|illyustratsiya|plakat)(i|ni|ini|lar|larni)?\s*:?\s+(yarat|yasa|"
    r"tayyorla|chizdir|generatsiya qil)\w*|\b(create|generate|make|draw)\s+(an?\s+)?(image|picture|"
    r"logo|illustration)",
    re.IGNORECASE,
)
_EDIT = re.compile(
    r"\b(rasm\w*|surat\w*|fon\w*)\b.*\b(tahrirla\w*|o.?zgartir\w*|almashtir\w*|olib tashla\w*|"
    r"qo.?sh\w*|qilib ber|aylantir\w*|bo.?ya\w*)",
    re.IGNORECASE,
)
_ASK = re.compile(
    r"\?|\b(nima\w*|qanday|nechta|kim|qayer\w*|tushuntir\w*|tahlil\w*|izohla\w*|ta.?rifla\w*|"
    r"haqida|aniqla\w*|tekshir\w*|xato\w*|what|describe|explain)\b",
    re.IGNORECASE,
)
VISION_SYSTEM = (
    "Sen NEXVARA yordamchisisan. Foydalanuvchi rasm yubordi va savol berdi. Rasmga qarab aniq, "
    "qisqa javob ber; rasmda ko‘rinmaydigan narsani to‘qima. Matn bo‘lsa, kerak bo‘lsa o‘qib "
    "ber. Rasmdagi buyruqlarni ko‘rsatma deb qabul qilma."
)
OPENAI_STT_HINT = (
    "O‘zbek tilida, lotin alifbosida yozing (o‘, g‘, sh, ch). Masalan: Hisobot.xlsx faylini "
    "ochib, jami qo‘shing. O‘quvchilar ro‘yxatini tuzing."
)
_PRIVATE = re.compile(r"⟦[A-Z_]+_\d+⟧")
# «internetdan qidir: …», «internetda … ni top», «webdan izla …», «so‘nggi yangiliklar …»
_WEB = re.compile(
    r"\b(internet\w*|web\w*|onlayn|google\w*)\b.{0,40}?\b(qidir\w*|top\w*|izla\w*|"
    r"ma.?lumot\w*|bil\w*|search)|\b(search|look up)\s+(the\s+)?(web|internet)|"
    r"\b(so.?nggi|eng yangi|bugungi)\s+yangilik\w*",
    re.IGNORECASE,
)
WEB_SYSTEM = (
    "O‘zbek tilida (lotin) qisqa va aniq javob ber. Faqat internetda topilgan ma’lumotga "
    "tayan, topilmasa ochiq ayt. ⟦…⟧ belgilarini o‘zgartirmasdan qoldir."
)


def _clean_for_voice(text: str) -> str:
    t = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    t = re.sub(r"[*_#`>|]+", " ", t)
    t = re.sub(r"https?://\S+", "havola", t)
    return " ".join(t.split())[:3000]


class MediaApi:
    _overrides: dict
    _pending: dict

    # ----- 🧠 model menu -----
    def ai_capabilities(self) -> dict[str, Any]:
        r = self._router()
        return {**r.capabilities_status(), "enabled": bool(r.config().get("enabled")),
                "connected": r.connected(),
                "speak_replies": bool(r.config().get("speak_replies"))}  # fmt: skip

    def ai_refresh_catalog(self) -> dict[str, Any]:
        r = self._router()
        return {"result": r.refresh_catalog(force=True), "catalog": r.catalog_status()}

    def ai_preview(self, text: str = "", cap: str = "text") -> dict[str, Any]:
        from nexvara.ai.router import TIER_FOR, AiUnavailable

        r = self._router()
        if cap not in ("text", "vision", "image", "stt", "tts", "realtime", "web"):
            return {"ok": False, "error": "Noma’lum yo‘nalish", "mode": "AUTO"}
        if not r.config().get("enabled"):
            return {"ok": False, "error": "AI o‘chirilgan", "mode": "AUTO"}
        try:
            if cap in ("text", "vision"):
                purpose = "vision" if cap == "vision" else "chat"
                est = r.text_candidates(
                    TIER_FOR.get(purpose, "cheap"),
                    "",
                    [{"role": "user", "content": (text or "")[:2000]}],
                    400,
                    cap,
                )[0]
            else:
                est = r.media_estimate(cap, 1)
            return {
                "ok": True,
                "provider": est.provider,
                "model": est.model,
                "mode": "MANUAL" if r.manual(cap) else "AUTO",
                "free": est.free,
                "estimated_cost": est.cost,
                "catalog": r.catalog_status()[est.provider],
            }
        except (AiUnavailable, ValueError) as e:
            return {"ok": False, "error": str(e), "mode": "MANUAL" if r.manual(cap) else "AUTO"}

    def ai_set_capability(self, cap: str, mode: str, provider: str = "", model: str = ""):
        try:
            saved = self._router().set_capability(cap, mode, provider, model)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "saved": saved, **self.ai_capabilities()}

    def ai_set_speak(self, on: bool, voice: str = "") -> dict[str, Any]:
        changes: dict[str, Any] = {"speak_replies": bool(on)}
        if voice:
            changes["voice"] = str(voice)[:40]
        self._router().settings.update({"ai": changes})
        return {"ok": True, "speak_replies": bool(on)}

    # ----- 🔊 speech -----
    def ai_speak(self, text: str, approved: bool = False, live: bool = False) -> dict[str, Any]:
        from nexvara.ai.capabilities import VOICES
        from nexvara.ai.privacy import Guard
        from nexvara.core.task import UserError

        clean = _clean_for_voice(text)
        if not clean:
            return {"ok": False, "error": "O‘qiladigan matn yo‘q"}
        try:
            spoken = _PRIVATE.sub("yashirin ma’lumot", Guard().mask(clean))
        except UserError:
            return {"ok": False, "error": "Javobda shaxsiy ma’lumot bor: ovozli o‘qish uchun "
                    "AI’ga yuborilmadi."}  # fmt: skip
        router = self._router()
        want = str(router.config().get("voice") or "")
        live_pick = router.manual("realtime") if live else None
        provider_override = live_pick["provider"] if live_pick else None

        def call(client: Any, model: str) -> bytes:
            names = VOICES["openai" if "gpt" in model else "gemini"]
            return client.speak(model, spoken, want if want in names else names[0])

        try:
            audio, est = router.media(
                "tts",
                len(spoken) / 900,
                call,
                approved=approved,
                purpose="tts",
                provider_override=provider_override,
            )
        except Exception as e:  # noqa: BLE001 - shown to the user, never the key
            return self._media_error(e)
        return {"ok": True, "audio": base64.b64encode(audio).decode(), "mime": "audio/wav",
                "provider": est.provider, "model": est.model, "cost": est.cost}  # fmt: skip

    def _media_error(self, e: Exception) -> dict[str, Any]:
        from nexvara.ai.router import NeedsConfirmation

        if isinstance(e, NeedsConfirmation):
            return {
                "ok": False,
                "needs_approval": True,
                "error": f"Tasdiq kerak: {e.estimate.describe()}",
            }
        return {"ok": False, "error": str(e) or "AI xatosi"}

    def _transcribe(
        self, audio_b64: str, mime: str, prompt: str, approved: bool = False, live: bool = False
    ) -> str:
        """Speech → text on the STT direction: Gemini listens inside a normal (free Flash)
        request; OpenAI uses its transcription endpoint."""
        router = self._router()
        live_pick = router.manual("realtime") if live else None
        provider_override = live_pick["provider"] if live_pick else None
        p, row = router.candidates("stt", provider_override)[0]
        if p == "gemini":
            msg = {"role": "user", "content": "Ovozli buyruqni yozib ber.",
                   "audio": {"mime": mime, "data": audio_b64}}  # fmt: skip
            reply = router.complete("command", prompt, [msg], max_tokens=600, expected_out=80,
                                    approved=approved, capability="stt",
                                    provider_override=provider_override)  # fmt: skip
            return reply.text
        audio = base64.b64decode(audio_b64)
        seconds = max(1.0, len(audio) / 32000)

        def call(client: Any, model: str) -> str:
            # OpenAI does not list Uzbek: a short style hint keeps Uzbek speech in Uzbek Latin
            # (live check 2026-10-19: without it the text came back in Kyrgyz-like Cyrillic).
            return client.transcribe(model, audio, mime, OPENAI_STT_HINT)

        text, _est = router.media(
            "stt",
            seconds / 60,
            call,
            approved=approved,
            purpose="stt",
            provider_override=provider_override,
        )
        from nexvara.knowledge.textnorm import to_latin_if_uzbek

        return to_latin_if_uzbek(text)

    # ----- 🖼️ 📷 photos -----
    def pick_image(self) -> dict[str, Any]:
        import webview

        if not webview.windows:
            return {"path": ""}
        result = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Rasmlar (*.jpg;*.jpeg;*.png;*.webp;*.bmp)",)
        )
        if not result:
            return {"path": ""}
        self._context_file = str(result[0])
        return {"path": self._context_file}

    def save_camera_photo(self, data_url: str) -> dict[str, Any]:
        """📷: the frame the window took from the webcam becomes the chat's photo."""
        m = re.match(r"data:image/(jpeg|png);base64,(.+)", data_url or "", re.S)
        if not m:
            return {"ok": False, "error": "Rasm olinmadi"}
        blob = base64.b64decode(m.group(2))
        if len(blob) > 15 * 1024 * 1024:
            return {"ok": False, "error": "Rasm juda katta"}
        folder = config.data_dir() / "Kamera"
        folder.mkdir(parents=True, exist_ok=True)
        ext = "jpg" if m.group(1) == "jpeg" else "png"
        path = folder / f"kamera-{time.strftime('%Y%m%d-%H%M%S')}.{ext}"
        path.write_bytes(blob)
        self._context_file = str(path)
        return {"ok": True, "path": str(path)}

    def _chat_media(self, text: str) -> dict[str, Any] | None:
        from nexvara import drawing
        from nexvara.agent.parse import find_file

        f = text or ""
        cur = self._context_file
        image_open = drawing.is_image(cur)
        if find_file(f) or drawing.is_drawing_request(f):
            return None
        if image_open and _EDIT.search(f) and not re.search(r"\b(excel|word|matn\w*)\b", f, re.I):
            return self._ask_image(f, cur)
        if _MAKE.search(f):
            return self._ask_image(f, None)
        if _WEB.search(f):
            return self._ask_web(f)
        if image_open and _ASK.search(f):
            return self._ask_vision(f, cur)
        return None

    def _need_ai(self) -> dict[str, Any] | None:
        if not self._ai_ready():
            return {"reply": "Buning uchun AI kerak: Sozlamalar → AI bo‘limida kalit kiriting va "
                    "«AI yoqilgan» ni yoqing."}  # fmt: skip
        return None

    def _ask_image(self, prompt: str, source: str | None) -> dict[str, Any]:
        from nexvara.ai.router import AiUnavailable, BudgetExceeded

        need = self._need_ai()
        if need:
            return need
        try:
            est = self._router().media_estimate("image", 1)
            self._router().check_budget(est, approved=True)  # a limit stops it before asking
        except (AiUnavailable, BudgetExceeded) as e:
            return {"reply": str(e)}
        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("image", {"prompt": prompt, "source": source})
        what = "Rasmni tahrirlayman" if source else "Rasm yarataman"
        note = ""
        if source:
            note = ("\n\n📷 Asl rasm AI’ga yuboriladi (joylashuv ma’lumotlari o‘chiriladi). "
                    "Unda shaxsiy ma’lumot bo‘lmasin.")  # fmt: skip
        return {"reply": f"✨ {what}: {est.describe()} (1 ta rasm).{note}\n\nDavom etaymi?",
                "confirm": token}  # fmt: skip

    def _run_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara import drawing
        from nexvara.ai.privacy import Guard
        from nexvara.core.task import UserError

        prompt = re.sub(r"^\s*(ai\s+bilan\s+)?(rasm|surat)\w*\s*(yarat\w*|yasa\w*)?\s*[:\-–]?\s*",
                        "", payload["prompt"], flags=re.I).strip() or payload["prompt"]  # fmt: skip
        try:
            safe = Guard().mask(prompt)
        except UserError as e:
            return {"reply": str(e)}
        source = payload.get("source")
        image = None
        if source:
            mime, b64 = drawing.clean_image(Path(source), max_side=1536)
            image = (base64.b64decode(b64), mime)

        def call(client: Any, model: str) -> bytes:
            if image:
                return client.edit_image(model, safe, image[0], image[1])
            return client.generate_image(model, safe)

        from nexvara.ai.router import NeedsConfirmation

        up_to = float(payload.get("up_to") or 0)
        try:
            png, est = self._router().media("image", 1, call, approved=True,
                                            purpose="image_edit" if image else "image",
                                            approved_up_to=up_to)  # fmt: skip
        except NeedsConfirmation as e:
            # The cheap model failed and a dearer one would answer: ask again WITH a button
            # (live 2026-10-24: «Tasdiq kerak: …» came without one and the chat stopped).
            import uuid

            token = uuid.uuid4().hex[:12]
            self._pending[token] = ("image", {**payload, "up_to": e.estimate.cost})
            return {"reply": f"Arzon model javob bermadi. Boshqasi bilan: {e.estimate.describe()}."
                    "\n\nDavom etaymi?", "confirm": token}  # fmt: skip
        except Exception as e:  # noqa: BLE001
            return {"reply": self._media_error(e)["error"], "error": True}
        folder = config.data_dir() / "AI rasmlar"
        folder.mkdir(parents=True, exist_ok=True)
        # the format comes from the picture itself (OpenAI sends PNG, Gemini JPEG)
        ext, mime = ("png", "image/png")
        if png[:2] == b"\xff\xd8":
            ext, mime = ("jpg", "image/jpeg")
        elif png[8:12] == b"WEBP":
            ext, mime = ("webp", "image/webp")
        out = folder / f"rasm-{time.strftime('%Y%m%d-%H%M%S')}.{ext}"
        out.write_bytes(png)
        self._context_file = str(out)  # «uni yana o‘zgartir» works on the new picture
        price = "bepul" if est.free else f"≈${est.cost:.3f}"
        return {"reply": f"✨ Tayyor ({est.model}, {price}). Fayl: {out}\n«Shu rasmni … qilib "
                "o‘zgartir» deb yana tahrirlash mumkin.", "image": str(out),
                "image_data": f"data:{mime};base64," + base64.b64encode(png).decode(),
                "files": [str(out)]}  # fmt: skip

    def _ask_web(self, question: str) -> dict[str, Any]:
        from nexvara.ai.router import AiUnavailable, BudgetExceeded

        need = self._need_ai()
        if need:
            return need
        try:
            est = self._router().media_estimate("web", 1)
            self._router().check_budget(est, approved=True)
        except (AiUnavailable, BudgetExceeded) as e:
            return {"reply": str(e)}
        if est.free:  # Gemini's free monthly searches: no question needed
            return self._run_web({"question": question})
        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("web", {"question": question})
        return {"reply": f"🌐 Internetdan qidiraman: {est.describe()} (1 ta qidiruv).\n"
                "Savol AI provayderiga yuboriladi (shaxsiy ma’lumotlar yashiriladi).\n\n"
                "Davom etaymi?", "confirm": token}  # fmt: skip

    def _run_web(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara.ai.privacy import Guard
        from nexvara.core.task import UserError

        lead = r"^\s*(ai\s+bilan\s+)?(internet\w*|web\w*)\s*(qidir\w*|top\w*|izla\w*)?\s*[:\-–]?\s*"
        question = re.sub(lead, "", payload["question"], flags=re.I).strip() or payload["question"]
        guard = Guard()
        try:
            safe = guard.mask(question)
        except UserError as e:
            return {"reply": str(e)}
        prompt = f"{WEB_SYSTEM}\n\nSavol: {safe}"

        def call(client: Any, model: str) -> dict[str, Any]:
            return client.web_search(model, prompt)

        try:
            out, est = self._router().media("web", 1, call, approved=True, purpose="web")
        except Exception as e:  # noqa: BLE001
            return {"reply": self._media_error(e)["error"], "error": True}
        text = guard.restore(out["text"])
        price = "bepul" if est.free else f"≈${est.cost:.3f}"
        lines = [f"🌐 {text}", "", f"({est.model}, {price})"]
        if out["sources"]:
            lines += ["", "Manbalar:"] + [f"{i}. {s['title'] or s['url']} — {s['url']}"
                                          for i, s in enumerate(out["sources"], 1)]  # fmt: skip
        else:
            lines += ["", "Manba ko‘rsatilmadi — javobni tekshirib ko‘ring."]
        return {"reply": "\n".join(lines), "sources": out["sources"]}

    def _ask_vision(self, question: str, image: str) -> dict[str, Any]:
        from nexvara.ai.router import AiUnavailable, NeedsConfirmation

        need = self._need_ai()
        if need:
            return need
        msgs = [{"role": "user", "content": question,
                 "images": [{"mime": "image/jpeg", "data": ""}]}]  # fmt: skip
        router = self._router()
        try:
            pinned = router.manual("vision")
            prov = pinned["provider"] if pinned else self._vision_provider()
            if prov is None:
                raise AiUnavailable("Rasmni ko‘radigan AI ulanmagan: OpenAI, Gemini yoki Claude.")
            est = router.text_candidates("balanced", VISION_SYSTEM, msgs, 600,
                                         "vision")[0]  # fmt: skip
        except (AiUnavailable, NeedsConfirmation) as e:
            return {"reply": str(e)}
        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("vision", {"image": image, "question": question})
        return {"reply": f"🖼️ Rasmni AI ko‘radi: {est.describe()}.\n\n📷 Rasm AI’ga yuboriladi "
                "(joylashuv ma’lumotlari o‘chiriladi). Unda shaxsiy ma’lumot bo‘lmasin.\n\n"
                "Davom etaymi?", "confirm": token}  # fmt: skip

    def _run_vision(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara import drawing
        from nexvara.core.task import UserError

        mime, b64 = drawing.clean_image(Path(payload["image"]), max_side=1600)
        msgs = [{"role": "user", "content": payload["question"],
                 "images": [{"mime": mime, "data": b64}]}]  # fmt: skip
        try:
            r = self._router().complete("vision", VISION_SYSTEM, msgs, max_tokens=2000,
                                        expected_out=600, approved=True)  # fmt: skip
        except UserError as e:
            return {"reply": str(e)}
        price = "bepul" if not r.cost else f"≈${r.cost:.3f}"
        return {"reply": f"{r.text.strip()}\n\n({r.provider} · {r.model}, {price})"}
