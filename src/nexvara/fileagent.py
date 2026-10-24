"""File Agent: search, inspect, copy/move/rename, ZIP, backup/restore, tidy a folder,
delete to the Recycle Bin, and Office -> PDF in bulk.

Safety rules (spec 10-11): nothing is ever overwritten (a free name is chosen instead),
deleting goes to the Recycle Bin, restoring first backs up the current file, and every
change is written to D:\\NEXVARA\\logs\\file-ops.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.knowledge.textnorm import fold

MAX_RESULTS = 300
MAX_DIRS = 6000
_SKIP = {
    "$recycle.bin", "system volume information", "windows", "program files",
    "program files (x86)", "programdata", "appdata", ".git", ".venv", "node_modules",
    "__pycache__", "recovery", "perflogs",
}  # fmt: skip

# Folder names used by "tidy": extension -> subfolder.
CATEGORIES = {
    "Hujjatlar": (".doc", ".docx", ".rtf", ".odt", ".txt"),
    "Jadvallar": (".xls", ".xlsx", ".xlsm", ".csv", ".ods"),
    "Taqdimotlar": (".ppt", ".pptx", ".odp"),
    "PDF": (".pdf",),
    "Rasmlar": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff"),
    "Arxivlar": (".zip", ".rar", ".7z"),
    "Video va audio": (".mp4", ".avi", ".mkv", ".mov", ".mp3", ".wav", ".m4a", ".ogg"),
    "Dasturlar": (".exe", ".msi"),
}
PDF_FROM = (".doc", ".docx", ".rtf", ".xls", ".xlsx", ".xlsm", ".csv", ".ppt", ".pptx")


@dataclass
class FileInfo:
    path: str
    name: str
    folder: str
    ext: str
    size: int
    modified: float
    created: float

    @classmethod
    def of(cls, p: Path) -> FileInfo:
        st = p.stat()
        return cls(str(p), p.name, str(p.parent), p.suffix.lower(), st.st_size, st.st_mtime,
                   st.st_ctime)  # fmt: skip


# ---------------- log ----------------


def log_path() -> Path:
    return config.data_dir() / "logs" / "file-ops.jsonl"


def log(action: str, **details: Any) -> None:
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps({"ts": time.time(), "action": action, **details}, ensure_ascii=False) + "\n"
        )


def recent_log(limit: int = 100) -> list[dict[str, Any]]:
    p = log_path()
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


# ---------------- search & info ----------------


def default_roots() -> list[Path]:
    from nexvara.agent.files import search_roots

    return search_roots()


def search(
    query: str,
    folder: str | Path | None = None,
    exts: tuple[str, ...] = (),
    limit: int = MAX_RESULTS,
) -> list[FileInfo]:
    """Files whose name contains every word of `query` (Uzbek letters folded), newest first."""
    words = [w for w in fold(query or "").split() if w]
    roots = [Path(folder)] if folder else default_roots()
    exts = tuple(e.lower() if e.startswith(".") else "." + e.lower() for e in exts)
    found: list[FileInfo] = []
    seen: set[str] = set()
    dirs = 0
    for root in roots:
        stack = [root]
        while stack and dirs < MAX_DIRS and len(found) < limit * 3:
            d = stack.pop()
            dirs += 1
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name.lower() not in _SKIP and not e.name.startswith("."):
                            stack.append(Path(e.path))
                        continue
                    name = fold(e.name)
                    if words and not all(w in name for w in words):
                        continue
                    if exts and not e.name.lower().endswith(exts):
                        continue
                    key = e.path.lower()
                    if key not in seen:
                        seen.add(key)
                        found.append(FileInfo.of(Path(e.path)))
                except OSError:
                    continue
    found.sort(key=lambda f: -f.modified)
    return found[:limit]


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def info(path: str | Path) -> dict[str, Any]:
    p = _existing(path)
    d = asdict(FileInfo.of(p))
    d["sha256"] = sha256(p)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as z:
            d["zip_entries"] = len(z.infolist())
    return d


# ---------------- safe file operations ----------------


def _existing(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute() or not p.exists():
        raise FileNotFoundError(f"Topilmadi: {path}")
    return p


def free_name(target: Path) -> Path:
    """'Hisobot.xlsx' -> 'Hisobot (2).xlsx' if taken; never overwrite."""
    if not target.exists():
        return target
    for i in range(2, 10000):
        cand = target.with_name(f"{target.stem} ({i}){target.suffix}")
        if not cand.exists():
            return cand
    raise RuntimeError("bo‘sh nom topilmadi")


def copy_to(paths: list[str], folder: str | Path) -> list[str]:
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for src in map(_existing, paths):
        target = free_name(dest / src.name)
        if src.is_dir():
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
        log("copy", src=str(src), dst=str(target))
        out.append(str(target))
    return out


def copy_as(path: str, folder: str | Path, new_name: str = "") -> str:
    """«beton sinovi deb D ga saqla»: a copy under a new name; the original and anything
    already in the folder stay untouched."""
    src = _existing(path)
    new_name = Path(new_name.strip()).name if new_name.strip() else src.name
    if any(c in _BAD_NAME for c in new_name) or new_name in (".", ".."):
        raise ValueError('Nomda ruxsat etilmagan belgi bor: < > : " / \\ | ? *')
    if Path(new_name).suffix.lower() != src.suffix.lower():
        new_name += src.suffix  # the user typed only a name: keep the extension
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    target = free_name(dest / new_name)
    shutil.copy2(src, target)
    log("copy", src=str(src), dst=str(target))
    return str(target)


def move_to(paths: list[str], folder: str | Path) -> list[str]:
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for src in map(_existing, paths):
        if src.parent.resolve() == dest.resolve():
            out.append(str(src))
            continue
        target = free_name(dest / src.name)
        shutil.move(str(src), str(target))
        log("move", src=str(src), dst=str(target))
        out.append(str(target))
    return out


_BAD_NAME = set('<>:"/\\|?*')


def rename(path: str, new_name: str) -> str:
    src = _existing(path)
    new_name = new_name.strip()
    if not new_name or any(c in _BAD_NAME for c in new_name) or new_name in (".", ".."):
        raise ValueError('Nomda ruxsat etilmagan belgi bor: < > : " / \\ | ? *')
    if not Path(new_name).suffix and src.suffix:
        new_name += src.suffix  # the user typed only a name: keep the extension
    target = src.with_name(new_name)
    if target.exists() and target.resolve() != src.resolve():
        raise FileExistsError(f"«{new_name}» nomli fayl allaqachon bor")
    src.rename(target)
    log("rename", src=str(src), dst=str(target))
    return str(target)


def rename_batch(paths: list[str], pattern: str) -> list[str]:
    """'Hisobot_{n}' -> Hisobot_1.xlsx, Hisobot_2.xlsx ... (in the given order)."""
    if "{n}" not in pattern:
        pattern += "_{n}"
    out = []
    width = len(str(len(paths)))
    for i, p in enumerate(paths, start=1):
        src = _existing(p)
        name = pattern.replace("{n}", str(i).zfill(width)) + src.suffix
        target = free_name(src.with_name(name))
        out.append(rename(str(src), target.name))
    return out


def make_zip(paths: list[str], out: str | Path | None = None) -> str:
    items = list(map(_existing, paths))
    if not items:
        raise ValueError("fayl tanlanmagan")
    target = Path(out) if out else items[0].parent / f"Arxiv-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    target = free_name(target)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for p in items:
            if p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        z.write(f, Path(p.name) / f.relative_to(p))
            else:
                z.write(p, p.name)
    log("zip", files=[str(p) for p in items], dst=str(target))
    return str(target)


def unzip(path: str, dest: str | Path | None = None) -> str:
    """Extract into a new folder next to the archive. Entries that would land outside it
    ('../x', absolute paths) are refused."""
    src = _existing(path)
    folder = free_name(Path(dest) if dest else src.with_suffix(""))
    folder.mkdir(parents=True)
    base = folder.resolve()
    with zipfile.ZipFile(src) as z:
        for m in z.infolist():
            target = (folder / m.filename).resolve()
            if base not in target.parents and target != base:
                raise ValueError(f"Xavfli arxiv: «{m.filename}» papkadan tashqariga chiqadi")
        z.extractall(folder)
    log("unzip", src=str(src), dst=str(folder))
    return str(folder)


# ---------------- backup, versions, restore ----------------


def backup_dir() -> Path:
    return config.data_dir() / "Zaxira" / "Fayllar"


def backup(paths: list[str]) -> list[str]:
    """Copy into Zaxira\\Fayllar\\<name>\\<time>_<name>: every backup is a version."""
    out = []
    for src in map(_existing, paths):
        if not src.is_file():
            continue
        folder = backup_dir() / _key(src)
        folder.mkdir(parents=True, exist_ok=True)
        target = free_name(folder / f"{time.strftime('%Y%m%d-%H%M%S')}_{src.name}")
        shutil.copy2(src, target)
        (folder / "asl-joyi.txt").write_text(str(src), encoding="utf-8")
        log("backup", src=str(src), dst=str(target))
        out.append(str(target))
    return out


def _key(src: Path) -> str:
    """One backup folder per original file (same name in different folders kept apart)."""
    digest = hashlib.sha1(str(src.resolve()).lower().encode("utf-8")).hexdigest()[:8]
    return f"{src.stem}-{digest}"


def versions(path: str) -> list[dict[str, Any]]:
    folder = backup_dir() / _key(Path(path))
    if not folder.is_dir():
        return []
    out = [
        {"path": str(p), "name": p.name, "size": p.stat().st_size, "modified": p.stat().st_mtime}
        for p in folder.iterdir()
        if p.is_file() and p.name != "asl-joyi.txt"
    ]
    return sorted(out, key=lambda v: -v["modified"])


def restore(version_path: str, original: str) -> dict[str, str]:
    """Put a backup back in place. The current file is backed up first, so nothing is lost."""
    ver = _existing(version_path)
    if backup_dir().resolve() not in ver.resolve().parents:
        raise ValueError("bu NEXVARA zaxirasi emas")
    orig = Path(original)
    saved = backup([str(orig)])[0] if orig.is_file() else ""
    shutil.copy2(ver, orig)
    log("restore", src=str(ver), dst=str(orig), previous=saved)
    return {"restored": str(orig), "previous_saved_as": saved}


# ---------------- tidy a folder ----------------


def tidy_plan(folder: str | Path) -> list[dict[str, str]]:
    """Which top-level files would move to which subfolder (nothing is moved yet)."""
    root = _existing(folder)
    if not root.is_dir():
        raise ValueError("papka emas")
    plan = []
    for p in sorted(root.iterdir()):
        if (
            not p.is_file()
            or p.name.startswith(("~$", "."))
            or p.suffix.lower() in (".lnk", ".ini")
        ):
            continue
        cat = next((c for c, exts in CATEGORIES.items() if p.suffix.lower() in exts), "Boshqa")
        plan.append({"path": str(p), "name": p.name, "to": cat})
    return plan


def tidy(folder: str | Path) -> dict[str, int]:
    root = _existing(folder)
    counts: dict[str, int] = {}
    for item in tidy_plan(root):
        move_to([item["path"]], root / item["to"])
        counts[item["to"]] = counts.get(item["to"], 0) + 1
    return counts


# ---------------- delete (Recycle Bin) ----------------


def recycle(paths: list[str]) -> int:
    """Send to the Recycle Bin (can be restored from there). Never a permanent delete."""
    from win32com.shell import shell, shellcon

    items = [str(_existing(p)) for p in paths]
    if not items:
        return 0
    flags = (
        shellcon.FOF_ALLOWUNDO | shellcon.FOF_NOCONFIRMATION | shellcon.FOF_SILENT
        | shellcon.FOF_NOERRORUI
    )  # fmt: skip
    rc, aborted = shell.SHFileOperation((0, shellcon.FO_DELETE, "\0".join(items), None, flags))
    if rc != 0 or aborted:
        raise OSError(f"Savatga o‘tkazib bo‘lmadi (kod {rc})")
    log("recycle", files=items)
    return len(items)


# ---------------- Office -> PDF ----------------


def combine_workbooks(task: Any, paths: list[str], keep_open: bool = True) -> dict[str, Any]:
    """«A.xlsx va B.xlsx ni bitta faylga varaq qilib yig‘»: a new workbook next to the first
    file, one sheet per file (its first sheet, named after the file). Visible Excel; the
    original files are opened read-only and closed unchanged."""
    from nexvara.skills.excel.bridge import ExcelSession

    items = [_existing(p) for p in paths]
    out = free_name(items[0].parent / f"Yig‘ma_{time.strftime('%Y%m%d-%H%M%S')}.xlsx")
    names: list[str] = []
    with ExcelSession(visible=True, keep_open=keep_open) as xl:
        book = xl.new_workbook()
        first_blank = book.Worksheets(1)
        for p in items:
            task.check_cancelled()
            with task.step(f"Qo‘shish: {p.name}") as s:
                src = xl.app.Workbooks.Open(str(p.resolve()), 0, True)  # UpdateLinks, ReadOnly
                try:
                    sheet = src.Worksheets(1)
                    sheet.Copy(None, book.Worksheets(book.Worksheets.Count))  # (Before, After)
                    new = book.Worksheets(book.Worksheets.Count)
                    base = re.sub(r"[\\/?*\[\]:]", " ", p.stem).strip()[:31] or "Varaq"
                    name, n = base, 2
                    taken = {book.Worksheets(i).Name for i in range(1, book.Worksheets.Count)}
                    while name in taken:
                        name, n = f"{base[:28]} ({n})", n + 1
                    new.Name = name
                    names.append(name)
                    s.detail = f"{new.UsedRange.Rows.Count} qator"
                finally:
                    src.Close(False)
        xl.app.DisplayAlerts = False
        first_blank.Delete()
        xl.app.DisplayAlerts = True
        book.Worksheets(1).Activate()
        with task.step("Saqlash") as s:
            saved = xl.save_as(book, out)
            s.detail = saved.name
    log("combine", files=[str(p) for p in items], dst=str(saved))
    return {"path": str(saved), "files": [str(saved)],
            "report": [f"{len(names)} ta varaq: " + ", ".join(names)]}  # fmt: skip


def convert_to_pdf(task: Any, paths: list[str], keep_open: bool = False) -> dict[str, Any]:
    """Each Word/Excel/PowerPoint file becomes a PDF next to it (a free name if taken)."""
    from nexvara.skills.excel import ops as xl_ops
    from nexvara.skills.excel.bridge import ExcelSession
    from nexvara.skills.powerpoint import ops as ppt_ops
    from nexvara.skills.powerpoint.ops import PowerPointSession
    from nexvara.skills.word import ops as word_ops
    from nexvara.skills.word.ops import WordSession

    groups: dict[str, list[Path]] = {"word": [], "excel": [], "ppt": []}
    skipped = []
    for p in map(Path, paths):
        ext = p.suffix.lower()
        if not p.is_file() or ext not in PDF_FROM:
            skipped.append(p.name)
        elif ext in (".doc", ".docx", ".rtf"):
            groups["word"].append(p)
        elif ext in (".ppt", ".pptx"):
            groups["ppt"].append(p)
        else:
            groups["excel"].append(p)
    made: list[str] = []
    failed: list[str] = []

    def target(p: Path) -> Path:
        return free_name(p.with_suffix(".pdf"))

    if groups["word"]:
        with (
            task.step(f"Word → PDF ({len(groups['word'])} ta)") as s,
            WordSession(visible=False, keep_open=False) as w,
        ):
            for p in groups["word"]:
                task.check_cancelled()
                try:
                    doc = w.open_document(p)
                    made.append(str(word_ops.export_pdf(doc, target(p))))
                    doc.Close(0)
                except Exception as e:  # one broken file must not stop the rest
                    failed.append(f"{p.name}: {e}")
                s.detail = f"{len(made)} ta tayyor"
    if groups["excel"]:
        with (
            task.step(f"Excel → PDF ({len(groups['excel'])} ta)") as s,
            ExcelSession(visible=False, keep_open=False) as x,
        ):
            for p in groups["excel"]:
                task.check_cancelled()
                try:
                    wb = x.open_workbook(p)
                    made.append(str(xl_ops.export_pdf(wb, target(p))))
                    wb.Close(False)
                except Exception as e:
                    failed.append(f"{p.name}: {e}")
                s.detail = f"{len(made)} ta tayyor"
    if groups["ppt"]:
        with (
            task.step(f"PowerPoint → PDF ({len(groups['ppt'])} ta)") as s,
            PowerPointSession(visible=True, keep_open=False) as pp,
        ):
            for p in groups["ppt"]:
                task.check_cancelled()
                try:
                    pres = pp.open_presentation(p)
                    made.append(str(ppt_ops.export_pdf(pres, target(p))))
                    pres.Close()
                except Exception as e:
                    failed.append(f"{p.name}: {e}")
                s.detail = f"{len(made)} ta tayyor"
    with task.step("Tekshirish") as s:
        ok = [m for m in made if Path(m).is_file() and Path(m).stat().st_size > 0]
        s.detail = f"{len(ok)}/{len(made)} PDF mavjud"
        if len(ok) != len(made):
            raise RuntimeError("Ba’zi PDF fayllar yaratilmadi")
    log("pdf", files=[str(p) for p in paths], made=made, failed=failed)
    report = [f"{len(made)} ta PDF yaratildi"]
    if skipped:
        report.append("O‘tkazib yuborildi (Office fayli emas): " + ", ".join(skipped))
    if failed:
        report.append("Xato: " + "; ".join(failed))
    return {"report": report, "files": made, "path": made[0] if made else ""}


# ---------------- an answer from the chat into a new Excel / Word file ----------------

_Q_LINE = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*(.+)$")
_OPT_LINE = re.compile(r"^\s*([A-Da-d])\s*[).]\s*(.+)$")
_KEY_LINE = re.compile(r"^\s*(?:to[‘’']?g[‘’']?ri\s+)?javob\w*\s*[:\-–]\s*([A-Da-d])\b", re.I)


def _clean_line(line: str) -> str:
    return re.sub(r"^[#>*\s]+|\*\*", "", line).strip()


def test_rows(text: str) -> list[list[str]] | None:
    """«1. Savol / A) … B) … / Javob: B» -> rows (№, Savol, A, B, C, D, Javob); None when the
    text is not a test (fewer than two numbered questions with options)."""
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        if m := _Q_LINE.match(line):
            rows.append([m.group(1), m.group(2).strip(), "", "", "", "", ""])
        elif rows and (k := _KEY_LINE.match(line)):
            rows[-1][6] = k.group(1).upper()
        elif rows and (o := _OPT_LINE.match(line)):
            rows[-1][2 + "ABCD".index(o.group(1).upper())] = o.group(2).strip()
        elif rows and not any(rows[-1][2:6]):
            rows[-1][1] += " " + line  # the question continues on the next line
    if sum(1 for r in rows if any(r[2:6])) < 2:
        return None
    return [["№", "Savol", "A", "B", "C", "D", "Javob"], *rows]


_NUMBER = re.compile(r"^-?\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?$|^-?\d+(?:[.,]\d+)?$")


def _cell(v: str) -> Any:
    v = v.strip().strip("*").strip()
    if _NUMBER.match(v):
        n = v.replace(" ", "").replace(" ", "").replace(",", ".")
        return float(n) if "." in n else int(n)
    return v


def grid_rows(text: str) -> list[list[Any]] | None:
    """A table in the text — tab-separated lines or a Markdown «| a | b |» table — as rows of
    cells (numbers as numbers, «=B2*C2» stays a formula). Live 2026-10-24: an AI-written
    sales table landed in one «Matn» column, so its formulas never worked."""
    rows: list[list[Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "\t" in line:
            cells = line.split("\t")
        elif line.startswith("|") and line.count("|") >= 2:
            cells = line.strip("|").split("|")
            if all(re.fullmatch(r"\s*:?-{2,}:?\s*", c) for c in cells):
                continue  # the |---|---| separator
        else:
            continue
        rows.append([_cell(c) for c in cells])
    if len(rows) < 2 or max(len(r) for r in rows) < 2:
        return None
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def write_to_office(task: Any, text: str, app: str, title: str = "",
                    keep_open: bool = True) -> dict[str, Any]:  # fmt: skip
    """«Excel’ni ochib o‘sha yerga yoz»: the text (usually NEXVARA's last answer) into a new
    visible Excel or Word file in Documents/NEXVARA; a test becomes a table."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Yoziladigan matn yo‘q")
    title = (title or "NEXVARA").strip()[:60]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[\/:*?\"<>|]", " ", title).strip() or "NEXVARA"
    folder = Path.home() / "Documents" / "NEXVARA"
    lines = [_clean_line(x) for x in text.splitlines()]
    table = test_rows(text)
    if app == "excel":
        from nexvara.skills.excel import ops as xl_ops
        from nexvara.skills.excel.bridge import ExcelSession

        grid = None if table else grid_rows(text)
        rows = table or grid or [["Matn"], *[[x] for x in lines if x]]
        out = free_name(folder / f"{safe} {stamp}.xlsx")
        with ExcelSession(visible=True, keep_open=keep_open) as xl:
            with task.step("Excel’ga yozish") as s:
                book = xl.new_workbook()
                ws = book.Worksheets(1)
                rng = xl_ops.write_rows(ws, rows)
                ws.Rows(1).Font.Bold = True
                if grid:
                    rng.Columns.AutoFit()
                else:
                    rng.WrapText = True
                    rng.VerticalAlignment = -4160  # xlTop
                    widths = [5, 60, 25, 25, 25, 25, 8] if table else [100]
                    for i, w in enumerate(widths, start=1):
                        ws.Columns(i).ColumnWidth = w
                s.detail = f"{len(rows) - 1} qator" + (" (test jadvali)" if table else "")
            with task.step("Saqlash") as s:
                saved = xl.save_as(book, out)
                s.detail = saved.name
            xl.show()
    elif app == "word":
        from nexvara.skills.word import ops as wd_ops

        out = free_name(folder / f"{safe} {stamp}.docx")
        with wd_ops.WordSession(visible=True, keep_open=keep_open) as wd:
            with task.step("Word’ga yozish") as s:
                doc = wd.new_document()
                wd_ops.add_heading(doc, title, 1)
                block: list[str] = []  # consecutive table lines → a real Word table

                def flush() -> None:
                    grid = grid_rows("\n".join(block))
                    if grid:
                        wd_ops.add_table(doc, [[str(c) for c in r] for r in grid])
                    else:
                        for b in block:
                            wd_ops.add_paragraph(doc, _clean_line(b))
                    block.clear()

                for raw in text.splitlines():
                    if "\t" in raw or raw.strip().startswith("|"):
                        block.append(raw)
                        continue
                    if block:
                        flush()
                    if line := _clean_line(raw):
                        wd_ops.add_paragraph(doc, line)
                if block:
                    flush()
                s.detail = f"{sum(1 for x in lines if x)} qator"
            with task.step("Saqlash") as s:
                saved = wd.save_as(doc, out)
                s.detail = saved.name
            wd.show()
    else:
        raise ValueError("Qaysi dastur: excel yoki word")
    log("write_to_office", app=app, dst=str(saved))
    return {"path": str(saved), "files": [str(saved)],
            "report": [f"{saved.name} — ekranda ochiq"]}  # fmt: skip
