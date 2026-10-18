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
from nexvara.agent.parse import DESCRIBE, Plan
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
    """An existing presentation: replace text, font, transitions, slide numbers, a quality
    check, PDF. Changes go to "<name>_NEXVARA.pptx"; the original stays untouched unless the
    user says "ustiga saqla" (a backup is made first)."""
    from nexvara.skills.powerpoint import ops
    from nexvara.skills.powerpoint.ops import PowerPointSession

    kinds = [a for a in plan.actions if a.kind not in ("open", "save")]
    allowed = {"pdf", "replace", "font", "transition", "slide_numbers", "check", "fix"}
    bad = [a for a in kinds if a.kind not in allowed]
    if bad:
        raise CommandError(
            f"PowerPoint faylida bu buyruq hali yo‘q: «{bad[0].text}». Bor buyruqlar: matnni "
            "almashtirish, shrift, o‘tish effekti, slayd raqamlari, slaydlarni tekshirish, PDF. "
            "Yangi taqdimot uchun: «7-sinf fizika Nyuton qonunlari bo‘yicha taqdimot»."
        )
    overwrite = any(a.kind == "save" and a.args.get("overwrite") for a in plan.actions)
    changes = [a for a in kinds if a.kind not in ("pdf", "check")]
    out = source if overwrite and source.suffix.lower() == ".pptx" else files.output_path(
        source, ".pptx"
    )  # fmt: skip
    pdf = files.output_path(source, ".pdf") if any(a.kind == "pdf" for a in kinds) else None
    report: list[str] = []
    checks: list[dict[str, Any]] = []
    with PowerPointSession(visible=visible, keep_open=keep_open) as pp:
        with task.step(f"Faylni ochish: {source.name}") as s:
            pres = pp.open_presentation(source)
            pp.show()
            s.detail = f"{int(pres.Slides.Count)} ta slayd"
        for a in kinds:
            if a.kind == "pdf":
                continue
            title = DESCRIBE.get(a.kind, a.kind)
            with task.step(title) as s:
                s.detail, ok = _PPT[a.kind](pres, a, ops)
                checks.append({"name": title, "ok": ok, "detail": s.detail})
                if not ok:
                    raise CommandError(f"{title}: {s.detail}")
                report.append(f"{title}: {s.detail}")
            if visible and pause:
                time.sleep(pause)
            task.check_cancelled()
        if changes:
            with task.step("Slayd matnini sig‘dirish") as s:
                repaired = _repair_overflow(pres)
                remaining = _overflow_problems(pres, ops)
                s.detail = f"{repaired} ta matn bloki; qolgan muammo: {len(remaining)}"
                if remaining:
                    raise CommandError("Matn slaydga sig‘madi: " + "; ".join(remaining[:4]))
        saved = None
        if changes:
            with task.step("Saqlash") as s:
                if overwrite:
                    files.backup(source)
                    report.append("Asl fayl ustiga saqlandi (oldin .bak nusxasi olindi)")
                    pres.Save()
                    saved = source
                else:
                    saved = pp.save_as(pres, out)
                s.detail = saved.name
            with task.step("Qayta ochib tekshirish") as s:
                pp.disown(pres)
                pres.Close()
                del pres
                pres = pp.open_presentation(saved)
                remaining = _overflow_problems(pres, ops)
                checks.append(
                    {
                        "name": "Slayd matni sig‘adi",
                        "ok": not remaining,
                        "detail": "; ".join(remaining[:4]),
                    }
                )
                s.detail = "matn sig‘adi" if not remaining else "; ".join(remaining[:4])
                if remaining:
                    raise CommandError("Saqlangan taqdimotda matn sig‘madi: " + s.detail)
        if pdf is not None:
            with task.step("PDF qilib saqlash") as s:
                ops.export_pdf(pres, pdf)
                s.detail = pdf.name
        if not keep_open:
            pp.disown(pres)
            pres.Close()
        del pres
    if pdf is not None:
        ok = pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-"
        checks.append({"name": "PDF", "ok": ok, "detail": pdf.name})
        if not ok:
            raise CommandError("PDF yaratilmadi")
        report.append(f"PDF: {pdf.name}")
    if saved is not None:
        checks.append({"name": "Fayl saqlandi", "ok": saved.is_file(), "detail": saved.name})
    path = saved or pdf or source
    return {"path": str(path), "source": str(source), "pdf": str(pdf) if pdf else "",
            "checks": checks, "report": report, "unknown": plan.unknown}  # fmt: skip


def _text_ranges(pres: Any) -> Any:
    """Every text range in every slide: shapes, groups and table cells."""

    def walk(shapes: Any) -> Any:
        for j in range(1, shapes.Count + 1):
            sh = shapes(j)
            if int(sh.Type) == 6:  # msoGroup
                yield from walk(sh.GroupItems)
            elif sh.HasTable:
                tbl = sh.Table
                for r in range(1, tbl.Rows.Count + 1):
                    for c in range(1, tbl.Columns.Count + 1):
                        yield tbl.Cell(r, c).Shape.TextFrame.TextRange
            elif sh.HasTextFrame and sh.TextFrame.HasText:
                yield sh.TextFrame.TextRange

    for i in range(1, pres.Slides.Count + 1):
        yield from walk(pres.Slides(i).Shapes)


def _pp_replace(pres: Any, a: Any, ops: Any) -> tuple[str, bool]:
    find, repl = str(a.args["find"]), str(a.args["replace"])
    before = sum(str(tr.Text).count(find) for tr in _text_ranges(pres))
    if not before:
        raise CommandError(f"Taqdimotda «{find}» topilmadi")
    for tr in _text_ranges(pres):
        start = 0
        for _ in range(500):
            text = str(tr.Text)
            pos = text.find(find, start)
            if pos < 0:
                break
            tr.Characters(pos + 1, len(find)).Text = repl  # keeps the run's formatting
            start = pos + len(repl)
    left = 0 if find in repl else sum(str(tr.Text).count(find) for tr in _text_ranges(pres))
    return f"«{find}» → «{repl}»: {before} ta", left == 0


def _pp_font(pres: Any, a: Any, ops: Any) -> tuple[str, bool]:
    name, size = a.args.get("name"), a.args.get("size")
    if not name:
        raise CommandError(
            "Taqdimotda faqat shrift nomini almashtiraman (o‘lcham har slaydda boshqacha "
            "bo‘ladi). Masalan: «shriftni Arial qil»"
        )
    n = 0
    for tr in _text_ranges(pres):
        tr.Font.Name = name
        n += 1
    ok = all(str(tr.Font.Name) == name for tr in _text_ranges(pres))
    extra = " (o‘lcham o‘zgartirilmadi)" if size else ""
    return f"{name}: {n} ta matn bloki{extra}", ok


def _pp_transition(pres: Any, a: Any, ops: Any) -> tuple[str, bool]:
    n = int(pres.Slides.Count)
    for i in range(1, n + 1):
        ops.set_transition(pres.Slides(i))
    ok = all(
        int(pres.Slides(i).SlideShowTransition.EntryEffect) == ops.PP_EFFECT_FADE
        for i in range(1, n + 1)
    )
    return f"{n} ta slaydga silliq o‘tish", ok


NUM_NAME = "NEXVARA_raqam"


def _pp_slide_numbers(pres: Any, a: Any, ops: Any) -> tuple[str, bool]:
    """A small number in the bottom right of every slide but the title slide (works on any
    layout, unlike the placeholder that many templates lack)."""
    w, h = float(pres.PageSetup.SlideWidth), float(pres.PageSetup.SlideHeight)
    n = int(pres.Slides.Count)
    for i in range(2, n + 1):
        shapes = pres.Slides(i).Shapes
        for j in range(shapes.Count, 0, -1):
            if str(shapes(j).Name) == NUM_NAME:
                shapes(j).Delete()
        box = shapes.AddTextbox(ops.MSO_TEXTBOX, w - 84, h - 34, 64, 24)
        box.Name = NUM_NAME
        tr = box.TextFrame.TextRange
        tr.InsertSlideNumber()
        tr.Font.Size = 12
        tr.Font.Color.RGB = ops.excel_color("#6B7280")
        tr.ParagraphFormat.Alignment = 3  # ppAlignRight
        del tr, box, shapes
    shown = [str(pres.Slides(i).Shapes(NUM_NAME).TextFrame.TextRange.Text) for i in range(2, n + 1)]
    ok = shown == [str(i) for i in range(2, n + 1)]
    return f"{max(n - 1, 0)} ta slaydda (sarlavha slaydidan tashqari)", ok


def _pp_check(pres: Any, a: Any, ops: Any) -> tuple[str, bool]:
    """Layout problems + Microsoft's rules (knowledge/office_guide.py): titles, 18 pt, bullets,
    alt text. A report; nothing is changed."""
    problems = []
    titles: dict[str, list[int]] = {}
    for i in range(1, pres.Slides.Count + 1):
        slide = pres.Slides(i)
        for p in ops.layout_problems(slide):
            if NUM_NAME not in p:
                problems.append(f"{i}-slayd: {p}")
        title = ops.slide_title(slide).strip()
        if not title:
            problems.append(f"{i}-slayd: sarlavha yo‘q")
        else:
            titles.setdefault(title.lower(), []).append(i)
        small, no_alt = 0.0, 0
        for j in range(1, slide.Shapes.Count + 1):
            sh = slide.Shapes(j)
            if str(sh.Name) == NUM_NAME:
                continue
            if int(sh.Type) == 13 and not str(sh.AlternativeText).strip():  # msoPicture
                no_alt += 1
            if sh.HasTable:  # table cells are text too
                tbl = sh.Table
                for r in range(1, tbl.Rows.Count + 1):
                    for c in range(1, tbl.Columns.Count + 1):
                        cell = tbl.Cell(r, c).Shape.TextFrame.TextRange
                        size = float(cell.Font.Size)
                        if 0 < size < 18 and str(cell.Text).strip():
                            small = size if not small else min(small, size)
                del tbl
            if sh.HasTextFrame and sh.TextFrame.HasText:
                tr = sh.TextFrame.TextRange
                for k in range(1, tr.Runs().Count + 1):
                    size = float(tr.Runs(k).Font.Size)
                    if 0 < size < 18 and str(tr.Runs(k).Text).strip():
                        small = size if not small else min(small, size)
                bullets = sum(1 for line in str(tr.Text).split("\r") if line.strip())
                if bullets > 6 and j != 1:
                    problems.append(f"{i}-slayd: {bullets} ta band — 6 tadan oshmasin")
                del tr
            del sh
        if small:
            problems.append(f"{i}-slayd: {small:g} pt matn — kamida 18 pt bo‘lsin")
        if no_alt:
            problems.append(f"{i}-slayd: {no_alt} ta rasmda izoh (alt matn) yo‘q")
        del slide
    problems += [f"{', '.join(map(str, ids))}-slaydlar: sarlavha bir xil"
                 for ids in titles.values() if len(ids) > 1]  # fmt: skip
    if not problems:
        return f"{pres.Slides.Count} ta slayd: muammo topilmadi", True
    more = f" (yana {len(problems) - 8} ta)" if len(problems) > 8 else ""
    return f"{len(problems)} ta kamchilik: " + "; ".join(problems[:8]) + more, True  # a report


def _pp_fix(pres: Any, a: Any, ops: Any) -> tuple[str, bool]:
    """Text below 18 pt becomes 18 pt (Microsoft); what cannot be decided for the user (a
    missing title, an overflow) is reported by the check that follows."""
    fixed = 0
    for i in range(1, pres.Slides.Count + 1):
        shapes = pres.Slides(i).Shapes
        for j in range(1, shapes.Count + 1):
            sh = shapes(j)
            if str(sh.Name) == NUM_NAME:
                continue
            ranges = []
            if sh.HasTable:
                tbl = sh.Table
                ranges = [
                    tbl.Cell(r, c).Shape.TextFrame.TextRange
                    for r in range(1, tbl.Rows.Count + 1)
                    for c in range(1, tbl.Columns.Count + 1)
                ]
            elif sh.HasTextFrame and sh.TextFrame.HasText:
                ranges = [sh.TextFrame.TextRange]
            for tr in ranges:
                for k in range(1, tr.Runs().Count + 1):
                    run = tr.Runs(k)
                    if 0 < float(run.Font.Size) < 18 and str(run.Text).strip():
                        run.Font.Size = 18
                        fixed += 1
            del sh
    fitted = _repair_overflow(pres)
    report, _ok = _pp_check(pres, a, ops)
    return (
        f"{fixed} ta matn bo‘lagi 18 pt ga kattalashtirildi; {fitted} ta sig‘dirildi. {report}",
        True,
    )


def _overflow_problems(pres: Any, ops: Any) -> list[str]:
    return [
        f"{i}-slayd: {p}"
        for i in range(1, pres.Slides.Count + 1)
        for p in ops.layout_problems(pres.Slides(i))
        if "matn sig'madi" in p
    ]


def _repair_overflow(pres: Any) -> int:
    """Ask PowerPoint to fit text inside its existing shape, without moving other content."""
    count = 0
    for i in range(1, pres.Slides.Count + 1):
        shapes = pres.Slides(i).Shapes
        for j in range(1, shapes.Count + 1):
            sh = shapes(j)
            if not sh.HasTextFrame or not sh.TextFrame.HasText:
                continue
            if float(sh.TextFrame.TextRange.BoundHeight) <= float(sh.Height):
                continue
            sh.TextFrame2.AutoSize = 2  # msoAutoSizeTextToFitShape
            count += 1
    return count


_PPT = {
    "replace": _pp_replace,
    "fix": _pp_fix,
    "font": _pp_font,
    "transition": _pp_transition,
    "slide_numbers": _pp_slide_numbers,
    "check": _pp_check,
}
