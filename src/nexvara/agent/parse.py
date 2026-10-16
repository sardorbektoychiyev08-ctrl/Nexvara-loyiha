"""Turn an Uzbek command into a plan of Office actions, without AI.

"Hisobot.xlsx ni och, dublikatlarni o‘chir, Summa bo‘yicha kamayish tartibida sarala,
jami qo‘sh, diagramma qo‘sh va saqla"
-> Plan(app="excel", file="Hisobot.xlsx", actions=[dedupe, sort(summa, desc), total, chart, save])

Column names and filter values stay as the user wrote them; the executor resolves them
against the real table (so "Toshkentni" finds the value "Toshkent").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from nexvara.knowledge.textnorm import fold

EXCEL_EXT = (".xlsx", ".xlsm", ".xls", ".csv")
WORD_EXT = (".docx", ".doc", ".rtf")
PPT_EXT = (".pptx", ".ppt")
OFFICE_EXT = EXCEL_EXT + WORD_EXT + PPT_EXT

_FILE = re.compile(
    r"[«\"“]([^«»\"“”]+?\.(?:xlsx|xlsm|xls|csv|docx|doc|rtf|pptx|ppt))[»\"”]"
    r"|((?:[A-Za-z]:[\\/])?[\w\\/.\-‘’()]+?\.(?:xlsx|xlsm|xls|csv|docx|doc|rtf|pptx|ppt))\b",
    re.IGNORECASE,
)
_SPLIT = re.compile(
    # "," splits clauses, except a decimal comma ("1,5").
    r"\s*(?:;|,(?!\d)|(?<!\d),)\s*"
    r"|\s+(?:va|keyin|so[‘’']?ng|hamda|undan keyin|shundan so[‘’']?ng)\s+"
)
_QUOTED = re.compile(r"[«\"“']([^«»\"“”']+)[»\"”']")


@dataclass
class Action:
    kind: str
    args: dict = field(default_factory=dict)
    text: str = ""


@dataclass
class Plan:
    app: str | None  # excel | word | powerpoint | None
    file: str | None
    actions: list[Action]
    unknown: list[str] = field(default_factory=list)

    def describe(self) -> list[str]:
        return [DESCRIBE.get(a.kind, a.kind) + _args_text(a) for a in self.actions]


DESCRIBE = {
    "open": "Faylni ochish",
    "new": "Yangi fayl yaratish",
    "sort": "Saralash",
    "filter": "Filtr",
    "clear_filter": "Filtrni olib tashlash",
    "dedupe": "Dublikatlarni o‘chirish",
    "clean": "Ma’lumotni tozalash",
    "format": "Jadvalni formatlash",
    "total": "Jami qatorini qo‘shish",
    "chart": "Diagramma qo‘shish",
    "pivot": "Yig‘ma jadval (Pivot)",
    "freeze": "Sarlavhani qotirish",
    "pdf": "PDF qilib saqlash",
    "csv": "CSV qilib saqlash",
    "save": "Saqlash",
    "replace": "Matnni almashtirish",
    "font": "Shriftni o‘zgartirish",
    "spacing": "Qator oralig‘i",
    "indent": "Xatboshi",
    "page_setup": "Sahifa sozlamalari (A4, chetlar)",
    "page_numbers": "Sahifa raqamlari",
    "toc": "Mundarija",
    "spelling": "Imloni tekshirish",
    "presentation": "Mavzu bo‘yicha taqdimot",
}


def _args_text(a: Action) -> str:
    shown = {k: v for k, v in a.args.items() if v not in (None, "", [], False)}
    return f" ({', '.join(f'{k}: {v}' for k, v in shown.items())})" if shown else ""


# ---------- helpers ----------


def find_file(text: str) -> str | None:
    m = _FILE.search(text)
    if not m:
        return None
    return (m.group(1) or m.group(2)).strip()


_LEADING_CONNECTOR = re.compile(
    r"^(?:va|keyin|so[‘’']?ng|hamda|undan keyin|shundan so[‘’']?ng|yana|ham)\s+", re.IGNORECASE
)


def split_clauses(text: str) -> list[str]:
    out = []
    for c in _SPLIT.split(text):
        c = (c or "").strip()
        while c and _LEADING_CONNECTOR.match(c):  # ", keyin ..." leaves "keyin" in front
            c = _LEADING_CONNECTOR.sub("", c, count=1).strip()
        if c:
            out.append(c)
    return out


def _has(f: str, *stems: str) -> bool:
    return any(re.search(rf"\b{s}", f) for s in stems)


_COMMON = "<common>"  # marker: strip the filler words below
# Filler matched as WHOLE words only: "da" must not eat "daromad", "bu" not "Buxoro".
_COMMON_WORDS = (
    r"ni|ning|ga|da|dan|bo[‘’']?yicha|boyicha|iltimos|menga|qilib|qil|ber|kerak|barcha|"
    r"hamma|shu|bu|ham|bilan|uchun|ichida|ichidagi|qismi|bo[‘’']?lsin|bolsin|eng|o[‘’']?sha|"
    r"osha|ushbu|mana"
)
# Filler stems that take suffixes ("ustunida", "qatorlarni", "faylida", "tartibida").
_COMMON_STEMS = r"ustun|qator|jadval|fayl|tartib"


def _strip_words(f: str, *patterns: str) -> str:
    """Remove command keywords (prefix match, they carry suffixes) and filler words."""
    f = _FILE.sub(" ", f)
    for p in patterns:
        if p is _COMMON:
            f = re.sub(rf"\b(?:{_COMMON_STEMS})\w*", " ", f)
            f = re.sub(rf"\b(?:{_COMMON_WORDS})\b", " ", f)
        else:
            f = re.sub(rf"\b(?:{p})\w*", " ", f)
    f = re.sub(r"[^\w\s<>=.,-]", " ", f)
    return re.sub(r"\s+", " ", f).strip()


def _column_ref(text: str) -> str | None:
    """Column letter ("B ustun") or None."""
    m = re.search(r"\b([A-Z]{1,2})\s*(?:-?\s*ustun)", text)
    return m.group(1) if m else None


# ---------- clause parsers ----------


def _sort(clause: str, f: str) -> Action:
    desc = _has(f, "kamay", "teskari", "kattadan", "yuqoridan", "z dan a", "desc")
    words = _strip_words(
        f,
        r"sarala|saralash|tartibla|tartiblash|kamay|o[‘’']?sish|o[‘’']?suvchi|teskari|kattadan|kichikdan|"
        r"yuqoridan|pastdan|alifbo|asc|desc",
        _COMMON,
    )
    return Action(
        "sort", {"column": _column_ref(clause) or words or None, "descending": desc}, clause
    )


_CMP = [
    (r"(\d+(?:[.,]\d+)?)\s*dan\s*(?:katta|ko[‘’']?p|ortiq|yuqori)", ">"),
    (r"(\d+(?:[.,]\d+)?)\s*dan\s*(?:kichik|kam|past)", "<"),
    (r"(>=|<=|>|<|=)\s*(\d+(?:[.,]\d+)?)", None),
]


def _filter(clause: str, f: str) -> Action:
    if _has(f, "olib tashla", "bekor", "tozala", "ochir", "o‘chir", "o'chir", "olib"):
        return Action("clear_filter", {}, clause)
    criteria = None
    for pat, op in _CMP:
        m = re.search(pat, f)
        if m:
            if op is None:
                criteria = f"{m.group(1)}{m.group(2).replace(',', '.')}"
            else:
                criteria = f"{op}{m.group(1).replace(',', '.')}"
            f = f[: m.start()] + " " + f[m.end() :]
            break
    quoted = _QUOTED.search(clause)
    words = _strip_words(
        f,
        r"filtrla|filtr|faqat|ko[‘’']?rsat|korsat|qoldir|katta\b|kichik\b|ortiq|kam\b|kamroq",
        _COMMON,
    )
    return Action(
        "filter",
        {
            "column": _column_ref(clause),
            "words": words,  # column name and/or value; resolved against the table
            "value": quoted.group(1) if quoted else None,
            "criteria": criteria,
        },
        clause,
    )


_CHART_KINDS = [
    (("ustunli", "ustun diagramma", "gistogramma", "column"), "column"),
    (("chiziqli", "grafik", "line"), "line"),
    (("doira", "aylana", "pirog", "pie"), "pie"),
    (("halqa", "donut", "doughnut"), "doughnut"),
    (("gorizontal", "bar"), "bar"),
]


def _chart(clause: str, f: str) -> Action:
    kind = next((k for keys, k in _CHART_KINDS if any(key in f for key in keys)), "column")
    words = _strip_words(
        f,
        r"diagramma|grafik|chizma|qo[‘’']?sh|qosh|yasa|chiz|ustunli|chiziqli|doira|aylana|"
        r"halqa|gorizontal|pirog|gistogramma",
        _COMMON,
    )
    return Action("chart", {"kind": kind, "words": words}, clause)


def _pivot(clause: str, f: str) -> Action:
    words = _strip_words(
        f, r"pivot|svodn|yig[‘’']?ma|yigma|jadval|yasa|qo[‘’']?sh|qosh|tuz|yarat", _COMMON
    )
    return Action("pivot", {"words": words}, clause)


def _replace(clause: str, f: str) -> Action | None:
    quotes = _QUOTED.findall(clause)
    if len(quotes) >= 2:
        return Action("replace", {"find": quotes[0], "replace": quotes[1]}, clause)
    m = re.search(r"(\S+)\s+(?:so[‘’']?zini|ni)\s+(\S+)\s+(?:ga|bilan)\s+almashtir", clause, re.I)
    if m:
        return Action("replace", {"find": m.group(1), "replace": m.group(2)}, clause)
    return None


_FONTS = ["Times New Roman", "Arial", "Calibri", "Cambria", "Segoe UI", "Tahoma", "Verdana"]


def _font(clause: str, f: str) -> Action:
    name = next((fn for fn in _FONTS if fold(fn) in f), None)
    size = re.search(r"\b(\d{1,2}(?:[.,]5)?)\s*(?:pt|o[‘’']?lcham|razmer|shrift|kegl)?", f)
    return Action(
        "font", {"name": name, "size": float(size.group(1).replace(",", ".")) if size else None},
        clause,
    )  # fmt: skip


def _spacing(clause: str, f: str) -> Action:
    m = re.search(r"(\d(?:[.,]\d+)?)", f)
    return Action("spacing", {"value": float(m.group(1).replace(",", ".")) if m else 1.5}, clause)


def _indent(clause: str, f: str) -> Action:
    m = re.search(r"(\d(?:[.,]\d+)?)\s*(?:sm|cm)?", f)
    return Action("indent", {"cm": float(m.group(1).replace(",", ".")) if m else 1.25}, clause)


def _classify(clause: str, app: str | None) -> Action | None:
    f = fold(clause)
    if (_has(f, "och", "yukla") and find_file(clause)) or re.fullmatch(
        r"\s*(shu )?(faylni )?och\w*\s*", f
    ):
        return Action("open", {}, clause)
    if _has(f, "almashtir"):
        return _replace(clause, f)
    if _has(f, "dublikat", "takror", "duplikat"):
        words = _strip_words(f, r"dublikat|takror|duplikat|ochir|o[‘’']?chir|olib|tashla", _COMMON)
        return Action("dedupe", {"words": words}, clause)
    if _has(f, "filtr"):
        return _filter(clause, f)
    if _has(f, "sarala", "tartibla", "saralash"):
        return _sort(clause, f)
    if _has(f, "pivot", "svodn", "yigma jadval", "yig‘ma jadval", "yig'ma jadval"):
        return _pivot(clause, f)
    if _has(f, "diagramma", "grafik", "chizma"):
        return _chart(clause, f)
    if _has(f, "jami", "yigindi", "yig‘indi", "itog"):
        return Action("total", {}, clause)
    if _has(f, "pdf"):
        return Action("pdf", {}, clause)
    if _has(f, "csv"):
        return Action("csv", {}, clause)
    if _has(f, "qotir", "muzlat", "zakrep"):
        return Action("freeze", {}, clause)
    if _has(f, "tozala", "bo‘sh qator", "bosh qator", "probel"):
        return Action("clean", {}, clause)
    if _has(f, "shrift", "font"):
        return _font(clause, f)
    if _has(f, "qator oralig", "interval", "oraliq"):
        return _spacing(clause, f)
    if _has(f, "xatboshi", "abzats", "otstup"):
        return _indent(clause, f)
    # "raqamlab chiq" numbers pages; "raqamlarini markazga" is about the numbers in a table.
    if _has(f, "sahifa raqam", "bet raqam", r"raqamla(?!r)"):
        return Action("page_numbers", {}, clause)
    if _has(f, "mundarija", "oglavlen"):
        return Action("toc", {}, clause)
    if _has(f, "imlo", "orfografiya", "xatolarni tekshir"):
        return Action("spelling", {}, clause)
    if _has(f, "a4", "chet", "hoshiya", "sahifa sozla", "standart"):
        return Action("page_setup", {}, clause)
    if _has(f, "formatla", "chiroyli", "bezat", "formati", "markazga", "professional"):
        return Action("format", {}, clause)
    if _has(f, "saqla", "saxrani", "save"):
        return Action("save", {"overwrite": _has(f, "ustiga", "o‘ziga", "ozi", "asl")}, clause)
    return None


def parse_command(text: str, context_file: str | None = None) -> Plan | None:
    """A plan when the text is an Office command; None for ordinary chat."""
    f = fold(text)
    file = find_file(text)
    if file is None and re.search(r"\b(shu|ushbu|oxirgi|o[‘’']?sha|osha) fayl", f):
        file = context_file
    ext = ("." + file.rsplit(".", 1)[-1].lower()) if file and "." in file else ""
    if ext in EXCEL_EXT or _has(f, "excel", "eksel", "jadvalni"):
        app = "excel"
    elif ext in WORD_EXT or _has(f, "word", "hujjat"):
        app = "word"
    elif ext in PPT_EXT or _has(f, "powerpoint", "taqdimot", "prezentats", "slayd"):
        app = "powerpoint"
    else:
        app = None

    actions: list[Action] = []
    unknown: list[str] = []
    for clause in split_clauses(text):
        a = _classify(clause, app)
        if a is None:
            unknown.append(clause)
        elif not (actions and a.kind == actions[-1].kind == "open"):
            actions.append(a)
    if not any(a.kind != "open" for a in actions) and file is None:
        return None  # nothing Office-like was asked
    if file is None and context_file and app is None:
        file = context_file
    if app is None and file:
        app = _app_for(file)
    return Plan(app, file, actions, unknown)


def _app_for(file: str) -> str | None:
    ext = "." + file.rsplit(".", 1)[-1].lower()
    if ext in EXCEL_EXT:
        return "excel"
    if ext in WORD_EXT:
        return "word"
    if ext in PPT_EXT:
        return "powerpoint"
    return None
