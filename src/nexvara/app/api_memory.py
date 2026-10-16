"""Memory and Teach NEXVARA pages of the UI bridge (mixed into app.api.Api)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class MemoryApi:
    _overrides: dict
    _history: Any

    def _mem(self):
        """The memory store: the desktop app's (D:\\NEXVARA\\app.db) or a test's; None in
        plain tests so they never touch the user's memory."""
        if "memory" in self._overrides:
            return self._overrides["memory"]
        if self._history is None:
            return None
        if getattr(self, "_memory", None) is None:
            from nexvara.memory.store import MemoryStore

            self._memory = MemoryStore()
        return self._memory

    def _need_mem(self):
        mem = self._mem()
        if mem is None:
            raise RuntimeError("xotira mavjud emas")
        return mem

    # ----- facts -----
    def memory_facts(self) -> list[dict[str, Any]]:
        mem = self._mem()
        return mem.facts() if mem else []

    def memory_add_fact(self, text: str) -> dict[str, Any]:
        try:
            self._need_mem().add_fact(text)
        except (ValueError, RuntimeError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def memory_update_fact(self, fact_id: int, text: str) -> dict[str, Any]:
        try:
            self._need_mem().update_fact(int(fact_id), text)
        except (ValueError, LookupError, RuntimeError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def memory_delete_fact(self, fact_id: int) -> bool:
        self._need_mem().delete_fact(int(fact_id))
        return True

    # ----- conversations, search, files -----
    def memory_chat(self, limit: int = 200) -> list[dict[str, Any]]:
        mem = self._mem()
        return mem.chat(int(limit)) if mem else []

    def memory_clear_chat(self) -> bool:
        self._need_mem().clear_chat()
        return True

    def memory_search(self, query: str) -> list[dict[str, Any]]:
        mem = self._mem()
        if not mem or not (query or "").strip():
            return []
        found = mem.search(query)
        q = (query or "").casefold()
        if self._history is not None:  # finished tasks match by title
            for t in self._history.list(500):
                if q in t["title"].casefold():
                    found.append({"kind": "task", "id": t["id"], "text": t["title"],
                                  "ts": t["created_at"]})  # fmt: skip
        return found[:50]

    def recent_files(self) -> list[dict[str, Any]]:
        """Files NEXVARA made or worked on, newest first (only those that still exist)."""
        if self._history is None:
            return []
        seen, out = set(), []
        for t in self._history.list(300):
            res = t.get("result") or {}
            for key in ("path", "pdf", "excerpt", "source"):
                p = res.get(key)
                if isinstance(p, str) and p and p not in seen and Path(p).is_file():
                    seen.add(p)
                    out.append({"path": p, "name": Path(p).name, "task": t["title"],
                                "ts": t.get("finished_at") or t["created_at"]})  # fmt: skip
        return out[:100]

    # ----- backup / restore -----
    def memory_export(self) -> dict[str, Any]:
        from nexvara import config

        mem = self._need_mem()
        folder = config.data_dir() / "Zaxira"
        path = folder / f"nexvara-xotira-{time.strftime('%Y%m%d-%H%M%S')}.json"
        mem.export_file(path)
        return {"ok": True, "path": str(path)}

    def memory_import(self, path: str = "") -> dict[str, Any]:
        mem = self._need_mem()
        if not path:
            import webview

            if not webview.windows:
                return {"ok": False, "error": "oyna yo‘q"}
            chosen = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG, file_types=("NEXVARA xotira (*.json)",)
            )
            if not chosen:
                return {"ok": False, "error": ""}
            path = chosen[0]
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            added = mem.import_data(data)
        except (OSError, ValueError) as e:
            return {"ok": False, "error": f"Faylni o‘qib bo‘lmadi: {e}"}
        return {"ok": True, **added}

    # ----- Teach NEXVARA -----
    def teach_rules(self) -> list[dict[str, Any]]:
        from nexvara.memory.teach import describe_rule

        mem = self._mem()
        if not mem:
            return []
        out = []
        for r in mem.rules():
            actions, err = describe_rule(r.app, r.text)
            out.append({"id": r.id, "app": r.app, "app_label": r.label(), "text": r.text,
                        "enabled": r.enabled, "version": r.version, "updated": r.updated,
                        "actions": actions, "problem": err})  # fmt: skip
        return out

    def teach_preview(self, app: str, text: str) -> dict[str, Any]:
        from nexvara.memory.store import RULE_APPS
        from nexvara.memory.teach import describe_rule

        if app not in RULE_APPS:
            return {"ok": False, "error": "Dasturni tanlang"}
        text = (text or "").strip()
        if not text:
            return {"ok": False, "error": "Qoidani yozing"}
        actions, err = describe_rule(app, text)
        return {"ok": bool(actions) and not err, "actions": actions, "error": err}

    def teach_add(self, app: str, text: str) -> dict[str, Any]:
        prev = self.teach_preview(app, text)
        if not prev["ok"]:
            return prev
        self._need_mem().add_rule(app, text.strip())
        return {"ok": True, "rules": self.teach_rules()}

    def teach_update(self, rule_id: int, text: str | None = None, enabled: bool | None = None):
        mem = self._need_mem()
        rule = mem.rule(int(rule_id))
        if text is not None:
            prev = self.teach_preview(rule.app, text)
            if not prev["ok"]:
                return prev
        mem.update_rule(int(rule_id), text, enabled)
        return {"ok": True, "rules": self.teach_rules()}

    def teach_delete(self, rule_id: int) -> list[dict[str, Any]]:
        self._need_mem().delete_rule(int(rule_id))
        return self.teach_rules()

    def teach_versions(self, rule_id: int) -> list[dict[str, Any]]:
        return self._need_mem().rule_versions(int(rule_id))
