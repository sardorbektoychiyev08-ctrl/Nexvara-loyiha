"""SQLite store for the textbook library: books, page texts, sections, full-text search."""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from nexvara.knowledge.textnorm import fold

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    sha256 TEXT NOT NULL,
    title TEXT NOT NULL,
    grade INTEGER,
    subject TEXT,
    year INTEGER,
    pages INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ok',      -- ok | no_text | cyrillic | error
    note TEXT NOT NULL DEFAULT '',
    added_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (book_id, page_no)
);
CREATE TABLE IF NOT EXISTS sections (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page_no INTEGER NOT NULL,
    title TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    folded, book_id UNINDEXED, page_no UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

SCHEMA_VERSION = 3  # 2: multi-line section titles, 3: table-of-contents lines skipped
_TOC_LEADER = re.compile(r"(?:\.\s?){4,}|…{2,}")

# "§ 25. Prujina bikirligi", "25-§. ...", "12-mavzu. ...", "IV bob. Harakat qonunlari"
_SECTION = re.compile(
    r"^\s*(?:§\s*\d+|\d+\s*-\s*§|\d+\s*-\s*mavzu|\d+\s*-\s*dars|[IVXL]+\s+bob)\s*[.:]?\s*(.{3,90})$",
    re.IGNORECASE,
)


@dataclass
class Book:
    id: int
    path: str
    title: str
    grade: int | None
    subject: str | None
    year: int | None
    pages: int
    status: str
    note: str

    def label(self) -> str:
        g = f"{self.grade}-sinf " if self.grade else ""
        y = f" ({self.year})" if self.year else ""
        return f"{g}{self.subject or self.title}{y}"


@dataclass
class Hit:
    book: Book
    page_no: int
    text: str
    score: float


def _upper_share(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if letters else 0.0


def find_sections(page_text: str) -> list[str]:
    """Section headings on a page. An all-caps heading wrapped over several lines
    ("11-§. XIVA XONLIGI USTIDAN" + "ROSSIYA IMPERIYASI ...") is joined back together."""
    lines = page_text.split("\n")
    out = []
    for i, line in enumerate(lines):
        m = _SECTION.match(line)
        if not (m and sum(ch.isalpha() for ch in m.group(1)) >= 3):
            continue
        if _TOC_LEADER.search(line):
            continue  # a table-of-contents line ("11-§. ... . . . . 36"), not the section itself
        title = line.strip()
        if _upper_share(m.group(1)) > 0.6:
            for nxt in lines[i + 1 : i + 3]:
                if nxt.strip() and _upper_share(nxt) > 0.6 and not _SECTION.match(nxt):
                    title += " " + nxt.strip()
                else:
                    break
        out.append(title)
    return out


def fts_query(text: str) -> str:
    """User words -> FTS5 query: every word must match (prefix match for stems)."""
    words = [w for w in re.findall(r"\w+", fold(text)) if len(w) >= 2]
    # Uzbek is agglutinative: "kasrlarni" should find "kasr". Use a short stem as a prefix.
    return " ".join(f'"{w[: max(4, len(w) - 3)]}"*' for w in words)


class Library:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys = ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version < SCHEMA_VERSION:
            # Everything here is derived from the PDFs, so an old index is simply rebuilt
            # on the next "Yangilash".
            self.db.executescript(
                "DROP TABLE IF EXISTS pages_fts; DROP TABLE IF EXISTS sections; "
                "DROP TABLE IF EXISTS pages; DROP TABLE IF EXISTS books;"
            )
        self.db.executescript(SCHEMA)
        self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self.db.close()

    # ----- books -----
    def _book(self, row: tuple) -> Book:
        return Book(*row)

    _COLS = "id, path, title, grade, subject, year, pages, status, note"

    def books(self, status: str | None = "ok") -> list[Book]:
        sql = f"SELECT {self._COLS} FROM books"
        args: tuple = ()
        if status:
            sql += " WHERE status = ?"
            args = (status,)
        sql += " ORDER BY grade, subject, year DESC"
        return [self._book(r) for r in self.db.execute(sql, args)]

    def book_by_path(self, path: str) -> tuple[Book, str] | None:
        row = self.db.execute(
            f"SELECT {self._COLS}, sha256 FROM books WHERE path = ?", (path,)
        ).fetchone()
        return (self._book(row[:-1]), row[-1]) if row else None

    def path_for_sha(self, sha: str) -> str | None:
        row = self.db.execute("SELECT path FROM books WHERE sha256 = ?", (sha,)).fetchone()
        return row[0] if row else None

    def remove_book(self, book_id: int) -> None:
        self.db.execute("DELETE FROM pages_fts WHERE book_id = ?", (book_id,))
        self.db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        self.db.commit()

    def add_book(
        self,
        *,
        path: str,
        sha256: str,
        title: str,
        grade: int | None,
        subject: str | None,
        year: int | None,
        pages: Iterable[str],
        status: str = "ok",
        note: str = "",
    ) -> int:
        """Insert (or replace) a book with its page texts. Returns the book id."""
        old = self.book_by_path(path)
        if old:
            self.remove_book(old[0].id)
        page_list = list(pages)
        cur = self.db.execute(
            "INSERT INTO books (path, sha256, title, grade, subject, year, pages, status, note, "
            "added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (path, sha256, title, grade, subject, year, len(page_list), status, note, time.time()),
        )
        book_id = int(cur.lastrowid)
        if status == "ok":
            for no, text in enumerate(page_list, start=1):
                self.db.execute(
                    "INSERT INTO pages (book_id, page_no, text) VALUES (?, ?, ?)",
                    (book_id, no, text),
                )
                self.db.execute(
                    "INSERT INTO pages_fts (folded, book_id, page_no) VALUES (?, ?, ?)",
                    (fold(text), book_id, no),
                )
                for title_line in find_sections(text):
                    self.db.execute(
                        "INSERT INTO sections (book_id, page_no, title) VALUES (?, ?, ?)",
                        (book_id, no, title_line),
                    )
        self.db.commit()
        return book_id

    def update_meta(self, book_id: int, *, grade: int | None, subject: str | None) -> None:
        self.db.execute(
            "UPDATE books SET grade = ?, subject = ? WHERE id = ?", (grade, subject, book_id)
        )
        self.db.commit()

    # ----- queries -----
    def grades_subjects(self) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for g, s in self.db.execute(
            "SELECT DISTINCT grade, subject FROM books WHERE status = 'ok' AND grade IS NOT NULL "
            "AND subject IS NOT NULL ORDER BY grade, subject"
        ):
            out.setdefault(g, []).append(s)
        return out

    def best_books(self, grade: int | None, subject: str | None) -> list[Book]:
        """Matching books, newest edition first (so a new textbook wins over an old one)."""
        sql = f"SELECT {self._COLS} FROM books WHERE status = 'ok'"
        args: list = []
        if grade is not None:
            sql += " AND grade = ?"
            args.append(grade)
        if subject is not None:
            sql += " AND subject = ?"
            args.append(subject)
        sql += " ORDER BY COALESCE(year, 0) DESC, added_at DESC"
        return [self._book(r) for r in self.db.execute(sql, args)]

    def page_text(self, book_id: int, page_no: int) -> str:
        row = self.db.execute(
            "SELECT text FROM pages WHERE book_id = ? AND page_no = ?", (book_id, page_no)
        ).fetchone()
        return row[0] if row else ""

    def book_pages(self, book_id: int) -> list[tuple[int, str]]:
        return list(
            self.db.execute(
                "SELECT page_no, text FROM pages WHERE book_id = ? ORDER BY page_no", (book_id,)
            )
        )

    def sections(self, book_id: int) -> list[tuple[int, str]]:
        return list(
            self.db.execute(
                "SELECT page_no, title FROM sections WHERE book_id = ? ORDER BY page_no",
                (book_id,),
            )
        )

    def search(
        self,
        query: str,
        grade: int | None = None,
        subject: str | None = None,
        limit: int = 10,
        newest_only: bool = True,
    ) -> list[Hit]:
        """Best-matching pages. With newest_only, only the newest edition per grade+subject."""
        books = {b.id: b for b in self.best_books(grade, subject)}
        if newest_only:
            seen: set[tuple] = set()
            keep = {}
            for b in books.values():  # already newest first
                key = (b.grade, b.subject)
                if key not in seen:
                    seen.add(key)
                    keep[b.id] = b
            books = keep
        if not books:
            return []
        q = fts_query(query)
        if not q:
            return []
        ids = ",".join(str(i) for i in books)
        rows = self.db.execute(
            f"SELECT book_id, page_no, bm25(pages_fts) FROM pages_fts WHERE pages_fts MATCH ? "
            f"AND book_id IN ({ids}) ORDER BY bm25(pages_fts) LIMIT ?",
            (q, limit),
        ).fetchall()
        return [
            Hit(books[int(b)], int(p), self.page_text(int(b), int(p)), -float(s))
            for b, p, s in rows
        ]
