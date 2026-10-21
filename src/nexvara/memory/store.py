"""Long-term memory in app.db: remembered facts, the chat log and taught rules.

Everything is local SQLite. Search uses FTS5 with the same Uzbek stem matching as the
textbook library ("maktabimiz" finds "maktab"). Rules keep every earlier version.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.knowledge.textnorm import fold

RULE_APPS = ("excel", "word", "powerpoint", "test")
APP_LABELS = {"excel": "Excel", "word": "Word", "powerpoint": "PowerPoint", "test": "Testlar"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_items (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    text, tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS chat_log (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chat_fts USING fts5(
    text, tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    app TEXT NOT NULL,
    text TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rule_versions (
    rule_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    app TEXT NOT NULL,
    text TEXT NOT NULL,
    ts REAL NOT NULL
);
"""

CHAT_KEEP = 5000

# Common Uzbek endings, longest first: "maktabimizda" -> "maktab", "fizikadan" -> "fizika".
_SUFFIXES = sorted(
    (
        "lar ning ni ga ka qa da ta dan tan dagi dagi gi ning imiz ingiz miz ngiz im ing "
        "si i m ng mi mas man san siz miz dir lik chi cha dek day roq"
    ).split(),
    key=len,
    reverse=True,
)


def stem(word: str) -> str:
    w = word
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)]
                changed = True
                break
    return w


def _match_query(text: str, joiner: str = " ") -> str:
    words = [w for w in re.findall(r"\w+", fold(text)) if len(w) >= 2]
    return joiner.join(f'"{stem(w)}"*' for w in words)


@dataclass
class Rule:
    id: int
    app: str
    text: str
    enabled: bool
    version: int
    created: float
    updated: float

    def label(self) -> str:
        return APP_LABELS.get(self.app, self.app)


class MemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.data_dir() / "app.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    # ----- facts -----
    def add_fact(self, text: str) -> int:
        text = text.strip()
        if not text:
            raise ValueError("bo‘sh matn")
        now = time.time()
        with self._lock, self._db() as db:
            cur = db.execute(
                "INSERT INTO memory_items (text, created, updated) VALUES (?, ?, ?)",
                (text, now, now),
            )
            db.execute(
                "INSERT INTO memory_fts (rowid, text) VALUES (?, ?)", (cur.lastrowid, fold(text))
            )
            return int(cur.lastrowid)

    def update_fact(self, fact_id: int, text: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("bo‘sh matn")
        with self._lock, self._db() as db:
            n = db.execute(
                "UPDATE memory_items SET text = ?, updated = ? WHERE id = ?",
                (text, time.time(), fact_id),
            ).rowcount
            if not n:
                raise LookupError("topilmadi")
            db.execute("DELETE FROM memory_fts WHERE rowid = ?", (fact_id,))
            db.execute("INSERT INTO memory_fts (rowid, text) VALUES (?, ?)", (fact_id, fold(text)))

    def delete_fact(self, fact_id: int) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM memory_items WHERE id = ?", (fact_id,))
            db.execute("DELETE FROM memory_fts WHERE rowid = ?", (fact_id,))

    def facts(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT id, text, created, updated FROM memory_items ORDER BY updated DESC"
            ).fetchall()
        return [{"id": r[0], "text": r[1], "created": r[2], "updated": r[3]} for r in rows]

    def relevant_facts(self, text: str, limit: int = 3) -> list[str]:
        """Only facts that share words with the request go to an AI prompt."""
        q = _match_query(text, " OR ")
        if not q:
            return []
        with self._db() as db:
            try:
                rows = db.execute(
                    "SELECT m.text FROM memory_fts f JOIN memory_items m ON m.id = f.rowid "
                    "WHERE memory_fts MATCH ? ORDER BY bm25(memory_fts) LIMIT ?",
                    (q, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [r[0] for r in rows]

    # ----- chat log -----
    def log_chat(self, role: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        with self._lock, self._db() as db:
            cur = db.execute(
                "INSERT INTO chat_log (ts, role, text) VALUES (?, ?, ?)", (time.time(), role, text)
            )
            db.execute(
                "INSERT INTO chat_fts (rowid, text) VALUES (?, ?)", (cur.lastrowid, fold(text))
            )
            old = db.execute(
                "SELECT id FROM chat_log ORDER BY id DESC LIMIT -1 OFFSET ?", (CHAT_KEEP,)
            ).fetchall()
            for (i,) in old:
                db.execute("DELETE FROM chat_log WHERE id = ?", (i,))
                db.execute("DELETE FROM chat_fts WHERE rowid = ?", (i,))

    def chat(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(  # by time: messages from another PC are added later
                "SELECT id, ts, role, text FROM chat_log ORDER BY ts DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"id": r[0], "ts": r[1], "role": r[2], "text": r[3]} for r in reversed(rows)]

    def recent_turns(self, limit: int = 15, days: int = 30) -> list[dict[str, str]]:
        """The last messages of the conversation (they survive an app restart)."""
        since = time.time() - days * 86400
        with self._db() as db:
            rows = db.execute(
                "SELECT role, text FROM chat_log WHERE ts >= ? ORDER BY ts DESC, id DESC LIMIT ?",
                (since, limit),
            ).fetchall()
        return [{"role": r[0], "text": r[1][:1500]} for r in reversed(rows)]

    def last_replies(self, limit: int = 8) -> list[str]:
        """NEXVARA's latest answers in full, newest first («shuni Excel’ga yoz»)."""
        with self._db() as db:
            rows = db.execute(
                "SELECT text FROM chat_log WHERE role = 'nexvara' ORDER BY ts DESC, id DESC "
                "LIMIT ?", (limit,)).fetchall()  # fmt: skip
        return [r[0] for r in rows]

    def recall(
        self, text: str, days: int = 30, limit: int = 6, skip_last: int = 15
    ) -> list[dict[str, Any]]:
        """Older chat lines (within `days`) that share words with the request, each with the
        answer that followed it. The newest `skip_last` lines are left out: they are sent
        as the recent conversation anyway."""
        q = _match_query(text, " OR ")
        if not q:
            return []
        since = time.time() - days * 86400
        with self._db() as db:
            newest = db.execute(
                "SELECT id FROM chat_log ORDER BY id DESC LIMIT 1 OFFSET ?", (skip_last - 1,)
            ).fetchone()
            cutoff = newest[0] if newest else 0
            try:
                rows = db.execute(
                    "SELECT c.id, c.ts, c.role, c.text FROM chat_fts f JOIN chat_log c "
                    "ON c.id = f.rowid WHERE chat_fts MATCH ? AND c.ts >= ? AND c.id < ? "
                    "ORDER BY bm25(chat_fts) LIMIT ?",
                    (q, since, cutoff, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                return []
            out = []
            for rid, ts, role, body in rows:
                pair = db.execute(
                    "SELECT role, text FROM chat_log WHERE id = ?",
                    (rid + 1 if role == "user" else rid - 1,),
                ).fetchone()
                q_text, a_text = (body, pair[1] if pair else "") if role == "user" else (
                    pair[1] if pair else "", body)  # fmt: skip
                out.append({"ts": ts, "user": q_text[:400], "nexvara": a_text[:600]})
        return sorted(out, key=lambda x: x["ts"])

    def day_summaries(self, days: int = 7, per_day: int = 4) -> list[str]:
        """A short local summary of each earlier day: what the user asked (no AI involved)."""
        today = time.strftime("%Y-%m-%d")
        since = time.time() - days * 86400
        with self._db() as db:
            rows = db.execute(
                "SELECT ts, text FROM chat_log WHERE role = 'user' AND ts >= ? ORDER BY id",
                (since,),
            ).fetchall()
        by_day: dict[str, list[str]] = {}
        for ts, body in rows:
            day = time.strftime("%Y-%m-%d", time.localtime(ts))
            short = " ".join(body.split())[:90]
            if day == today or len(short) < 6 or fold(short) in ("ha", "yoq"):
                continue
            items = by_day.setdefault(day, [])
            if short not in items:
                items.append(short)
        return [
            f"{d}: " + "; ".join(v[-per_day:]) + (f" (+{len(v) - per_day} ta)" if len(v) > per_day
                                                  else "")
            for d, v in sorted(by_day.items())
        ]  # fmt: skip

    def forget_chat(self, text: str) -> int:
        """«… ni unut»: delete chat lines that contain all the given words."""
        q = _match_query(text, " AND ")
        if not q:
            return 0
        with self._lock, self._db() as db:
            try:
                ids = [
                    r[0]
                    for r in db.execute(
                        "SELECT rowid FROM chat_fts WHERE chat_fts MATCH ?", (q,)
                    ).fetchall()
                ]
            except sqlite3.OperationalError:
                return 0
            for i in ids:
                db.execute("DELETE FROM chat_log WHERE id = ?", (i,))
                db.execute("DELETE FROM chat_fts WHERE rowid = ?", (i,))
        return len(ids)

    def forget_last(self, n: int) -> int:
        with self._lock, self._db() as db:
            ids = [r[0] for r in db.execute(
                "SELECT id FROM chat_log ORDER BY id DESC LIMIT ?", (n,)).fetchall()]  # fmt: skip
            for i in ids:
                db.execute("DELETE FROM chat_log WHERE id = ?", (i,))
                db.execute("DELETE FROM chat_fts WHERE rowid = ?", (i,))
        return len(ids)

    # ----- chat between this user's PCs (sync.py, only when settings sync.chat is on) -----
    def chat_since(self, since: float, limit: int = 1000) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT id, ts, role, text FROM chat_log WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                (since, limit),
            ).fetchall()
        return [{"id": r[0], "ts": r[1], "role": r[2], "text": r[3]} for r in rows]

    def chat_exists(self, chat_id: int) -> bool:
        with self._db() as db:
            return (
                db.execute("SELECT 1 FROM chat_log WHERE id = ?", (chat_id,)).fetchone() is not None
            )

    def import_chat(self, ts: float, role: str, text: str) -> int:
        """A message from another PC, with its own time; the same message is kept once."""
        text = (text or "").strip()
        with self._lock, self._db() as db:
            same = db.execute(
                "SELECT id FROM chat_log WHERE ts = ? AND role = ? AND text = ?", (ts, role, text)
            ).fetchone()
            if same:
                return same[0]
            cur = db.execute(
                "INSERT INTO chat_log (ts, role, text) VALUES (?, ?, ?)", (ts, role, text)
            )
            db.execute(
                "INSERT INTO chat_fts (rowid, text) VALUES (?, ?)", (cur.lastrowid, fold(text))
            )
            return cur.lastrowid

    def delete_chat(self, chat_id: int) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM chat_log WHERE id = ?", (chat_id,))
            db.execute("DELETE FROM chat_fts WHERE rowid = ?", (chat_id,))

    def clear_chat(self) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM chat_log")
            db.execute("DELETE FROM chat_fts")

    # ----- rules (Teach NEXVARA) -----
    def _rule(self, r: tuple) -> Rule:
        return Rule(r[0], r[1], r[2], bool(r[3]), r[4], r[5], r[6])

    def add_rule(self, app: str, text: str) -> Rule:
        if app not in RULE_APPS:
            raise ValueError("noma’lum dastur")
        text = text.strip()
        if not text:
            raise ValueError("bo‘sh qoida")
        now = time.time()
        with self._lock, self._db() as db:
            cur = db.execute(
                "INSERT INTO rules (app, text, enabled, version, created, updated) "
                "VALUES (?, ?, 1, 1, ?, ?)",
                (app, text, now, now),
            )
            db.execute(
                "INSERT INTO rule_versions VALUES (?, 1, ?, ?, ?)", (cur.lastrowid, app, text, now)
            )
            rid = int(cur.lastrowid)
        return self.rule(rid)

    def rule(self, rule_id: int) -> Rule:
        with self._db() as db:
            r = db.execute(
                "SELECT id, app, text, enabled, version, created, updated FROM rules WHERE id = ?",
                (rule_id,),
            ).fetchone()
        if r is None:
            raise LookupError("qoida topilmadi")
        return self._rule(r)

    def rules(self, app: str | None = None, enabled_only: bool = False) -> list[Rule]:
        sql = "SELECT id, app, text, enabled, version, created, updated FROM rules"
        cond, args = [], []
        if app:
            cond.append("app = ?")
            args.append(app)
        if enabled_only:
            cond.append("enabled = 1")
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        with self._db() as db:
            rows = db.execute(sql + " ORDER BY id", args).fetchall()
        return [self._rule(r) for r in rows]

    def update_rule(self, rule_id: int, text: str | None = None, enabled: bool | None = None):
        old = self.rule(rule_id)
        now = time.time()
        with self._lock, self._db() as db:
            if text is not None and text.strip() and text.strip() != old.text:
                version = old.version + 1
                db.execute(
                    "UPDATE rules SET text = ?, version = ?, updated = ? WHERE id = ?",
                    (text.strip(), version, now, rule_id),
                )
                db.execute(
                    "INSERT INTO rule_versions VALUES (?, ?, ?, ?, ?)",
                    (rule_id, version, old.app, text.strip(), now),
                )
            if enabled is not None:
                db.execute(
                    "UPDATE rules SET enabled = ?, updated = ? WHERE id = ?",
                    (int(bool(enabled)), now, rule_id),
                )
        return self.rule(rule_id)

    def rule_versions(self, rule_id: int) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT version, text, ts FROM rule_versions WHERE rule_id = ? ORDER BY version",
                (rule_id,),
            ).fetchall()
        return [{"version": r[0], "text": r[1], "ts": r[2]} for r in rows]

    def delete_rule(self, rule_id: int) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            db.execute("DELETE FROM rule_versions WHERE rule_id = ?", (rule_id,))

    # ----- search across memory -----
    def search(self, text: str, limit: int = 30) -> list[dict[str, Any]]:
        q = _match_query(text)
        if not q:
            return []
        out: list[dict[str, Any]] = []
        with self._db() as db:
            for kind, sql in (
                ("fact", "SELECT m.id, m.text, m.updated FROM memory_fts f "
                         "JOIN memory_items m ON m.id = f.rowid WHERE memory_fts MATCH ? "
                         "ORDER BY bm25(memory_fts) LIMIT ?"),
                ("chat", "SELECT c.id, c.role || ': ' || c.text, c.ts FROM chat_fts f "
                         "JOIN chat_log c ON c.id = f.rowid WHERE chat_fts MATCH ? "
                         "ORDER BY bm25(chat_fts) LIMIT ?"),
            ):  # fmt: skip
                try:
                    rows = db.execute(sql, (q, limit)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                out += [{"kind": kind, "id": r[0], "text": r[1], "ts": r[2]} for r in rows]
        words = [w for w in fold(text).split() if len(w) >= 3]
        for r in self.rules():
            if any(stem(w) in fold(r.text) for w in words):
                out.append({"kind": "rule", "id": r.id, "text": f"{r.label()}: {r.text}",
                            "ts": r.updated})  # fmt: skip
        return out[:limit]

    # ----- backup / restore -----
    def export(self) -> dict[str, Any]:
        return {
            "format": "nexvara-memory",
            "version": 1,
            "exported": time.time(),
            "facts": self.facts(),
            "rules": [{**asdict(r), "versions": self.rule_versions(r.id)} for r in self.rules()],
            "chat": self.chat(limit=CHAT_KEEP),
        }

    def export_file(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.export(), ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    def import_data(self, data: dict[str, Any]) -> dict[str, int]:
        """Merge a backup: facts and rules that already exist (same text) are skipped."""
        if not isinstance(data, dict) or data.get("format") != "nexvara-memory":
            raise ValueError("bu NEXVARA xotira fayli emas")
        have = {f["text"] for f in self.facts()}
        n_facts = 0
        for f in data.get("facts") or []:
            t = str(f.get("text") or "").strip()
            if t and t not in have:
                self.add_fact(t)
                have.add(t)
                n_facts += 1
        rules = {(r.app, r.text) for r in self.rules()}
        n_rules = 0
        for r in data.get("rules") or []:
            key = (r.get("app"), str(r.get("text") or "").strip())
            if key[0] in RULE_APPS and key[1] and key not in rules:
                new = self.add_rule(*key)
                if not r.get("enabled", True):
                    self.update_rule(new.id, enabled=False)
                rules.add(key)
                n_rules += 1
        return {"facts": n_facts, "rules": n_rules}
