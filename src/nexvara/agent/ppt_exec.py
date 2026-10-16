"""PowerPoint commands: a lesson presentation built from a textbook topic (no AI), and
converting an existing presentation to PDF."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.agent import files
from nexvara.agent.excel_exec import CommandError
from nexvara.agent.parse import Plan
from nexvara.core.task import Task
from nexvara.knowledge.quiz import build_quiz, extract_definitions, extract_facts
from nexvara.knowledge.textnorm import fold, letter_ratio, sentences
from nexvara.knowledge.topicdoc import TopicRequest, lookup
from nexvara.knowledge.topics import Topic, paragraphs

MAX_BULLETS = 5
MAX_CONTENT_SLIDES = 6
_FORMULA = re.compile(r"[=→≈≠²³√∑Δ]")


def _short(sentence: str, words: int = 22) -> str:
    w = sentence.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


_GLUED = re.compile(r"[a-z‘’][A-Z]")  # "QorasaroySag‘bon": map labels run together


def _key_sentence(paragraph: str) -> str | None:
    for s in sentences(paragraph):
        words = s.split()
        if not (5 <= len(words) <= 40) or letter_ratio(s) <= 0.7 or _FORMULA.search(s):
            continue
        if _GLUED.search(s) or not s.endswith((".", "!", "?", ":")):
            continue
        capitalised = sum(w[:1].isupper() for w in words[:6])
        if capitalised >= 4:  # a list of names/labels, not a sentence
            continue
        return _short(s)
    return None


def _good_subheading(text: str, topic_title: str) -> bool:
    """Real sub-headings only: not the topic title again, not all-caps map/figure labels."""
    if fold(re.sub(r"[^\w]", "", text)) == fold(re.sub(r"[^\w]", "", topic_title)):
        return False
    if re.match(r"^\s*\d+\s*-?\s*§", text):
        return False  # the topic's own heading in another form ("21§. ...")
    letters = [c for c in text if c.isalpha()]
    upper = sum(c.isupper() for c in letters) / len(letters) if letters else 1
    return upper < 0.5 and 2 <= len(text.split()) <= 10


def outline_slides(topic: Topic) -> list[dict[str, Any]]:
    """Slide plan: [{"kind", "title", "bullets", "notes"}] — pure, so it is unit-testable."""
    blocks = paragraphs(topic.text)
    pages = [(topic.start_page, topic.text)]
    slides: list[dict[str, Any]] = []

    # Content: group paragraphs under sub-headings; one key sentence per paragraph.
    groups: list[tuple[str, list[str]]] = []
    current_title = "Asosiy mazmun"
    current: list[str] = []
    for kind, text in blocks:
        if kind == "heading" and _good_subheading(text, topic.title):
            if current:
                groups.append((current_title, current))
            current_title, current = text, []
        elif kind == "para":
            current.append(text)
    if current:
        groups.append((current_title, current))
    seen: set[str] = set()
    for title, paras in groups:
        bullets = []
        for b in (_key_sentence(p) for p in paras):
            if b and fold(b) not in seen:
                seen.add(fold(b))
                bullets.append(b)
        for i in range(0, len(bullets), MAX_BULLETS):
            chunk = bullets[i : i + MAX_BULLETS]
            part = f" ({i // MAX_BULLETS + 1})" if len(bullets) > MAX_BULLETS else ""
            slides.append({"kind": "bullets", "title": _short(title, 10) + part,
                           "bullets": chunk, "notes": "\n\n".join(paras)[:3000]})  # fmt: skip
        if len([s for s in slides if s["kind"] == "bullets"]) >= MAX_CONTENT_SLIDES:
            break

    defs = extract_definitions(pages)[:MAX_BULLETS]
    if defs:
        slides.append({"kind": "bullets", "title": "Asosiy tushunchalar",
                       "bullets": [_short(f"{d.term} — {d.defn}", 26) for d in defs],
                       "notes": "\n".join(d.sentence for d in defs)})  # fmt: skip
    years = [f for f in extract_facts(pages) if f.kind == "year"][:MAX_BULLETS]
    if years:
        slides.append({"kind": "bullets", "title": "Muhim sanalar",
                       "bullets": [_short(f.sentence, 20) for f in years],
                       "notes": "\n".join(f.sentence for f in years)})  # fmt: skip
    # The textbook's own review questions are better than generated ones.
    own = [s for s in sentences(topic.text) if s.endswith("?") and 4 <= len(s.split()) <= 25]
    if own:
        slides.append({"kind": "bullets", "title": "Savollar",
                       "bullets": [_short(q, 22) for q in own[:MAX_BULLETS]],
                       "notes": "Darslikdagi savollar."})  # fmt: skip
    else:
        quiz = [q for q in build_quiz(pages, 6, seed=3).questions if q.kind == "mcq"][:3]
        if quiz:
            slides.append({"kind": "bullets", "title": "Savollar",
                           "bullets": [_short(q.text.split("\n")[-1].strip("«»"), 22)
                                       for q in quiz],
                           "notes": "\n".join(f"{q.text} — javob: "
                                              f"{q.options['ABCD'.index(q.answer)]}"
                                              for q in quiz)})  # fmt: skip
    slides.append({"kind": "bullets", "title": "Uyga vazifa",
                   "bullets": [f"Darslikning {topic.pages_label}ni o‘qish",
                               "Asosiy tushunchalarni daftarga yozish",
                               "Mavzu oxiridagi savollarga javob berish"],
                   "notes": ""})  # fmt: skip
    return slides


def default_presentation_path(topic: Topic) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{topic.book.grade or 'x'}-sinf {topic.book.subject or ''} {topic.title}"[:80]
    name = re.sub(r"[^\w‘’' -]", "", name).strip().replace(" ", "_")
    return config.data_dir() / "Taqdimotlar" / f"{name}_{stamp}.pptx"


def run_topic_presentation(
    task: Task,
    req: TopicRequest,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
) -> dict[str, Any]:
    from nexvara.skills.powerpoint.ops import PowerPointSession

    with task.step("Darslikdan mavzuni topish") as s:
        topic = lookup(req)
        plan = outline_slides(topic)
        s.detail = f"{topic.book.label()} · {topic.title} · {len(plan) + 1} slayd"
        if not any(sl["bullets"] for sl in plan[:-1]):
            raise CommandError("Mavzu matnidan slayd tuzib bo‘lmadi (ehtimol skaner sahifa)")
    out = Path(out_path) if out_path else default_presentation_path(topic)
    files_ok = out.suffix.lower() == ".pptx"
    if not files_ok:
        raise CommandError("Taqdimot .pptx bo‘lishi kerak")
    with PowerPointSession(visible=visible, keep_open=keep_open) as pp:
        checks = _build(task, pp, topic, plan, out, visible, pause, keep_open)
    return {"path": str(out), "pdf": str(out.with_suffix(".pdf")), "checks": checks,
            "title": topic.title, "book": topic.book.label(), "slides": len(plan) + 1}  # fmt: skip


def _build(task, pp, topic, plan, out, visible, pause, keep_open) -> list[dict[str, Any]]:
    # COM objects live only in this frame, so they are released before PowerPoint quits.
    from nexvara.skills.powerpoint import ops

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with task.step("Slaydlarni yaratish") as s:
        pres = pp.new_presentation()
        ops.apply_theme(pres)
        pp.show()
        source = f"{topic.book.label()} · {topic.pages_label}"
        sl = ops.add_title_slide(pres, topic.title, source)
        ops.set_notes(sl, f"Mavzu: {topic.title}. Manba: {source}.")
        for spec in plan:
            sl = ops.add_bullets_slide(pres, spec["title"], spec["bullets"])
            if spec["notes"]:
                ops.set_notes(sl, spec["notes"])
            ops.animate(sl, sl.Shapes.Placeholders(2))
            beat()
        for i in range(1, pres.Slides.Count + 1):
            ops.set_transition(pres.Slides(i))
        s.detail = f"{pres.Slides.Count} ta slayd"

    with task.step("Joylashuvni tekshirish") as s:
        problems = []
        for i in range(1, pres.Slides.Count + 1):
            slide = pres.Slides(i)
            body = slide.Shapes.Placeholders(2) if i > 1 else None
            # Long bullets: shrink the text until it fits, then re-check.
            if body is not None:
                size = 20
                while size > 12 and ops.layout_problems(slide):
                    size -= 2
                    body.TextFrame.TextRange.Font.Size = size
            problems += [f"{i}-slayd: {p}" for p in ops.layout_problems(slide)]
        s.detail = f"{len(problems)} ta muammo"
        if problems:
            raise CommandError("Joylashuv: " + "; ".join(problems[:5]))
        del slide, body

    with task.step("Saqlash (PPTX + PDF)") as s:
        out.parent.mkdir(parents=True, exist_ok=True)
        pp.save_as(pres, out)
        pdf = ops.export_pdf(pres, out.with_suffix(".pdf"))
        s.detail = out.name
        n_slides = pres.Slides.Count
        pp.disown(pres)
        pres.Close()
        del pres, sl
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        pres2 = pp.open_presentation(out)
        pp.show()
        checks = [
            {"name": "Slaydlar soni", "ok": pres2.Slides.Count == n_slides, "detail": n_slides},
            {"name": "Sarlavha", "ok": ops.slide_title(pres2.Slides(1)) == topic.title},
            {"name": "PDF", "ok": pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-"},
        ]
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o‘tdi"
        if failed:
            raise CommandError("Tekshiruv o‘tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            pp.disown(pres2)
            pres2.Close()
    return checks


def run_ppt_plan(
    task: Task,
    plan: Plan,
    source: Path,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
) -> dict[str, Any]:
    """Existing presentation: only "PDF ga aylantir" is supported so far."""
    from nexvara.skills.powerpoint import ops
    from nexvara.skills.powerpoint.ops import PowerPointSession

    kinds = {a.kind for a in plan.actions} - {"open", "save"}
    if kinds - {"pdf"}:
        raise CommandError(
            "PowerPoint faylida hozircha faqat «PDF ga aylantir» buyrug‘i bor. "
            "Yangi taqdimot uchun: «7-sinf fizika Nyuton qonunlari bo‘yicha taqdimot»."
        )
    pdf = files.output_path(source, ".pdf")
    with PowerPointSession(visible=visible, keep_open=keep_open) as pp:
        with task.step(f"Faylni ochish: {source.name}") as s:
            pres = pp.open_presentation(source)
            pp.show()
            s.detail = f"{pres.Slides.Count} ta slayd"
        with task.step("PDF qilib saqlash") as s:
            ops.export_pdf(pres, pdf)
            s.detail = pdf.name
            if not keep_open:
                pp.disown(pres)
                pres.Close()
            del pres
    ok = pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-"
    if not ok:
        raise CommandError("PDF yaratilmadi")
    return {"path": str(pdf), "source": str(source), "checks": [{"name": "PDF", "ok": ok}],
            "report": [f"PDF: {pdf.name}"], "unknown": plan.unknown}  # fmt: skip
