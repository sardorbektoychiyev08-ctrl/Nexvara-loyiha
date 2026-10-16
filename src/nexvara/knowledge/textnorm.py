"""Text clean-up for Uzbek (Latin) textbook PDFs."""

from __future__ import annotations

import re

# Official Uzbek Latin: o‘ g‘ use U+2018, the tutuq (ʼ) uses U+2019.
OKINA = "‘"
TUTUQ = "’"
_APOS = "�`´ʻʼ'‘’"

_OG = re.compile(rf"([oOgG])[{_APOS}]")
_TUTUQ_CANDIDATE = re.compile(rf"(?<![oOgG])[{_APOS}]")
_ANY_APOS = re.compile(rf"[{_APOS}]")
_SOFT_HYPHEN = re.compile(r"­\s*")
_HYPHEN_BREAK = re.compile(r"(\w)[-–]\s*\n\s*([a-zа-яўқғҳ])")
_HYPHEN_SPACE = re.compile(r"(\w{2,})- ([a-zа-яўқғҳ]{2,})")
_BULLETS = re.compile(r"^[►•▪●■◆➤✓*]+\s*")
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЎҚҒҲ0-9«\"(])")


def normalize(text: str) -> str:
    """Repair apostrophes broken by PDF fonts, join hyphenated words, tidy whitespace."""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = _SOFT_HYPHEN.sub("", t)
    t = _OG.sub(lambda m: m.group(1) + OKINA, t)
    t = _TUTUQ_CANDIDATE.sub(TUTUQ, t)  # the o‘/g‘ fixed above are left alone
    t = _HYPHEN_BREAK.sub(r"\1\2", t)
    t = _HYPHEN_SPACE.sub(r"\1\2", t)
    # " - " is NOT joined: "Tezlik - jismning ..." is a definition, not a broken word.
    t = _SPACES.sub(" ", t)
    t = "\n".join(line.strip() for line in t.split("\n"))
    return _BLANK_LINES.sub("\n\n", t).strip()


def fold(text: str) -> str:
    """Search key: lower-case, apostrophes removed ("O‘zbekiston" -> "ozbekiston")."""
    return _ANY_APOS.sub("", text).lower()


def _is_heading(line: str, next_line: str) -> bool:
    letters = [ch for ch in line if ch.isalpha()]
    if len(letters) >= 2 and sum(ch.isupper() for ch in letters) / len(letters) >= 0.6:
        return True  # "XIX ASR OXIRI", "1-§. JISMLARNING HARAKATI"
    words = line.split()
    # Short title-like line without ending punctuation, followed by a new capitalised line.
    return 0 < len(words) <= 4 and line[-1:] not in ".,:;!?-–—" and next_line[:1].isupper()


def content_lines(text: str) -> list[str]:
    """Lines of running text: headings dropped, bullet marks stripped."""
    lines = [_BULLETS.sub("", ln).strip() for ln in text.split("\n")]
    out: list[str] = []
    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if ln and not _is_heading(ln, nxt):
            out.append(ln)
        elif out and out[-1][-1:] not in ".!?":
            out[-1] += "."  # a dropped heading also ends the previous fragment
    return out


def sentences(text: str) -> list[str]:
    """Split normalized text into sentences (line breaks inside a sentence are joined)."""
    flat = " ".join(content_lines(text))
    return [s.strip() for s in _SENT_SPLIT.split(flat) if s.strip()]


def letter_ratio(s: str) -> float:
    if not s:
        return 0.0
    return sum(ch.isalpha() for ch in s) / len(s)


def is_cyrillic(text: str, threshold: float = 0.3) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    cyr = sum("Ѐ" <= ch <= "ӿ" for ch in letters)
    return cyr / len(letters) >= threshold
