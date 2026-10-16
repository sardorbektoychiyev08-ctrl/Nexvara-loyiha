"""Find a topic in a textbook and cut out its text: "7-sinf fizika, Nyuton qonunlari".

A topic is a §-section: it starts at its heading and ends where the next § starts.
Matching tries section titles first (what a teacher usually names), then full text.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from nexvara.knowledge.store import Book, Library
from nexvara.knowledge.textnorm import fold

MAX_TOPIC_PAGES = 12
_PARA_SECTION = re.compile(r"^\s*(?:§\s*\d+|\d+\s*-\s*§|\d+\s*-\s*mavzu|\d+\s*-\s*dars)", re.I)
_PAGE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
_CHAPTER_HEADER = re.compile(r"^[IVXL]+\s+bob\.", re.I)  # "IV bob. Harakat qonunlari"


@dataclass
class Topic:
    book: Book
    title: str  # display title, e.g. "11-§. Xiva xonligi ustidan rossiya imperiyasi..."
    start_page: int
    end_page: int
    text: str
    matched_by: str  # "sarlavha" | "matn"

    @property
    def pages_label(self) -> str:
        if self.start_page == self.end_page:
            return f"{self.start_page}-bet"
        return f"{self.start_page}–{self.end_page}-betlar"


def display_title(title: str) -> str:
    """'11-§. XIVA XONlIGI USTIDAN' -> '11-§. Xiva xonligi ustidan' (all-caps -> sentence case)."""
    letters = [c for c in title if c.isalpha()]
    upper = sum(c.isupper() for c in letters) / len(letters) if letters else 0
    if upper < 0.5:
        return title.strip()
    m = re.match(r"^(\s*\S+\s*[.:]?\s*)(.*)$", title)
    head, rest = (m.group(1), m.group(2)) if m else ("", title)
    rest = rest.lower()
    return (head + rest[:1].upper() + rest[1:]).strip()


_TOC_ENTRY = re.compile(r"^\s*(\d+)\s*[-–]\s*§§?\.?\s*(.*)$")
_LEADER_NUM = re.compile(r"(?:\.\s?){3,}\s*(\d{1,3})\s*$")
_LEADER = re.compile(r"(?:\.\s?){3,}.*$")
_NUM_LINE = re.compile(r"^\s*(\d{1,3})\s*$")


def _section_number(title: str) -> int | None:
    m = re.match(r"^\s*(\d+)\s*[-–]\s*§|^\s*§\s*(\d+)", title)
    return int(m.group(1) or m.group(2)) if m else None


def parse_toc(page_texts: list[str]) -> list[tuple[int, str, int]]:
    """(§ number, title, printed page) from contents pages.

    Handles "12-§. Title ........ 44" and the wrapped form "12-§. Title" / "........ 44".
    """
    out: list[tuple[int, str, int]] = []
    for text in page_texts:
        lines = [ln.strip() for ln in text.split("\n")]
        i = 0
        while i < len(lines):
            m = _TOC_ENTRY.match(lines[i])
            if not m:
                i += 1
                continue
            num, title = int(m.group(1)), m.group(2)
            printed = None
            j = i
            while True:
                cur = lines[j] if j > i else title
                lm = _LEADER_NUM.search(cur)
                if lm:
                    printed = int(lm.group(1))
                    title = (title if j == i else title + " " + cur[: lm.start()]).strip()
                    title = _LEADER.sub("", title).strip()
                    break
                if j > i:
                    nm = _NUM_LINE.match(cur)
                    if nm:
                        printed = int(nm.group(1))
                        break
                    if not cur or _TOC_ENTRY.match(cur) or j - i > 2:
                        break
                    title += " " + _LEADER.sub("", cur)
                j += 1
                if j >= len(lines):
                    break
            if printed is not None:
                out.append((num, f"{num}-§. {title.strip()}", printed))
            i = max(j, i + 1)
    return out


def page_offset(lib: Library, book: Book) -> int | None:
    """PDF page minus printed page number, from page numbers printed at the top or bottom."""
    votes: Counter[int] = Counter()
    for page, text in lib.book_pages(book.id):
        lines = [ln for ln in text.split("\n") if ln.strip()]
        for ln in lines[:1] + lines[-1:]:
            m = _NUM_LINE.match(ln)
            if m:
                votes[page - int(m.group(1))] += 1
    if not votes:
        return None
    offset, n = votes.most_common(1)[0]
    return offset if n >= 5 else None


def section_starts(lib: Library, book: Book) -> list[tuple[int, str]]:
    """Every §-section with its PDF page, in page order.

    Headings found in the body win. Sections whose heading is not in the text layer
    (drawn as an image in some books) are placed from the contents page + page offset.
    """
    sections = [(p, t) for p, t in lib.sections(book.id) if _PARA_SECTION.match(t)]
    per_page = Counter(p for p, _t in sections)
    toc_pages = {p for p, n in per_page.items() if n >= 4}  # a contents page lists many §
    seen: set[str] = set()
    out = []
    for page, title in sections:
        key = fold(title)
        if page not in toc_pages and key not in seen:
            seen.add(key)
            out.append((page, title))

    have = {_section_number(t) for _p, t in out}
    pages = lib.book_pages(book.id)
    contents = [t for p, t in pages if len(re.findall(r"(?m)^\s*\d+\s*[-–]\s*§", t)) >= 4]
    offset = page_offset(lib, book) if contents else None
    if offset is not None:
        for num, title, printed in parse_toc(contents):
            page = printed + offset
            if num not in have and 1 <= page <= book.pages:
                have.add(num)
                out.append((page, title))
    out.sort(key=lambda pt: (pt[0], _section_number(pt[1]) or 0))
    return out


def _stems(text: str) -> list[str]:
    # Uzbek suffixes run up to 4 letters ("qonun-lari", "Nyuton-ning"): compare stems.
    words = [w for w in re.findall(r"\w+", fold(text)) if len(w) >= 3]
    return [w[: max(4, len(w) - 4)] for w in words]


def _title_score(query: str, title: str) -> float:
    stems = _stems(query)
    if not stems:
        return 0.0
    words = re.findall(r"\w+", fold(title))
    hit = sum(1 for s in stems if any(w.startswith(s) for w in words))
    return hit / len(stems)


def _slice(lib: Library, book: Book, start: tuple[int, str], nxt: tuple[int, str] | None):
    """Text from the start heading up to (not including) the next heading."""
    start_page, start_title = start
    end_page = min(nxt[0] if nxt else start_page + 4, start_page + MAX_TOPIC_PAGES - 1)
    end_page = min(end_page, book.pages)
    parts = []
    for page in range(start_page, end_page + 1):
        text = lib.page_text(book.id, page)
        if page == start_page:
            first_line = start_title.split(" ")[0]
            i = text.find(first_line)
            text = text[i:] if i >= 0 else text
        if nxt and page == nxt[0] and page != start_page or (nxt and page == nxt[0] == start_page):
            j = text.find(nxt[1].split(" ")[0], 1)
            if j > 0:
                text = text[:j]
            elif page != start_page:
                end_page = page - 1
                break
        parts.append((page, text))
    return end_page, parts


def _strip_running_lines(parts: list[tuple[int, str]]) -> str:
    """Drop page numbers and headers/footers that repeat on most pages of the topic."""
    counts: Counter[str] = Counter()
    for _p, text in parts:
        counts.update({ln.strip() for ln in text.split("\n") if ln.strip()})
    # Running headers often alternate between even and odd pages, so a third is enough.
    repeated = {
        ln
        for ln, c in counts.items()
        if len(parts) >= 3 and c >= max(2, len(parts) * 0.34) and len(ln.split()) <= 8
    }
    lines = []
    for _p, text in parts:
        for ln in text.split("\n"):
            s = ln.strip()
            if _PAGE_NUMBER.match(s) or s in repeated or _CHAPTER_HEADER.match(s):
                continue
            lines.append(s)
    return "\n".join(lines).strip()


def candidate_books(lib: Library, grade: int | None, subject: str | None) -> list[Book]:
    """Every part of the edition in use per grade+subject (new RTM quarters beat the old
    portal edition). A generic subject ("Tarix") also matches "O‘zbekiston tarixi"."""
    books = lib.current_edition(grade, subject)
    if not books and subject:
        key = fold(subject)
        books = [
            b for b in lib.current_edition(grade, None) if b.subject and key in fold(b.subject)
        ]
    return books


def find_topic(lib: Library, grade: int | None, subject: str | None, query: str) -> Topic:
    if not query.strip():
        raise ValueError("Qaysi mavzu kerakligini yozing")
    books = candidate_books(lib, grade, subject)
    if not books:
        what = " ".join(x for x in (f"{grade}-sinf" if grade else "", subject or "") if x)
        raise LookupError(f"Kutubxonada {what or 'mos'} darslik topilmadi")
    # Several candidate books: prefer one whose section title matches, else the first that
    # mentions the topic at all.
    found: list[tuple[float, Topic]] = []
    for book in books:
        try:
            t = _find_in_book(lib, book, query)
        except LookupError:
            continue
        found.append((_title_score(query, t.title), t))
    if not found:
        where = books[0].label() if len(books) == 1 else "mos darsliklar"
        raise LookupError(f"«{query}» mavzusi {where}da topilmadi")
    return max(found, key=lambda st: st[0])[1]


def _find_in_book(lib: Library, book: Book, query: str) -> Topic:
    starts = section_starts(lib, book)

    # Best title match; on a tie the earlier section wins.
    scored = sorted((-_title_score(query, t), i) for i, (_p, t) in enumerate(starts))
    best = -scored[0][0] if scored else 0.0
    # Pages of THIS book that contain every word of the query.
    hits = [
        h for h in lib.search(query, book.grade, book.subject, limit=30) if h.book.id == book.id
    ]
    # A title that matches every word wins. A partial title match ("amir" ~ "Amirligida")
    # is only trusted when the text itself has no better answer.
    if best == 1.0 or (best >= 0.67 and not hits):
        idx, how = scored[0][1], "sarlavha"
    else:
        if not hits:
            raise LookupError(f"«{query}» mavzusi {book.label()} darsligida topilmadi")
        page = hits[0].page_no
        before = [i for i, (p, _t) in enumerate(starts) if p <= page]
        if not before:  # no § headings in this book: return the matching page and its neighbour
            end = min(page + 1, book.pages)
            parts = [(p, lib.page_text(book.id, p)) for p in range(page, end + 1)]
            title = query.strip()[:1].upper() + query.strip()[1:]
            return Topic(book, title, page, end, _strip_running_lines(parts), "matn")
        idx, how = before[-1], "matn"

    start = starts[idx]
    nxt = starts[idx + 1] if idx + 1 < len(starts) else None
    end_page, parts = _slice(lib, book, start, nxt)
    return Topic(
        book, display_title(start[1]), start[0], end_page, _strip_running_lines(parts), how
    )


def paragraphs(text: str) -> list[tuple[str, str]]:
    """('heading'|'para', text) blocks for Word: wrapped lines joined into paragraphs."""
    out: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            out.append(("para", " ".join(buf)))
            buf.clear()

    for line in text.split("\n"):
        s = line.strip()
        if not s:
            flush()
            continue
        letters = [c for c in s if c.isalpha()]
        upper = sum(c.isupper() for c in letters) / len(letters) if letters else 0
        if (upper > 0.6 and len(letters) >= 4) or _PARA_SECTION.match(s):
            flush()
            out.append(("heading", display_title(s)))
            continue
        buf.append(s)
        if s[-1:] in ".!?:":
            flush()
    flush()
    # Merge consecutive headings produced by a wrapped all-caps title.
    merged: list[tuple[str, str]] = []
    for kind, t in out:
        if kind == "heading" and merged and merged[-1][0] == "heading":
            merged[-1] = ("heading", f"{merged[-1][1]} {t[:1].lower()}{t[1:]}")
        else:
            merged.append((kind, t))
    return merged


def preview(topic: Topic, chars: int = 600) -> str:
    body = " ".join(t for k, t in paragraphs(topic.text) if k == "para")
    return body[:chars].rsplit(" ", 1)[0] + ("…" if len(body) > chars else "")
