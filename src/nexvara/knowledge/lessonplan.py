"""«Dars ishlanmasi»: a 45-minute lesson plan from a textbook topic, without AI.

Structure as Uzbek teachers write it: topic card (class, subject, textbook pages, lesson type,
methods, equipment), three aims (ta’limiy, tarbiyaviy, rivojlantiruvchi), the course of the
lesson (organisation 2 min, homework check 8, new topic 20, consolidation 10, assessment 3,
homework 2), key terms from the textbook, consolidation questions with answers, homework.
Every fact comes from the textbook topic itself (`quiz.extract_definitions`, `build_quiz`); the
teacher reviews it before the lesson. The same request also builds the slide deck.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.knowledge.topicdoc import TopicRequest, lookup
from nexvara.knowledge.topics import Topic

STAGES = [  # (stage, minutes)
    ("Tashkiliy qism", 2),
    ("Uy vazifasini so‘rash", 8),
    ("Yangi mavzu bayoni", 20),
    ("Mustahkamlash", 10),
    ("Baholash", 3),
    ("Uyga vazifa", 2),
]
_WORDS = re.compile(r"\bdars\s+(ishlanma|reja|konspekt)\w*|\bdarsga\s+tayyorla\w*", re.IGNORECASE)


def is_lesson_request(text: str) -> bool:
    return bool(_WORDS.search(text or ""))


def parse_lesson_request(text: str) -> TopicRequest | None:
    """'7-sinf fizika Nyuton qonunlari dars ishlanmasi' -> TopicRequest; else None."""
    from nexvara.knowledge.service import _remaining_topic, detect_grade, detect_subject
    from nexvara.knowledge.textnorm import fold

    if not is_lesson_request(text):
        return None
    grade, subject = detect_grade(text), detect_subject(text)
    if grade is None and subject is None:
        return None
    f = _WORDS.sub(" ", fold(text))
    f = re.sub(r"\b(45|80)\s*daqiqa\w*|\bai\s+bilan\b|\buchun\b|\btuz\w*|\btayyorla\w*", " ", f)
    topic = _remaining_topic(f, subject)
    return TopicRequest(grade, subject, topic) if topic else None


def lesson_content(topic: Topic, questions: int = 5) -> dict[str, Any]:
    """Everything the plan says, taken from the textbook topic (no Office needed)."""
    from nexvara.knowledge.quiz import build_quiz, extract_definitions, extract_facts
    from nexvara.knowledge.textnorm import content_lines

    pages = _pages(topic)
    defs = extract_definitions(pages)[:8]
    facts = extract_facts(pages)[:4]
    quiz = build_quiz(pages, count=questions, seed=7, kinds=("mcq", "tf", "fill")).questions
    terms = [d.term for d in defs]
    lines = [ln for ln in content_lines(topic.text) if 6 <= len(ln.split()) <= 40][:6]
    subject = topic.book.subject or "fan"
    title = re.sub(r"^\s*\d+\s*-?\s*§\.?\s*", "", topic.title).strip() or topic.title
    key = ", ".join(terms[:4]) if terms else title
    aims = {
        "Ta’limiy": f"O‘quvchilarga «{title}» mavzusi bo‘yicha asosiy tushunchalar ({key}) haqida "
        "bilim berish va ularni amalda qo‘llashni o‘rgatish.",
        "Tarbiyaviy": "Diqqat, mas’uliyat va jamoada ishlash ko‘nikmasini, fanga qiziqishni "
        "tarbiyalash.",
        "Rivojlantiruvchi": f"Mantiqiy fikrlash, solishtirish va xulosa chiqarishni, {subject} "
        "atamalari bilan to‘g‘ri gapirishni rivojlantirish.",
    }
    teach = {
        "Tashkiliy qism": (
            "Salomlashish, davomatni aniqlash, darsga tayyorgarlikni tekshirish.",
            "Darsga tayyorlanadi.",
        ),
        "Uy vazifasini so‘rash": (
            "O‘tgan mavzu bo‘yicha savol-javob, 2–3 o‘quvchini doskaga chaqirish.",
            "Javob beradi, bir-birini to‘ldiradi.",
        ),
        "Yangi mavzu bayoni": (
            "Taqdimot yordamida yangi mavzuni tushuntirish: "
            + "; ".join(terms[:5] or [title])
            + ".",
            "Tinglaydi, asosiy tushunchalarni daftarga yozadi.",
        ),
        "Mustahkamlash": (
            f"{len(quiz)} ta savol (pastda) bo‘yicha savol-javob, juftlikda ishlash.",
            "Savollarga javob beradi, javoblarni muhokama qiladi.",
        ),
        "Baholash": ("Faol o‘quvchilarni rag‘batlantirish va baholash.", "Natijani biladi."),
        "Uyga vazifa": (
            f"Darslikning {topic.pages_label}ini o‘qish, savollarga javob yozish.",
            "Vazifani yozib oladi.",
        ),
    }
    return {
        "title": title,
        "topic": topic,
        "aims": aims,
        "teach": teach,
        "defs": defs,
        "facts": facts,
        "quiz": quiz,
        "lines": lines,
    }


def _pages(topic: Topic) -> list[tuple[int, str]]:
    """The topic's pages with their real numbers (for «… -bet» references)."""
    from nexvara.knowledge.service import open_library

    lib = open_library()
    try:
        pages = [
            (p, lib.page_text(topic.book.id, p))
            for p in range(topic.start_page, topic.end_page + 1)
        ]
    finally:
        lib.close()
    return [(p, t) for p, t in pages if t] or [(topic.start_page, topic.text)]


def default_path(topic: Topic) -> Path:
    name = f"{topic.book.grade or 'x'}-sinf {topic.book.subject or ''} {topic.title}"[:70]
    name = re.sub(r"[^\w‘’' -]", "", name).strip().replace(" ", "_")
    return config.data_dir() / "Dars ishlanmalari" / f"{name}_{time.strftime('%Y%m%d-%H%M%S')}.docx"


def run_lesson(
    task: Any,
    req: TopicRequest,
    out_dir: Path | None = None,
    *,
    slides: bool = True,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
) -> dict[str, Any]:
    from nexvara.skills.word import ops
    from nexvara.skills.word.ops import WordSession

    with task.step("Darslikdan mavzuni topish") as s:
        topic = lookup(req)
        data = lesson_content(topic)
        s.detail = f"{topic.book.label()} · {topic.title} · {topic.pages_label}"
    out = default_path(topic)
    if out_dir is not None:
        out = Path(out_dir) / out.name
    out.parent.mkdir(parents=True, exist_ok=True)
    with (
        WordSession(visible=visible, keep_open=keep_open) as w,
        task.step("Word: dars ishlanmasi") as s,
    ):
        doc = w.new_document()
        w.show()
        ops.page_setup(doc)
        ops.add_paragraph(doc, "DARS ISHLANMASI", ops.STYLE_HEADING[1], align="center")
        book = topic.book
        ops.add_table(
            doc,
            [
                ["Bo‘lim", "Ma’lumot"],
                ["Sana", "____ - ____ - 20___"],
                ["Sinf", f"{book.grade or '___'}-sinf"],
                ["Fan", book.subject or "___"],
                ["Mavzu", data["title"]],
                ["Darslik", f"{book.label()}, {topic.pages_label}"],
                ["Dars turi", "Yangi bilim beruvchi dars"],
                ["Dars metodi", "Suhbat, aqliy hujum, savol-javob, juftlikda ishlash"],
                ["Jihozlar", "Darslik, taqdimot (NEXVARA), doska, tarqatma savollar"],
            ],
        )
        ops.add_heading(doc, "Darsning maqsadi", 2)
        for k, v in data["aims"].items():
            ops.add_paragraph(doc, f"{k}: {v}")
        ops.add_heading(doc, "Darsning borishi (45 daqiqa)", 2)
        rows = [["Bosqich", "Vaqt", "O‘qituvchi faoliyati", "O‘quvchi faoliyati"]]
        rows += [[st, f"{mins} daq.", *data["teach"][st]] for st, mins in STAGES]
        ops.add_table(doc, rows, numeric_columns=(2,))
        if data["defs"]:
            ops.add_heading(doc, "Asosiy tushunchalar (darslikdan)", 2)
            ops.add_bullets(doc, [f"{d.term} — {d.defn} ({d.page}-bet)" for d in data["defs"]])
        if data["facts"]:
            ops.add_heading(doc, "Esda tutish uchun", 2)
            ops.add_bullets(doc, [f"{f.sentence} ({f.page}-bet)" for f in data["facts"]])
        ops.add_heading(doc, "Mustahkamlash savollari", 2)
        for i, q in enumerate(data["quiz"], 1):
            ops.add_paragraph(doc, f"{i}. {q.text}")
            for j, opt in enumerate(q.options):
                ops.add_paragraph(doc, f"    {'ABCD'[j]}) {opt}")
            ops.add_paragraph(doc, f"    Javob: {q.answer}", size=11)
        if not data["quiz"]:
            ops.add_paragraph(
                doc, "Mavzu matnidan avtomatik savol chiqmadi — 3–5 ta savolni o‘qituvchi qo‘shadi."
            )
        ops.add_heading(doc, "Uyga vazifa", 2)
        ops.add_paragraph(
            doc,
            f"Darslikning {topic.pages_label}ini o‘qish va mavzu oxiridagi "
            "savollarga yozma javob berish.",
        )
        ops.add_paragraph(
            doc,
            "Manba: "
            + book.label()
            + ", "
            + topic.pages_label
            + ". NEXVARA darslik matnidan tuzdi — darsdan oldin o‘qituvchi ko‘rib "
            "chiqadi.",
            size=10,
        )
        ops.add_page_numbers(doc)
        w.save_as(doc, out)
        pdf = ops.export_pdf(doc, out.with_suffix(".pdf"))
        s.detail = f"{out.name} ({len(data['quiz'])} ta savol, {len(data['defs'])} ta tushuncha)"
        if not keep_open:
            w.disown(doc)
            doc.Close(ops.WD_DO_NOT_SAVE)
        del doc
    result: dict[str, Any] = {
        "path": str(out),
        "pdf": str(pdf),
        "title": topic.title,
        "book": book.label(),
        "questions": len(data["quiz"]),
        "checks": [{"name": "Dars ishlanmasi", "ok": out.is_file()}],
    }
    if slides:
        from nexvara.agent.ppt_exec import run_topic_presentation

        deck = out.with_name(out.stem.replace("_", " ")[:60].replace(" ", "_") + "_taqdimot.pptx")
        res = run_topic_presentation(
            task, req, deck, visible=visible, keep_open=keep_open, pause=pause
        )
        result["slides"] = res["path"]
        result["checks"] += res.get("checks", [])
    result["report"] = [f"Dars ishlanmasi: {out.name}"] + (
        [f"Taqdimot: {Path(result['slides']).name}"] if slides else []
    )
    return result
