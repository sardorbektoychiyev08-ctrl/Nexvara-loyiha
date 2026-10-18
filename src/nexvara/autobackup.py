"""Weekly automatic backup of the small, irreplaceable user data.

Copied: the databases (memory, chat, history, workflows, journal, devices — through SQLite's
own backup, safe while the app runs), settings, BI dashboards, CAD drawings, answer-sheet
sets, account and sync files. Not copied: textbooks (big, can be downloaded again),
installers, updates, logs, temp files. Each backup is a folder with a SHA-256 manifest;
only the newest `keep` automatic backups are kept (older automatic ones are removed, a
manual full backup from scripts/backup_userdata.py is never touched).
Credential Manager secrets (AI keys, Google session) are never written to a file.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from nexvara import config

WEEK = 7 * 86400
SKIP_DIRS = {"darsliklar", "releases", "updates", "tmp", "logs", "android", "telegram"}
SKIP_EXT = {".pdf", ".djvu", ".exe", ".apk", ".zip", ".tmp", ".log"}
MAX_FILE = 100 * 1024 * 1024  # a file this big is not "small user data"
PREFIX = "auto-"


def default_root(data: Path | None = None) -> Path:
    data = data or config.data_dir()
    return data.parent / f"{data.name}-zaxira" / "auto"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _wanted(rel: Path, src: Path) -> bool:
    if rel.parts[0].casefold() in SKIP_DIRS or src.suffix.casefold() in SKIP_EXT:
        return False
    return src.stat().st_size <= MAX_FILE


def backup(data: Path | None = None, root: Path | None = None, keep: int = 4) -> dict[str, Any]:
    data = data or config.data_dir()
    root = root or default_root(data)
    dest = root / (PREFIX + time.strftime("%Y%m%d-%H%M%S"))
    files: dict[str, dict[str, Any]] = {}
    for src in sorted(data.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(data)
        if not _wanted(rel, src):
            continue
        target = dest / "data" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".db":
            # closing(): `with connect()` only commits, the file would stay open (Windows lock)
            with (
                closing(sqlite3.connect(f"file:{src}?mode=ro", uri=True)) as db,
                closing(sqlite3.connect(target)) as t,
            ):
                db.backup(t)
        else:
            shutil.copy2(src, target)
        files[rel.as_posix()] = {"size": target.stat().st_size, "sha256": _sha(target)}
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {"created": time.time(), "source": str(data), "files": files,
                "note": "Avtomatik zaxira: darsliklar va sirlar kiritilmagan."}  # fmt: skip
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
    bad = verify(dest)
    removed = prune(root, keep)
    size = sum(f["size"] for f in files.values())
    return {"path": str(dest), "files": len(files), "bytes": size, "verify_errors": bad,
            "removed": removed}  # fmt: skip


def verify(dest: Path) -> list[str]:
    m = json.loads((dest / "manifest.json").read_text("utf-8"))
    bad = []
    for rel, info in m["files"].items():
        p = dest / "data" / rel
        if not p.is_file() or p.stat().st_size != info["size"] or _sha(p) != info["sha256"]:
            bad.append(rel)
    return bad


def backups(root: Path | None = None) -> list[Path]:
    root = root or default_root()
    if not root.is_dir():
        return []
    return sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith(PREFIX)
                   and (p / "manifest.json").is_file()), reverse=True)  # fmt: skip


def prune(root: Path, keep: int) -> list[str]:
    """Only NEXVARA's own automatic backups (auto-… with a manifest) are ever removed."""
    old = backups(root)[max(1, keep) :]
    for p in old:
        shutil.rmtree(p, ignore_errors=True)
    return [p.name for p in old]


def due(settings: dict[str, Any], now: float | None = None) -> bool:
    b = settings.get("backup") or {}
    return bool(b.get("auto", True)) and (now or time.time()) - float(b.get("last") or 0) >= WEEK


class AutoBackup:
    """Checks at start and every few hours; makes a backup when a week has passed."""

    def __init__(self, settings: Any, on_done: Any = None) -> None:
        self.settings = settings
        self.on_done = on_done
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_result: dict[str, Any] | None = None

    def run_now(self) -> dict[str, Any]:
        s = self.settings.load()
        b = s.get("backup") or {}
        root = Path(b["folder"]) if b.get("folder") else None
        res = backup(root=root, keep=int(b.get("keep") or 4))
        if not res["verify_errors"]:
            self.settings.update({"backup": {"last": time.time()}})
        self.last_result = res
        if self.on_done:
            self.on_done(res)
        return res

    def tick(self, now: float | None = None) -> dict[str, Any] | None:
        if not due(self.settings.load(), now):
            return None
        return self.run_now()

    def start(self, every: float = 6 * 3600, first_delay: float = 120) -> None:
        if self._thread is not None:
            return

        def loop() -> None:
            if self._stop.wait(first_delay):  # let the app open first
                return
            while True:
                try:
                    self.tick()
                except Exception:  # noqa: BLE001 - a backup error never stops the app
                    import logging

                    logging.getLogger(__name__).exception("automatic backup failed")
                if self._stop.wait(every):
                    return

        self._thread = threading.Thread(target=loop, name="auto-backup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
