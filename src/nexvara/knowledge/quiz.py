"""Rule-based (no AI) test questions from textbook text.

Sources of questions, all taken from the textbook:
- definitions: "Massa — bu ...", "... kuch deb ataladi", "Kuch deb ... aytiladi",
  glossary lines "Kontributsiya – ...";
- facts with a year ("1873-yil ...") or a plain number in a non-formula sentence.
Distractors for "which term?" questions come from definitions elsewhere in the same
book (`term_pool`), so every option is a real concept of that subject. Quality is
"a solid draft a teacher can edit"; AI mode (M7) will write richer questions.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from nexvara.knowledge.textnorm import fold, letter_ratio, sentences

LETTERS = "ABCD"

_UP = "A-ZА-ЯЎҚҒҲ"
_W = r"[A-Za-zА-Яа-яЎўҚқҒғҲҳ‘’'-]"
_TERM = rf"{_W}+(?:\s{_W}+){{0,3}}"
# "Massa — bu jismning ..." (an em/en dash, or a spaced hyphen)
_DEF_DASH = re.compile(rf"^(?P<term>[{_UP}]{_TERM})\s+(?:—|–|-)\s+(?:bu\s+)?(?P<defn>.{{20,240}})$")
# "Jismning tezligini o‘zgartiruvchi sabab kuch deb ataladi."
_DEF_ATALADI = re.compile(
    rf"^(?P<defn>.{{20,240}})\s+(?P<term>{_W}+)\s+deb\s+"
    r"(?:ataladi|aytiladi|yuritiladi|nomlanadi)\.?$"
)
# "Kuch deb jismlarning o‘zaro ta’sir o‘lchoviga aytiladi."
_DEF_DEB = re.compile(
    rf"^(?P<term>[{_UP}]{_W}*(?:\s{_W}+){{0,2}})\s+deb\s+(?P<defn>.{{20,240}}?)\s+"
    r"(?:aytiladi|ataladi)\.?$"
)
_YEAR = re.compile(r"(?<!\d)(1[0-9]{3}|20[0-4][0-9])(?=\s*-?\s*yil)")
_NUMBER = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)(?=\s+[a-zA-Z‘’]{2,})")
_FORMULA = re.compile(r"[=→≈≠/²³√∑∆Δ]|\b[a-zA-Z]\d\b|\d\s*[a-zA-Z]\s*=")
_SUFFIX_START = {
    "ning", "ga", "da", "ni", "dan", "bilan", "uchun", "esa", "va", "ham", "u", "bu", "lar",
}  # fmt: skip
_WEAK_TERMS = {
    "endi", "lekin", "ammo", "shuning", "demak", "masalan", "bunda", "keyin", "chunki", "uning",
    "shu", "bu", "u", "ular", "biz", "siz", "men", "sen", "ushbu", "mazkur", "har", "bir", "eng",
}  # fmt: skip
_SURNAME = re.compile(r"(?:ov|ova|ev|eva|yev|yeva)$")
# Endings that mark a word as part of the sentence rather than of a two-word term.
_NOT_TERM_WORD = (
    "ni", "ga", "da", "dan", "ning", "gan", "adi", "ib", "lar", "lari", "ka", "ta", "si",
    "dir", "lik", "kalikka",
)  # fmt: skip


def _extend_term(defn: str, term: str) -> tuple[str, str]:
    """'... sanoq jismi deb ataladi' -> term 'sanoq jismi' when the word before looks like a
    modifier ('sanoq'), else keep the single word."""
    head, _, prev = defn.rpartition(" ")
    p = fold(prev)
    if head and prev.islower() and len(p) >= 3 and not p.endswith(_NOT_TERM_WORD):
        return head, f"{prev} {term}"
    return defn, term


@dataclass
class Question:
    kind: str  # mcq | fill | tf | match
    text: str
    answer: str  # letter for mcq, word for fill, "To‘g‘ri"/"Noto‘g‘ri" for tf, "1-B, ..." for match
    options: list[str] = field(default_factory=list)
    pairs: list[tuple[str, str]] = field(default_factory=list)  # match: (term, definition)
    source: str = ""  # "93-bet"


@dataclass
class Definition:
    term: str
    defn: str
    sentence: str
    page: int


@dataclass
class Fact:
    sentence: str
    answer: str
    kind: str  # year | number
    page: int


def _clean_term(term: str) -> str | None:
    t = term.strip(" ,;:.-—–")
    words = t.split()
    if not 1 <= len(words) <= 4 or len(t) < 3 or letter_ratio(t.replace(" ", "")) < 0.9:
        return None
    letters = [c for c in t if c.isalpha()]
    if sum(c.isupper() for c in letters) / len(letters) > 0.5 and len(letters) > 3:
        return None  # headings like "XIX ASR OXIRI"
    if any(fold(w) in _WEAK_TERMS for w in words) or fold(words[-1]).endswith(("ning", "dagi")):
        return None
    if len(words) == 1 and _SURNAME.search(fold(t)) and t[0].isupper():
        return None  # author lists: "Rajabov – ..."
    return t[0].upper() + t[1:]


def _clean_defn(defn: str) -> str | None:
    d = defn.strip(" .;:")
    words = d.split()
    if len(words) < 4 or fold(words[0]) in _SUFFIX_START or _FORMULA.search(d):
        return None
    if letter_ratio(d) < 0.7:
        return None
    return d[0].upper() + d[1:]


def _good_sentence(s: str, min_words: int = 6, max_words: int = 40) -> bool:
    n = len(s.split())
    return min_words <= n <= max_words and letter_ratio(s) > 0.65 and not s.endswith("?")


def extract_definitions(pages: list[tuple[int, str]]) -> list[Definition]:
    out: list[Definition] = []
    seen: set[str] = set()
    for page, text in pages:
        for s in sentences(text):
            if not _good_sentence(s, 4, 45):
                continue
            for pat in (_DEF_DASH, _DEF_DEB, _DEF_ATALADI):
                m = pat.match(s)
                if not m:
                    continue
                raw_defn, raw_term = m.group("defn"), m.group("term")
                if pat is _DEF_ATALADI:
                    raw_defn, raw_term = _extend_term(raw_defn, raw_term)
                term, defn = _clean_term(raw_term), _clean_defn(raw_defn)
                if term and defn and fold(term) not in seen and fold(term) not in fold(defn):
                    seen.add(fold(term))
                    out.append(Definition(term, defn, s, page))
                break
    return out


def extract_facts(pages: list[tuple[int, str]]) -> list[Fact]:
    out: list[Fact] = []
    seen: set[str] = set()
    for page, text in pages:
        for s in sentences(text):
            if not _good_sentence(s, 7, 35) or fold(s) in seen or _FORMULA.search(s):
                continue
            m = _YEAR.search(s)
            if m:
                out.append(Fact(s, m.group(1), "year", page))
                seen.add(fold(s))
                continue
            numbers = re.findall(r"\d+", s)
            m = _NUMBER.search(s)
            if m and len(numbers) == 1 and not s.startswith(m.group(1)):
                out.append(Fact(s, m.group(1), "number", page))
                seen.add(fold(s))
    return out


def _blank(sentence: str, answer: str) -> str | None:
    i = sentence.find(answer)
    if i < 0:
        return None
    out = sentence[:i] + "________" + sentence[i + len(answer) :]
    return out if answer not in out else None


def _number_distractors(answer: str, kind: str, pool: list[str], rng: random.Random) -> list[str]:
    try:
        base = float(answer.replace(",", "."))
    except ValueError:
        return []
    # Same-kind values from the topic first, but only plausible ones (years within 150).
    others = [p for p in dict.fromkeys(pool) if p != answer]
    if kind == "year":
        others = [p for p in others if abs(int(p) - base) <= 150]
    rng.shuffle(others)
    picks = others[:3]
    deltas = [1, 2, 5, 10, -1, -3, -5, -10] if kind == "year" else [2, 0.5, 3, 1.5, 10]
    for d in deltas:
        if len(picks) == 3:
            break
        cand = base + d if kind == "year" else base * d
        txt = str(int(cand)) if float(cand).is_integer() else f"{cand:g}".replace(".", ",")
        if txt != answer and txt not in picks and cand > 0:
            picks.append(txt)
    return picks


def _mcq(stem: str, answer: str, distractors: list[str], rng: random.Random, source: str):
    options = list(dict.fromkeys([answer, *distractors]))
    if len(options) < 4:
        return None
    options = options[:4]
    rng.shuffle(options)
    return Question("mcq", stem, LETTERS[options.index(answer)], options, source=source)


@dataclass
class QuizResult:
    questions: list[Question]
    requested: int
    note: str = ""


def build_quiz(
    pages: list[tuple[int, str]],
    count: int = 20,
    seed: int = 1,
    kinds: tuple[str, ...] = ("mcq", "fill", "tf", "match"),
    term_pool: list[str] | None = None,
) -> QuizResult:
    """Up to `count` questions (a matching block counts as one). Deterministic for a seed.

    `term_pool`: definition terms from the whole book, used as distractors.
    """
    rng = random.Random(seed)
    defs = extract_definitions(pages)
    facts = extract_facts(pages)
    pool = list(dict.fromkeys([d.term for d in defs] + list(term_pool or [])))
    rng.shuffle(defs)
    rng.shuffle(facts)

    def src(page: int) -> str:
        return f"{page}-bet"

    by_kind: dict[str, list[Question]] = {"mcq": [], "fill": [], "tf": []}
    used: set[str] = set()

    # 1) definition -> which term?
    for d in defs:
        others = [t for t in pool if fold(t) != fold(d.term)]
        rng.shuffle(others)
        q = None
        if "mcq" in kinds:
            stem = f"Quyidagi ta’rif qaysi tushunchaga tegishli?\n«{d.defn}»"
            q = _mcq(stem, d.term, others[:3], rng, src(d.page))
        if q:
            by_kind["mcq"].append(q)
            used.add(d.sentence)

    # 2) year / number facts
    years = [f.answer for f in facts if f.kind == "year"]
    numbers = [f.answer for f in facts if f.kind == "number"]
    for f in facts:
        stem = _blank(f.sentence, f.answer)
        if not stem:
            continue
        q = None
        if "mcq" in kinds:
            distractors = _number_distractors(
                f.answer, f.kind, years if f.kind == "year" else numbers, rng
            )
            q = _mcq(f"Bo‘sh joyga mos javobni tanlang:\n{stem}", f.answer, distractors,
                     rng, src(f.page))  # fmt: skip
        if q is None and "fill" in kinds:
            q = Question("fill", f"Bo‘sh joyni to‘ldiring:\n{stem}", f.answer, source=src(f.page))
        if q:
            by_kind[q.kind].append(q)

    # 3) fill-in on definition sentences not already used for a "which term?" question
    if "fill" in kinds:
        for d in defs:
            if d.sentence in used:
                continue
            for ans in (d.term, d.term.lower()):
                stem = _blank(d.sentence, ans)
                if stem:
                    by_kind["fill"].append(
                        Question(
                            "fill", f"Bo‘sh joyni to‘ldiring:\n{stem}", ans, source=src(d.page)
                        )
                    )
                    break

    # 4) true / false from definitions: alternate true and term-swapped statements
    if "tf" in kinds and len(defs) >= 2:
        for i, d in enumerate(defs):
            body = f"{d.defn[0].lower()}{d.defn[1:]}."
            if i % 2 == 0:
                stmt, ans = f"{d.term} — {body}", "To‘g‘ri"
            else:
                stmt, ans = f"{defs[(i + 1) % len(defs)].term} — {body}", "Noto‘g‘ri"
            by_kind["tf"].append(
                Question("tf", f"To‘g‘ri yoki noto‘g‘ri?\n{stmt}", ans, source=src(d.page))
            )

    # 5) one matching block of 4 definitions
    match_q = None
    if "match" in kinds and len(defs) >= 4:
        chosen = rng.sample(defs, 4)
        shuffled = chosen[:]
        rng.shuffle(shuffled)
        key = ", ".join(f"{i + 1}-{LETTERS[shuffled.index(d)]}" for i, d in enumerate(chosen))
        match_q = Question(
            "match",
            "Tushunchalarni ularning ta’riflari bilan moslang:",
            key,
            pairs=[(d.term, s.defn) for d, s in zip(chosen, shuffled, strict=True)],
            source=", ".join(sorted({src(d.page) for d in chosen})),
        )

    # Mix: mostly multiple choice, then fill-in, then true/false; top up from what is left.
    target = count - (1 if match_q else 0)
    quota = {"mcq": round(target * 0.6), "fill": round(target * 0.2), "tf": target}
    picked: list[Question] = []
    for kind in ("mcq", "fill", "tf"):
        room = max(min(quota[kind], target - len(picked)), 0)
        picked += by_kind[kind][:room]
    rest = [q for k in ("mcq", "fill", "tf") for q in by_kind[k] if q not in picked]
    picked += rest[: max(target - len(picked), 0)]
    rng.shuffle(picked)
    if match_q:
        picked.append(match_q)

    note = ""
    if len(picked) < count:
        note = (
            f"Matndan faqat {len(picked)} ta savol chiqdi ({count} ta so‘ralgan). "
            "Mavzuni kengaytiring yoki AI rejimini ulang."
        )
    return QuizResult(picked, count, note)
