"""Official (older, 2017–2019) textbooks from the ministry portal eduportal.uz.

The portal's grade pages are "batafsil1/<id>?menu=33"; the id is NOT the grade, so the
grade is taken from the file path "Umumiyfiles/darsliklar/<grade>/<name>_uzb.pdf".
"""

from __future__ import annotations

import http.cookiejar
import logging
import re
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

BASE = "http://eduportal.uz"
PAGE_IDS = range(1, 41)
SOURCE_DIR = "eduportal"
_LINK = re.compile(
    r"Umumiyfiles/darsliklar/(\d{1,2})/([^\"'<>\s]+?_(uzb|rus|qqr|qozoq|qirgiz|tojik|turkman)\.pdf)",
    re.I,
)


@dataclass(frozen=True)
class RemoteBook:
    grade: int
    name: str
    lang: str

    @property
    def url(self) -> str:
        return f"{BASE}/Umumiyfiles/darsliklar/{self.grade}/{self.name}"


@dataclass
class DownloadReport:
    downloaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    bytes: int = 0

    def summary(self) -> str:
        mb = self.bytes / 1_048_576
        out = f"{len(self.downloaded)} ta yuklandi ({mb:.0f} MB), {len(self.skipped)} ta bor edi"
        return out + (f", {len(self.failed)} ta xato" if self.failed else "")


def _opener() -> urllib.request.OpenerDirector:
    # The portal sets a session cookie on the first request and redirects without it.
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    opener.addheaders = [("User-Agent", "Mozilla/5.0 (NEXVARA textbook downloader)")]
    return opener


def parse_page(html: str, lang: str = "uzb") -> list[RemoteBook]:
    out = []
    for grade, name, file_lang in _LINK.findall(html):
        if file_lang.lower() == lang and 1 <= int(grade) <= 11:
            out.append(RemoteBook(int(grade), name, file_lang.lower()))
    return out


def list_textbooks(lang: str = "uzb", opener=None) -> list[RemoteBook]:
    opener = opener or _opener()
    found: dict[str, RemoteBook] = {}
    for pid in PAGE_IDS:
        try:
            with opener.open(f"{BASE}/Eduportal/batafsil1/{pid}?menu=33", timeout=40) as r:
                html = r.read().decode("utf-8", "replace")
        except OSError as e:
            log.debug("eduportal page %s: %s", pid, e)  # unused ids answer 500
            continue
        for b in parse_page(html, lang):
            found[b.url] = b
    return sorted(found.values(), key=lambda b: (b.grade, b.name))


def target_path(root: Path, book: RemoteBook) -> Path:
    return root / SOURCE_DIR / f"{book.grade}-sinf" / book.name


def _is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def download_all(
    root: Path,
    books: list[RemoteBook],
    progress: Callable[[int, int, str], None] | None = None,
    opener=None,
    retries: int = 3,
) -> DownloadReport:
    """Download missing books into root/eduportal/<grade>-sinf/. Resumable: complete files
    are skipped; partial downloads (.part) are restarted."""
    opener = opener or _opener()
    report = DownloadReport()
    for i, book in enumerate(books, start=1):
        if progress:
            progress(i, len(books), f"{book.grade}-sinf {book.name}")
        dest = target_path(root, book)
        if dest.is_file() and _is_pdf(dest):
            report.skipped.append(book.name)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(".part")
        for attempt in range(1, retries + 1):
            try:
                with opener.open(book.url, timeout=120) as r, part.open("wb") as f:
                    while chunk := r.read(1 << 16):
                        f.write(chunk)
                if not _is_pdf(part):
                    raise OSError("PDF emas (server xato sahifa qaytardi)")
                size = part.stat().st_size
                part.replace(dest)
                report.downloaded.append(book.name)
                report.bytes += size
                break
            except OSError as e:
                log.warning("%s attempt %s: %s", book.url, attempt, e)
                part.unlink(missing_ok=True)
                if attempt == retries:
                    report.failed.append(f"{book.grade}-sinf {book.name}: {e}")
                else:
                    time.sleep(2 * attempt)
    return report
