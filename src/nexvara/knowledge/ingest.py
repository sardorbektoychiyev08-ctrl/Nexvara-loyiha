"""Index the PDF textbooks a user drops into the library folder."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from nexvara.knowledge.catalog import describe
from nexvara.knowledge.store import Library
from nexvara.knowledge.textnorm import is_cyrillic, normalize

log = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 150  # below this the PDF is a scan without a text layer


@dataclass
class IngestReport:
    added: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    no_text: list[str] = field(default_factory=list)
    cyrillic: list[str] = field(default_factory=list)
    unknown_meta: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"{len(self.added)} ta yangi", f"{len(self.unchanged)} ta o‘zgarmagan"]
        for name, items in (
            ("dublikat", self.duplicates),
            ("matnsiz (skaner)", self.no_text),
            ("kirill yozuvida", self.cyrillic),
            ("sinf/fani aniqlanmadi", self.unknown_meta),
            ("xato", self.errors),
            ("o‘chirilgan", self.removed),
        ):
            if items:
                parts.append(f"{len(items)} ta {name}")
        return ", ".join(parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_pages(path: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(normalize(page.extract_text() or ""))
        except Exception as e:  # one broken page must not lose the whole book
            log.warning("%s: page extraction failed: %s", path.name, e)
            pages.append("")
    return pages


def ingest_folder(root: Path, lib: Library, progress=None) -> IngestReport:
    """Index new/changed PDFs under `root`; forget books whose files were deleted.

    `progress(i, n, name)` is called before each file (used for the live task panel).
    """
    root.mkdir(parents=True, exist_ok=True)
    report = IngestReport()
    files = sorted(p for p in root.rglob("*") if p.suffix.lower() == ".pdf" and p.is_file())
    present = {str(p.resolve()) for p in files}

    for book in lib.books(status=None):
        if book.path not in present:
            lib.remove_book(book.id)
            report.removed.append(Path(book.path).name)

    for i, path in enumerate(files, start=1):
        if progress:
            progress(i, len(files), path.name)
        key = str(path.resolve())
        try:
            sha = sha256_file(path)
            known = lib.book_by_path(key)
            if known and known[1] == sha:
                report.unchanged.append(path.name)
                continue
            other = lib.path_for_sha(sha)
            if other and other != key:
                report.duplicates.append(f"{path.name} = {Path(other).name}")
                continue
            pages = extract_pages(path)
            info = describe(path, "\n".join(pages[:4]), root)
            text_pages = [p for p in pages if len(p) >= MIN_CHARS_PER_PAGE]
            status, note = "ok", ""
            if len(text_pages) < max(3, len(pages) // 4):
                status, note = "no_text", "PDF skanerlangan, matn qatlami yo‘q (OCR kerak)"
                report.no_text.append(path.name)
            elif is_cyrillic(" ".join(text_pages[:10])):
                status, note = "cyrillic", "Kirill yozuvi: hozircha faqat lotin yozuvi"
                report.cyrillic.append(path.name)
            if status == "ok" and (info.grade is None or info.subject is None):
                report.unknown_meta.append(path.name)
            lib.add_book(
                path=key,
                sha256=sha,
                title=info.title,
                grade=info.grade,
                subject=info.subject,
                year=info.year,
                pages=pages,
                status=status,
                note=note,
            )
            if status == "ok":
                report.added.append(path.name)
        except Exception as e:
            log.exception("Failed to index %s", path)
            report.errors.append(f"{path.name}: {type(e).__name__}: {e}")
    return report
