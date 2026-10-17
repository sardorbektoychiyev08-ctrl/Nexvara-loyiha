"""Offline Uzbek understanding for Files, NEXVARA BI, Workflows and Settings → ToolCalls.

No AI: patterns are deliberately strict, so anything not matched falls through to the other
handlers (Office commands, tests, topics ...) or to the AI planner when it is on. Paths:
quoted «...» / "..." text, absolute Windows paths without spaces (D:\\Ish\\Arxiv), file names
with an extension, and "ish stoli", "hujjatlar", "yuklanmalar".
"""

from __future__ import annotations

import re
from pathlib import Path

from nexvara.agent.tools import ToolCall, special_folder
from nexvara.knowledge.textnorm import fold

_QUOTED = re.compile(r"[«“\"]([^«»“”\"]+)[»”\"]")
_ABS = re.compile(r"(?<![\w«\"])([A-Za-z]:[\\/][^\s«»\"“”,;]*)")
_NAME = re.compile(r"(?<![\\/\w])([\w\-()‘’']+(?:\.[\w\-()]+)*\.[A-Za-z][A-Za-z0-9]{1,4})\b")
_SPECIAL = re.compile(r"\b(ish stoli|hujjatlar|yuklanmalar|yuklab olinganlar|desktop|downloads)\w*")
_APOS_SUFFIX = re.compile(r"[‘’'`](ga|ni|dan|da|gacha|ning)$", re.IGNORECASE)
_DATA_EXT = (".xlsx", ".xlsm", ".xls", ".csv", ".json", ".xml", ".txt", ".tsv")


def locations(text: str) -> list[str]:
    """Paths and file names in the order they appear."""
    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []

    def add(m: re.Match, value: str) -> None:
        a, b = m.span()
        if any(a < y and x < b for x, y in taken):
            return
        taken.append((a, b))
        found.append((a, _APOS_SUFFIX.sub("", value.strip()).rstrip(".")))

    for m in _QUOTED.finditer(text):
        add(m, m.group(1))
    for m in _ABS.finditer(text):
        add(m, m.group(1))
    for m in _NAME.finditer(text):
        add(m, m.group(1))
    for m in _SPECIAL.finditer(fold(text)):
        add(m, m.group(1))
    return [v for _a, v in sorted(found)]


def _is_folder(v: str) -> bool:
    p = Path(v)
    if special_folder(v) is not None:
        return True
    return p.is_dir() or (p.is_absolute() and not p.suffix)


def _has(f: str, pattern: str) -> bool:
    return re.search(pattern, f) is not None


def _quoted_or_before(text: str, word: str) -> str:
    """«Name» anywhere, else the 1–3 words right before `word` ("Savdo 2026 dashboardini")."""
    q = _QUOTED.search(text)
    if q and not re.search(r"\.[A-Za-z]{2,5}$", q.group(1)):
        return q.group(1).strip()
    m = re.search(rf"((?:[\w‘’'-]+\s+){{1,3}}){word}", fold(text))
    if not m:
        return ""
    words = [
        w
        for w in m.group(1).split()
        if w not in ("shu", "bu", "ushbu", "osha", "oxirgi", "mening", "va", "keyin", "ni", "yangi")
    ]
    return " ".join(words[-3:])


# ---------------- Files ----------------


def _files(text: str, f: str) -> list[ToolCall] | None:
    locs = locations(text)
    folders = [v for v in locs if _is_folder(v)]
    files = [v for v in locs if v not in folders]
    # No file named: which earlier thing is meant ("topilgan fayllar", "uni", "shu fayl").
    if files:
        refs: list[str] = []
    elif re.search(r"\b(topilgan\w*|ularni|shularni|osha fayllar\w*|shu fayllar\w*)\b", f):
        refs = ["topilgan fayllar"]
    elif re.search(r"\b(uni|natija\w*|yangi fayl\w*)\b", f):
        refs = ["uni"]
    else:
        refs = ["shu fayl"]

    if _has(f, r"\bnusxa\w*|\bkochir\w*") and folders and not _has(f, r"\bustun|\bqator|\bjadval"):
        dest = folders[-1]
        tool = "files.copy" if _has(f, r"\bnusxa\w*") else "files.move"
        return [ToolCall(tool, {"paths": files or refs, "folder": dest})]
    m = re.search(r"(?:[«\"“]([^«»\"“”]+)[»\"”]|([\w\-.]+))\s+deb\s+(?:qayta\s+)?nomla", text, re.I)
    if m or _has(f, r"\bnomini\b.*\b(ga|qilib)\s+(ozgartir|almashtir)\w*"):
        if m:
            name = m.group(1) or m.group(2)
        else:
            m2 = re.search(
                r"nomini\s+(?:[«\"“]([^«»\"“”]+)[»\"”]|(\S+?))\s*(?:ga|qilib)\s", text, re.I
            )
            name = (m2.group(1) or m2.group(2)) if m2 else ""
        src = [v for v in files if v != name]
        if name and (len(src) > 1 or refs == ["topilgan fayllar"] or "{n}" in name):
            return [ToolCall("files.rename_batch", {"paths": src or refs, "pattern": name})]
        if name:
            return [ToolCall("files.rename", {"path": next(iter(src), ""), "name": name})]
    if _has(f, r"\b(zip|arxiv)\w*\s+(dan\s+)?(chiqar|och)\w*|\bunzip"):
        return [ToolCall("files.unzip", {"path": next(iter(files), "")})]
    if _has(f, r"\b(zip\w*|arxivla\w*|arxivga\s+(joyla|sol|qosh)\w*|arxiv\s+(qil|yarat)\w*|siqib)"):
        return [ToolCall("files.zip", {"paths": locs or refs})]
    if _has(f, r"\b(zaxira|versiya)\w*") and _has(f, r"\btikla\w*"):
        n = re.search(r"(\d+)\s*-?\s*versiya", f)
        return [ToolCall("files.restore", {"path": next(iter(files), ""),
                                           "version": int(n.group(1)) if n else 1})]  # fmt: skip
    if _has(f, r"\bversiya\w*") and _has(f, r"\b(korsat|qanday|bor|royxat)\w*"):
        return [ToolCall("files.versions", {"path": next(iter(files), "")})]
    if _has(f, r"\bzaxira\w*") and _has(f, r"\b(ol|qil|yarat|saqla|nusxa)\w*"):
        return [ToolCall("files.backup", {"paths": files or refs})]
    if (
        folders
        and _has(f, r"\bpapka\w*")
        and _has(f, r"\b(tartibla\w*|turlarga\s+ajrat\w*|turiga\s+qarab)")
    ):
        return [ToolCall("files.tidy", {"folder": folders[-1]})]
    if _has(f, r"\bsavat\w*") or _has(
        f,
        r"(^\S+\.[a-z0-9]{2,5}\s+(faylini\s+|ni\s+)?|\b(topilgan|shu|bu|osha)\s+fayl\w*\s+)ochir\w*\s*$",
    ):
        return [ToolCall("files.recycle", {"paths": files or refs})]
    if (
        _has(f, r"\bpdf\w*")
        and _has(f, r"\b(fayllar\w*|papka\w*|topilgan\w*|ularni)")
        and _has(f, r"\b(qil|aylantir|ogir|saqla|konvert)\w*")
    ):
        if folders:
            return [ToolCall("files.pdf", {"folder": folders[-1]})]
        return [ToolCall("files.pdf", {"paths": files or refs})]
    if files and _has(f, r"(haqida\s+malumot|hajmi\s+qancha|qancha\s+joy|qachon\s+ozgar)"):
        return [ToolCall("files.info", {"path": files[0]})]
    if _has(f, r"\bfayl\w*") and _has(f, r"\b(top|qidir|izla)\w*"):
        ext = re.search(r"\b(excel|word|powerpoint|pdf|xlsx|docx|pptx|csv|zip|rasm|jpg|png)\b", f)
        if folders or ext:
            exts = {"excel": "xlsx xls", "word": "docx doc", "powerpoint": "pptx ppt",
                    "rasm": "jpg jpeg png"}  # fmt: skip
            words = re.sub(
                r"\b(fayl\w*|top\w*|qidir\w*|izla\w*|menga|barcha|hamma|papka\w*|ichida\w*|"
                r"excel|word|powerpoint|pdf|xlsx|docx|pptx|csv|zip|rasm\w*|jpg|png|"
                r"dan|da|ni|shu|bu)\b", " ", fold(_ABS.sub(" ", _QUOTED.sub(" ", text))),
            )  # fmt: skip
            return [ToolCall("files.search", {
                "query": " ".join(words.split()), "folder": folders[-1] if folders else "",
                "ext": exts.get(ext.group(1), ext.group(1)) if ext else ""})]  # fmt: skip
    return None


# ---------------- NEXVARA BI ----------------


def _filter(text: str) -> str:
    m = re.search(r"\bfaqat\s+(?:[«\"“]([^«»\"“”]+)[»\"”]|([\w‘’'-]+))", text, re.I)
    if m:
        return (m.group(1) or m.group(2)).strip()
    m = re.search(
        r"(?:[«\"“]([^«»\"“”]+)[»\"”]|([\w‘’'-]+))\s+(?:bo[‘’']?yicha|uchun)\b", text, re.I
    )
    return (m.group(1) or m.group(2)).strip() if m else ""


_DASH = r"(?:dashboard|dashbord)\w*"
_Q = r"[«\"“]([^«»\"“”]+)[»\"”]"
_WTYPES = (r"(ustun\w*|gistogramm\w*|doira\w*|pirog\w*|chiziq\w*|grafik\w*|nuqta\w*|kpi|"
           r"ko[‘’']?rsatkich\w*|jadval\w*)")  # fmt: skip
_DATE = r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./]\d{1,2}[./]\d{4})"


def _dash_name(text: str) -> str:
    """«Savdo 2026» dashboardi... / Savdo dashboardida ... ('' = the one we talked about)."""
    m = re.search(_Q + r"\s+" + _DASH, text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"((?:[\w‘’'-]+\s+){1,3})" + _DASH, text, re.I)
    if not m:
        return ""
    stop = {"shu", "bu", "ushbu", "osha", "oxirgi", "mening", "va", "keyin", "ni", "yangi", "bir"}
    words = [w for w in m.group(1).split() if fold(w) not in stop and not _NAME.fullmatch(w)]
    return " ".join(words[-3:])


def _column_ref(text: str, quotes: list[str]) -> str:
    m = re.search(r"(?:" + _Q + r"|([\w‘’'-]+))\s+ustun\w*", text, re.I)
    if m:
        return (m.group(1) or m.group(2)).strip()
    return quotes[0] if quotes else ""


def _dates(text: str) -> dict[str, str]:
    out = {}
    m = re.search(_DATE + r"\s*(?:dan|-dan|’dan|'dan)\b", text)
    if m:
        out["date_from"] = m.group(1)
    m = re.search(_DATE + r"\s*(?:gacha|-gacha|’gacha|'gacha)\b", text)
    if m:
        out["date_to"] = m.group(1)
    return out


def _formula_words(expr: str) -> str:
    rep = [
        (r"\bminus\b|\bayir\w*", "-"),
        (r"\bplyus\b|\bqo[‘’']?shuv\b", "+"),
        (r"\bkarra\b|\bko[‘’']?paytir\w*", "*"),
        (r"\bbo[‘’']?ling\w*|\bbo[‘’']?lin\w*", "/"),
    ]
    for pat, op in rep:
        expr = re.sub(pat, f" {op} ", expr, flags=re.I)
    return re.sub(r"\s+", " ", expr).strip()


def _bi(text: str, f: str) -> list[ToolCall] | None:
    if not re.search(r"\b" + _DASH, f):
        return None
    name = _dash_name(text)
    quotes = [q for q in _QUOTED.findall(text) if q != name]
    data_files = [v for v in locations(text) if v.lower().endswith(_DATA_EXT) and v != name]
    view = {"filter": _filter(text), **_dates(text)}
    page = re.search(r"(\d+)\s*-?\s*sahifa", f)
    if page:
        view["page"] = int(page.group(1))

    def call(tool: str, **args) -> list[ToolCall]:
        return [ToolCall(tool, {"name": name, **args})]

    # ----- other files: rows below (append) or columns by a key (join) -----
    if data_files and _has(f, r"\b(birlashtir|ulab|ula\b|bogla|qo\w*sh|ostiga|davomiga)\w*"):
        if _has(f, r"\b(yarat|tuz)\w*") and not _has(f, r"\bbirlashtir"):
            pass  # "X.xlsx dan dashboard yarat" below
        else:
            key = re.search(r"([\w‘’'-]+)\s+bo[‘’']?yicha", text, re.I)
            if _has(f, r"\bbirlashtir|\bula|\bbogla") and key:
                return call("bi.add_step", op="join", file=data_files[-1], on=key.group(1))
            return call("bi.add_step", op="append", file=data_files[-1])
    if data_files:
        if _has(f, r"\bsaqla\w*|\bnom\w*"):
            return [
                ToolCall(
                    "bi.create",
                    {
                        "file": data_files[0],
                        "name": quotes[0] if quotes else Path(data_files[0]).stem,
                    },
                )
            ]
        return None  # "Savdo.xlsx dan dashboard yarat": the page builds it (existing handler)

    if _has(f, r"\bdashboardlar|\b(royxat|qaysi)\w*") and not _QUOTED.search(text):
        if not _has(f, r"\b(vidjet|diagramm|qadam|bosqich)\w*"):
            return [ToolCall("bi.list")]

    # ----- data steps -----
    n = re.search(r"(\d+)\s*-?\s*(qadam|bosqich)", f)
    if n and _has(f, r"\b(ochir|olib\s+tashla|bekor\s+qil)\w*"):
        return call("bi.remove_step", number=int(n.group(1)))
    if _has(f, r"\b(qadam|bosqich|etl)\w*") and _has(f, r"\b(korsat|royxat|qanday|qaysi)\w*"):
        return call("bi.steps")
    if (
        "=" in text
        and _has(f, r"\b(ustun|formula|hisobla|qosh)\w*")
        and not _has(f, r"\bqoldir|\bqolsin|\bfiltr")
    ):
        left, right = text.split("=", 1)
        lq = _QUOTED.findall(left)
        new = lq[-1] if lq else (re.findall(r"[\w‘’'-]+", left) or [""])[-1]
        expr = right
        for cut in re.finditer(r"\s+(?:ustun\w*|formula\w*|qo[‘’']?sh\w*|deb)\b", right):
            before = right[: cut.start()]
            if before.count("[") == before.count("]"):  # not inside a [column name]
                expr = before
                break
        return call(
            "bi.add_step", op="calc", new_name=new.strip(), formula=_formula_words(expr.strip(" ."))
        )
    cmp = re.search(
        r"(?:" + _Q + r"|([\w‘’'-]+))\s*(>=|<=|!=|>|<|=)\s*([\w.,‘’' -]+?)\s+(?:bo[‘’']?lgan\s+)?"
        r"(?:qator\w*\s+)?(?:qolsin|qoldir|filtrla)",
        text,
        re.I,
    )
    if cmp:
        return call("bi.add_step", op="filter", column=cmp.group(1) or cmp.group(2),
                    cmp=cmp.group(3), value=cmp.group(4).strip())  # fmt: skip
    m = re.search(
        r"(?:" + _Q + r"|([\w‘’'-]+))\s+(\d+(?:[.,]\d+)?)\s*dan\s+(katta|kichik|ko[‘’']?p|kam)"
        r"\w*\s+(?:bo[‘’']?lgan\s+)?(?:qator\w*\s+)?(?:qolsin|qoldir)",
        text,
        re.I,
    )
    if m:
        op = ">" if fold(m.group(4)).startswith(("katta", "kop")) else "<"
        return call("bi.add_step", op="filter", column=m.group(1) or m.group(2), cmp=op,
                    value=m.group(3))  # fmt: skip
    col = _column_ref(text, quotes)
    if _has(f, r"\bustun\w*") and _has(f, r"\bdeb\s+(qayta\s+)?nomla|\bnomini\b"):
        new = quotes[-1] if len(quotes) >= 2 else ""
        return call("bi.add_step", op="rename", column=col, new_name=new)
    if (
        _has(f, r"\bustun\w*")
        and _has(f, r"\b(olib\s+tashla|ochir)\w*")
        and not _has(f, r"\bbosh\b")
    ):
        return call("bi.add_step", op="drop_col", column=col)
    if _has(f, r"\bbosh\b") and _has(f, r"\btoldir\w*"):
        v = re.search(r"(\d+(?:[.,]\d+)?)\s+bilan", f)
        value = "o‘rtacha" if _has(f, r"\bortacha") else (v.group(1) if v else "0")
        return call("bi.add_step", op="fill_null", column=col, value=value)
    if _has(f, r"\b(takror\w*|dublikat\w*)") and _has(f, r"\b(ochir|olib\s+tashla)\w*"):
        return call("bi.add_step", op="dedupe")
    if _has(f, r"\bbosh\s+qator\w*") and _has(f, r"\b(ochir|olib\s+tashla)\w*"):
        if _has(f, r"\bustun\w*"):
            return call("bi.add_step", op="drop_null", column=col)
        return call("bi.add_step", op="drop_empty")
    t = re.search(r"\b(son|raqam|sana|matn)\s+tur\w*", f)
    if t and _has(f, r"\bustun\w*"):
        return call("bi.add_step", op="set_type", column=col, type=t.group(1))

    # ----- widgets -----
    wref = re.search(r"(\d+)\s*-?\s*(vidjet|diagramm|grafik|korsatkich)\w*", f)
    wq = re.search(_Q + r"\s+(?:vidjet|diagramm|grafig|grafik|ko[‘’']?rsatkich)\w*", text, re.I)
    widget = wref.group(1) if wref else (wq.group(1) if wq else "")
    # "...dagi 3-vidjetni 2-sahifaga ko‘chir",
    # "«Ulush» diagrammasini «Mahsulotlar» sahifasiga o‘tkaz"
    pnum = re.search(r"(\d+)\s*-?\s*sahifa\w*", f)
    pq = re.search(_Q + r"\s+sahifa\w*", text, re.I)
    page_ref = pnum.group(1) if pnum else (pq.group(1) if pq else "")
    if widget and page_ref and _has(f, r"\b(kochir|kochirib|otkaz|olib\s+ot|joyla)\w*"):
        return call("bi.move_widget", widget=widget, page=page_ref)
    # "«Savdo» dashboardidagi 2-sahifani o‘chir" (asks first: the tool is risky)
    if page_ref and not widget and _has(f, r"\b(ochir|olib\s+tashla)\w*"):
        return call("bi.delete_page", page=page_ref)
    if _has(f, r"\b(vidjet|diagramm)\w*lar\w*") and _has(f, r"\b(korsat|royxat|qanday|qaysi)\w*"):
        return call("bi.widgets")
    if widget and _has(f, r"\b(ochir|olib\s+tashla)\w*"):
        return call("bi.remove_widget", widget=widget)
    if widget and not _has(f, r"\bqosh\w*\s*$"):
        args: dict = {"widget": widget}
        typ = re.search(_WTYPES + r"\s+(qil|bolsin|ga\s+ozgartir|korinish)", f)
        if typ:
            args["type"] = typ.group(1)
        ttl = re.search(r"sarlavha\w*\s+" + _Q, text, re.I)
        if ttl:
            args["title"] = ttl.group(1)
        agg = re.search(r"\b(ortacha|yigindi|soni|eng katta|eng kichik)\b", f)
        if agg:
            args["agg"] = agg.group(1)
        x = re.search(r"([\w‘’'-]+)\s+bo[‘’']?yicha", text, re.I)
        if x:
            args["x"] = x.group(1)
        y = re.search(
            r"(?:qiymat\w*\s+" + _Q + r"|" + _Q + r"\s+(?:ni\s+)?ko[‘’']?rsatsin)", text, re.I
        )
        if y:
            args["y"] = y.group(1) or y.group(2)
        top = re.search(r"eng\s+katta\s+(\d+)|(\d+)\s+tasi", f)
        if top:
            args["top"] = int(top.group(1) or top.group(2))
        if len(args) > 1:
            return call("bi.edit_widget", **args)
    kind = re.search(_WTYPES + r"\s+(diagramm\w*|vidjet\w*|qosh\w*)", f)
    if kind and _has(f, r"\bqosh\w*"):
        m = re.search(
            r"([\w‘’'-]+)\s+bo[‘’']?yicha\s+(.+?)\s+(?:ustun|gistogramm|doira|pirog|chiziq|"
            r"grafik|nuqta|kpi|ko[‘’']?rsatkich|jadval)",
            text,
            re.I,
        )
        y = m.group(2).strip() if m else (quotes[0] if quotes else "")
        agg = re.search(r"\b(ortacha|soni)\b", fold(y))
        if agg:
            y = re.sub(r"(?i)\b(o[‘’']?rtacha|soni)\b", "", y).strip()
        return call(
            "bi.add_widget",
            type=kind.group(1),
            x=m.group(1) if m else "",
            y=y,
            agg=agg.group(1) if agg else "",
            **({"page": view["page"]} if page else {}),
        )
    if _has(f, r"\bsahifa\w*") and _has(f, r"\bqosh\w*") and quotes:
        return call("bi.add_page", title=quotes[-1])

    # ----- the dashboard itself -----
    if _has(f, r"\bdeb\s+(qayta\s+)?nomla|\bnomini\b") and quotes:
        return call("bi.rename", new_name=quotes[-1])
    if _has(f, r"\b(eksport|export|pdf|png|rasm|excel|csv|xlsx)\w*"):
        fmt = re.search(r"\b(pdf|png|rasm|excel|xlsx|csv)\b", f)
        return call("bi.export", format=fmt.group(1) if fmt else "pdf", **view)
    if _has(f, r"\bochir\w*"):
        return call("bi.delete")
    if _has(f, r"\b(korsatkich|kpi|natija|qancha|jami|xulosa|tahlil)\w*"):
        return call("bi.summary", **view)
    if _has(f, r"\b(och|korsat|chiqar)\w*"):
        return call("bi.open", **view)
    return None


# ---------------- Workflows ----------------

_TIME = re.compile(
    r"\b(?:har\s+kuni|kunda|kuniga|har\s+kun)\s+(?:ertalab\s+|kechqurun\s+)?(?:soat\s+)?"
    r"(\d{1,2})(?:[:.](\d{2}))?\s*(?:da|ga)?\b", re.IGNORECASE)  # fmt: skip
_WATCH = re.compile(
    r"(?:[«\"“]([^«»\"“”]+)[»\"”]|([A-Za-z]:[\\/]\S*))\s+papka\w*\s*(?:ga|ichiga)?"
    r"\s+yangi\s+fayl\s+(?:tushganda|kelganda|qo[‘’']?shilganda)\w*",
    re.I,
)


def _wf_name(text: str) -> str:
    return _quoted_or_before(text, r"(workflow|ish jarayon)")


def split_steps(body: str) -> list[str]:
    parts = re.split(
        r"\s*(?:;|\n+|\s\d+[.)]\s+|,?\s+(?:keyin|so[‘’']?ng|undan\s+keyin)\s+)\s*", body
    )
    return [p.strip(" .,") for p in parts if p and p.strip(" .,")]


def _workflow(text: str, f: str) -> list[ToolCall] | None:
    if not _has(f, r"\b(workflow|ish jarayon)\w*"):
        return None
    name = _wf_name(text)
    if _has(f, r"\b(yarat|tuz|qosh|saqla)\w*") and ":" in text:
        head, body = text.split(":", 1)
        args: dict = {"name": _quoted_or_before(head, r"(workflow|ish jarayon)") or name}
        t = _TIME.search(body)
        if t:
            args["time"] = f"{int(t.group(1)):02d}:{t.group(2) or '00'}"
            body = body[: t.start()] + body[t.end() :]
        w = _WATCH.search(body)
        if w:
            args["folder"] = w.group(1) or w.group(2)
            body = body[: w.start()] + body[w.end() :]
        if re.search(r"\bxatoda\s+davom\s+et", fold(body)):
            args["on_error"] = "continue"
            body = re.sub(r"(?i)\bxatoda\s+davom\s+et\w*", "", body)
        args["steps"] = split_steps(body)
        return [ToolCall("workflow.create", args)]
    if _has(f, r"\btarix\w*"):
        return [ToolCall("workflow.history", {"name": name})]
    if _has(f, r"\bpauza|\btoxtatib\s+tur"):
        return [ToolCall("workflow.pause", {"name": name})]
    if _has(f, r"\bdavom\s+ettir"):
        return [ToolCall("workflow.resume", {"name": name})]
    if _has(f, r"\btasdiqla\w*"):
        return [ToolCall("workflow.approve", {"name": name})]
    if _has(f, r"\b(toxtat|bekor\s+qil)\w*"):
        return [ToolCall("workflow.stop", {"name": name})]
    if _has(f, r"\b(butunlay\s+ochir|ochirib\s+tashla|olib\s+tashla)\w*"):
        return [ToolCall("workflow.delete", {"name": name})]
    if _has(f, r"\b(ochir|ochirib\s+qoy)\w*"):
        return [ToolCall("workflow.enable", {"name": name, "enabled": False})]
    if _has(f, r"\b(yoq|yoqib\s+qoy|faollashtir)\b"):
        return [ToolCall("workflow.enable", {"name": name, "enabled": True})]
    if _has(f, r"\b(ishga\s+tushir|boshla|bajar|yurgiz)\w*"):
        return [ToolCall("workflow.run", {"name": name})]
    if _has(f, r"\b(korsat|royxat|qaysi|bor)\w*"):
        return [ToolCall("workflow.list")]
    return None


# ---------------- Settings, updates, sync ----------------


def _num(s: str) -> str:
    return s.replace(",", ".")


def _settings(text: str, f: str) -> list[ToolCall] | None:
    def set_(key: str, value) -> list[ToolCall]:
        return [ToolCall("settings.set", {"key": key, "value": str(value)})]

    if re.fullmatch(
        r"(sozlama\w*)(\s+(ni|larni))?(\s+(korsat|qanday|ochib ber)\w*)?", f.strip(" ?!.")
    ):
        return [ToolCall("settings.show")]
    m = re.search(r"\b(savol|test)\w*\s+soni\w*\s+(\d+)", f) or re.search(
        r"\bsukut\w*\s+(boyicha\s+)?(\d+)\s+ta\s+savol", f)  # fmt: skip
    if m:
        return set_("test_count", m.group(2))
    m = re.search(r"\bvariant\w*\s+(soni\w*\s+)?(\d+)\s*(ta\s+)?(bolsin|qil|ga)", f)
    if m:
        return set_("test_variants", m.group(2))
    if _has(f, r"\boffice\w*\s+(oyna\w*\s+)?ochiq\s+qol\w*"):
        return set_("keep_office_open", "true")
    if _has(f, r"\boffice\w*\s+(oyna\w*\s+)?(yopil|yop)\w*"):
        return set_("keep_office_open", "false")
    m = re.search(r"\b(kunlik|oylik)\s+(ai\s+)?(limit|byudjet)\w*\s+(\d+(?:[.,]\d+)?)", f)
    if m:
        key = "ai.daily_budget_usd" if m.group(1) == "kunlik" else "ai.monthly_budget_usd"
        return set_(key, _num(m.group(4)))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(\$|dollar\w*)\s*(dan\s+)?qimmat", f)
    if m:
        return set_("ai.confirm_over_usd", _num(m.group(1)))
    if _has(f, r"^(ai|suniy intellekt)\w*\s+(ni\s+)?(yoq|yoqib\s+qoy)\b"):
        return set_("ai.enabled", "true")
    if _has(f, r"^(ai|suniy intellekt)\w*\s+(ni\s+)?(ochir|ochirib\s+qoy)\w*"):
        return set_("ai.enabled", "false")
    m = re.search(r"\bport\w*\s+(\d{4,5})", f)
    if m and _has(f, r"\btelefon|\bport"):
        return set_("remote.port", m.group(1))
    if _has(f, r"\byangilanish\w*\s+(kanal|papka|manzil)\w*"):
        loc = next(iter(locations(text)), "")
        m2 = re.search(r"https://\S+", text)
        if m2 or loc:
            return set_("update.channel", m2.group(0) if m2 else loc)
    if _has(
        f,
        r"\b(yangilanish\w*\s+(ni\s+)?(tekshir|bormi|bor\s*mi)|yangi\s+versiya\s+(bormi|chiqdimi))",
    ):
        return [ToolCall("settings.update_check")]
    if _has(f, r"\bsinxron\w*"):
        if _has(f, r"\bpapka\w*"):
            loc = next(iter(locations(text)), "")
            if loc:
                return set_("sync.folder", loc)
        if _has(f, r"\bgoogle\s+drive"):
            return set_("sync.google_drive", "false" if _has(f, r"\bochir\w*") else "true")
        if _has(f, r"\b(ochir|ochirib\s+qoy)\w*"):
            return set_("sync.enabled", "false")
        if _has(f, r"\b(yoq|yoqib\s+qoy)\b"):
            return set_("sync.enabled", "true")
        return [ToolCall("sync.now")]
    return None


def parse(text: str) -> list[ToolCall] | None:
    f = fold(text).strip()
    for fn in (_workflow, _bi, _settings, _files):
        calls = fn(text, f)
        if calls:
            return calls
    return None


# ---------------- several tasks in one message ----------------

_CHAIN = re.compile(
    r"\s*(?:;|\n+|,?\s+(?:va\s+)?(?:keyin(?:\s+esa)?|so[‘’']ng(?:ra)?|undan\s+(?:keyin|so[‘’']ng)|"
    r"shundan\s+(?:keyin|so[‘’']ng)|oxirida)\s+|(?:^|\s)\d+[.)]\s+)",
    re.IGNORECASE,
)


def split_chain(text: str) -> list[str]:
    """'A.xlsx ni PDF qil, keyin uni D:\\Arxiv ga ko‘chir' -> two tasks. Office clauses about the
    same file stay one command ("och, keyin saralab saqla")."""
    from nexvara.agent.parse import find_file, parse_command

    if ":" in text and re.search(r"\b(workflow|ish jarayon)\w*", fold(text)):
        return [text]  # a workflow definition lists its own steps
    parts = [p.strip(" ,.") for p in _CHAIN.split(text) if p and p.strip(" ,.")]
    if len(parts) < 2:
        return [text]
    merged: list[str] = []
    office_prev = False
    for p in parts:
        plan = parse_command(p, None)
        is_office = plan is not None and bool(plan.actions)
        explicit = find_file(p) is not None or bool(locations(p))
        refers = re.search(r"\b(uni|natija\w*|shu fayl\w*)\b", fold(p)) is not None
        if (
            merged
            and office_prev
            and is_office
            and not explicit
            and not refers
            and parse(p) is None
        ):
            merged[-1] = f"{merged[-1]}, {p}"
            continue
        merged.append(p)
        office_prev = is_office
    return merged
