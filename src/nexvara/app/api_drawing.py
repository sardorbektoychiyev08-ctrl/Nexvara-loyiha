"""Drawings in chat (mixed into app.api.Api): "velosiped g‘ildiragi chizmasini chizib ber",
or a photo of a hand-drawn sketch + "shu chizmani mukammal chiz". See nexvara/drawing.py."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


class DrawingApi:
    _overrides: dict
    _history: Any
    _pending: dict
    _output_dir: Path | None

    def _chat_drawing(self, text: str) -> dict[str, Any] | None:
        from nexvara import drawing
        from nexvara.agent.parse import find_file
        from nexvara.app.api import _BACKGROUND
        from nexvara.knowledge.service import parse_test_request
        from nexvara.knowledge.textnorm import fold

        last = getattr(self, "_last_drawing", None)
        edit = last is not None and drawing.is_edit_request(text)
        if last is None and drawing.is_edit_request(text):
            return {"reply": "Hali chizma yo‘q. Avval «… chizmasini chizib ber» deb yozing yoki "
                    "qo‘lda chizilgan rasmni yuboring."}  # fmt: skip
        if not edit and (
            not drawing.is_drawing_request(text) or parse_test_request(text) is not None
        ):
            return None
        f = fold(text)
        if re.search(r"\b(diagramma|grafik|dashboard)\w*", f) or "chizmachilik" in f:
            return None  # Excel charts and BI have their own commands; a school subject is not
        if find_file(text) and not drawing.is_image(find_file(text)):
            return None
        cur = self._context_file
        image = (
            None if edit else (cur if drawing.is_image(cur) and drawing.wants_photo(text) else None)
        )
        if not self._ai_ready():
            return {"reply": "Chizma chizish uchun AI kerak: Sozlamalar → AI bo‘limida OpenAI, "
                    "Gemini yoki Claude kalitini kiriting va AI’ni yoqing. Qo‘lda chizilgan rasm "
                    "bo‘yicha chizish ham shu provayderlar orqali ishlaydi."}  # fmt: skip
        from nexvara.ai.router import TIER_FOR, AiUnavailable

        router = self._router()
        if image and self._vision_provider() is None:
            return {"reply": "Rasmni o‘qiydigan AI ulanmagan: OpenAI, Gemini yoki Claude "
                    "kalitini kiriting (DeepSeek rasmni o‘qimaydi)."}  # fmt: skip
        system, msgs = drawing.ai_messages(text, ("image/jpeg", "") if image else None,
                                           last if edit else None)  # fmt: skip
        try:
            est = router.estimate(TIER_FOR["drawing"], system, msgs, 5000, self._vision_provider()
                                  if image else None)  # fmt: skip
        except AiUnavailable as e:
            return {"reply": str(e)}
        import uuid

        token = uuid.uuid4().hex[:12]
        bg = bool(_BACKGROUND.search(text))
        self._pending[token] = ("drawing", {"text": text, "image": image, "background": bg,
                                            "edit": edit})  # fmt: skip
        what = f"«{last['title']}» chizmasini o‘zgartiraman" if edit else "Chizmani AI tuzadi"
        reply = f"{what}, NEXVARA chizadi (PDF, PNG, AutoCAD DXF): {est.describe()}."
        if image:
            reply += (f"\n\n📷 Rasm: {Path(image).name}. U AI’ga yuboriladi — joylashuv (GPS) va "
                      "boshqa yashirin ma’lumotlari o‘chiriladi, lekin rasmning o‘zini yashirib "
                      "bo‘lmaydi. Rasmda shaxsiy ma’lumot (ism, yuz, hujjat) "
                      "bo‘lmasin.")  # fmt: skip
        return {"reply": reply + "\n\nDavom etaymi?", "confirm": token}

    def _vision_provider(self) -> str | None:
        from nexvara.ai.providers import VISION

        router = self._router()
        first = router.provider_name()
        if first in VISION:
            return first
        return next((p for p in router.connected() if p in VISION), None)

    def _run_drawing(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara import config, drawing

        router = self._router()
        text, image = payload["text"], payload.get("image")
        previous = getattr(self, "_last_drawing", None) if payload.get("edit") else None
        folder = self._output_dir or (config.data_dir() / "Chizmalar")
        show = self._history is not None and not payload.get("background")

        def fn(task: Any) -> dict[str, Any]:
            img = None
            if image:
                with task.step("Rasmni tayyorlash (joylashuv ma’lumotlari o‘chiriladi)"):
                    img = drawing.clean_image(Path(image))
            with task.step("AI chizmani tuzmoqda") as s:
                system, msgs = drawing.ai_messages(text, img, previous)
                reply = router.complete("drawing", system, msgs, max_tokens=8000,
                                        expected_out=5000, approved=True)  # fmt: skip
                spec = drawing.parse_reply(reply.text)
                s.detail = f"{len(spec['shapes'])} ta element, ≈${reply.cost:.3f}"
            with task.step("Chizish: PDF, PNG, DXF (AutoCAD)"):
                out = drawing.export(spec, folder)
            self._last_drawing = spec  # "oxirgi chizmani o‘zgartir: ..." continues from here
            if show:
                with task.step("Kompyuter ekranida ochish"):
                    opener = self._overrides.get("open_file") or os.startfile
                    opener(out["pdf"])  # noqa: S606 - our own file
            report = [f"Chizma: {spec['title']}", f"{len(spec['shapes'])} ta element"]
            return {"path": out["png"], "pdf": out["pdf"], "svg": out["svg"], "dxf": out["dxf"],
                    "report": report}  # fmt: skip

        title = "Chizma" + (" (rasmdan)" if image else "") + f": {text[:40]}"
        snap = self._runner.start(title, fn).snapshot()
        return {"reply": "Chizyapman — jarayon vazifalar panelida. Tayyor bo‘lgach PDF kompyuter "
                "ekranida ochiladi, PNG’ni telefonga olish mumkin.", "task": snap}  # fmt: skip
