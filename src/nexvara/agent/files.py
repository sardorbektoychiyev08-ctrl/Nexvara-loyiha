"""Find the file a user named ("Hisobot.xlsx") and choose safe output paths."""

from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path

from nexvara import config
from nexvara.knowledge.textnorm import fold

_SKIP_DIRS = {
    "$recycle.bin", "system volume information", "windows", "program files",
    "program files (x86)", "programdata", "appdata", ".git", ".venv", "node_modules",
    "__pycache__", "recovery", "perflogs",
}  # fmt: skip
MAX_DEPTH = 4
MAX_DIRS = 4000


def search_roots(extra: list[Path] | None = None) -> list[Path]:
    home = Path.home()
    roots = list(extra or [])
    for name in ("Desktop", "Documents", "Downloads", "OneDrive/Desktop", "OneDrive/Documents"):
        roots.append(home / name)
    roots.append(config.data_dir())
    if os.name == "nt":
        for drive in "DEFGH":
            if Path(f"{drive}:/").exists():
                roots.append(Path(f"{drive}:/"))
    seen, out = set(), []
    for r in roots:
        key = str(r).lower()
        if r.is_dir() and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def resolve(name: str, near: Path | None = None) -> Path:
    """Absolute path for `name`; searches the usual folders when only a file name is given.

    Raises LookupError (with the folders searched) when nothing matches.
    """
    p = Path(name.strip().strip('"«»'))
    if p.is_absolute():
        if p.is_file():
            return p
        raise LookupError(f"Fayl topilmadi: {p}")
    target = fold(p.name)
    matches: list[Path] = []
    roots = search_roots([near] if near else None)
    dirs_seen = 0
    for root in roots:
        stack = [(root, 0)]
        while stack and dirs_seen < MAX_DIRS:
            d, depth = stack.pop()
            dirs_seen += 1
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                try:
                    if e.is_file() and fold(e.name) == target:
                        matches.append(Path(e.path))
                    elif (
                        e.is_dir()
                        and depth < MAX_DEPTH
                        and e.name.lower() not in _SKIP_DIRS
                        and not e.name.startswith(".")
                    ):
                        stack.append((Path(e.path), depth + 1))
                except OSError:
                    continue
        if matches:
            break  # nearer roots win
    if not matches:
        where = ", ".join(str(r) for r in roots)
        raise LookupError(
            f"«{p.name}» fayli topilmadi. Qidirilgan joylar: {where}. "
            "Faylni 📎 tugmasi bilan tanlang yoki to‘liq yo‘lini yozing."
        )
    # Several copies: the most recently changed one.
    return max(matches, key=lambda m: m.stat().st_mtime)


def output_path(source: Path, ext: str | None = None, suffix: str = "_NEXVARA") -> Path:
    """'Hisobot.xlsx' -> 'Hisobot_NEXVARA.xlsx' next to it (numbered if taken). Never the source."""
    ext = ext or source.suffix
    stem = source.stem
    # Reworking our own output: "X_NEXVARA" -> "X_NEXVARA-2", not "X_NEXVARA_NEXVARA".
    stem = re.sub(rf"{re.escape(suffix)}(-\d+)?$", "", stem)
    source = source.with_name(stem + source.suffix)
    base = source.with_name(f"{source.stem}{suffix}{ext}")
    if not base.exists():
        return base
    for i in range(2, 1000):
        cand = source.with_name(f"{source.stem}{suffix}-{i}{ext}")
        if not cand.exists():
            return cand
    raise RuntimeError("bo‘sh fayl nomi topilmadi")


def backup(path: Path) -> Path:
    """Copy of the original before an in-place save: 'Hisobot.bak-20261016-1500.xlsx'."""
    dst = path.with_name(f"{path.stem}.bak-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
    shutil.copy2(path, dst)
    return dst
