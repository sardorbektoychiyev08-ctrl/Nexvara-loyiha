"""High-level library actions used by the UI and chat: index the folder, make a test."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.core.task import Task
from nexvara.knowledge.catalog import SUBJECTS, detect_grade, detect_subject
from nexvara.knowledge.ingest import ingest_folder
from nexvara.knowledge.quiz import LETTERS, Question, QuizResult, build_quiz, extract_definitions
from nexvara.knowledge.store import Book, Library
from nexvara.knowledge.textnorm import fold

MAX_QUESTIONS = 60
MAX_VARIANTS = 6


@dataclass
class TestRequest:
    __test__ = False  # not a pytest test class

    grade: int | None
    subject: str | None
    topic: str = ""
    count: int = 20
    variants: int = 1

    def validate(self) -> None:
        if not 1 <= self.count <= MAX_QUESTIONS:
            raise ValueError(f"savollar soni 1–{MAX_QUESTIONS} oralig‘ida bo‘lsin")
        if not 1 <= self.variants <= MAX_VARIANTS:
            raise ValueError(f"variantlar soni 1–{MAX_VARIANTS} oralig‘ida bo‘lsin")
        if self.grade is not None and not 1 <= self.grade <= 11:
            raise ValueError("sinf 1–11 oralig‘ida bo‘lsin")


_COUNT = re.compile(r"(\d{1,3})\s*(?:ta)?\s*(?:test|savol)")
_VARIANTS = re.compile(r"(\d)\s*(?:ta)?\s*variant")
_TEST_WORDS = ("test", "savol", "nazorat ishi", "viktorina")


def _without_files(text: str) -> str:
    """Drop file names/paths: words inside "D:/Testlar/x.xlsx" are not part of the request."""
    from nexvara.agent.parse import _FILE

    return _FILE.sub(" ", text)


def parse_test_request(text: str) -> TestRequest | None:
    """'7-sinf fizika Nyuton qonunlari 20 ta test 2 variant' -> TestRequest; None if not a test."""
    text = _without_files(text)
    f = fold(text)
    if not any(w in f for w in _TEST_WORDS):
        return None
    grade = detect_grade(text)
    subject = detect_subject(text)
    m = _COUNT.search(f)
    count = int(m.group(1)) if m else 20
    v = _VARIANTS.search(f)
    variants = int(v.group(1)) if v else 1
    return TestRequest(grade, subject, _remaining_topic(f, subject), count, variants)


# Words that ask for a topic's text rather than a test.
_TOPIC_WORDS = ("mavzu", "chiqar", "korsat", "matn", "oqib", "topib", "kerak", "ochib", "bolim")
_FILLER = (
    r"\b(?:test\w*|savol\w*|tuz\w*|ber\w*|yarat\w*|kerak\w*|iltimos|menga|uchun|boyicha|"
    r"mavzu\w*|dan|haqida|darslik\w*|chiqar\w*|korsat\w*|matn\w*|oqib|topib|top|ochib|och|"
    r"bolim\w*|shu|ushbu|qilib|ham|va|bilan|mana|bu|ni|kitob\w*|taqdimot\w*|prezentats\w*|"
    r"slayd\w*|tayyorla\w*|yasa\w*|ai|sun\W?iy|intellekt\w*|aqlli|yordamida)\b"
)
_PRESENTATION_WORDS = ("taqdimot", "prezentats", "slayd")


def parse_presentation_request(text: str):
    """'7-sinf fizika Nyuton qonunlari bo‘yicha taqdimot tayyorla' -> TopicRequest; else None.

    Needs a grade or subject (otherwise it is an ordinary PowerPoint command).
    """
    from nexvara.agent.parse import find_file
    from nexvara.knowledge.topicdoc import TopicRequest

    f = fold(text)
    if not any(w in f for w in _PRESENTATION_WORDS) or any(w in f for w in _TEST_WORDS):
        return None
    if find_file(text):
        return None  # a command about an existing .pptx file
    grade, subject = detect_grade(text), detect_subject(text)
    if grade is None and subject is None:
        return None
    topic = _remaining_topic(f, subject)
    return TopicRequest(grade, subject, topic) if topic else None


def _remaining_topic(folded: str, subject: str | None) -> str:
    """Drop what we understood (grade, counts, subject, filler words); the rest is the topic."""
    topic = folded
    for pat in (
        r"\d{1,2}\s*-?\s*sinf\w*",
        r"\d{1,3}\s*(?:ta)?\s*(?:test|savol)\w*",
        r"\d\s*(?:ta)?\s*variant\w*",
        _FILLER,
    ):
        topic = re.sub(pat, " ", topic)
    if subject:
        for name, keys in SUBJECTS:
            if name == subject:
                for k in keys:
                    # "tarixdan", "fizikadan": drop the subject word with its suffix
                    topic = re.sub(rf"\b{re.escape(k)}\w*", " ", topic)
    topic = re.sub(r"[^\w‘’' -]", " ", topic)
    return re.sub(r"\s+", " ", topic).strip()


def parse_topic_request(text: str):
    """'7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber' -> TopicRequest; else None.

    Tests take priority (see parse_test_request). A topic request must name a grade or a
    subject, so ordinary chat ("menga yordam kerak") is not mistaken for one.
    """
    from nexvara.knowledge.topicdoc import TopicRequest

    text = _without_files(text)
    f = fold(text)
    if any(w in f for w in _TEST_WORDS) or not any(w in f for w in _TOPIC_WORDS):
        return None
    grade, subject = detect_grade(text), detect_subject(text)
    if grade is None and subject is None:
        return None
    topic = _remaining_topic(f, subject)
    return TopicRequest(grade, subject, topic) if topic else None


def open_library() -> Library:
    return Library(config.database_path())


def index_library(task: Task) -> dict[str, Any]:
    root = config.textbooks_dir()
    lib = open_library()
    try:
        with task.step("Darsliklar papkasini tekshirish") as s:
            s.detail = str(root)
            root.mkdir(parents=True, exist_ok=True)
        with task.step("Indekslash") as s:

            def progress(i: int, n: int, name: str) -> None:
                task.check_cancelled()
                s.detail = f"{i}/{n}: {name}"

            report = ingest_folder(root, lib, progress)
            s.detail = report.summary()
        books = lib.books()
        return {
            "summary": report.summary(),
            "books": len(books),
            "problems": report.no_text + report.cyrillic + report.unknown_meta + report.errors,
        }
    finally:
        lib.close()


def _pages_for(lib: Library, req: TestRequest) -> tuple[Book, list[tuple[int, str]], str]:
    from nexvara.knowledge.topics import candidate_books

    books = candidate_books(lib, req.grade, req.subject)
    if not books:
        what = " ".join(
            x for x in (f"{req.grade}-sinf" if req.grade else "", req.subject or "") if x
        )
        raise LookupError(f"Kutubxonada {what or 'mos'} darslik topilmadi")
    book = books[0]
    if req.topic:
        # Search every part of the current edition (1-chorak, 2-chorak, ...).
        hits = []
        for g, s in dict.fromkeys((b.grade, b.subject) for b in books):
            hits += lib.search(req.topic, g, s, limit=12)
        hits.sort(key=lambda h: -h.score)
        pages = [(h.page_no, h.text) for h in hits[:12]]
        if not pages:
            raise LookupError(f"«{req.topic}» mavzusi {book.label()} darsligida topilmadi")
        book = hits[0].book
        return book, sorted(pages), req.topic
    pages = [pg for b in books if (b.grade, b.subject) == (book.grade, book.subject)
             for pg in lib.book_pages(b.id)]  # fmt: skip
    return book, pages, "umumiy"


MAX_EXTRA_PAGES = 18
MAX_FIGURE_PAGES = 40  # the whole book only for the caption pool, pictures from the topic


def figures_tmp_dir() -> Path:
    return config.data_dir() / "tmp"


def _figures_for(book: Book, pages: list[int]):
    """Pictures (cut out to a temp folder) on the test's pages, plus every caption of the
    book as the distractor pool. Empty for scanned books (no caption text to anchor on)."""
    import logging
    import uuid

    from nexvara.knowledge.figures import book_captions, extract_figures, figures_in_pdf

    pdf = Path(book.path)
    if not pdf.is_file() or book.note.startswith("OCR"):
        return [], []
    try:
        wanted = sorted(set(pages))[:MAX_FIGURE_PAGES]
        figs = figures_in_pdf(pdf, wanted)
        if not figs:
            return [], []
        out = figures_tmp_dir() / f"rasm_{uuid.uuid4().hex[:8]}"
        return extract_figures(pdf, figs, out), book_captions(pdf)
    except Exception:  # pictures are a bonus; never fail the whole test because of them
        logging.getLogger(__name__).exception("figure extraction failed for %s", pdf)
        return [], []


def _topic_pages(lib: Library, req: TestRequest, book, hit_pages, topic_label):
    """Pages for a topic test: the whole §-section of the topic, widened with the following
    pages until the text yields enough questions (a short section gives few questions)."""
    from nexvara.knowledge.topics import find_topic

    try:
        t = find_topic(lib, req.grade, req.subject, req.topic)
    except (LookupError, ValueError):
        return book, hit_pages, topic_label
    book = t.book
    start, end = t.start_page, t.end_page
    pages = [(p, lib.page_text(book.id, p)) for p in range(start, end + 1)]
    while len(build_quiz(pages, req.count, seed=1000).questions) < req.count and end < min(
        book.pages, t.end_page + MAX_EXTRA_PAGES
    ):
        end += 3
        pages = [(p, lib.page_text(book.id, p)) for p in range(start, min(end, book.pages) + 1)]
    return book, pages, t.title


def topic_material(req: TestRequest) -> tuple[Book, list[tuple[int, str]], str]:
    """The book, the pages a test on `req` is built from, and the topic's title."""
    req.validate()
    lib = open_library()
    try:
        book, pages, topic = _pages_for(lib, req)
        if req.topic:
            book, pages, topic = _topic_pages(lib, req, book, pages, topic)
        return book, pages, topic
    finally:
        lib.close()


def make_quizzes(req: TestRequest) -> tuple[Book, str, list[QuizResult]]:
    book, pages, topic = topic_material(req)
    lib = open_library()
    try:
        pool = [d.term for d in extract_definitions(lib.book_pages(book.id))]
        figures, captions = _figures_for(book, [p for p, _t in pages])
        quizzes = [
            build_quiz(pages, req.count, seed=1000 + v, term_pool=pool, figures=figures,
                       caption_pool=captions)
            for v in range(req.variants)
        ]  # fmt: skip
        return book, topic, quizzes
    finally:
        lib.close()


def default_test_path(book: Book, topic: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{book.grade or 'x'}-sinf {book.subject or book.title} {topic}"[:70]
    name = re.sub(r"[^\w‘’' -]", "", name).strip().replace(" ", "_")
    return config.tests_output_dir() / f"test_{name}_{stamp}.docx"


def answer_key_rows(quiz: QuizResult) -> list[list[str]]:
    rows = [["№", "Javob", "Manba"]]
    for i, q in enumerate(quiz.questions, start=1):
        rows.append([str(i), q.answer, q.source])
    return rows


def question_lines(q: Question, number: int) -> list[str]:
    """Plain lines of one question (used for Word output and for chat previews)."""
    head, _, rest = q.text.partition("\n")
    lines = [f"{number}. {head}"]
    if rest:
        lines.append(rest)
    if q.kind == "mcq":
        lines += [f"{LETTERS[i]}) {opt}" for i, opt in enumerate(q.options)]
    elif q.kind == "fill":
        lines.append("Javob: ____________________")
    elif q.kind == "tf":
        lines.append("A) To‘g‘ri    B) Noto‘g‘ri")
    return lines
