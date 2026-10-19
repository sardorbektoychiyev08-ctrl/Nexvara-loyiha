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
        names = {**DESCRIBE, **({"format": "Hujjatni rasmiy formatlash"} if self.app == "word"
                                else {"format": "Slaydlarni formatlash"} if self.app == "powerpoint"
                                else {})}  # fmt: skip
        return [names.get(a.kind, a.kind) + _args_text(a) for a in self.actions]


DESCRIBE = {
    "open": "Faylni ochish",
    "new": "Yangi fayl yaratish",
    "create_table": "Yangi Excel jadvali yaratish",
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
    "highlight": "Shartli formatlash (rang bilan belgilash)",
    "numfmt": "Raqam formati",
    "autofit": "Ustun kengligini moslashtirish",
    "stats": "Statistika qatorlari",
    "formula": "Hisoblangan ustun (formula)",
    "rename_sheet": "Varaq nomini o‘zgartirish",
    "delete_column": "Ustunni o‘chirish",
    "print_setup": "Chop etishga tayyorlash",
    "align": "Matnni tekislash",
    "header": "Kolontitul",
    "orientation": "Sahifa yo‘nalishi",
    "margins": "Sahifa chetlari",
    "count": "Hujjat statistikasi",
    "title": "Sarlavha uslubi",
    "tables": "Jadvallarni formatlash",
    "transition": "Slayd o‘tish effekti",
    "slide_numbers": "Slayd raqamlari",
    "check": "Sifatni tekshirish",
    "fix": "Kamchiliklarni tuzatish",
    "validate": "Kiritishni cheklash (Data Validation)",
}


def _args_text(a: Action) -> str:
    shown = {k: v for k, v in a.args.items() if v not in (None, "", [], False)}
    return f" ({', '.join(f'{k}: {v}' for k, v in shown.items())})" if shown else ""


# ---------- helpers ----------


def _validation(clause: str, f: str) -> Action | None:
    """«Baho ustuniga faqat 2 dan 5 gacha butun son», «Holat ustuniga tanlash ro‘yxati:
    Bajarildi, Jarayonda», «Narx ustuniga faqat musbat son», «Sana ustuniga faqat sana»."""
    noise = (r"faqat|kiritil\w*|kirit\w*|bolsin|ruxsat|cheklov\w*|cheklash|validatsiya|"
             r"validation|tanlash|royxat\w*|ochiluvchi|ustun\w*|dan|gacha|butun|son\w*|"
             r"raqam\w*|musbat|sana\w*|oraliq\w*")  # fmt: skip
    words = re.sub(r"\d+", " ", _strip_words(f, noise, _COMMON)).split()
    words = " ".join(words)
    col = _column_ref(clause)
    lst = re.search(r"(?:ro[‘’']?yxat\w*|tanlash)[^:]*:\s*(.+)$", clause, re.I)
    if lst:
        items = [
            x.strip(' .«»"') for x in re.split(r"[,;]|\s+va\s+", lst.group(1)) if x.strip(" .")
        ]
        if len(items) >= 2:
            pre = clause[: lst.start()]
            head = _strip_words(fold(pre), r"tanlash|royxat\w*|ochiluvchi|ustun\w*|ga|uchun",
                                _COMMON)  # fmt: skip
            return Action("validate", {"kind": "list", "items": items[:50], "column": col,
                                       "words": head}, clause)  # fmt: skip
    nums = [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", clause)]
    whole = _has(f, "butun")
    if _has(f, "sana") and not nums:  # «Sana ustuniga faqat sana»: the column may be «Sana»
        return Action("validate", {"kind": "date", "column": col, "words": words or "sana"},
                      clause)  # fmt: skip
    if _has(f, "musbat") and not nums:
        return Action("validate", {"kind": "whole" if whole else "decimal", "min": 0,
                                   "max": None, "column": col, "words": words}, clause)  # fmt: skip
    if len(nums) >= 2 and _has(f, "gacha", "oraliq", "orasida"):
        lo, hi = sorted(nums[-2:])
        return Action("validate", {"kind": "whole" if whole else "decimal", "min": lo, "max": hi,
                                   "column": col, "words": words}, clause)  # fmt: skip
    return None


def find_file(text: str) -> str | None:
    m = _FILE.search(text)
    if not m:
        return None
    return (m.group(1) or m.group(2)).strip()


_LEADING_CONNECTOR = re.compile(
    r"^(?:va|keyin|so[‘’']?ng|hamda|undan keyin|shundan so[‘’']?ng|yana|ham)\s+", re.IGNORECASE
)


_STAT_PAIR = re.compile(
    r"\b(eng (?:katta|kichik)|o[‘’']?rtacha|maksimum|minimum|soni)\s+va\s+"
    r"(?=eng |o[‘’']?rtacha|maksimum|minimum|soni)",
    re.IGNORECASE,
)


# «Holat ustuniga tanlash ro‘yxati: Bajarildi, Jarayonda, Bekor» — those commas are the list's
_LIST_TAIL = re.compile(r"((?:ro[‘’']?yxat\w*|tanlash)[^:,]{0,40}:)(.*?)"
                        r"(?=,\s*(?:keyin|so[‘’']?ng)\b|[.;]|$)", re.IGNORECASE)  # fmt: skip


def split_clauses(text: str) -> list[str]:
    text = _STAT_PAIR.sub(r"\1 & ", text)  # "eng katta va eng kichik" is one request
    text = _LIST_TAIL.sub(lambda m: m.group(1) + m.group(2).replace(",", "\x1f"), text)
    out = []
    for c in _SPLIT.split(text):
        c = (c or "").replace("\x1f", ",").strip()
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
    desc = _has(f, "kamay", "teskari", "kattadan", "yuqoridan", "z dan a", "desc") or bool(
        # «eng katta summadan boshlab» / «eng ko‘pidan» (live check 2026-10-19: sorted ascending)
        re.search(r"\beng (katta|ko[‘’']?p|yuqori)\w*\b.*\bboshla", f)
    )
    words = _strip_words(
        f,
        r"sarala|saralash|tartibla|tartiblash|sartirovka|sortirovka|sortla|kamay|o[‘’']?sish|o[‘’']?suvchi|teskari|kattadan|kichikdan|"
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


def _criteria(f: str) -> tuple[str | None, str]:
    """(">500000", text without it) for "500000 dan katta" / "> 500000"; (None, f) if absent."""
    for pat, op in _CMP:
        m = re.search(pat, f)
        if m:
            if op is None:
                crit = f"{m.group(1)}{m.group(2).replace(',', '.')}"
            else:
                crit = f"{op}{m.group(1).replace(',', '.')}"
            return crit, f[: m.start()] + " " + f[m.end() :]
    return None, f


def _filter(clause: str, f: str) -> Action:
    if _has(f, "olib tashla", "bekor", "tozala", "ochir", "o‘chir", "o'chir", "olib"):
        return Action("clear_filter", {}, clause)
    criteria, f = _criteria(f)
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


_COLORS = {
    "qizil": "#FCA5A5", "sariq": "#FDE68A", "yashil": "#86EFAC", "kok": "#93C5FD",
    "havorang": "#BAE6FD", "pushti": "#F9A8D4", "toq sariq": "#FDBA74", "binafsha": "#C4B5FD",
}  # fmt: skip


def _highlight(clause: str, f: str) -> Action:
    if _has(f, "rang shkala", "shkala", "issiqlik xarita"):
        mode, n = "scale", None
    elif _has(f, "malumot chiziq", "data bar", "chiziqcha", "katak ichida gistogramma"):
        mode, n = "bars", None
    else:
        top = re.search(r"eng (katta|yuqori|kichik|past)\w*\s*(\d+)\s*ta", f) or re.search(
            r"(\d+)\s*ta\s*eng (katta|yuqori|kichik|past)", f
        )  # fmt: skip
        if top:
            word, num = (top.group(1), top.group(2)) if top.group(1).isalpha() else (
                top.group(2), top.group(1))  # fmt: skip
            mode, n = ("top" if word in ("katta", "yuqori") else "bottom"), int(num)
            f = f[: top.start()] + " " + f[top.end() :]
        else:
            mode, n = "cells", None
    criteria, f = _criteria(f)
    color = next((c for name, c in _COLORS.items() if name in f), None)
    words = _strip_words(
        f,
        r"belgila|boya|rangla|ajrat|korsat|rang|shkala|issiqlik|xarita|malumot|chiziq|data|bar|"
        r"katak|qiymat|kattalar|kichiklar|" + "|".join(_COLORS),
        _COMMON,
    )
    return Action("highlight", {"mode": mode, "criteria": criteria, "top": n, "color": color,
                                "words": words, "column": _column_ref(clause)}, clause)  # fmt: skip


def _numfmt(clause: str, f: str) -> Action:
    if _has(f, "foiz", "protsent"):
        kind = "percent"
    elif _has(f, "sana"):
        kind = "date"
    elif _has(f, "pul", "som", "valyuta", "sum\\b"):
        kind = "money"
    elif _has(f, "dollar", "usd"):
        kind = "usd"
    elif _has(f, "butun"):
        kind = "integer"
    else:
        kind = "decimal"
    dec = re.search(r"(\d)\s*(?:ta\s*)?(?:xona|raqam)", f)
    words = _strip_words(
        f,
        r"format|formatiga|formatida|qil|otkaz|aylantir|korinish|pul|som|sum\b|valyuta|foiz|"
        r"protsent|sana|kasr|butun|son|xona|raqam|verguldan|keyin|dollar|usd|\d",
        _COMMON,
    )
    return Action("numfmt", {"kind": kind, "decimals": int(dec.group(1)) if dec else None,
                             "words": words, "column": _column_ref(clause)}, clause)  # fmt: skip


_STAT_WORDS = [
    (("ortacha", "average"), "average"),
    (("eng katta", "maksimum", "maksimal", "max"), "max"),
    (("eng kichik", "minimum", "minimal", "min"), "min"),
    (("soni", "nechta", "count"), "count"),
    (("mediana",), "median"),
]


def _stats(clause: str, f: str) -> Action:
    funcs = [fn for keys, fn in _STAT_WORDS if any(re.search(rf"\b{k}\b", f) for k in keys)]
    return Action("stats", {"funcs": funcs or ["average"]}, clause)


_OPS_WORDS = [
    (r"\bminus\b|\bayir\w*", "-"), (r"\bplyus\b|\bqo[‘’']?shuv\b", "+"),
    (r"\bko[‘’']?paytir\w*|\bmarta\b", "*"), (r"\bbo[‘’']?lin\w*|\bbo[‘’']?lib\b", "/"),
]  # fmt: skip


def _formula(clause: str, f: str) -> Action | None:
    """ "Foyda = Daromad - Xarajat", "Foyda ustunini qo‘sh: Daromad minus Xarajat"."""
    text = re.sub(r"[«»\"“”]", "", clause)
    m = re.search(r"^(.*?)=(.+)$", text)
    if m:
        name, expr = m.group(1), m.group(2)
    else:
        m = re.search(r"^(.*?)\bustun\w*\s+(?:qo[‘’']?sh|qosh|yarat|hisobla)\w*\s*:(.+)$", text,
                      re.IGNORECASE)  # fmt: skip
        if not m:
            return None
        name, expr = m.group(1), m.group(2)
    name = re.sub(r"(?i)\b(?:yangi|ustun\w*|qo[‘’']?sh\w*|qosh\w*|hisobla\w*|yarat\w*)\b", " ",
                  name)  # fmt: skip
    name = re.sub(r"\s+", " ", name).strip(" :,-")
    expr = re.sub(r"(?i)\b(?:ustun\w*|bo[‘’']?lsin|bolsin|qo[‘’']?sh\w*|qosh\w*|hisobla\w*)\b",
                  " ", expr)  # fmt: skip
    for pat, op in _OPS_WORDS:
        expr = re.sub(pat, f" {op} ", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\s+", " ", expr).strip(" .,")
    if not name or not expr or not re.search(r"[-+*/]", expr):
        return None
    return Action("formula", {"name": name, "expr": expr}, clause)


def _margins(clause: str, f: str) -> Action | None:
    sides = {"top": r"yuqori|tepa", "right": r"ong", "bottom": r"past|quyi", "left": r"chap"}
    out: dict[str, float] = {}
    for side, pat in sides.items():
        m = re.search(rf"\b(?:{pat})\w*\s*(?:chet\w*\s*)?(\d+(?:[.,]\d+)?)", f)
        if m:
            out[side] = float(m.group(1).replace(",", "."))
    if not out:
        m = re.search(r"chet\w*\s*(?:hammasi\s*)?(\d+(?:[.,]\d+)?)\s*(?:sm|cm)", f)
        if not m:
            return None
        v = float(m.group(1).replace(",", "."))
        out = {"top": v, "right": v, "bottom": v, "left": v}
    if any(not 0 <= v <= 10 for v in out.values()):
        return None
    return Action("margins", out, clause)


def _align(clause: str, f: str) -> Action:
    if _has(f, "kenglik", "ikki tomon", "eniga", "shirina"):
        how = "justify"
    elif _has(f, "markaz", "orta"):
        how = "center"
    elif _has(f, "ong"):
        how = "right"
    else:
        how = "left"
    target = "headings" if _has(f, "sarlavha") else "body"
    return Action("align", {"how": how, "target": target}, clause)


def _classify_extra(clause: str, f: str, app: str | None) -> Action | None:
    """Commands added for professional use (highlighting, number formats, layout...)."""
    quoted = _QUOTED.search(clause)
    if app == "powerpoint" or _has(f, "slayd"):
        if _has(f, "otish effekt", "animats", "otish", "perexod"):
            return Action("transition", {}, clause)
        if _has(f, "slayd raqam", "raqamla"):
            return Action("slide_numbers", {}, clause)
        if _has(f, "tekshir"):
            return Action("check", {}, clause)
    if _has(f, "belgila", "boya", "rangla", "ajratib korsat", "rang shkala", "shkala",
            "data bar", "malumot chiziq"):  # fmt: skip
        return _highlight(clause, f)
    if _has(f, "ortacha", "maksimum", "minimum", "mediana") or re.search(
        r"\beng (katta|kichik)\b.*\b(qator|qiymat|hisobla|qosh)", f
    ):  # fmt: skip
        return _stats(clause, f)
    if "=" in clause or re.search(r"\bustun\w*\s+(qosh|yarat|hisobla)\w*\s*:", f):
        a = _formula(clause, f)
        if a is not None:
            return a
    if re.search(r"\b(pul|som|foiz|protsent|valyuta|sana|kasr|butun son|dollar)\w*\b", f) and (
        _has(f, "format", "korinish", "otkaz", "aylantir", "qil", "xona")
    ):
        return _numfmt(clause, f)
    if _has(f, "ustun") and _has(f, "ochir", "olib tashla") and not _has(f, "takror", "dublikat"):
        words = _strip_words(f, r"ochir|olib|tashla", _COMMON)
        return Action("delete_column", {"words": words, "column": _column_ref(clause)}, clause)
    if _has(
        f,
        "faqat",
        "tanlash royxat",
        "royxatdan tanla",
        "ochiluvchi royxat",
        "cheklov",
        "cheklash",
        "validatsiya",
        "validation",
    ):
        v = _validation(clause, f)
        if v is not None:
            return v
    if _has(f, "varaq", "list") and _has(f, "nom") and quoted:
        return Action("rename_sheet", {"name": quoted.group(1).strip()}, clause)
    if _has(f, "kenglig", "moslashtir", "avtomatik kenglik", "avtopodbor"):
        return Action("autofit", {}, clause)
    if _has(f, "kolontitul", "header", "footer"):
        if not quoted:
            return None
        where = "footer" if _has(f, "past", "quyi", "footer") else "header"
        return Action("header", {"where": where, "text": quoted.group(1)}, clause)
    if _has(f, "albom", "landshaft", "gorizontal sahifa", "portret", "kitob shakl"):
        landscape = not _has(f, "portret", "kitob")
        if app == "excel" or _has(f, "bir sahifa", "chop"):
            return Action("print_setup", {"landscape": landscape, "fit": True}, clause)
        return Action("orientation", {"landscape": landscape}, clause)
    if _has(f, "bir sahifaga", "chop etish", "chopga", "pechat"):
        return Action("print_setup", {"landscape": None, "fit": True}, clause)
    if _has(f, "chet", "hoshiya", "maydon") and re.search(r"\d", f):
        a = _margins(clause, f)
        if a is not None:
            return a
    if _has(f, "tekisla", "vyravn"):
        return _align(clause, f)
    if re.search(r"\bsarlavha (qil|uslub)", f) or _has(f, "birinchi qatorni sarlavha"):
        return Action("title", {}, clause)
    if re.search(r"\b(soz|sahifa|belgi|harf)\w*\b.*\b(sana|nechta|hisobla)", f) or _has(
        f, "statistika"
    ):
        return Action("count", {}, clause)
    if app == "word" and _has(f, "jadval") and _has(f, "formatla", "chiroyli", "bezat", "chegara"):
        return Action("tables", {}, clause)
    # «rasmiy ariza ko‘rinishiga keltir» (live check 2026-10-19: only the PDF was made)
    if (
        app == "word"
        and _has(f, "rasmiy")
        and _has(f, "keltir", "korinish", "tayyorla", "moslashtir", "aylantir", "qilib ber")
    ):
        return Action("format", {}, clause)
    # «mayda yozuvlarni kattalashtir»: the fix pass raises small text to the official minimum
    if app in ("word", "powerpoint") and re.search(
        r"\b(mayda|kichik|kichkina)\w*\s+(yozuv|matn|shrift|harf)\w*.*"
        r"\b(kattalashtir|katta qil|oshir)",
        f,
    ):
        return Action("fix", {}, clause)
    # "kamchiliklarni tuzat", "hujjatni tekshirib tuzat": fix what «tekshir» reports
    if app in ("excel", "word", "powerpoint") and _has(
        f, "tuzat", "to[‘’']?g[‘’']?irla", "togirla"
    ):
        if _has(f, "kamchilik", "xato", "hujjat", "jadval", "fayl", "tekshir", "slayd", "taqdimot"):
            return Action("fix", {}, clause)
    # "hujjatni tekshir", "jadvalni tekshir": official rules (knowledge/office_guide.py)
    if (
        app in ("excel", "word")
        and _has(f, "tekshir", "nazorat qil")
        and not _has(f, "imlo", "orfografiya")
    ):
        return Action("check", {}, clause)
    return None


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
    if _has(f, "sarala", "tartibla", "saralash", "sartirovka", "sortirovka", "sortla"):
        return _sort(clause, f)
    if _has(f, "pivot", "svodn", "yigma jadval", "yig‘ma jadval", "yig'ma jadval"):
        return _pivot(clause, f)
    if _has(f, "diagramma", "grafik", "chizma"):
        return _chart(clause, f)
    extra = _classify_extra(clause, f, app)
    if extra is not None:
        return extra
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
    created = _new_excel_table(text)
    if created is not None:
        return created
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

    # Clauses are read for the app of the file in hand ("jadvallarni formatla" in Word).
    cls_app = app or (_app_for(context_file) if file is None and context_file else None)
    actions: list[Action] = []
    unknown: list[str] = []
    for clause in split_clauses(text):
        a = _classify(clause, cls_app)
        if a is None:
            unknown.append(clause)
        elif actions and a.kind == actions[-1].kind == "margins":
            actions[-1].args.update(a.args)  # "chap chetini 3 sm, o‘ng chetini 1,5 sm"
        elif not (actions and a.kind == actions[-1].kind == "open"):
            actions.append(a)
    if not any(a.kind != "open" for a in actions) and file is None:
        return None  # nothing Office-like was asked
    if file is None and context_file and app is None:
        file = context_file
    if app is None and file:
        app = _app_for(file)
    return Plan(app, file, actions, unknown)


def _new_excel_table(text: str) -> Plan | None:
    """A named blank workbook requested in chat, with its actual column headings."""
    if not re.search(r"\b(?:excel|eksel)\w*", fold(text)) or find_file(text):
        return None
    # «5 ustunli o‘quvchilar jadvali tuz: A, B, …», also without the count and with
    # «…, ustunlari: A, B» / «… jadval yarat — A, B».
    m = re.search(
        r"(?:\b(?:excel|eksel)[’'‘ʼ`]?\w*\s+)?(?:\b(?P<count>\d{1,2})\s*ustunli\s+)?"
        r"(?P<title>\S.*?)\s+"
        r"jadval\w*\s+(?:tuz|yarat|ochib ber|qil)\w*[\s,]*(?:ustunlari\s*)?[:\-–—]\s*"
        r"(?P<headers>.+)$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    headers = [h.strip() for h in re.split(r"[,;]", m.group("headers")) if h.strip()]
    count = int(m.group("count")) if m.group("count") else len(headers)
    title = re.sub(r"^(?:da|ga|de)\s+", "", m.group("title").strip(), flags=re.IGNORECASE)
    action = Action("create_table", {"count": count, "headers": headers, "title": title}, text)
    return Plan("excel", None, [action])


def _app_for(file: str) -> str | None:
    ext = "." + file.rsplit(".", 1)[-1].lower()
    if ext in EXCEL_EXT:
        return "excel"
    if ext in WORD_EXT:
        return "word"
    if ext in PPT_EXT:
        return "powerpoint"
    return None
