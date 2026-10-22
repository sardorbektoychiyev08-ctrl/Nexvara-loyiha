"""Typing mistakes fixed before a message is understood: «exselni och», «vordga yoz»,
«menga6-sinif informatkadan 20 talik test» -> «Excelni och», «Wordga yoz», «menga 6-sinf
informatikadan 20 ta test». File paths and quoted text are never changed.

Only common, unambiguous slips are fixed here; the AI (when it is on) also reads the meaning
of a badly written message by itself (see HUMAN_STYLE and the planner prompt).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# (pattern, replacement): spelling variants of Office names and school words
_RULES = [
    # «menga6-sinf»: a word glued to the grade number
    (re.compile(r"(?<=[^\W\d_])(?=\d{1,2}\s*-?\s*sini?f)", re.I), " "),
    (re.compile(r"\bsinif", re.I), "sinf"),
    (re.compile(r"\b(?:e[kx]s+e?l+|exe?l+|ekce?l+|excell?)(?!l?en)", re.I), "Excel"),
    (re.compile(r"\bvord", re.I), "Word"),
    (re.compile(r"\bp(?:a?u|o)(?:[vw]e?|e)r\s*-?\s*p(?:o|oy|oi)nt", re.I), "PowerPoint"),
    (re.compile(r"\b(\d{1,3})\s*tal(?:ik|i)\b", re.I), r"\1 ta"),
]

# Long words that are often mistyped; a near miss keeps its suffix («informatkadan»).
_VOCAB = (
    "informatika", "matematika", "biologiya", "geografiya", "geometriya", "adabiyot",
    "taqdimot", "prezentatsiya", "diagramma", "hisobot", "dashboard", "darslik", "saralash",
    "variant", "algebra", "kimyo", "fizika",
)  # fmt: skip

# Kept as they are: file paths, «quoted» and "quoted" text.
_PROTECT = re.compile(
    r"«[^»]*»|\"[^\"]*\"|“[^”]*”|[A-Za-z]:[\\/][^\s,;]*|\S+\.(?:xlsx?|xlsm|csv|docx?|pptx?|pdf)\b",
    re.I,
)
_WORD = re.compile(r"[^\W\d_]{5,}")


def _near(word: str) -> str:
    w = word.lower()
    for v in _VOCAB:
        if w.startswith(v):
            return word
    best, out = 0.0, word
    for v in _VOCAB:
        if w[0] != v[0] or len(w) < len(v) - 2:
            continue
        for k in range(len(v) - 2, min(len(v) + 2, len(w)) + 1):
            r = SequenceMatcher(None, w[:k], v).ratio()
            if r > best:
                best, out = r, v + w[k:]
    return out if best >= 0.88 else word


def _fix_part(part: str) -> str:
    for pat, rep in _RULES:
        part = pat.sub(rep, part)
    return _WORD.sub(lambda m: _near(m.group()), part)


def fix(text: str) -> str:
    out, pos = [], 0
    for m in _PROTECT.finditer(text):
        out.append(_fix_part(text[pos : m.start()]))
        out.append(m.group())
        pos = m.end()
    out.append(_fix_part(text[pos:]))
    return "".join(out)
