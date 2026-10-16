"""Work out grade, subject and edition year of a textbook from its path and first pages."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from nexvara.knowledge.textnorm import fold

# Canonical subject -> folded keywords. Order matters: specific names before generic ones.
SUBJECTS: list[tuple[str, tuple[str, ...]]] = [
    ("Jismoniy tarbiya", ("jismoniy tarbiya", "jismoniy_tarbiya", "jismoniy")),
    ("O‘zbekiston tarixi", ("ozbekiston tarixi", "ozbekiston_tarixi")),
    ("Jahon tarixi", ("jahon tarixi", "jahon_tarixi", "qadimgi dunyo", "qadimgi_dunyo")),
    ("Ona tili", ("ona tili", "ona_tili", "onatili")),
    ("O‘zbek tili", ("ozbek tili", "ozbek_tili")),
    ("Ingliz tili", ("ingliz", "english")),
    ("Rus tili", ("rus tili", "rus_tili", "русский")),
    ("Nemis tili", ("nemis",)),
    ("Fransuz tili", ("fransuz",)),
    ("Tasviriy san’at", ("tasviriy",)),
    ("Atrofimizdagi olam", ("atrofimizdagi",)),
    ("Tabiiy fanlar", ("tabiiy fan", "tabiiy_fan", "science")),
    ("Davlat va huquq asoslari", ("huquq",)),
    ("Algebra", ("algebra",)),
    ("Geometriya", ("geometriya",)),
    ("Matematika", ("matematika", "matemati", "mathemati", "maths", " math ")),
    ("Fizika", ("fizika", "physics")),
    ("Kimyo", ("kimyo", "chemistry")),
    ("Biologiya", ("biologiya", "botanika", "zoologiya", "odam va uning salomatligi", "biology")),
    ("Geografiya", ("geografiya", "geography")),
    ("Informatika", ("informatika", "informatics", "computer science")),
    ("Adabiyot", ("adabiyot",)),
    ("O‘qish", ("oqish",)),
    ("Alifbe", ("alifbe", "alifbo")),
    ("Texnologiya", ("texnologiya",)),
    ("Musiqa", ("musiqa",)),
    ("Odobnoma", ("odobnoma",)),
    ("Nutq o‘stirish", ("nutq ostirish", "nutq_ostirish")),
    ("Milliy istiqlol g‘oyasi", ("milliy istiqlol", "milliy_istiqlol")),
    ("Ma’naviyat asoslari", ("manaviyat",)),
    ("Tadbirkorlik asoslari", ("tadbirkorlik",)),
    ("Iqtisodiy bilim asoslari", ("iqtisod",)),
    ("Dunyo dinlari tarixi", ("dunyo dinlari", "dunyo_dinlari")),
    ("Chaqiruvgacha tayyorgarlik", ("chaqiruv",)),
    ("Chizmachilik", ("chizmachilik",)),
    ("Astronomiya", ("astronomiya",)),
    ("Vatan tuyg‘usi", ("vatan tuygusi", "vatan_tuygusi")),
    ("Tarbiya", ("tarbiya",)),
    ("Tarix", ("tarix",)),
]

_GRADE_PATTERNS = [
    re.compile(r"(?<!\d)(1[01]|[1-9])\s*[-_ ]?\s*sinf"),
    re.compile(r"sinf\s*[-_ ]?\s*(1[01]|[1-9])(?!\d)"),
    re.compile(r"(?:^|[^a-z])(?:g|grade\s*)(1[01]|[1-9])(?!\d)"),  # "G6", "Grade 6"
    re.compile(r"(?:^|[_\- .(])(1[01]|[1-9])(?:[_\- .)]|$)"),
]
_YEAR = re.compile(r"(?<!\d)(20[0-4]\d)(?!\d)")


@dataclass
class BookInfo:
    title: str
    grade: int | None
    subject: str | None
    year: int | None


def detect_subject(*texts: str) -> str | None:
    for text in texts:
        f = fold(text).replace("-", " ")
        for name, keys in SUBJECTS:
            if any(k in f for k in keys):
                return name
    return None


def detect_grade(*texts: str) -> int | None:
    for text in texts:
        f = fold(text)
        for pat in _GRADE_PATTERNS:
            m = pat.search(f)
            if m:
                return int(m.group(1))
    return None


def detect_year(text: str) -> int | None:
    now = dt.date.today().year
    years = [int(y) for y in _YEAR.findall(text) if 2000 <= int(y) <= now]
    return max(years) if years else None


def describe(path: Path, first_pages_text: str, library_root: Path | None = None) -> BookInfo:
    """Grade/subject from the file name and folders first, then from the book's own text."""
    rel = str(path.relative_to(library_root)) if library_root else path.name
    stem = path.stem
    # The first pages say e.g. "FIZIKA 7-sinf uchun darslik"; only trust the opening text.
    head = first_pages_text[:3000]
    subject = detect_subject(rel, head)
    grade = detect_grade(rel) or detect_grade(head)
    year = detect_year(head)
    title = re.sub(r"[_]+", " ", stem).strip()
    return BookInfo(title=title, grade=grade, subject=subject, year=year)
