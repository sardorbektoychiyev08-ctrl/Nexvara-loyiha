"""Workflows page of the UI bridge (mixed into app.api.Api)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class WorkflowsApi:
    _runner: Any
    _overrides: dict
    _history: Any

    def _wf(self):
        """(store, engine); None in plain tests so they never touch the user's workflows."""
        if getattr(self, "_wf_engine", None) is None:
            from nexvara.workflows import WorkflowEngine, WorkflowStore

            store = self._overrides.get("workflow_store")
            if store is None:
                if self._history is None:
                    return None
                store = WorkflowStore()
            self._wf_engine = WorkflowEngine(store, self._runner, self._wf_execute)
        return self._wf_engine

    def _wf_execute(self, text: str) -> dict[str, Any]:
        mem = self._mem()
        if mem is not None:
            mem.log_chat("workflow", text)
        return self._chat_inner(text, _use_ai=False)  # workflows never spend on AI by themselves

    def start_background(self) -> None:
        """Desktop app only: watch folders and schedules for workflows."""
        eng = self._wf()
        if eng is not None:
            eng.start_watching()
        self.start_remote_if_enabled()  # phone access, if the user turned it on
        self._auto_backup().start()  # weekly copy of the small user data

    def _auto_backup(self):
        if getattr(self, "_backup", None) is None:
            from nexvara.appdata import Settings
            from nexvara.autobackup import AutoBackup

            self._backup = AutoBackup(Settings())
        return self._backup

    def _chat_backup(self, f: str, text: str) -> dict[str, Any] | None:
        """«zaxira qil», «zaxira qachon qilingan», «avtomatik zaxirani o'chir/yoq»."""
        if not re.search(r"\bzaxira\w*", f):
            return None
        if self._history is None and "backup" not in self._overrides:
            return {"reply": "Zaxira bu rejimda o‘chirilgan."}
        bk = self._overrides.get("backup") or self._auto_backup()
        auto = "avto" in f or "haftalik" in f
        if auto and re.search(r"\b(ochir|toxtat|kerak emas)\w*", f):
            bk.settings.update({"backup": {"auto": False}})
            return {"reply": "Haftalik avtomatik zaxira o‘chirildi. Qayta yoqish: «avtomatik "
                    "zaxirani yoq»."}  # fmt: skip
        if auto and re.search(r"\b(yoq|yoqib qoy|yoqing)\b", f):
            bk.settings.update({"backup": {"auto": True}})
            return {"reply": "Haftalik avtomatik zaxira yoqildi."}
        if re.search(r"\b(qachon|holat\w*|bormi|qayerda)\b", f):
            from nexvara.autobackup import backups

            s = bk.settings.load().get("backup") or {}
            items = backups(Path(s["folder"]) if s.get("folder") else None)
            on = "yoqilgan (har hafta)" if s.get("auto", True) else "o‘chirilgan"
            if not items:
                return {"reply": f"Avtomatik zaxira {on}. Hali zaxira qilinmagan. «Zaxira qil» "
                        "deb yozsangiz, hozir qilaman."}  # fmt: skip
            return {"reply": f"Avtomatik zaxira {on}. Oxirgisi: {items[0].name[5:]}, jami "
                    f"{len(items)} ta.\nJoyi: {items[0].parent}"}  # fmt: skip
        if re.search(r"\b(qil|ol|yarat|saqla)\w*", f):
            res = bk.run_now()
            if res["verify_errors"]:
                bad = len(res["verify_errors"])
                return {"reply": f"Zaxira qilindi, lekin {bad} ta fayl tekshiruvdan o‘tmadi. "
                        "Qaytadan urinib ko‘ring.", "error": True}  # fmt: skip
            mb = res["bytes"] / 1e6
            return {"reply": f"✅ Zaxira tayyor: {res['files']} ta fayl ({mb:.1f} MB), har biri "
                    f"tekshirildi.\nJoyi: {res['path']}\nDarsliklar kiritilmaydi (ular qayta "
                    "yuklanadi), API kalitlari faylga yozilmaydi.",
                    "files": [res["path"]]}  # fmt: skip
        return None

    def _need_wf(self):
        eng = self._wf()
        if eng is None:
            raise RuntimeError("workflowlar bu rejimda o‘chirilgan")
        return eng

    def wf_templates(self) -> list[dict[str, Any]]:
        from nexvara.workflows import TEMPLATES

        return TEMPLATES

    def wf_list(self) -> list[dict[str, Any]]:
        eng = self._wf()
        if eng is None:
            return []
        last = {}
        for r in eng.store.runs(limit=200):
            last.setdefault(r["wf_id"], r)
        return [{**w.to_dict(), "last_run": last.get(w.id)} for w in eng.store.all()]

    def wf_save(self, data: dict[str, Any]) -> dict[str, Any]:
        from nexvara.workflows import Workflow

        try:
            wf = Workflow.from_dict(data or {})
            if wf.id:  # keep the daily bookkeeping of an edited workflow
                wf.last_daily = self._need_wf().store.get(wf.id).last_daily
            saved = self._need_wf().store.save(wf)
        except (ValueError, TypeError, LookupError, RuntimeError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "id": saved.id, "workflows": self.wf_list()}

    def wf_delete(self, wf_id: int) -> list[dict[str, Any]]:
        self._need_wf().store.delete(int(wf_id))
        return self.wf_list()

    def wf_run(self, wf_id: int, file: str = "") -> dict[str, Any]:
        eng = self._need_wf()
        try:
            wf = eng.store.get(int(wf_id))
            if wf.trigger.get("type") == "folder" and not file:
                return {"ok": False, "error": "Bu workflow fayl bilan ishlaydi: faylni tanlang"}
            return {"ok": True, **eng.start(wf, file)}
        except (LookupError, RuntimeError) as e:
            return {"ok": False, "error": str(e)}

    def wf_runs(self, wf_id: int = 0) -> list[dict[str, Any]]:
        eng = self._wf()
        return eng.store.runs(int(wf_id) or None) if eng else []

    def wf_active(self) -> list[dict[str, Any]]:
        eng = self._wf()
        return eng.active() if eng else []

    def wf_approve(self, run_id: int) -> bool:
        return self._need_wf().approve(int(run_id))

    def wf_pause(self, run_id: int) -> bool:
        return self._need_wf().pause(int(run_id))

    def wf_resume(self, run_id: int) -> bool:
        return self._need_wf().resume(int(run_id))

    def wf_pick_file(self) -> str:
        import webview

        if not webview.windows:
            return ""
        chosen = webview.windows[0].create_file_dialog(webview.OPEN_DIALOG)
        return str(chosen[0]) if chosen else ""
