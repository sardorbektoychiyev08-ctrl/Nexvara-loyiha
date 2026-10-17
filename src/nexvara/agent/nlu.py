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


def _bi(text: str, f: str) -> list[ToolCall] | None:
    if not _has(f, r"\b(dashboard|dashbord)\w*"):
        return None
    name = _quoted_or_before(text, r"(dashboard|dashbord)")
    data_file = next((v for v in locations(text) if v.lower().endswith(_DATA_EXT)), "")
    if data_file and _has(f, r"\bsaqla\w*|\bnom\w*"):
        q = [v for v in _QUOTED.findall(text) if v != data_file]
        return [
            ToolCall("bi.create", {"file": data_file, "name": q[0] if q else Path(data_file).stem})
        ]
    if data_file:
        return None  # "Savdo.xlsx dan dashboard yarat": the page builds it (existing handler)
    if _has(f, r"\b(royxat|qaysi)\w*|dashboard\w*\s+(ni\s+)?korsat\w*$|dashboardlar"):
        if not _QUOTED.search(text) and _has(f, r"dashboardlar|royxat|qaysi"):
            return [ToolCall("bi.list")]
    kind = re.search(
        r"\b(ustun\w*|gistogramm\w*|doira\w*|pirog\w*|chiziq\w*|grafik\w*|"
        r"nuqta\w*|kpi|korsatkich\w*|jadval\w*)\s+(diagramm\w*|vidjet\w*|qosh\w*)",
        f,
    )
    if kind and _has(f, r"\bqosh\w*"):
        m = re.search(
            r"([\w‘’'-]+)\s+bo[‘’']?yicha\s+(.+?)\s+(?:ustun|gistogramm|doira|pirog|chiziq|"
            r"grafik|nuqta|kpi|ko[‘’']?rsatkich|jadval)",
            text,
            re.I,
        )
        q = re.search(r"[«“\"]([^«»“”\"]+)[»”\"]", text)
        y = m.group(2).strip() if m else ""
        agg = re.search(r"\b(ortacha|soni)\b", fold(y))
        if agg:
            y = re.sub(r"(?i)\b(o[‘’']?rtacha|soni)\b", "", y).strip()
        return [ToolCall("bi.add_widget", {
            "name": q.group(1) if q else name, "type": kind.group(1), "x": m.group(1) if m else "",
            "y": y, "agg": agg.group(1) if agg else ""})]  # fmt: skip
    flt = _filter(text)
    if _has(f, r"\b(eksport|export|pdf|png|rasm|excel|csv|xlsx)\w*"):
        fmt = re.search(r"\b(pdf|png|rasm|excel|xlsx|csv)\b", f)
        return [ToolCall("bi.export", {"name": name, "format": fmt.group(1) if fmt else "pdf",
                                       "filter": flt})]  # fmt: skip
    if _has(f, r"\bochir\w*"):
        return [ToolCall("bi.delete", {"name": name})]
    if _has(f, r"\b(korsatkich|kpi|natija|qancha|jami|xulosa|tahlil)\w*"):
        return [ToolCall("bi.summary", {"name": name, "filter": flt})]
    if _has(f, r"\b(och|korsat|chiqar)\w*"):
        return [ToolCall("bi.open", {"name": name, "filter": flt})]
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
