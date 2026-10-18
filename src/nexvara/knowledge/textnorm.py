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
_INITIAL_END = re.compile(r"(?:^|\s)[A-ZА-ЯЎҚҒҲ]\.$")
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
    out: list[str] = []
    for piece in (s.strip() for s in _SENT_SPLIT.split(flat)):
        if not piece:
            continue
        # "... chekingan M." + "Chernyayev ..." is one sentence: a single initial is not an end.
        if out and _INITIAL_END.search(out[-1]):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return out


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


# ---------------- Uzbek Cyrillic -> Latin (the official alphabet: o‘, g‘, sh, ch) ----------------
_UZ_ONLY = set("ўқғҳЎҚҒҲ")
_UZ_WORDS = {"ва", "учун", "билан", "бу", "ҳам", "бўлади", "эди", "деб", "қилиш", "кейин", "ўз",
             "бир", "нима", "қандай", "ёки", "керак", "мумкин", "эмас", "бўлиб"}  # fmt: skip
_RU_WORDS = {"и", "в", "не", "что", "это", "на", "как", "для", "по", "из", "от", "его", "который",
             "при", "был", "или", "так", "все", "она", "они", "мы", "вы", "же"}  # fmt: skip
_CYR_RUN = re.compile(r"[Ѐ-ӿ]")
_VOWELS = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")
_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "x", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "’", "ы": "i",
    "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o‘", "қ": "q", "ғ": "g‘", "ҳ": "h",
}  # fmt: skip


def has_cyrillic(text: str) -> bool:
    return bool(_CYR_RUN.search(text or ""))


def is_uzbek_cyrillic(text: str) -> bool:
    """Cyrillic text in Uzbek (ў қ ғ ҳ, Uzbek words), not Russian."""
    if not has_cyrillic(text):
        return False
    if sum(ch in _UZ_ONLY for ch in text) >= 2:
        return True
    words = re.findall(r"[Ѐ-ӿ]+", text.lower())
    uz = sum(w in _UZ_WORDS for w in words)
    ru = sum(w in _RU_WORDS for w in words)
    return uz > ru


def cyr_to_latin(text: str) -> str:
    """Uzbek Cyrillic -> Uzbek Latin. Latin letters, digits and punctuation stay as they are."""
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        low = ch.lower()
        if low not in _MAP and low not in ("е", "ц"):
            out.append(ch)
            continue
        prev = text[i - 1] if i else ""
        start = not prev.isalpha()
        if low == "е":  # "ye" at the start of a word and after a vowel or ъ/ь
            lat = "ye" if start or prev in _VOWELS or prev.lower() in ("ъ", "ь") else "e"
        elif low == "ц":  # "s" at the start and after a consonant, "ts" after a vowel
            lat = "ts" if prev in _VOWELS else "s"
        else:
            lat = _MAP[low]
        if ch != low and lat:  # an upper-case letter: "Ш" -> "Sh", or "SH" inside a CAPS word
            nxt = text[i + 1] if i + 1 < n else ""
            caps = (nxt.isalpha() and nxt.isupper()) or (prev.isalpha() and prev.isupper())
            lat = lat.upper() if caps else lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def to_latin_if_uzbek(text: str) -> str:
    """Uzbek written in Cyrillic becomes Latin; Russian and Latin text are left alone."""
    return cyr_to_latin(text) if is_uzbek_cyrillic(text) else text
