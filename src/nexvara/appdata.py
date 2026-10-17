"""Things that must survive a restart: task history and user settings.

History lives in its own SQLite file (app.db), separate from the textbook index, which
may be rebuilt at any time. Settings are a small JSON file the user could even edit.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from nexvara import config

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "dark",
    "test_count": 20,
    "test_variants": 1,
    "keep_office_open": True,
    # phone access over the local network; screen_view: the paired phone may see the screen
    "remote": {"enabled": False, "port": 8765, "screen_view": True},
    # Private release channel: a folder or an https:// URL with a signed latest.json.
    "update": {"channel": "", "auto_check": True},
    # Settings, memory and Teach rules between devices (sync.py). The passphrase is in
    # Credential Manager (NEXVARA/sync/passphrase), never here.
    "sync": {"enabled": False, "folder": "", "google_drive": False, "last": 0.0},
    # Google on the phone: the "Web application" OAuth client ID (public, not a secret) that
    # Android puts into the ID token's audience; the PC checks the phone's token against it.
    "google": {"android_web_client_id": ""},
    "ai": {
        "enabled": False,
        "provider": "",  # openai | anthropic | gemini | deepseek
        "daily_budget_usd": 1.0,
        "monthly_budget_usd": 10.0,
        "confirm_over_usd": 0.05,  # ask before a single request that may cost more
        "task_limit_usd": 0.50,  # a single request estimated above this is refused
        "limits": {},  # provider -> {"daily_usd": x, "monthly_usd": y} (optional, own caps)
        "fallback": False,  # busy/down provider -> another one; off: no paid call by itself
        "send_textbook_text": True,
        "models": {},  # provider -> tier -> model id (filled when a key is checked)
        "checked": {},  # provider -> {"at": time, "models": n} of the last key check
        "prices": {},  # model id -> [input, output] USD per 1M tokens, overrides the table
    },
}

_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '{}',
    steps TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS history_created ON history(created_at DESC);
"""


def _merge(base: dict, extra: dict) -> dict:
    out = deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.data_dir() / "settings.json")
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        return _merge(DEFAULT_SETTINGS, saved if isinstance(saved, dict) else {})

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Merge `changes` into the stored settings (unknown keys are ignored)."""
        with self._lock:
            current = self.load()
            clean = {k: v for k, v in changes.items() if k in DEFAULT_SETTINGS}
            merged = _merge(current, clean)
            _validate(merged)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
            return merged


def _validate(s: dict[str, Any]) -> None:
    if s["theme"] not in ("dark", "light"):
        raise ValueError("theme: dark yoki light")
    if not 1 <= int(s["test_count"]) <= 60:
        raise ValueError("test_count 1–60")
    if not 1 <= int(s["test_variants"]) <= 6:
        raise ValueError("test_variants 1–6")
    if not 1024 <= int(s["remote"]["port"]) <= 65535:
        raise ValueError("port 1024–65535")
    ch = str(s["update"]["channel"]).strip()
    if ch.startswith("http://"):
        raise ValueError("yangilanish kanali: faqat https:// yoki papka")
    ai = s["ai"]
    if ai["provider"] not in ("", "openai", "anthropic", "gemini", "deepseek"):
        raise ValueError("noma’lum AI provayder")
    for k in ("daily_budget_usd", "monthly_budget_usd", "confirm_over_usd"):
        if float(ai[k]) < 0:
            raise ValueError(f"{k} manfiy bo‘lmasin")
    if ai.get("task_limit_usd") not in (None, "") and float(ai["task_limit_usd"]) < 0:
        raise ValueError("task_limit_usd manfiy bo‘lmasin")
    for prov, lim in (ai.get("limits") or {}).items():
        if prov not in ("openai", "anthropic", "gemini", "deepseek") or not isinstance(lim, dict):
            raise ValueError("noma’lum provayder limiti")
        for v in lim.values():
            if v not in (None, "") and float(v) < 0:
                raise ValueError("limit manfiy bo‘lmasin")


class History:
    """Finished tasks, newest first; kept across restarts."""

    def __init__(self, path: Path | None = None, keep: int = 500) -> None:
        self.path = path or (config.data_dir() / "app.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.keep = keep
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(_HISTORY_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    def save(self, snap: dict[str, Any]) -> None:
        with self._lock, self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO history (id, title, status, error, result, steps, "
                "created_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    snap["id"],
                    snap["title"],
                    snap["status"],
                    snap.get("error", ""),
                    json.dumps(snap.get("result") or {}, ensure_ascii=False, default=str),
                    json.dumps(snap.get("steps") or [], ensure_ascii=False, default=str),
                    time.time() if snap.get("created_at") is None else snap["created_at"],
                    snap.get("finished_at"),
                ),
            )
            db.execute(
                "DELETE FROM history WHERE id NOT IN "
                "(SELECT id FROM history ORDER BY created_at DESC LIMIT ?)",
                (self.keep,),
            )

    def list(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT id, title, status, error, result, steps, created_at, finished_at "
                "FROM history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "title": r[1],
                "status": r[2],
                "error": r[3],
                "result": json.loads(r[4] or "{}"),
                "steps": json.loads(r[5] or "[]"),
                "created_at": r[6],
                "finished_at": r[7],
                "cancel_requested": False,
            }
            for r in rows
        ]

    def clear(self) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM history")
