"""Reading a photo in chat (mixed into app.api.Api): "shu rasmdagi matnni o‘qi".

Free and offline by default (Windows OCR, enhanced photo, best of Latin/Cyrillic). With
"AI bilan" — handwriting, tables, messy photos — the picture goes to a vision model after the
user's "Ha" (EXIF/GPS removed first, like drawings); the text is saved next to the photo.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_READ = re.compile(
    r"\b(matn\w*|yozuv\w*|o[‘’']?qi\w*|ko[‘’']?chir\w*|ocr|tekst\w*|qo[‘’']?lyozma\w*)\b",
    re.IGNORECASE,
)
PROMPT = (
    "Transcribe ALL text in the image exactly as written (printed or handwritten), in its own "
    "language and script (Uzbek Latin/Cyrillic, Russian, English). Keep paragraphs and line "
    "breaks, render tables as lines with ' | ' between cells. Output only the text."
)


_TO_OFFICE = re.compile(
    r"\b(excel|eksel|xlsx|jadval\w*|word|vord|docx|hujjat\w*)\b.*\b(qil|aylantir|otkaz|ko.?chir|"
    r"o.?tkaz|yarat|tuz|sol)\w*|\b(qil|aylantir|o.?tkaz)\w*\b.*\b(excel|word)\w*",
    re.IGNORECASE,
)


def office_target(text: str) -> str | None:
    """«shu rasmni Excel qil» -> "excel", «… Word hujjatga aylantir» -> "word"."""
    from nexvara.knowledge.textnorm import fold

    f = fold(text)
    if not _TO_OFFICE.search(f):
        return None
    if re.search(r"\b(word|vord|docx|hujjat\w*)\b", f):
        return "word"
    return "excel"


class ReadingApi:
    _overrides: dict
    _pending: dict

    def _chat_read(self, text: str) -> dict[str, Any] | None:
        from nexvara import drawing
        from nexvara.app.api import _wants_ai

        cur = self._context_file
        from nexvara.agent.parse import find_file

        to = office_target(text or "") if not find_file(text or "") else None
        if to and cur and (drawing.is_image(cur) or (cur.lower().endswith(".txt")
                                                      and Path(cur).is_file())):  # fmt: skip
            return self._chat_photo_office(cur, to, _wants_ai(text), text)
        if (
            not drawing.is_image(cur)
            or not _READ.search(text or "")
            or drawing.is_drawing_request(text)
        ):
            return None
        if _wants_ai(text):
            if not self._ai_ready():
                return {
                    "reply": "AI bilan o‘qish uchun Sozlamalar → AI’da OpenAI, Gemini yoki Claude "
                    "kalitini kiriting. AI’siz o‘qish uchun «AI bilan» so‘zini yozmang."
                }
            if self._vision_provider() is None:
                return {
                    "reply": "Rasmni o‘qiydigan AI ulanmagan: OpenAI, Gemini yoki Claude kerak."
                }
            from nexvara.ai.router import AiUnavailable

            msgs = [
                {
                    "role": "user",
                    "content": "Read the image.",
                    "images": [{"mime": "image/jpeg", "data": ""}],
                }
            ]
            try:
                est = self._router().estimate(
                    "balanced", PROMPT, msgs, 1500, self._vision_provider()
                )
            except AiUnavailable as e:
                return {"reply": str(e)}
            import uuid

            token = uuid.uuid4().hex[:12]
            self._pending[token] = ("read", {"image": cur})
            return {
                "reply": f"Rasmdagi matnni AI o‘qiydi (qo‘lyozma ham): {est.describe()}."
                "\n\n📷 Rasm AI’ga yuboriladi (joylashuv ma’lumotlari o‘chiriladi). "
                "Unda shaxsiy ma’lumot bo‘lmasin."
                "\n\nDavom etaymi?",
                "confirm": token,
            }
        reader = self._overrides.get("ocr")
        if reader is None:
            from nexvara.knowledge.ocr import ocr_image as reader
        lang = "ru" if re.search(r"\bkirill\w*|\brus\w*", text, re.I) else ""
        try:
            out = reader(Path(cur), lang)
        except Exception as e:
            return {"reply": f"Rasmni o‘qib bo‘lmadi: {e}"}
        return self._read_done(cur, out, "kompyuterda, internetsiz")

    def _chat_photo_office(self, cur: str, to: str, ai: bool, text: str) -> dict[str, Any]:
        """Photo (or its OCR text) → Excel/Word. With «AI bilan» the photo is read by a
        vision AI after «Ha» (tables come out much better)."""
        from nexvara import drawing

        if ai and drawing.is_image(cur):
            return self._ask_read_ai(cur, to)
        if drawing.is_image(cur):
            reader = self._overrides.get("ocr")
            if reader is None:
                from nexvara.knowledge.ocr import ocr_image as reader
            lang = "ru" if re.search(r"\bkirill\w*|\brus\w*", text, re.I) else ""
            try:
                body = reader(Path(cur), lang)
            except Exception as e:
                return {"reply": f"Rasmni o‘qib bo‘lmadi: {e}"}
            Path(cur).with_suffix(".txt").write_text(body, encoding="utf-8")
            how = "kompyuterda, internetsiz"
        else:
            body = Path(cur).read_text(encoding="utf-8", errors="replace")
            how = "oldin o‘qilgan matndan"
        return self._photo_to_office(cur, body, to, how)

    def _photo_to_office(self, image: str, body: str, to: str, how: str) -> dict[str, Any]:
        from nexvara import photodoc
        from nexvara.core.task import UserError

        if to == "excel":
            try:
                res = photodoc.convert(body, image, "excel")
            except UserError as e:
                return {"reply": str(e), "error": True}
            self._context_file = res["path"]
            return {"reply": f"📊 Rasmdagi jadval Excel’ga o‘tkazildi ({how}): "
                    f"{res['rows']} qator, "
                    f"{res['cols']} ustun, ramka va sarlavha bilan.\nFayl: {res['path']}\n"
                    "Raqamlarni rasm bilan solishtirib chiqing: OCR ba’zan adashadi.",
                    "files": [res["path"]]}  # fmt: skip
        fn = self._overrides.get("photo_word")
        keep = self._keep_open()

        def work(task: Any) -> dict[str, Any]:
            with task.step("Word hujjat") as s:
                if fn is not None:
                    res = fn(body, image)
                else:
                    res = photodoc.convert(body, image, "word", keep_open=keep)
                s.detail = Path(res["path"]).name
            return res

        snap = self._runner.start("Rasm → Word", work).snapshot()
        return {"reply": f"📄 Rasmdagi matnni ({how}) Word hujjatga yozyapman — jarayon o‘ng "
                "panelda.", "task": snap}  # fmt: skip

    def _ask_read_ai(self, cur: str, to: str = "") -> dict[str, Any]:
        if not self._ai_ready():
            return {
                "reply": "AI bilan o‘qish uchun Sozlamalar → AI’da OpenAI, Gemini yoki Claude "
                "kalitini kiriting. AI’siz o‘qish uchun «AI bilan» so‘zini yozmang."
            }
        if self._vision_provider() is None:
            return {"reply": "Rasmni o‘qiydigan AI ulanmagan: OpenAI, Gemini yoki Claude kerak."}
        from nexvara.ai.router import AiUnavailable

        msgs = [{"role": "user", "content": "Read the image.",
                 "images": [{"mime": "image/jpeg", "data": ""}]}]  # fmt: skip
        try:
            est = self._router().estimate("balanced", PROMPT, msgs, 1500, self._vision_provider())
        except AiUnavailable as e:
            return {"reply": str(e)}
        import uuid

        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("read", {"image": cur, "to": to})
        what = {"excel": " va Excel jadvalga o‘tkazadi", "word": " va Word hujjatga yozadi"}
        return {"reply": f"Rasmdagi matnni AI o‘qiydi (qo‘lyozma ham){what.get(to, '')}: "
                f"{est.describe()}.\n\n📷 Rasm AI’ga yuboriladi (joylashuv ma’lumotlari "
                "o‘chiriladi). Unda shaxsiy ma’lumot bo‘lmasin.\n\nDavom etaymi?",
                "confirm": token}  # fmt: skip

    def _read_done(self, image: str, out: str, how: str) -> dict[str, Any]:
        txt = Path(image).with_suffix(".txt")
        txt.write_text(out, encoding="utf-8")
        self._context_file = str(txt)  # "shu matndan test tuz" continues from here
        if not out.strip():
            return {
                "reply": "Rasmda matn topilmadi. Yaqinroq, yorug‘ joyda, tekis suratga oling yoki "
                "«AI bilan o‘qi» deb yozing (qo‘lyozma uchun)."
            }
        body = out if len(out) <= 3500 else out[:3500] + "…"
        return {
            "reply": f"📄 Rasmdagi matn ({how}):\n\n{body}\n\nFayl: {txt.name}. Endi «shu matndan "
            "test tuz» yoki «AI bilan qisqa konspekt qil» deyishingiz mumkin.",
            "text_file": str(txt),
        }

    def _run_read(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara import drawing
        from nexvara.core.task import UserError

        img = drawing.clean_image(Path(payload["image"]), max_side=2000)
        msgs = [
            {
                "role": "user",
                "content": "Read the image.",
                "images": [{"mime": img[0], "data": img[1]}],
            }
        ]
        try:
            reply = self._router().complete(
                "ocr", PROMPT, msgs, max_tokens=4000, expected_out=1500, approved=True
            )
        except UserError as e:
            return {"reply": str(e)}
        how = f"AI, ≈${reply.cost:.3f}"
        if payload.get("to"):
            body = reply.text.strip()
            Path(payload["image"]).with_suffix(".txt").write_text(body, encoding="utf-8")
            return self._photo_to_office(payload["image"], body, payload["to"], how)
        return self._read_done(payload["image"], reply.text.strip(), how)
