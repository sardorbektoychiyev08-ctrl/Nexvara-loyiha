"""Drawings in chat (mixed into app.api.Api): "velosiped g‘ildiragi chizmasini chizib ber",
or a photo of a hand-drawn sketch + "shu chizmani mukammal chiz". See nexvara/drawing.py.

Simple parts ("100x60 plastina, markazida 20 mm teshik") are drawn exactly and for free,
without AI (nexvara/drawing_offline.py). An AutoCAD DXF the user has ("chizma.dxf ni PDF qil")
is shown as PDF/PNG/Word (nexvara/cad.py); «chizma.dxf ni Hisobot.docx ga qo‘y» puts the
drawing (with its measurements) at the end of that Word document, in visible Word."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_DXF_FILE = re.compile(
    r"[«\"“]([^«»\"“”]+?\.(?:dxf|dwg))[»\"”]|((?:[A-Za-z]:[\\/])?[\w\\/.\-‘’()]+?\.(?:dxf|dwg))\b",
    re.IGNORECASE,
)
_DOCX_FILE = re.compile(
    r"[«\"“]([^«»\"“”]+?\.docx?)[»\"”]|((?:[A-Za-z]:[\\/])?[\w\\/.\-‘’()]+?\.docx?)\b",
    re.IGNORECASE,
)
_INTO = re.compile(r"\b(qo[‘’']?y\w*|joyla\w*|qo[‘’']?sh\w*|kirit\w*|ichiga)", re.IGNORECASE)
_DXF_VERBS = re.compile(
    r"\b(pdf|png|word|docx|rasm\w*|ko[‘’']?rsat\w*|korsat\w*|och\w*|aylantir\w*|ko[‘’']?r\b|chop|"
    r"ichida nima|tarkib\w*|tekshir\w*)",
    re.IGNORECASE,
)


class DrawingApi:
    _overrides: dict
    _history: Any
    _pending: dict
    _output_dir: Path | None

    def _chat_drawing(self, text: str) -> dict[str, Any] | None:
        from nexvara import drawing, drawing_offline
        from nexvara.agent.parse import find_file
        from nexvara.app.api import _BACKGROUND
        from nexvara.knowledge.service import parse_test_request
        from nexvara.knowledge.textnorm import fold

        dxf = self._dxf_request(text)
        if dxf is not None:
            return dxf
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
        bg = bool(_BACKGROUND.search(text))
        if image is None:
            base = getattr(self, "_last_params", None) if edit else None
            try:
                params = drawing_offline.parse(text, base) if (base or not edit) else None
            except ValueError as e:
                return {"reply": f"Chizib bo‘lmaydi: {e}"}
            if params is not None and base is not None and params == base:
                params = None  # nothing in the change was understood: the AI may, if connected
                if not self._ai_ready():
                    return {"reply": "O‘zgarishni tushunmadim. O‘lcham bilan yozing, masalan: "
                            "«oxirgi chizmani o‘zgartir: eni 150, teshik 12 mm "
                            "bo‘lsin»."}  # fmt: skip
            if params is not None:
                return self._run_offline_drawing(params, text, bg)
        if not self._ai_ready():
            return {"reply": "Bunday chizma uchun AI kerak: Sozlamalar → AI bo‘limida OpenAI, "
                    "Gemini yoki Claude kalitini kiriting va AI’ni yoqing.\n\nAI’siz ham "
                    "aniq chizaman (bepul): plastina, kvadrat, doira, halqa/shayba, uchburchak, "
                    "olti burchakli detal (gayka), ellips — o‘lchamlari bilan. Masalan:\n"
                    "• «100x60 plastina, markazida 20 mm teshik chizib ber»\n"
                    "• «120x80 plastina, burchaklarida 4 ta 10 mm teshik, burchaklari R8 chiz»\n"
                    "• «Shayba chiz: tashqi diametri 40, ichki diametri 21»\n"
                    "• «Uchburchak chiz, tomonlari 30, 40 va 50»"}  # fmt: skip
        from nexvara.ai.router import TIER_FOR, AiUnavailable

        router = self._router()
        if image and self._vision_provider() is None:
            return {"reply": "Rasmni o‘qiydigan AI ulanmagan: OpenAI, Gemini, Claude "
                    "yoki DeepSeek Flash kalitini kiriting."}  # fmt: skip
        system, msgs = drawing.ai_messages(text, ("image/jpeg", "") if image else None,
                                           last if edit else None)  # fmt: skip
        from nexvara.ai.router import BudgetExceeded

        # The limits are checked before asking (live check 2026-10-19: «Ha» was asked for
        # $0.051, then the $0.05 task limit stopped it): the strong model if it fits, else the
        # balanced one (said openly), else a clear refusal — never a «Ha» that cannot run.
        est, tier, refusal = None, TIER_FOR["drawing"], ""
        for t in dict.fromkeys((TIER_FOR["drawing"], "balanced")):
            try:
                cand = router.text_candidates(t, system, msgs, 5000,
                                              "vision" if image else "text")[0]  # fmt: skip
                router.check_budget(cand, approved=True)
            except AiUnavailable as e:  # no fitting model at all: say so (no weaker fallback)
                refusal = refusal or str(e)
                break
            except BudgetExceeded as e:  # a strong model exists but the limit is lower
                refusal = refusal or str(e)
                continue
            est, tier = cand, t
            break
        if est is None:
            return {"reply": refusal}
        import uuid

        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("drawing", {"text": text, "image": image, "background": bg,
                                            "edit": edit, "tier": tier})  # fmt: skip
        what = f"«{last['title']}» chizmasini o‘zgartiraman" if edit else "Chizmani AI tuzadi"
        reply = f"{what}, NEXVARA chizadi (PDF, PNG, AutoCAD DXF): {est.describe()}."
        if tier != TIER_FOR["drawing"]:
            reply += ("\n\nKuchli model limitingizga sig‘madi — muvozanatli model bilan chizaman "
                      "(limitni Sozlamalar → AI da o‘zgartirish mumkin).")  # fmt: skip
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

    def _drawing_folder(self) -> Path:
        from nexvara import config

        return self._output_dir or (config.data_dir() / "Chizmalar")

    def _finish_drawing(self, task: Any, spec: dict[str, Any], show: bool) -> dict[str, Any]:
        """Export PDF/PNG/SVG/DXF, check the DXF the way AutoCAD would read it, open the PDF."""
        from nexvara import cad, drawing

        with task.step("Chizish: PDF, PNG, DXF (AutoCAD)") as s:
            out = drawing.export(spec, self._drawing_folder())
            s.detail = Path(out["pdf"]).stem
        with task.step("AutoCAD faylini tekshirish") as s:
            doc = cad.read(Path(out["dxf"]))
            problems = cad.audit(doc)
            info = cad.summary(doc)
            if problems or not info["entities"]:
                from nexvara.core.task import UserError

                raise UserError("DXF tekshiruvdan o‘tmadi: " + "; ".join(problems[:3]))
            s.detail = f"{info['entities']} ta obyekt, {len(info['layers'])} ta qatlam, mm"
        self._last_drawing = spec  # "oxirgi chizmani o‘zgartir: ..." continues from here
        if show:
            with task.step("Kompyuter ekranida ochish"):
                opener = self._overrides.get("open_file") or os.startfile
                opener(out["pdf"])  # noqa: S606 - our own file
        report = [f"Chizma: {spec['title']}", f"{len(spec['shapes'])} ta element",
                  f"AutoCAD: {Path(out['dxf']).name} (DXF 2010, mm, qatlamlar bilan)"]  # fmt: skip
        return {"path": out["png"], "pdf": out["pdf"], "svg": out["svg"], "dxf": out["dxf"],
                "report": report}  # fmt: skip

    def _run_offline_drawing(self, params: dict[str, Any], text: str,
                             background: bool) -> dict[str, Any]:  # fmt: skip
        from nexvara import drawing_offline

        show = self._history is not None and not background

        def fn(task: Any) -> dict[str, Any]:
            with task.step("O‘lchamlarni hisoblash (AI’siz)") as s:
                spec = drawing_offline.build_spec(params)
                s.detail = f"{drawing_offline.describe(params)}, masshtab {spec['scale']}"
            res = self._finish_drawing(task, spec, show)
            self._last_params = params
            return res

        title = f"Chizma (AI’siz): {drawing_offline.describe(params)}"
        snap = self._runner.start(title, fn).snapshot()
        return {"reply": f"Chizyapman (AI’siz, bepul): {drawing_offline.describe(params)}. "
                "Tayyor bo‘lgach PDF ochiladi; AutoCAD uchun DXF fayl ham yoniga saqlanadi. "
                "O‘zgartirish uchun: «oxirgi chizmani o‘zgartir: teshik 10 mm bo‘lsin».",
                "task": snap}  # fmt: skip

    def _run_drawing(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara import drawing

        router = self._router()
        text, image = payload["text"], payload.get("image")
        previous = getattr(self, "_last_drawing", None) if payload.get("edit") else None
        show = self._history is not None and not payload.get("background")

        def fn(task: Any) -> dict[str, Any]:
            img = None
            if image:
                with task.step("Rasmni tayyorlash (joylashuv ma’lumotlari o‘chiriladi)"):
                    img = drawing.clean_image(Path(image))
            with task.step("AI chizmani tuzmoqda") as s:
                system, msgs = drawing.ai_messages(text, img, previous)
                reply = router.complete("drawing", system, msgs, max_tokens=8000,
                                        expected_out=5000, approved=True,
                                        tier=payload.get("tier"))  # fmt: skip
                spec = drawing.parse_reply(reply.text)
                s.detail = f"{len(spec['shapes'])} ta element, ≈${reply.cost:.3f}"
            res = self._finish_drawing(task, spec, show)
            self._last_params = None  # an AI drawing is edited by the AI
            return res

        title = "Chizma" + (" (rasmdan)" if image else "") + f": {text[:40]}"
        snap = self._runner.start(title, fn).snapshot()
        return {"reply": "Chizyapman — jarayon vazifalar panelida. Tayyor bo‘lgach PDF kompyuter "
                "ekranida ochiladi, PNG’ni telefonga olish mumkin.", "task": snap}  # fmt: skip

    # ----- an existing AutoCAD file -----
    def _dxf_request(self, text: str) -> dict[str, Any] | None:
        """ "chizma.dxf ni PDF qil", "shu DXF faylni ko‘rsat" -> PDF + PNG of that drawing."""
        from nexvara.agent import files

        m = _DXF_FILE.search(text)
        cur = self._context_file
        name = (m.group(1) or m.group(2)).strip() if m else None
        if name is None:
            is_cad = bool(cur) and Path(cur).suffix.lower() in (".dxf", ".dwg")
            if not (is_cad and re.search(r"\b(dxf|dwg|autocad|chizma\w*|shu fayl\w*)", text,
                                         re.IGNORECASE)):  # fmt: skip
                return None
            name = cur
        into = _DOCX_FILE.search(text)
        if not (_DXF_VERBS.search(text) or (into and _INTO.search(text))):
            return None
        try:
            near = Path(cur).parent if cur else None
            path = files.resolve(name, near)
            target = files.resolve((into.group(1) or into.group(2)).strip(), path.parent) if (
                into and _INTO.search(text)) else None  # fmt: skip
        except LookupError as e:
            return {"reply": str(e)}
        self._context_file = str(path)
        if target is not None:
            return self._run_dxf_into_word(path, target)
        return self._run_dxf_view(path, bool(re.search(r"\b(word|docx)\b", text, re.I)))

    def _run_dxf_into_word(self, dxf: Path, docx: Path) -> dict[str, Any]:
        """The drawing picture and its measurements table at the end of an existing Word
        document; Word stays visible and the document is saved in place."""
        import tempfile

        from nexvara import cad

        if dxf.suffix.lower() == ".dwg":
            return {"reply": "DWG’ni avval AutoCAD’da DXF qilib saqlang."}
        keep = bool(self.get_settings().get("keep_office_open", True))
        writer = self._overrides.get("word_insert_drawing")

        def fn(task: Any) -> dict[str, Any]:
            with task.step(f"AutoCAD faylini o‘qish: {dxf.name}") as s:
                doc = cad.read(dxf)
                rows = cad.measurements(doc)
                s.detail = rows[0][1]
            with tempfile.TemporaryDirectory() as tmp:
                png = Path(tmp) / f"{dxf.stem}.png"
                with task.step("Rasm qilish"):
                    cad.render(doc, None, png, dpi=200)
                with task.step(f"Word’ga qo‘yish: {docx.name}") as s:
                    (writer or _word_insert)(docx, png, dxf.stem, rows, keep)
                    s.detail = "hujjat oxiriga, o‘lchamlar jadvali bilan"
            done = (
                f"«{dxf.name}» chizmasi «{docx.name}» oxiriga qo‘yildi (o‘lchamlar jadvali bilan)"
            )
            return {"path": str(docx), "report": [done]}

        snap = self._runner.start(f"Chizma → Word: {docx.name}", fn).snapshot()
        return {"reply": f"«{dxf.name}» chizmasini «{docx.name}» ga qo‘yyapman — Word ekranda "
                "ochiladi.", "task": snap}  # fmt: skip

    def _run_dxf_view(self, path: Path, word: bool = False) -> dict[str, Any]:
        from nexvara import cad

        if path.suffix.lower() == ".dwg":
            return {"reply": "DWG — AutoCAD’ning yopiq formati. AutoCAD’da «Fayl → Saqlash "
                    "(Save As) → DXF» qilib saqlang, keyin shu DXF’ni PDF/rasmga "
                    "aylantiraman."}  # fmt: skip
        show = self._history is not None
        folder = self._drawing_folder()

        def fn(task: Any) -> dict[str, Any]:
            with task.step(f"AutoCAD faylini o‘qish: {path.name}") as s:
                doc = cad.read(path)
                info = cad.summary(doc)
                if not info["entities"]:
                    from nexvara.core.task import UserError

                    raise UserError("Chizmada hech narsa yo‘q (model maydoni bo‘sh)")
                kinds = ", ".join(f"{k} {v}" for k, v in list(info["types"].items())[:6])
                s.detail = f"{info['entities']} ta obyekt ({kinds})"
            with task.step("PDF va PNG qilish") as s:
                folder.mkdir(parents=True, exist_ok=True)
                stem = path.stem[:60]
                out = cad.render(doc, folder / f"{stem}.pdf", folder / f"{stem}.png")
                s.detail = Path(out["pdf"]).name
            if word:
                with task.step("Word fayl qilish") as s:
                    docx = folder / f"{stem}.docx"
                    rows = cad.measurements(doc)
                    out["docx"] = str(cad.png_to_docx(Path(out["png"]), docx, path.stem, rows))
                    s.detail = Path(out["docx"]).name
            if show:
                with task.step("Kompyuter ekranida ochish"):
                    opener = self._overrides.get("open_file") or os.startfile
                    opener(out["docx" if word else "pdf"])  # noqa: S606 - our own file
            w, h = info["size"]
            report = [f"{path.name}: {info['entities']} ta obyekt, {len(info['layers'])} ta qatlam",
                      f"O‘lchami: {w:g} × {h:g} {info['units']}".strip()]  # fmt: skip
            res = {"path": out["png"], "pdf": out["pdf"], "source": str(path), "report": report}
            if word:
                res["docx"] = out["docx"]
            return res

        snap = self._runner.start(f"AutoCAD fayli: {path.name}", fn).snapshot()
        what = "PDF, rasm va Word’ga" if word else "PDF va rasmga"
        return {"reply": f"«{path.name}» chizmasini {what} aylantiryapman — tayyor "
                "bo‘lgach ochiladi.", "task": snap}  # fmt: skip


def _word_insert(docx: Path, png: Path, title: str, rows: list[tuple[str, str]],
                 keep_open: bool) -> None:  # fmt: skip
    """Real Word (visible): heading, picture fitted to the page width, measurements table."""
    from nexvara.skills.word import ops

    with ops.WordSession(visible=True, keep_open=keep_open) as w:
        doc = w.open_document(docx)
        ops.add_paragraph(doc, f"Chizma: {title}", ops.STYLE_HEADING[2])
        ops.add_paragraph(doc, "")
        sec = doc.Sections(1).PageSetup
        usable_cm = (sec.PageWidth - sec.LeftMargin - sec.RightMargin) / 28.3465
        ops.add_picture(doc, png, width_cm=round(usable_cm, 1))
        ops.add_table(doc, [["Ko‘rsatkich", "Qiymat"]] + [[a.strip(), v] for a, v in rows])
        w.show()
        doc.Save()
        del doc
