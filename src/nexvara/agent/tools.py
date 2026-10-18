"""The agent's tools: every section's actions as named, typed, validated calls.

Both planners produce `ToolCall`s: the offline Uzbek rules (agent/nlu.py) and the optional AI
planner (ai/features.plan), which sees `catalog()` as its tool list. Execution is always here,
so a call from the AI gets exactly the same checks as a button: path checks, no overwrite,
and `risky` tools (delete, tidy, restore over a file, removing a dashboard or workflow) only
after the user's "Ha".
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexvara.knowledge.textnorm import fold


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        t = TOOLS.get(self.tool)
        shown = ", ".join(f"{k}: {_short(v)}" for k, v in self.args.items() if v not in ("", None))
        return f"{t.title if t else self.tool}" + (f" ({shown})" if shown else "")


def _short(v: Any) -> str:
    if isinstance(v, list):
        return ", ".join(Path(str(x)).name or str(x) for x in v[:5]) + ("…" if len(v) > 5 else "")
    s = str(v)
    return Path(s).name if ("\\" in s or "/" in s) and len(s) > 40 else s


@dataclass
class Tool:
    name: str
    title: str  # Uzbek, shown in plans and confirmations
    params: dict[str, tuple[str, bool, str]]  # name -> (type, required, description)
    run: Callable[[Any, dict[str, Any]], dict[str, Any]]
    risky: bool = False


TOOLS: dict[str, Tool] = {}

# Lookups that change nothing: an AI plan made only of these runs without asking.
READ_ONLY = frozenset({
    "files.search", "files.info", "files.versions", "bi.list", "bi.summary", "bi.steps",
    "bi.widgets", "workflow.list", "workflow.history", "settings.show", "settings.update_check",
})  # fmt: skip


def tool(tool_name: str, title: str, /, risky: bool = False, **params: tuple[str, bool, str]):
    def deco(fn):
        TOOLS[tool_name] = Tool(tool_name, title, params, fn, risky)
        return fn

    return deco


class ToolError(Exception):
    """Shown to the user as the reply."""


# ---------------- validation ----------------

_TYPES = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list}


def validate(call: ToolCall) -> ToolCall:
    t = TOOLS.get(call.tool)
    if t is None:
        raise ToolError(f"Noma’lum amal: {call.tool}")
    if not isinstance(call.args, dict):
        raise ToolError("Amal parametrlari noto‘g‘ri")
    out: dict[str, Any] = {}
    for key, value in call.args.items():
        if key not in t.params:
            continue  # the AI may invent parameters; they are dropped, not trusted
        typ = t.params[key][0]
        try:
            if typ == "array":
                value = [str(v) for v in (value if isinstance(value, list) else [value])]
            elif typ == "boolean":
                value = value if isinstance(value, bool) else fold(str(value)) in (
                    "true", "1", "ha", "on")  # fmt: skip
            elif typ in ("integer", "number"):
                value = _TYPES[typ](value)
            else:
                value = str(value).strip()
        except (TypeError, ValueError) as e:
            raise ToolError(f"{t.title}: «{key}» noto‘g‘ri") from e
        out[key] = value
    for key, (_typ, required, _d) in t.params.items():
        if required and out.get(key) in (None, "", []):
            raise ToolError(f"{t.title}: «{key}» kerak")
    return ToolCall(call.tool, out)


def catalog() -> list[dict[str, Any]]:
    """JSON-schema-like description for the AI planner."""
    out = []
    for t in TOOLS.values():
        props = {k: {"type": typ, "description": d} for k, (typ, _r, d) in t.params.items()}
        out.append({
            "name": t.name, "description": t.title + (" (tasdiq so‘raladi)" if t.risky else ""),
            "parameters": {"type": "object", "properties": props,
                           "required": [k for k, (_t, r, _d) in t.params.items() if r]},
        })  # fmt: skip
    return out


# ---------------- resolving paths ----------------

_SPECIAL_FOLDERS = {
    "ish stoli": "Desktop", "rabochiy stol": "Desktop", "desktop": "Desktop",
    "hujjatlar": "Documents", "documents": "Documents", "mening hujjatlarim": "Documents",
    "yuklanmalar": "Downloads", "yuklab olinganlar": "Downloads", "downloads": "Downloads",
    "rasmlar": "Pictures",
}  # fmt: skip


def special_folder(name: str) -> Path | None:
    key = fold(name).strip()
    for k, v in _SPECIAL_FOLDERS.items():
        if key == k or key.startswith(k + " "):
            p = Path.home() / v
            if v == "Desktop":
                one = Path.home() / "OneDrive" / "Desktop"
                p = one if one.is_dir() and not p.is_dir() else p
            return p
    return None


def resolve_file(api: Any, value: str, text: str = "") -> Path:
    ctx = api._ctx
    v = (value or "").strip().strip('«»"“”')
    if not v or ctx.refers_to_file(v):
        cur = ctx.current_file(v or text)
        if not cur:
            raise ToolError("Qaysi fayl? Fayl nomini yozing yoki 📎 bilan tanlang.")
        return Path(cur)
    v = api._alias_path(v) or v
    p = Path(v)
    if p.is_absolute():
        if not p.exists():
            raise ToolError(f"Topilmadi: {p}")
        return p
    from nexvara.agent import files

    for d in ctx.recent_dirs():  # folders this conversation already touched come first
        if (d / v).exists():
            return d / v
    try:
        near = Path(ctx.file).parent if ctx.file else None
        return files.resolve(v, near)
    except LookupError as e:
        raise ToolError(str(e)) from e


def resolve_files(api: Any, values: list[str], text: str = "") -> list[str]:
    """Named files; "topilgan fayllar" = the last search/list; "uni" / "shu fayl" / nothing =
    the current file (see Context.current_file)."""
    ctx = api._ctx
    out: list[str] = []
    for v in [x for x in values if x] or [""]:
        if ctx.refers_to_files(v):
            if not ctx.files:
                raise ToolError("Qaysi fayllar? Avval qidiring, masalan «hisobot fayllarini top».")
            out += [p for p in ctx.files if p not in out]
        else:
            out.append(str(resolve_file(api, v, text)))
    return out


def resolve_folder(api: Any, value: str, create: bool = False) -> Path:
    ctx = api._ctx
    v = (value or "").strip().strip('«»"“”')
    if not v or ctx.refers_to_folder(v):
        if ctx.folder:
            return Path(ctx.folder)
        raise ToolError("Qaysi papka? To‘liq yo‘lini yozing, masalan D:\\Arxiv")
    v = api._alias_path(v) or v
    sp = special_folder(v)
    p = sp if sp is not None else Path(v)
    if not p.is_absolute():
        base = Path(ctx.file).parent if ctx.file else None
        if base is None:
            raise ToolError(f"«{v}» papkasi qayerda? To‘liq yo‘lini yozing, masalan D:\\{v}")
        p = base / v
    if p.is_dir():
        return p
    # «D:\Ish papkasi», «…\Ish papkasidagi»: the AI (or the user) glued the Uzbek word to the
    # path (live check 2026-10-19) — the folder is the part before it.
    bare = re.sub(r"(?i)[\s\\/]+papka\w*\s*$", "", str(p)).rstrip()
    if bare != str(p) and Path(bare).is_dir():
        return Path(bare)
    if create and p.parent.is_dir():
        p.mkdir()
        return p
    raise ToolError(f"Papka topilmadi: {p}")


def _ok(r: dict[str, Any]) -> Any:
    if not r.get("ok", True):
        raise ToolError(r.get("error") or "Bajarilmadi")
    return r.get("result")


def _names(paths: list[str]) -> str:
    return "\n".join(f"• {p}" for p in paths[:15]) + (f"\n… yana {len(paths) - 15}" if
                                                      len(paths) > 15 else "")  # fmt: skip


# =====================================================================
# Files
# =====================================================================


@tool(
    "files.search",
    "Fayl qidirish",
    query=("string", False, "nomidagi so‘zlar"),
    folder=("string", False, "qaysi papkada"),
    ext=("string", False, "kengaytma: xlsx, pdf ..."),
)
def files_search(api, a):
    folder = str(resolve_folder(api, a["folder"])) if a.get("folder") else ""
    query, ext = str(a.get("query") or ""), str(a.get("ext") or "")
    # «Excel fayllari xlsx» is a kind of file, not words in its name (live check 2026-10-19:
    # the AI sent it as the query and nothing was found).
    kinds = {"excel": "xlsx", "eksel": "xlsx", "word": "docx", "vord": "docx", "pdf": "pdf",
             "powerpoint": "pptx", "taqdimot": "pptx", "rasm": "jpg"}  # fmt: skip
    words = [w for w in re.split(r"[\s,;]+", query) if w]
    keep = []
    for w in words:
        f = fold(w).strip(".*")
        k = next((v for key, v in kinds.items() if f.startswith(key)), None)
        if k and not ext:
            ext = k
        if (
            k
            or f in ("xlsx", "xls", "docx", "doc", "pptx", "pdf", "csv")
            or re.match(r"^(fayl|hujjat|jadval|ro.?yxat|barcha|hamma)\w*$", f)
        ):
            continue
        keep.append(w)
    r = api.files_search(" ".join(keep), folder, ext)
    if not r.get("ok"):
        raise ToolError(r["error"])
    paths = [f["path"] for f in r["files"]][:30]
    api._ctx.set_files(paths)
    if folder:
        api._ctx.folder = folder
    what = " ".join(x for x in (a.get("query", ""), a.get("ext", "")) if x) or "fayllar"
    if not paths:
        return {"reply": f"«{what}» bo‘yicha fayl topilmadi."}
    return {"reply": f"Topildi ({len(paths)}):\n{_names(paths)}", "files": paths}


@tool("files.info", "Fayl haqida ma’lumot", path=("string", False, "fayl"))
def files_info(api, a):
    p = resolve_file(api, a.get("path", ""))
    info = _ok(api.files_info(str(p)))
    size = info.get("size", 0)
    return {"reply": f"{p.name}\n• joyi: {p.parent}\n• hajmi: {size / 1024:.1f} KB\n"
            f"• SHA-256: {info.get('sha256', '')[:16]}…"}  # fmt: skip


def _copy_or_move(api, a, move: bool):
    paths = resolve_files(api, a.get("paths") or [])
    dest = resolve_folder(api, a["folder"], create=True)
    out = _ok((api.files_move if move else api.files_copy)(paths, str(dest)))
    api._ctx.set_files(out)
    api._ctx.folder = str(dest)
    if out:
        api._ctx.result = out[-1]
    verb = "ko‘chirildi" if move else "nusxalandi"
    return {"reply": f"{len(out)} ta fayl {dest} ga {verb} (ustiga yozilmadi):\n{_names(out)}",
            "files": out}  # fmt: skip


@tool("files.copy", "Nusxa olish", paths=("array", False, "fayllar"),
      folder=("string", True, "qaysi papkaga"))  # fmt: skip
def files_copy(api, a):
    return _copy_or_move(api, a, move=False)


@tool("files.move", "Ko‘chirish", paths=("array", False, "fayllar"),
      folder=("string", True, "qaysi papkaga"))  # fmt: skip
def files_move(api, a):
    return _copy_or_move(api, a, move=True)


@tool("files.rename", "Nomini o‘zgartirish", path=("string", False, "fayl"),
      name=("string", True, "yangi nom"))  # fmt: skip
def files_rename(api, a):
    p = resolve_file(api, a.get("path", ""))
    name = a["name"]
    if "." not in name and p.suffix:
        name += p.suffix  # "Yanvar deb nomla" keeps .xlsx
    new = _ok(api.files_rename(str(p), name))
    api._ctx.file = api._ctx.result = new
    return {"reply": f"Nomi o‘zgardi: {p.name} → {Path(new).name}"}


@tool("files.rename_batch", "Ommaviy nomlash", paths=("array", False, "fayllar"),
      pattern=("string", True, "masalan Hisobot_{n}"))  # fmt: skip
def files_rename_batch(api, a):
    paths = resolve_files(api, a.get("paths") or ["topilgan fayllar"])
    out = _ok(api.files_rename_batch(paths, a["pattern"]))
    api._ctx.set_files(out)
    return {"reply": f"{len(out)} ta fayl nomlandi:\n{_names(out)}", "files": out}


@tool("files.zip", "ZIP arxiv qilish", paths=("array", False, "fayllar yoki papka"))
def files_zip(api, a):
    vals = a.get("paths") or []
    paths = []
    for v in vals:
        if Path(v).is_dir() or special_folder(v):
            paths.append(str(resolve_folder(api, v)))
        else:
            paths += resolve_files(api, [v])
    if not paths:
        paths = resolve_files(api, [])
    out = _ok(api.files_zip(paths))
    api._ctx.result = out
    return {"reply": f"Arxiv tayyor: {out}", "files": [out]}


@tool("files.unzip", "ZIP dan chiqarish", path=("string", False, "zip fayl"))
def files_unzip(api, a):
    p = resolve_file(api, a.get("path", ""))
    out = _ok(api.files_unzip(str(p)))
    api._ctx.folder = out
    return {"reply": f"Chiqarildi: {out}"}


@tool("files.backup", "Zaxira nusxa olish", paths=("array", False, "fayllar"))
def files_backup(api, a):
    out = _ok(api.files_backup(resolve_files(api, a.get("paths") or [])))
    return {"reply": f"Zaxira olindi ({len(out)}):\n{_names(out)}"}


@tool("files.versions", "Zaxira versiyalari", path=("string", False, "fayl"))
def files_versions(api, a):
    p = resolve_file(api, a.get("path", ""))
    vers = api.files_versions(str(p))
    if not vers:
        return {"reply": f"{p.name} uchun zaxira yo‘q. «zaxira nusxasini ol» deb yozing."}
    lines = [f"{i}. {v['name']}" for i, v in enumerate(vers[:10], 1)]
    return {"reply": f"{p.name} versiyalari (eng yangisi 1-):\n" + "\n".join(lines)}


@tool("files.restore", "Zaxiradan tiklash", risky=True, path=("string", False, "fayl"),
      version=("integer", False, "nechanchi versiya (1 = eng yangi)"))  # fmt: skip
def files_restore(api, a):
    p = resolve_file(api, a.get("path", ""))
    vers = api.files_versions(str(p))
    i = int(a.get("version") or 1)
    if not 1 <= i <= len(vers):
        raise ToolError(f"{p.name} uchun {i}-versiya yo‘q (jami {len(vers)})")
    r = _ok(api.files_restore(vers[i - 1]["path"], str(p)))
    return {"reply": f"Tiklandi: {p.name}. Hozirgi holati zaxiraga saqlandi: "
            f"{Path(r['previous_saved_as']).name or '—'}"}  # fmt: skip


@tool("files.tidy", "Papkani turlarga ajratish", risky=True, folder=("string", True, "papka"))
def files_tidy(api, a):
    folder = resolve_folder(api, a["folder"])
    counts = _ok(api.files_tidy(str(folder)))
    api._ctx.folder = str(folder)
    if not counts:
        return {"reply": "Tartiblanadigan fayl yo‘q."}
    return {"reply": f"{folder} tartiblandi: " + ", ".join(f"{k} — {v}" for k, v in counts.items())}


@tool("files.recycle", "Savatga o‘chirish", risky=True, paths=("array", False, "fayllar"))
def files_recycle(api, a):
    paths = resolve_files(api, a.get("paths") or [])
    n = _ok(api.files_recycle(paths))
    api._ctx.files = [p for p in api._ctx.files if p not in paths]
    return {"reply": f"{n} ta fayl Savatga o‘tkazildi (u yerdan tiklash mumkin)."}


@tool("files.pdf", "PDF ga aylantirish (ommaviy)", paths=("array", False, "fayllar"),
      folder=("string", False, "papkadagi barcha Office fayllar"))  # fmt: skip
def files_pdf(api, a):
    if a.get("folder"):
        folder = resolve_folder(api, a["folder"])
        r = api.files_search("", str(folder), "docx doc xlsx xls pptx ppt")
        paths = [f["path"] for f in r.get("files", []) if Path(f["path"]).parent == folder]
        api._ctx.folder = str(folder)
    else:
        paths = resolve_files(api, a.get("paths") or [])
    if not paths:
        raise ToolError("PDF qilinadigan Word/Excel/PowerPoint fayli topilmadi")
    snap = api.files_to_pdf(paths)
    if "id" not in snap:
        raise ToolError(snap.get("error", "Boshlanmadi"))
    return {"reply": f"{len(paths)} ta fayl PDF qilinmoqda — jarayon o‘ng panelda.", "task": snap}


# =====================================================================
# NEXVARA BI
# =====================================================================


def _dashboard(api, name: str) -> dict[str, Any]:
    items = api.bi_list()
    if not items:
        raise ToolError(
            "Saqlangan dashboard yo‘q. Avval «Savdo.xlsx dan dashboard yarat» deb yozing."
        )
    if not name or fold(name) in ("uni", "shuni", "dashboard", "shu dashboard"):
        hit = next((d for d in items if d["file"] == api._ctx.dashboard), None)
        if hit:
            return hit
        if len(items) == 1:
            return items[0]
        raise ToolError("Qaysi dashboard? " + ", ".join(f"«{d['name']}»" for d in items))
    key = fold(name)
    hits = [d for d in items if fold(d.get("name") or "") == key] or [
        d for d in items if key in fold(d.get("name") or "")]  # fmt: skip
    if not hits:
        raise ToolError(f"«{name}» dashboardi topilmadi. Bor: "
                        + ", ".join(f"«{d['name']}»" for d in items))  # fmt: skip
    return hits[0]


def _bi_cfg(api, d: dict[str, Any]) -> dict[str, Any]:
    opened = api.bi_open(d["file"])
    if not opened.get("ok"):
        raise ToolError(opened["error"])
    api._ctx.dashboard = d["file"]
    return opened["config"]


def _bi_columns(api, cfg: dict[str, Any]) -> list[str]:
    prev = api.bi_preview(cfg)
    if not prev.get("ok"):
        raise ToolError(prev["error"])
    return [c["name"] for c in prev["columns"]]


def _bi_save(api, cfg: dict[str, Any]) -> str:
    saved = api.bi_save(cfg)
    if not saved.get("ok"):
        raise ToolError(saved["error"])
    api._ctx.dashboard = saved["file"]
    return saved["file"]


def _iso(value: str) -> str:
    from nexvara.bi.data import parse_date

    d = parse_date(value)
    if d is None:
        raise ToolError(f"Sana tushunarsiz: «{value}» (masalan 2026-01-31 yoki 31.01.2026)")
    return d.isoformat()[:10]


def _bi_state(api, cfg: dict[str, Any], flt: str, a: dict[str, Any] | None = None):
    """'Toshkent' or 'Hudud=Toshkent' -> slicer state (the column is found by its values);
    date_from/date_to -> the date range."""
    a = a or {}
    state: dict[str, Any] = {"filters": {}, "page": 0}
    notes = []
    if a.get("date_from") or a.get("date_to"):
        if not cfg.get("date_col"):
            raise ToolError("Bu dashboardda sana ustuni yo‘q")
        if a.get("date_from"):
            state["date_from"] = _iso(a["date_from"])
        if a.get("date_to"):
            state["date_to"] = _iso(a["date_to"])
        notes.append(f"{state.get('date_from', '…')} — {state.get('date_to', '…')}")
    if a.get("page"):
        state["page"] = max(0, int(a["page"]) - 1)
    if not flt:
        return state, ", ".join(notes)
    from nexvara.bi.dash import compute

    col, _, val = flt.partition("=") if "=" in flt else ("", "", flt)
    res = compute(cfg, {}, table=api._bi_table(cfg))
    wanted = fold(val.strip())
    for c, values in res["slicers"].items():
        if col and fold(c) != fold(col.strip()):
            continue
        for v in values:
            if fold(str(v)) == wanted:
                state["filters"] = {c: [v]}
                return state, ", ".join([f"{c} = {v}", *notes])
    raise ToolError(f"Dashboardda «{flt}» qiymati topilmadi (filtr ustunlari: "
                    + ", ".join(res["slicers"]) + ")")  # fmt: skip


_VIEW = {"filter": ("string", False, "masalan Toshkent yoki Hudud=Toshkent"),
         "date_from": ("string", False, "sanadan"), "date_to": ("string", False, "sanagacha"),
         "page": ("integer", False, "sahifa raqami")}  # fmt: skip


@tool("bi.create", "Dashboard yaratish", file=("string", False, "ma’lumot fayli yoki papka"),
      name=("string", False, "saqlash nomi"))  # fmt: skip
def bi_create(api, a):
    v = a.get("file", "")
    src = Path(v) if v and Path(v).is_dir() else resolve_file(api, v)
    api._ctx.file = str(src) if src.is_file() else api._ctx.file
    if not a.get("name"):
        return {"reply": f"{src.name} dan dashboard tayyorlayapman — NEXVARA BI bo‘limi ochiladi.",
                "open_bi": str(src)}  # fmt: skip
    r = api.bi_auto(str(src))
    if not r.get("ok"):
        raise ToolError(r["error"])
    file = _bi_save(api, {**r["config"], "name": a["name"]})
    return {"reply": f"«{a['name']}» dashboardi yaratildi va saqlandi ({src.name}).",
            "bi_ui": {"open": file}}  # fmt: skip


@tool("bi.list", "Saqlangan dashboardlar")
def bi_list(api, a):
    items = api.bi_list()
    if not items:
        return {"reply": "Saqlangan dashboard yo‘q."}
    return {"reply": "Dashboardlar:\n" + "\n".join(
        f"• {d['name']} — {Path(str(d.get('source') or '')).name}" for d in items)}  # fmt: skip


@tool("bi.open", "Dashboardni ochish", name=("string", False, "dashboard nomi"), **_VIEW)
def bi_open(api, a):
    d = _dashboard(api, a.get("name", ""))
    state, note = _bi_state(api, _bi_cfg(api, d), a.get("filter", ""), a)
    return {"reply": f"«{d['name']}» dashboardi ochildi" + (f" ({note})" if note else "") + ".",
            "bi_ui": {"open": d["file"], "state": state}}  # fmt: skip


@tool("bi.summary", "Dashboard ko‘rsatkichlari", name=("string", False, "dashboard nomi"), **_VIEW)
def bi_summary(api, a):
    from nexvara.bi.dash import compute

    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    state, note = _bi_state(api, cfg, a.get("filter", ""), a)
    res = compute(cfg, state, table=api._bi_table(cfg))
    kpis = [w for w in res["widgets"] if w.get("type") == "kpi"]

    def num(w: dict[str, Any]) -> str:
        v = w.get("value")
        if not isinstance(v, int | float):
            return "—"
        text = f"{v:,.1f}" if w.get("unit") == "%" else f"{v:,.0f}"
        return text.replace(",", " ") + (" %" if w.get("unit") == "%" else "")

    lines = [f"• {w.get('title')}: {num(w)}" for w in kpis]
    head = f"«{d['name']}»" + (f" ({note})" if note else "") + f": {res['rows']} ta qator"
    return {"reply": head + ("\n" + "\n".join(lines) if lines else "")}


@tool("bi.export", "Dashboardni eksport qilish", name=("string", False, "dashboard nomi"),
      format=("string", True, "pdf, png, xlsx yoki csv"), **_VIEW)  # fmt: skip
def bi_export(api, a):
    fmt = fold(a["format"]).strip(". ")
    fmt = {"excel": "xlsx", "rasm": "png"}.get(fmt, fmt)
    if fmt not in ("pdf", "png", "xlsx", "csv"):
        raise ToolError("Format: PDF, PNG, Excel yoki CSV")
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    state, note = _bi_state(api, cfg, a.get("filter", ""), a)
    if fmt in ("xlsx", "csv"):
        r = api.bi_export(cfg, state, fmt)
        if not r.get("ok"):
            raise ToolError(r["error"])
        api._ctx.result = r["path"]
        return {"reply": f"Eksport qilindi: {r['path']}", "files": [r["path"]]}
    # PDF/PNG are drawn by the page itself: open it there and press export.
    return {"reply": f"«{d['name']}» {fmt.upper()} qilinmoqda — NEXVARA BI bo‘limida." +
            (f" ({note})" if note else ""),
            "bi_ui": {"open": d["file"], "state": state, "export": fmt}}  # fmt: skip


# ----- data steps (ETL): formula columns, joining/appending files, cleaning -----

_STEP_OPS = ("calc", "join", "append", "filter", "rename", "drop_col", "fill_null", "drop_null",
             "dedupe", "drop_empty", "set_type")  # fmt: skip


def _formula(expr: str, columns: list[str]) -> str:
    """'Daromad - Xarajat' -> '[Daromad] - [Xarajat]' (longest names first, already
    bracketed names are kept)."""
    if "[" in expr:
        return expr
    out = expr
    for c in sorted(columns, key=len, reverse=True):
        pat = re.compile(rf"(?<![\w\[]){re.escape(c)}(?![\w\]])", re.IGNORECASE)
        out = pat.sub(lambda _m, c=c: f"[{c}]", out)
    return out


@tool(
    "bi.add_step",
    "Dashboard ma’lumotiga qadam qo‘shish",
    name=("string", False, "dashboard"),
    op=("string", True, ", ".join(_STEP_OPS)),
    column=("string", False, "ustun"),
    new_name=("string", False, "yangi ustun nomi"),
    formula=("string", False, "masalan Daromad - Xarajat"),
    file=("string", False, "boshqa fayl"),
    on=("string", False, "qaysi ustun bo‘yicha birlashtirish"),
    cmp=("string", False, "=, !=, >, >=, <, <=, contains"),
    value=("string", False, "qiymat"),
    type=("string", False, "number, date, text"),
)
def bi_add_step(api, a):
    from nexvara.bi.data import describe_step

    op = a["op"]
    if op not in _STEP_OPS:
        raise ToolError("Qadam turi: " + ", ".join(_STEP_OPS))
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    columns = _bi_columns(api, cfg)
    step: dict[str, Any] = {"op": op}
    if op == "calc":
        if not a.get("new_name") or not a.get("formula"):
            raise ToolError(
                "Formula ustuni: nomi va formulasi kerak, masalan «Foyda = Daromad - Xarajat»"
            )
        step.update(name=a["new_name"], expr=_formula(a["formula"], columns))
    elif op in ("join", "append"):
        other = resolve_file(api, a.get("file", ""))
        step["file"] = str(other)
        if op == "join":
            if not a.get("on"):
                raise ToolError("Qaysi ustun bo‘yicha birlashtiray? Masalan «Mahsulot bo‘yicha»")
            step["on"] = _column(columns, a["on"])
    elif op in ("filter", "rename", "drop_col", "fill_null", "drop_null", "set_type"):
        step["col"] = _column(columns, a.get("column", ""))
        if op == "filter":
            cmp = {"teng": "=", "katta": ">", "kichik": "<", "ichida": "contains"}.get(
                fold(a.get("cmp", "")), a.get("cmp") or "=")  # fmt: skip
            step.update(cmp=cmp, value=a.get("value", ""))
        elif op == "rename":
            if not a.get("new_name"):
                raise ToolError("Yangi nomni yozing")
            step["name"] = a["new_name"]
        elif op == "fill_null":
            v = fold(a.get("value", ""))
            step["value"] = {"ortacha": "__mean__", "": "__zero__", "0": "__zero__"}.get(
                v, a["value"]
            )
        elif op == "set_type":
            t = fold(a.get("type") or a.get("value", ""))
            step["type"] = {"son": "number", "raqam": "number", "sana": "date",
                            "matn": "text"}.get(t, t)  # fmt: skip
    new = {**cfg, "steps": [*(cfg.get("steps") or []), step]}
    test = api.bi_preview(new)  # run it once: a bad formula or a missing file fails here
    if not test.get("ok"):
        raise ToolError(f"Qadam qo‘shilmadi: {test['error']}")
    file = _bi_save(api, new)
    note = " · ".join(test.get("notes") or [])
    return {"reply": f"«{d['name']}»: {describe_step(step)} ✓ ({test['total']} ta qator"
            + (f"; {note}" if note else "") + ")", "bi_ui": {"open": file}}  # fmt: skip


@tool("bi.steps", "Dashboard ma’lumot qadamlari", name=("string", False, "dashboard"))
def bi_steps(api, a):
    from nexvara.bi.data import describe_step

    d = _dashboard(api, a.get("name", ""))
    steps = _bi_cfg(api, d).get("steps") or []
    if not steps:
        return {"reply": f"«{d['name']}»da ma’lumot qadamlari yo‘q (asl fayl o‘zgarmagan holda)."}
    return {"reply": f"«{d['name']}» qadamlari:\n" + "\n".join(
        f"{i}. {describe_step(s)}" for i, s in enumerate(steps, 1))}  # fmt: skip


@tool("bi.remove_step", "Ma’lumot qadamini olib tashlash", name=("string", False, "dashboard"),
      number=("integer", True, "nechanchi qadam"))  # fmt: skip
def bi_remove_step(api, a):
    from nexvara.bi.data import describe_step

    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    steps = list(cfg.get("steps") or [])
    i = int(a["number"])
    if not 1 <= i <= len(steps):
        raise ToolError(f"{i}-qadam yo‘q (jami {len(steps)})")
    gone = steps.pop(i - 1)
    new = {**cfg, "steps": steps}
    test = api.bi_preview(new)
    if not test.get("ok"):
        raise ToolError(f"Olib tashlab bo‘lmaydi: keyingi qadamlar unga bog‘liq ({test['error']})")
    file = _bi_save(api, new)
    return {"reply": f"Olib tashlandi: {describe_step(gone)}", "bi_ui": {"open": file}}


# ----- widgets (charts, KPIs, tables) -----

_WIDGET_WORDS = {"ustun": "bar", "gistogram": "bar", "doira": "pie", "pirog": "pie",
                 "chiziq": "line", "grafik": "line", "nuqta": "scatter", "kpi": "kpi",
                 "korsatkich": "kpi", "jadval": "table"}  # fmt: skip
_TYPE_UZ = {"bar": "ustunli", "line": "chiziqli", "pie": "doiraviy", "scatter": "nuqtali",
            "kpi": "KPI", "table": "jadval"}  # fmt: skip
_AGG_UZ = {"ortacha": "avg", "orta": "avg", "soni": "count", "son": "count", "eng kichik": "min",
           "eng katta": "max", "yigindi": "sum", "jami": "sum", "summa": "sum"}  # fmt: skip


def _column(columns: list[str], wanted: str) -> str:
    w = fold(wanted).strip()
    hit = next((c for c in columns if fold(c) == w), None) or next(
        (c for c in columns if w and (w in fold(c) or fold(c) in w)), None)  # fmt: skip
    if hit is None:
        raise ToolError(f"«{wanted}» ustuni topilmadi. Ustunlar: " + ", ".join(columns))
    return hit


def _wtype(value: str) -> str:
    t = fold(value)
    t = next((v for k, v in _WIDGET_WORDS.items() if t.startswith(k)), t)
    if t not in _TYPE_UZ:
        raise ToolError("Vidjet turi: ustunli, chiziqli, doiraviy, nuqtali, KPI yoki jadval")
    return t


def _agg(value: str) -> str:
    v = fold(value).strip()
    v = _AGG_UZ.get(v, v) or "sum"
    if v not in ("sum", "avg", "count", "min", "max"):
        raise ToolError("Hisob: yig‘indi, o‘rtacha, soni, eng katta yoki eng kichik")
    return v


def _find_widget(cfg: dict[str, Any], ref: str) -> tuple[int, int]:
    """'3' (numbered across pages, as bi.widgets shows them) or a title fragment."""
    flat = [(p, i) for p, page in enumerate(cfg["pages"]) for i, _w in enumerate(page["widgets"])]
    if str(ref).strip().isdigit():
        n = int(ref)
        if not 1 <= n <= len(flat):
            raise ToolError(f"{n}-vidjet yo‘q (jami {len(flat)})")
        return flat[n - 1]
    key = fold(ref)
    for p, i in flat:
        if key and key in fold(str(cfg["pages"][p]["widgets"][i].get("title") or "")):
            return p, i
    raise ToolError(f"«{ref}» vidjeti topilmadi. «vidjetlarini ko‘rsat» deb yozing.")


@tool("bi.widgets", "Dashboard vidjetlari", name=("string", False, "dashboard"))
def bi_widgets(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    lines, n = [], 0
    for page in cfg["pages"]:
        lines.append(f"— {page.get('title') or 'Sahifa'}")
        for w in page["widgets"]:
            n += 1
            ys = w.get("y")
            what = ", ".join(ys) if isinstance(ys, list) else (ys or "")
            by = f" / {w['x']}" if w.get("x") else ""
            lines.append(f"{n}. {w.get('title') or '—'} ({_TYPE_UZ.get(w['type'], w['type'])}"
                         f"{': ' + what if what else ''}{by}, {w.get('agg', 'sum')})")  # fmt: skip
    return {"reply": f"«{d['name']}» vidjetlari:\n" + "\n".join(lines)}


@tool("bi.add_widget", "Dashboardga vidjet qo‘shish", name=("string", False, "dashboard nomi"),
      type=("string", True, "bar, line, pie, scatter, kpi yoki table"),
      x=("string", False, "qaysi ustun bo‘yicha"), y=("string", False, "qaysi raqam ustuni"),
      agg=("string", False, "sum, avg, count, min, max"), title=("string", False, "sarlavha"),
      page=("integer", False, "sahifa raqami"))  # fmt: skip
def bi_add_widget(api, a):
    import uuid

    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    columns = _bi_columns(api, cfg)
    typ = _wtype(a["type"])
    w: dict[str, Any] = {"id": uuid.uuid4().hex[:8], "type": typ, "agg": _agg(a.get("agg", ""))}
    if a.get("x"):
        w["x"] = _column(columns, a["x"])
    if a.get("y"):
        w["y"] = _column(columns, a["y"])
    elif typ != "table" and w["agg"] != "count":
        raise ToolError("Qaysi raqam ustuni? Masalan «Filial bo‘yicha Daromad ustunli diagramma»")
    if typ in ("bar", "pie", "line", "scatter") and "x" not in w:
        raise ToolError("Qaysi ustun bo‘yicha? Masalan «Filial bo‘yicha ...»")
    w["title"] = a.get("title") or " · ".join(str(v) for v in (w.get("y"), w.get("x")) if v)
    p = max(0, min(int(a.get("page") or 1) - 1, len(cfg["pages"]) - 1))
    cfg["pages"][p]["widgets"].append(w)
    file = _bi_save(api, cfg)
    return {"reply": f"«{d['name']}» dashboardiga qo‘shildi: {w['title']} ({_TYPE_UZ[typ]}).",
            "bi_ui": {"open": file}}  # fmt: skip


@tool(
    "bi.edit_widget",
    "Vidjetni tahrirlash",
    name=("string", False, "dashboard"),
    widget=("string", True, "raqami yoki sarlavhasidan so‘z"),
    title=("string", False, "yangi sarlavha"),
    type=("string", False, "yangi tur"),
    x=("string", False, "bo‘yicha ustun"),
    y=("string", False, "raqam ustuni"),
    agg=("string", False, "hisob"),
    top=("integer", False, "nechta eng katta qiymat"),
)
def bi_edit_widget(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    columns = _bi_columns(api, cfg)
    p, i = _find_widget(cfg, a["widget"])
    w = dict(cfg["pages"][p]["widgets"][i])
    changed = []
    if a.get("type"):
        w["type"] = _wtype(a["type"])
        changed.append(f"tur: {_TYPE_UZ[w['type']]}")
    if a.get("title"):
        w["title"] = a["title"]
        changed.append(f"sarlavha: {a['title']}")
    if a.get("x"):
        w["x"] = _column(columns, a["x"])
        changed.append(f"bo‘yicha: {w['x']}")
    if a.get("y"):
        w["y"] = _column(columns, a["y"])
        changed.append(f"qiymat: {w['y']}")
    if a.get("agg"):
        w["agg"] = _agg(a["agg"])
        changed.append(f"hisob: {w['agg']}")
    if a.get("top"):
        w["top"] = int(a["top"])
        changed.append(f"eng kattasi: {w['top']} ta")
    if not changed:
        raise ToolError("Nimani o‘zgartiray? Tur, sarlavha, ustun yoki hisobni yozing.")
    if w["type"] in ("bar", "pie", "line", "scatter") and not w.get("x"):
        raise ToolError("Bu turdagi diagrammaga «... bo‘yicha» ustuni kerak")
    cfg["pages"][p]["widgets"][i] = w
    from nexvara.bi.dash import compute_widget

    try:  # the new combination must still compute
        compute_widget(api._bi_table(cfg), w, cfg.get("date_col"))
    except (LookupError, ValueError, TypeError, KeyError) as e:
        raise ToolError(f"Bu o‘zgarish ishlamaydi: {e}") from e
    file = _bi_save(api, cfg)
    return {"reply": f"«{w.get('title')}» o‘zgardi: " + ", ".join(changed), "bi_ui": {"open": file}}


@tool("bi.remove_widget", "Vidjetni olib tashlash", name=("string", False, "dashboard"),
      widget=("string", True, "raqami yoki sarlavhasi"))  # fmt: skip
def bi_remove_widget(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    p, i = _find_widget(cfg, a["widget"])
    gone = cfg["pages"][p]["widgets"].pop(i)
    file = _bi_save(api, cfg)
    return {
        "reply": f"Olib tashlandi: {gone.get('title') or gone['type']}",
        "bi_ui": {"open": file},
    }


@tool("bi.add_page", "Dashboardga sahifa qo‘shish", name=("string", False, "dashboard"),
      title=("string", True, "sahifa nomi"))  # fmt: skip
def bi_add_page(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    cfg["pages"].append({"title": a["title"], "widgets": []})
    file = _bi_save(api, cfg)
    return {
        "reply": f"«{a['title']}» sahifasi qo‘shildi ({len(cfg['pages'])}-sahifa). Vidjet "
        f"qo‘shishda «{len(cfg['pages'])}-sahifaga» deb yozing.",
        "bi_ui": {"open": file},
    }


def _find_page(cfg: dict[str, Any], ref: str) -> int:
    """'2' (1-based) or a page title (exact, then a fragment) -> index."""
    pages = cfg["pages"]
    r = str(ref).strip()
    if r.isdigit():
        n = int(r)
        if not 1 <= n <= len(pages):
            raise ToolError(f"{n}-sahifa yo‘q (jami {len(pages)})")
        return n - 1
    key = fold(r)
    for exact in (True, False):
        for i, p in enumerate(pages):
            t = fold(str(p.get("title") or ""))
            if key and (t == key if exact else key in t):
                return i
    names = ", ".join(f"{i}. {p.get('title') or 'Sahifa'}" for i, p in enumerate(pages, 1))
    raise ToolError(f"«{ref}» sahifasi topilmadi. Sahifalar: {names}")


@tool("bi.move_widget", "Vidjetni boshqa sahifaga ko‘chirish", name=("string", False, "dashboard"),
      widget=("string", True, "vidjet raqami yoki sarlavhasi"),
      page=("string", True, "qaysi sahifaga: raqami yoki nomi"))  # fmt: skip
def bi_move_widget(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    p, i = _find_widget(cfg, a["widget"])
    to = _find_page(cfg, a["page"])
    w = cfg["pages"][p]["widgets"][i]
    title = w.get("title") or _TYPE_UZ.get(w["type"], w["type"])
    target = cfg["pages"][to].get("title") or f"{to + 1}-sahifa"
    if to == p:
        return {"reply": f"«{title}» allaqachon «{target}» sahifasida."}
    cfg["pages"][to]["widgets"].append(cfg["pages"][p]["widgets"].pop(i))
    file = _bi_save(api, cfg)
    return {"reply": f"«{title}» → «{target}» sahifasiga ko‘chirildi.",
            "bi_ui": {"open": file, "state": {"page": to}}}  # fmt: skip


@tool(
    "bi.delete_page",
    "Dashboard sahifasini o‘chirish",
    risky=True,
    name=("string", False, "dashboard"),
    page=("string", True, "sahifa raqami yoki nomi"),
)
def bi_delete_page(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    if len(cfg["pages"]) < 2:
        raise ToolError("Bu dashboardning yagona sahifasi — uni o‘chirib bo‘lmaydi.")
    i = _find_page(cfg, a["page"])
    gone = cfg["pages"].pop(i)
    file = _bi_save(api, cfg)
    n = len(gone.get("widgets") or [])
    return {"reply": f"«{gone.get('title') or f'{i + 1}-sahifa'}» sahifasi o‘chirildi"
            + (f" ({n} ta vidjeti bilan)." if n else "."), "bi_ui": {"open": file}}  # fmt: skip


@tool("bi.rename", "Dashboard nomini o‘zgartirish", name=("string", False, "dashboard"),
      new_name=("string", True, "yangi nom"))  # fmt: skip
def bi_rename(api, a):
    d = _dashboard(api, a.get("name", ""))
    cfg = _bi_cfg(api, d)
    if any(fold(x.get("name") or "") == fold(a["new_name"]) for x in api.bi_list()):
        raise ToolError(f"«{a['new_name']}» nomli dashboard allaqachon bor")
    file = _bi_save(api, {**cfg, "name": a["new_name"]})
    if Path(file) != Path(d["file"]):
        api.bi_delete(d["file"])
    return {"reply": f"Dashboard nomi: «{d['name']}» → «{a['new_name']}»", "bi_ui": {"open": file}}


@tool("bi.delete", "Dashboardni o‘chirish", risky=True, name=("string", True, "dashboard nomi"))
def bi_delete(api, a):
    d = _dashboard(api, a["name"])
    api.bi_delete(d["file"])
    return {"reply": f"«{d['name']}» dashboardi o‘chirildi."}


# =====================================================================
# Workflows
# =====================================================================


def _wf_engine(api):
    eng = api._wf()
    if eng is None:
        raise ToolError("Workflowlar bu rejimda o‘chirilgan.")
    return eng


def _workflow(api, name: str):
    eng = _wf_engine(api)
    flows = eng.store.all()
    if not flows:
        raise ToolError("Saqlangan workflow yo‘q.")
    key = fold(name or api._ctx.workflow)
    hits = [w for w in flows if fold(w.name) == key] or [w for w in flows if key and (
        key in fold(w.name) or fold(w.name) in key)]  # fmt: skip
    if not hits:
        raise ToolError(f"Qaysi workflow? «{name}» topilmadi. Saqlanganlari: "
                        + ", ".join(f"«{w.name}»" for w in flows))  # fmt: skip
    api._ctx.workflow = hits[0].name
    return hits[0]


def _active_run(api, wf) -> dict[str, Any]:
    for r in api.wf_active():
        if r.get("wf_id") == wf.id or r.get("name") == wf.name:
            return r
    raise ToolError(f"«{wf.name}» hozir bajarilmayapti.")


@tool("workflow.list", "Workflowlar ro‘yxati")
def wf_list(api, a):
    flows = api.wf_list()
    if not flows:
        return {"reply": "Saqlangan workflow yo‘q."}
    lines = []
    for w in flows:
        t = w["trigger"]
        when = {"daily": f"har kuni {t.get('time')}", "folder": f"papka: {t.get('folder')}"}.get(
            t.get("type"), "qo‘lda")  # fmt: skip
        last = (w.get("last_run") or {}).get("status", "")
        lines.append(
            f"• {w['name']} — {len(w['steps'])} qadam, {when}"
            + ("" if w["enabled"] else ", o‘chirilgan")
            + (f", oxirgi: {last}" if last else "")
        )
    return {"reply": "Workflowlar:\n" + "\n".join(lines)}


@tool("workflow.create", "Workflow yaratish", name=("string", True, "nomi"),
      steps=("array", True, "buyruqlar ketma-ketligi (oddiy o‘zbekcha)"),
      time=("string", False, "har kuni SS:DD da"), folder=("string", False, "kuzatiladigan papka"),
      retries=("integer", False, "qayta urinish 0–5"),
      on_error=("string", False, "stop yoki continue"))  # fmt: skip
def wf_create(api, a):
    steps = []
    for s in a["steps"]:
        s = s.strip()
        m = re.fullmatch(r"(\d+)\s*(soniya|sekund|daqiqa|minut)\w*\s+kut\w*", fold(s))
        if m:
            sec = int(m.group(1)) * (60 if m.group(2) in ("daqiqa", "minut") else 1)
            steps.append({"kind": "wait", "seconds": sec})
        elif re.fullmatch(r"(tasdiq\w*|menga sora\w*|sorab ol\w*)", fold(s)):
            steps.append({"kind": "approve", "text": "Davom etaymi?"})
        elif s:
            steps.append({"kind": "command", "text": s})
    trigger: dict[str, Any] = {"type": "manual"}
    if a.get("time"):
        trigger = {"type": "daily", "time": a["time"]}
    elif a.get("folder"):
        trigger = {"type": "folder", "folder": str(resolve_folder(api, a["folder"]))}
        for st in steps:  # "shu fayl"/"uni" in a folder workflow = the new file
            if st["kind"] == "command" and "{fayl}" not in st["text"]:
                st["text"] = re.sub(r"\b(shu faylni|shu fayl|uni)\b", "{fayl}", st["text"], count=1)
                if "{fayl}" not in st["text"]:
                    st["text"] = "{fayl} ni " + st["text"]
    data = {"name": a["name"], "steps": steps, "trigger": trigger,
            "retries": a.get("retries", 1), "on_error": a.get("on_error") or "stop"}  # fmt: skip
    existing = [w for w in _wf_engine(api).store.all() if fold(w.name) == fold(a["name"])]
    if existing:
        data["id"] = existing[0].id
    r = api.wf_save(data)
    if not r.get("ok"):
        raise ToolError(r["error"])
    api._ctx.workflow = a["name"]
    when = {"daily": f"har kuni soat {trigger.get('time')} da",
            "folder": f"{trigger.get('folder')} ga yangi fayl tushganda"}.get(trigger["type"],
                                                                             "qo‘lda")  # fmt: skip
    lines = "\n".join(f"{i}. " + (s.get("text") or f"{s.get('seconds')} soniya kutish")
                      for i, s in enumerate(steps, 1))  # fmt: skip
    verb = "yangilandi" if existing else "saqlandi"
    return {"reply": f"«{a['name']}» workflowi {verb} ({when}):\n{lines}"}


@tool("workflow.run", "Workflowni ishga tushirish", name=("string", False, "nomi"),
      file=("string", False, "fayl (papka workflowi uchun)"))  # fmt: skip
def wf_run(api, a):
    wf = _workflow(api, a.get("name", ""))
    file = str(resolve_file(api, a["file"])) if a.get("file") else (api._ctx.file or "")
    r = api.wf_run(wf.id, file if wf.trigger.get("type") == "folder" else "")
    if not r.get("ok"):
        raise ToolError(r["error"])
    return {"reply": f"«{wf.name}» workflowi boshlandi — jarayon o‘ng panelda.", "task": r["task"]}


@tool("workflow.pause", "Workflowni pauza qilish", name=("string", False, "nomi"))
def wf_pause(api, a):
    wf = _workflow(api, a.get("name", ""))
    api.wf_pause(_active_run(api, wf)["run_id"])
    return {"reply": f"«{wf.name}» pauzada. «davom ettir» deb yozing."}


@tool("workflow.resume", "Workflowni davom ettirish", name=("string", False, "nomi"))
def wf_resume(api, a):
    wf = _workflow(api, a.get("name", ""))
    api.wf_resume(_active_run(api, wf)["run_id"])
    return {"reply": f"«{wf.name}» davom etmoqda."}


@tool("workflow.approve", "Workflow qadamini tasdiqlash", name=("string", False, "nomi"))
def wf_approve(api, a):
    wf = _workflow(api, a.get("name", ""))
    if not api.wf_approve(_active_run(api, wf)["run_id"]):
        raise ToolError(f"«{wf.name}» hozir tasdiq kutmayapti.")
    return {"reply": f"«{wf.name}»: tasdiqlandi, davom etadi."}


@tool("workflow.stop", "Workflowni to‘xtatish", name=("string", False, "nomi"))
def wf_stop(api, a):
    wf = _workflow(api, a.get("name", ""))
    run = _active_run(api, wf)
    api.cancel_task(run.get("task_id", ""))
    return {"reply": f"«{wf.name}» to‘xtatildi."}


@tool("workflow.enable", "Workflowni yoqish/o‘chirish", name=("string", False, "nomi"),
      enabled=("boolean", True, "yoqilsinmi"))  # fmt: skip
def wf_enable(api, a):
    wf = _workflow(api, a.get("name", ""))
    data = {**wf.to_dict(), "enabled": bool(a["enabled"])}
    r = api.wf_save(data)
    if not r.get("ok"):
        raise ToolError(r["error"])
    return {
        "reply": f"«{wf.name}» "
        + ("yoqildi." if a["enabled"] else "o‘chirildi (jadval va papka kuzatuvi to‘xtaydi).")
    }


@tool("workflow.history", "Workflow tarixi", name=("string", False, "nomi"))
def wf_history(api, a):
    wf = _workflow(api, a.get("name", ""))
    runs = api.wf_runs(wf.id)[:10]
    if not runs:
        return {"reply": f"«{wf.name}» hali ishga tushmagan."}
    import time as _t

    lines = [f"• {_t.strftime('%d.%m %H:%M', _t.localtime(r['started']))} — {r['status']}"
             f" ({r.get('trigger', '')})" for r in runs]  # fmt: skip
    return {"reply": f"«{wf.name}» tarixi:\n" + "\n".join(lines)}


@tool("workflow.delete", "Workflowni o‘chirish", risky=True, name=("string", True, "nomi"))
def wf_delete(api, a):
    wf = _workflow(api, a["name"])
    api.wf_delete(wf.id)
    api._ctx.workflow = ""
    return {"reply": f"«{wf.name}» workflowi o‘chirildi."}


# =====================================================================
# Settings (never API keys: those are typed only into Settings → AI)
# =====================================================================

# key -> (label, type, (min, max) or choices)
SETTINGS: dict[str, tuple[str, str, Any]] = {
    "theme": ("Mavzu", "choice", ("dark", "light")),
    "test_count": ("Savollar soni (sukut)", "int", (1, 60)),
    "test_variants": ("Variantlar soni (sukut)", "int", (1, 6)),
    "keep_office_open": ("Office oynasi ochiq qolsin", "bool", None),
    "ai.enabled": ("AI yoqilgan", "bool", None),
    "ai.provider": ("Asosiy AI provayder", "choice", ("openai", "anthropic", "gemini", "deepseek")),
    "ai.daily_budget_usd": ("Kunlik AI limiti, $", "float", (0, 1000)),
    "ai.monthly_budget_usd": ("Oylik AI limiti, $", "float", (0, 10000)),
    "ai.confirm_over_usd": ("Shundan qimmat so‘rovda so‘rash, $", "float", (0, 100)),
    "ai.send_textbook_text": ("Darslik parchalarini AI’ga yuborish", "bool", None),
    "ai.free_mode": ("Bepul rejim (Gemini bepul darajasi)", "bool", None),
    "remote.port": ("Telefon ulanish porti", "int", (1024, 65535)),
    "update.channel": ("Yangilanish kanali", "str", None),
    "update.auto_check": ("Yangilanishni o‘zi tekshirsin", "bool", None),
    "sync.enabled": ("Sinxronlash yoqilgan", "bool", None),
    "sync.folder": ("Sinxronlash papkasi", "str", None),
    "sync.google_drive": ("Google Drive orqali sinxronlash", "bool", None),
}


def _get(settings: dict[str, Any], key: str) -> Any:
    cur: Any = settings
    for part in key.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def _show(v: Any) -> str:
    if isinstance(v, bool):
        return "ha" if v else "yo‘q"
    return {"dark": "qorong‘i", "light": "yorug‘"}.get(v, str(v)) if v != "" else "—"


@tool("settings.show", "Sozlamalarni ko‘rsatish")
def settings_show(api, a):
    s = api.get_settings()
    lines = [f"• {label}: {_show(_get(s, k))}" for k, (label, _t, _r) in SETTINGS.items()]
    return {"reply": "Sozlamalar:\n" + "\n".join(lines) +
            "\n\nAI kalitlari faqat Sozlamalar → AI bo‘limida kiritiladi."}  # fmt: skip


@tool("settings.set", "Sozlamani o‘zgartirish", key=("string", True, ", ".join(SETTINGS)),
      value=("string", True, "yangi qiymat"))  # fmt: skip
def settings_set(api, a):
    key = a["key"]
    if key not in SETTINGS:
        raise ToolError(f"«{key}» sozlamasini chatdan o‘zgartirib bo‘lmaydi.")
    label, typ, rng = SETTINGS[key]
    raw = a["value"]
    f = fold(raw).strip(" .")
    try:
        if typ == "bool":
            value: Any = f in ("true", "1", "ha", "yoqilsin", "on", "qolsin", "ruxsat")
        elif typ == "int":
            value = int(re.search(r"-?\d+", raw).group())
        elif typ == "float":
            value = float(re.search(r"\d+(?:[.,]\d+)?", raw).group().replace(",", "."))
        elif typ == "choice":
            value = {"yorug": "light", "qorongi": "dark", "oq": "light", "qora": "dark",
                     "claude": "anthropic", "chatgpt": "openai"}.get(f, f)  # fmt: skip
            if value not in rng:
                raise ValueError
        else:
            value = raw.strip().strip('«»"')
    except (AttributeError, ValueError):
        raise ToolError(f"{label}: «{raw}» qiymati tushunarsiz") from None
    if typ in ("int", "float") and not rng[0] <= value <= rng[1]:
        raise ToolError(f"{label}: {rng[0]}–{rng[1]} oralig‘ida bo‘lsin")
    if key == "ai.enabled" and value and not api._ai_has_key():
        raise ToolError("AI’ni yoqish uchun avval Sozlamalar → AI bo‘limida kalit kiriting.")
    parts = key.split(".")
    change: dict[str, Any] = {parts[-1]: value}
    for p in reversed(parts[:-1]):
        change = {p: change}
    r = api.save_settings(change)
    if not r.get("ok"):
        raise ToolError(r["error"])
    out = {"reply": f"{label}: {_show(value)} ✓"}
    if key == "theme":
        out["theme"] = value
    return out


@tool("settings.update_check", "Yangilanishni tekshirish")
def update_check(api, a):
    r = api.update_check()
    if not r.get("ok"):
        raise ToolError(r["error"])
    c = r["check"]
    if c["available"]:
        return {"reply": f"Yangi versiya bor: {c['version']}. {c.get('notes', '')}\n"
                "O‘rnatish uchun Sozlamalar → Versiya va yangilanish → «O‘rnatish»."}  # fmt: skip
    return {"reply": f"Eng so‘nggi versiya o‘rnatilgan ({r['current']}) ✓"}


@tool("sync.now", "Sinxronlash")
def sync_now(api, a):
    r = api.sync_now()
    if not r.get("ok"):
        raise ToolError(r["error"])
    return {"reply": r["summary"]}


# =====================================================================
# Pass-through to the offline command pipeline (Office, tests, topics ...)
# =====================================================================


@tool("nexvara.command", "Buyruq", text=("string", True, "ilova tushunadigan o‘zbekcha buyruq"))
def command(api, a):
    out = api._chat_inner(a["text"], _use_ai=False)
    if out.get("unhandled"):
        raise ToolError(f"Buni bajara olmadim: «{a['text']}»")
    return out


def run(api: Any, call: ToolCall) -> dict[str, Any]:
    """Validate and run one call (the caller already handled confirmation)."""
    call = validate(call)
    try:
        return TOOLS[call.tool].run(api, call.args)
    except ToolError:
        raise
    except (OSError, ValueError, RuntimeError, LookupError) as e:
        raise ToolError(str(e) or type(e).__name__) from e
