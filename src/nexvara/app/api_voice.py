"""Spoken commands on the PC (mixed into app.api.Api): the chat's microphone records a short WAV,
Gemini writes down what was said (Uzbek, Latin), and the text runs as a normal chat command.

Windows' own speech recognition has no Uzbek, so Gemini is used (free in «Bepul rejim»). A voice
cannot be masked like text, so the first use asks for consent and remembers it.
"""

from __future__ import annotations

import base64
from typing import Any

MAX_AUDIO_BYTES = 2_500_000  # ~75 s of 16 kHz mono WAV
TRANSCRIBE = (
    "Sen nutqni matnga aylantiruvchisan. Ovozli yozuvdagi buyruqni so‘zma-so‘z, o‘zbek tilida "
    "lotin alifbosida yoz (fayl va dastur nomlarini o‘zgartirma). Faqat matnni qaytar: izoh, "
    "qo‘shtirnoq va tarjima yo‘q. Hech narsa eshitilmasa bo‘sh qator qaytar."
)
CONSENT = (
    "Ovozli buyruq Google Gemini’ga yuboriladi va matnga aylantiriladi. Matndagi shaxsiy "
    "ma’lumotlarni NEXVARA yashiradi, lekin ovozning o‘zini yashirib bo‘lmaydi. Bepul rejimda "
    "Google so‘rovlarni xizmatlarini yaxshilash uchun ishlatishi mumkin. Rozimisiz?"
)


class VoiceApi:
    _overrides: dict

    def voice_status(self) -> dict[str, Any]:
        router = self._router()
        ready = bool(router.config().get("enabled")) and bool(router.keys.load("gemini"))
        return {
            "ready": ready,
            "consent": bool(router.config().get("voice_consent")),
            "consent_text": CONSENT,
        }

    def voice_command(
        self, audio_b64: str, mime: str = "audio/wav", consent: bool = False
    ) -> dict[str, Any]:
        from nexvara.core.task import UserError

        st = self.voice_status()
        if not st["ready"]:
            return {
                "ok": False,
                "error": "Ovozli buyruq uchun Gemini kaliti kerak: Sozlamalar → "
                "AI (aistudio.google.com da bepul olinadi) va «AI yoqilgan» belgisi.",
            }
        if not st["consent"]:
            if not consent:
                return {"ok": False, "needs_consent": CONSENT}
            self._router().settings.update({"ai": {"voice_consent": True}})
        try:
            size = len(base64.b64decode(audio_b64 or "", validate=True))
        except ValueError:
            return {"ok": False, "error": "Ovoz yozuvi buzilgan"}
        if size < 2000:
            return {"ok": False, "error": "Ovoz juda qisqa — tugmani bosib, gapirib, yana bosing"}
        if size > MAX_AUDIO_BYTES:
            return {"ok": False, "error": "Ovoz juda uzun (1 daqiqagacha gapiring)"}
        msg = {
            "role": "user",
            "content": "Ovozli buyruqni yozib ber.",
            "audio": {
                "mime": mime if mime.startswith("audio/") else "audio/wav",
                "data": audio_b64,
            },
        }
        try:
            reply = self._router().complete(
                "command", TRANSCRIBE, [msg], max_tokens=600, expected_out=80, approved=True
            )
        except UserError as e:
            return {"ok": False, "error": str(e)}
        text = " ".join(reply.text.split()).strip(' "«»')
        if not text:
            return {"ok": False, "error": "Gap eshitilmadi — mikrofonga yaqinroq gapiring"}
        return {"ok": True, "text": text}
