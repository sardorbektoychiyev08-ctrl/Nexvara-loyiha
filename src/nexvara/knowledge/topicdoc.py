"""Put a textbook topic in front of the user: an editable Word document with the topic text,
and a PDF with the original textbook pages (pictures, formulas and tables intact)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.core.task import Task
from nexvara.knowledge.topics import Topic, find_topic, paragraphs
from nexvara.skills.common import validate_output_path


@dataclass
class TopicRequest:
    grade: int | None
    subject: str | None
    topic: str


class VerificationError(Exception):
    pass


def default_topic_path(topic: Topic) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{topic.book.grade or 'x'}-sinf {topic.book.subject or ''} {topic.title}"[:80]
    name = re.sub(r"[^\w‘’' -]", "", name).strip().replace(" ", "_")
    return config.data_dir() / "Mavzular" / f"{name}_{stamp}.docx"


def lookup(req: TopicRequest) -> Topic:
    from nexvara.knowledge.service import open_library

    lib = open_library()
    try:
        return find_topic(lib, req.grade, req.subject, req.topic)
    finally:
        lib.close()


def extract_pages_pdf(book_pdf: Path, start: int, end: int, out: Path) -> Path:
    """Copy pages start..end (1-based, inclusive) of the original book into a new PDF."""
    from pypdf import PdfReader, PdfWriter

    validate_output_path(out, (".pdf",))
    reader = PdfReader(str(book_pdf))
    writer = PdfWriter()
    for i in range(start - 1, min(end, len(reader.pages))):
        writer.add_page(reader.pages[i])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    return out


def run_topic(
    task: Task,
    req: TopicRequest,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
) -> dict[str, Any]:
    from nexvara.skills.word.ops import WordSession

    with task.step("Darslikdan mavzuni topish") as s:
        topic = lookup(req)
        blocks = paragraphs(topic.text)
        s.detail = f"{topic.book.label()} · {topic.title} · {topic.pages_label}"
        if not any(k == "para" for k, _ in blocks):
            raise LookupError("Mavzu topildi, lekin uning matni bo‘sh (ehtimol skaner sahifa)")

    out = Path(out_path) if out_path else default_topic_path(topic)
    validate_output_path(out, (".docx",))
    excerpt = out.with_name(out.stem + "_asl_sahifalar.pdf")

    with task.step("Asl sahifalar (PDF)") as s:
        extract_pages_pdf(Path(topic.book.path), topic.start_page, topic.end_page, excerpt)
        s.detail = f"{topic.pages_label} → {excerpt.name}"
    task.check_cancelled()

    with WordSession(visible=visible, keep_open=keep_open) as w:
        checks = _write_and_verify(task, w, topic, blocks, out, excerpt, visible, pause, keep_open)
    return {
        "path": str(out),
        "excerpt": str(excerpt),
        "book_path": topic.book.path,
        "start_page": topic.start_page,
        "end_page": topic.end_page,
        "title": topic.title,
        "book": topic.book.label(),
        "checks": checks,
    }


def _write_and_verify(
    task: Task,
    w: Any,
    topic: Topic,
    blocks: list[tuple[str, str]],
    out: Path,
    excerpt: Path,
    visible: bool,
    pause: float,
    keep_open: bool,
) -> list[dict[str, Any]]:
    # COM objects live only in this frame, so they are released before Word quits.
    from nexvara.skills.word import ops

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    source = f"Manba: {topic.book.label()}, {topic.pages_label}"
    with task.step("Word'da mavzu matni") as s:
        doc = w.new_document()
        ops.page_setup(doc)
        ops.set_header(doc, f"NEXVARA · {topic.book.label()}")
        ops.add_page_numbers(doc)
        w.show()
        ops.add_paragraph(doc, topic.title, ops.STYLE_HEADING[1])
        ops.add_paragraph(doc, source, size=9)
        for kind, text in blocks:
            if kind == "heading":
                if text != topic.title:
                    ops.add_heading(doc, text, 2)
            else:
                ops.add_paragraph(doc, text, align="justify")
        ops.add_paragraph(
            doc,
            "Matn darslik PDF'idan avtomatik olindi. Rasm, formula va jadvallar uchun "
            f"«{excerpt.name}» faylidagi asl sahifalarga qarang.",
            size=9,
        )
        s.detail = f"{sum(k == 'para' for k, _ in blocks)} ta paragraf"
    beat()

    with task.step("Saqlash") as s:
        w.save_as(doc, out)
        s.detail = out.name
        w.disown(doc)
        doc.Close(ops.WD_DO_NOT_SAVE)
        del doc
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        doc2 = w.open_document(out)
        w.show()
        checks = verify_topic_doc(doc2, topic, blocks, excerpt)
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o‘tdi"
        if failed:
            raise VerificationError("Tekshiruv o‘tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            w.disown(doc2)
            doc2.Close(ops.WD_DO_NOT_SAVE)
    return checks


def verify_topic_doc(
    doc: Any, topic: Topic, blocks: list[tuple[str, str]], excerpt: Path
) -> list[dict[str, Any]]:
    from pypdf import PdfReader

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    first = str(doc.Paragraphs(1).Range.Text).strip()
    check("Sarlavha", first == topic.title, first)
    text = str(doc.Content.Text)
    check("Manba ko‘rsatilgan", topic.pages_label in text)
    paras = [t for k, t in blocks if k == "para"]
    check("Matn to‘liq", all(p[:40] in text for p in paras[:3] + paras[-2:]))
    n_pages = len(PdfReader(str(excerpt)).pages) if excerpt.is_file() else 0
    want = topic.end_page - topic.start_page + 1
    check("Asl sahifalar PDF", n_pages == want, f"{n_pages} (kutilgan {want})")
    return checks
