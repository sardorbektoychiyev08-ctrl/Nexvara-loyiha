"""Write generated tests into Word, live and visible: variants, then the teacher's answer keys."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from nexvara.core.task import Task
from nexvara.knowledge.quiz import LETTERS, QuizResult
from nexvara.knowledge.service import (
    TestRequest,
    answer_key_rows,
    default_test_path,
    make_quizzes,
    question_lines,
)
from nexvara.skills.common import validate_output_path

_QUESTION_LINE = re.compile(r"^\d+\. ")


class VerificationError(Exception):
    pass


def run_make_test(
    task: Task,
    req: TestRequest,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
    make: Any = None,
) -> dict[str, Any]:
    """`make(req) -> (book, topic, quizzes)`; the offline generator by default (the AI
    generator is passed in by the app when the user asks for an AI test)."""
    from nexvara.skills.word.ops import WordSession

    with task.step("Darslikdan mavzuni topish" if make is None else "AI savollar tuzmoqda") as s:
        book, topic, quizzes = (make or make_quizzes)(req)
        n = len(quizzes[0].questions)
        s.detail = f"{book.label()} · «{topic}» · {n} ta savol"
        if n == 0:
            raise LookupError("Bu mavzu matnidan savol tuzib bo‘lmadi; boshqa mavzuni tanlang.")

    out = Path(out_path) if out_path else default_test_path(book, topic)
    validate_output_path(out, (".docx",))
    pdf = out.with_suffix(".pdf")
    validate_output_path(pdf, (".pdf",))

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    try:
        with WordSession(visible=visible, keep_open=keep_open) as w:
            checks = _write_and_verify(
                task,
                w,
                book.label(),
                topic,
                quizzes,
                out,
                pdf,
                beat,
                keep_open,
                ai_generated=make is not None,
            )
    finally:
        # The cut-out pictures are embedded in the .docx now; drop the temp copies.
        import shutil

        for d in {Path(x.image).parent for q in quizzes for x in q.questions if x.image}:
            shutil.rmtree(d, ignore_errors=True)
    pictures = sum(1 for x in quizzes[0].questions if x.image)

    notes = [q.note for q in quizzes if q.note]
    return {
        "path": str(out),
        "pdf": str(pdf),
        "checks": checks,
        "book": book.label(),
        "topic": topic,
        "questions": n,
        "variants": len(quizzes),
        "note": notes[0] if notes else "",
        "pictures": pictures,
        # Answer keys per variant ("ABDC…"), so answer sheets can be checked by photo.
        "answers": ["".join(x.answer for x in q.questions) for q in quizzes],
    }


def _write_and_verify(
    task: Task,
    w: Any,
    book_label: str,
    topic: str,
    quizzes: list[QuizResult],
    out: Path,
    pdf: Path,
    beat: Any,
    keep_open: bool,
    *,
    ai_generated: bool = False,
) -> list[dict[str, Any]]:
    # COM objects live only in this frame, so they are released before Word quits.
    from nexvara.skills.word import ops

    with task.step("Word'ni ochish") as s:
        doc = w.new_document()
        ops.page_setup(doc, margins_cm=(1.5, 1.5, 1.5, 2.0))
        ops.set_header(doc, f"NEXVARA · {book_label}")
        ops.add_page_numbers(doc)
        w.show()
        s.detail = f"Word {w.version}"
    beat()

    for v, quiz in enumerate(quizzes, start=1):
        with task.step(f"{v}-variant") as s:
            title = f"{book_label}: «{topic}» — test"
            if len(quizzes) > 1:
                title += f" ({v}-variant)"
            p = ops.add_paragraph(doc, title, ops.STYLE_HEADING[1], align="center")
            if v > 1:
                p.PageBreakBefore = True
            ops.add_paragraph(
                doc, "F.I.Sh.: ______________________   Sinf: ______   Sana: ________"
            )
            for i, q in enumerate(quiz.questions, start=1):
                lines = question_lines(q, i)
                # A question never breaks across pages: stem, picture and options stay together.
                stem = ops.add_paragraph(doc, lines[0], bold=True)
                stem.KeepWithNext = True
                if q.image:
                    shape = ops.add_picture(doc, q.image, width_cm=8)
                    if shape.Height > ops.cm_to_pt(7):  # tall pictures: cap the height
                        ratio = shape.Width / shape.Height
                        shape.Height = ops.cm_to_pt(7)
                        shape.Width = shape.Height * ratio
                    doc.Paragraphs.Last.KeepWithNext = True
                    del shape
                for k, line in enumerate(lines[1:], start=1):
                    p = ops.add_paragraph(doc, line)
                    p.KeepWithNext = k < len(lines) - 1
                if q.kind == "match":
                    rows = [["Tushuncha", "Ta’rif"]] + [
                        [f"{k + 1}. {term}", f"{LETTERS[k]}) {defn}"]
                        for k, (term, defn) in enumerate(q.pairs)
                    ]
                    ops.add_table(doc, rows)
            s.detail = f"{len(quiz.questions)} ta savol"
            w.show()
        beat()

    with task.step("Javoblar kaliti"):
        p = ops.add_paragraph(doc, "Javoblar kaliti (o‘qituvchi uchun)", ops.STYLE_HEADING[1])
        p.PageBreakBefore = True
        for v, quiz in enumerate(quizzes, start=1):
            if len(quizzes) > 1:
                ops.add_heading(doc, f"{v}-variant", 2)
            ops.add_table(doc, answer_key_rows(quiz), numeric_columns=(1, 2))
        method = "AI yordamida" if ai_generated else "AI ishlatilmasdan"
        ops.add_paragraph(
            doc,
            f"Savollar darslik matni asosida {method} avtomatik tuzildi. "
            "Betlar javoblar kalitida ko‘rsatilgan. Mazmun va javoblarni tarqatishdan "
            "oldin o‘qituvchi tekshirsin.",
            size=9,
        )
    beat()

    with task.step("Saqlash (DOCX + PDF)") as s:
        w.save_as(doc, out)
        ops.export_pdf(doc, pdf)
        s.detail = f"{out.name}"
        w.disown(doc)
        doc.Close(ops.WD_DO_NOT_SAVE)
        del p, doc
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        doc2 = w.open_document(out)
        w.show()
        checks = verify_test(doc2, quizzes, pdf)
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o‘tdi"
        if failed:
            raise VerificationError("Tekshiruv o‘tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            w.disown(doc2)
            doc2.Close(ops.WD_DO_NOT_SAVE)
    return checks


def verify_test(doc: Any, quizzes: list[QuizResult], pdf: Path) -> list[dict[str, Any]]:
    from nexvara.skills.word import ops

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    numbered = 0
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        if not p.Range.Information(12) and _QUESTION_LINE.match(str(p.Range.Text)):
            numbered += 1
    expected = sum(len(q.questions) for q in quizzes)
    check("Savollar soni", numbered == expected, f"{numbered} (kutilgan {expected})")

    match_tables = sum(1 for q in quizzes for x in q.questions if x.kind == "match")
    tables = doc.Tables.Count
    check("Jadvallar", tables == len(quizzes) + match_tables, str(tables))
    keys_ok = True
    for v, quiz in enumerate(quizzes):
        t = doc.Tables(tables - len(quizzes) + v + 1)
        if t.Rows.Count != len(quiz.questions) + 1:
            keys_ok = False
            continue
        for r, q in enumerate(quiz.questions, start=2):
            if ops.cell_text(t, r, 2) != q.answer:
                keys_ok = False
    check("Javoblar kaliti", keys_ok)
    mcq_ok = all(
        len(x.options) == 4 and x.answer in LETTERS for q in quizzes for x in q.questions
        if x.kind == "mcq"
    )  # fmt: skip
    check("A/B/C/D variantlar", mcq_ok)
    pictures = sum(1 for q in quizzes for x in q.questions if x.image)
    check("Rasmli savollar", doc.InlineShapes.Count == pictures, f"{pictures} ta rasm")
    check("PDF", pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-", str(pdf))
    return checks
