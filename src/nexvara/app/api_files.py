"""Files page of the UI bridge (mixed into app.api.Api)."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _safe(fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "result": fn()}
    except (OSError, ValueError, RuntimeError, LookupError) as e:
        return {"ok": False, "error": str(e)}


class FilesApi:
    _runner: Any
    _overrides: dict

    def files_search(self, query: str = "", folder: str = "", ext: str = "") -> dict[str, Any]:
        from nexvara import fileagent

        exts = tuple(e.strip() for e in re.split(r"[ ,;]+", ext or "") if e.strip())
        if folder and not Path(folder).is_dir():
            return {"ok": False, "error": f"Papka topilmadi: {folder}"}
        if not (query or "").strip() and not folder and not exts:
            return {"ok": False, "error": "Fayl nomidan bir so‘z yozing yoki papkani tanlang"}
        found = fileagent.search(query, folder or None, exts)
        roots = [Path(folder)] if folder else fileagent.default_roots()
        return {"ok": True, "files": [asdict(f) for f in found], "roots": [str(r) for r in roots]}

    def files_info(self, path: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.info(path))

    def files_pick_folder(self) -> str:
        import webview

        if not webview.windows:
            return ""
        chosen = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return str(chosen[0]) if chosen else ""

    def files_copy(self, paths: list[str], folder: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.copy_to(paths, folder))

    def files_save_as(self, path: str, folder: str, name: str = "") -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.copy_as(path, folder, name))

    def files_move(self, paths: list[str], folder: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.move_to(paths, folder))

    def files_rename(self, path: str, name: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.rename(path, name))

    def files_rename_batch(self, paths: list[str], pattern: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.rename_batch(paths, pattern))

    def files_zip(self, paths: list[str]) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.make_zip(paths))

    def files_unzip(self, path: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.unzip(path))

    def files_backup(self, paths: list[str]) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.backup(paths))

    def files_versions(self, path: str) -> list[dict[str, Any]]:
        from nexvara import fileagent

        return fileagent.versions(path)

    def files_restore(self, version: str, original: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.restore(version, original))

    def files_tidy_plan(self, folder: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.tidy_plan(folder))

    def files_tidy(self, folder: str) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.tidy(folder))

    def files_recycle(self, paths: list[str]) -> dict[str, Any]:
        from nexvara import fileagent

        return _safe(lambda: fileagent.recycle(paths))

    def files_log(self) -> list[dict[str, Any]]:
        from nexvara import fileagent

        return fileagent.recent_log()

    def files_to_pdf(self, paths: list[str]) -> dict[str, Any]:
        from nexvara import fileagent

        if not paths:
            return {"error": "Fayl tanlanmagan"}
        fn = self._overrides.get("files_to_pdf")
        if fn is None:

            def fn(task: Any) -> dict[str, Any]:
                return fileagent.convert_to_pdf(task, list(paths))

        return self._runner.start(f"PDF'ga aylantirish: {len(paths)} ta fayl", fn).snapshot()

    def excel_combine(self, paths: list[str]) -> dict[str, Any]:
        """Several workbooks (or CSV) into one new workbook next to the first, a sheet each
        (the first sheet of every file, named after the file); the originals are not changed."""
        from nexvara.fileagent import combine_workbooks

        if len(paths) < 2:
            return {"error": "Kamida 2 ta fayl kerak"}
        fn = self._overrides.get("excel_combine")
        if fn is None:
            keep = bool(self.get_settings().get("keep_office_open", True))

            def fn(task: Any) -> dict[str, Any]:
                return combine_workbooks(task, list(paths), keep_open=keep)

        return self._runner.start(f"Excel fayllarini yig‘ish: {len(paths)} ta", fn).snapshot()

    def _last_answer(self) -> str:
        """The latest real answer: not a question back, a plan or a «Davom etaymi?» prompt."""
        from nexvara.app.api_agent import _service_line

        mem = self._mem()
        replies = mem.last_replies() if mem is not None else [
            t["text"] for t in reversed(self._ctx.turns) if t["role"] != "user"]  # fmt: skip
        for text in replies:
            t = (text or "").strip()
            if (t and not _service_line(t) and not t.startswith("Tushundim")
                    and not t.rstrip().endswith("?")):  # fmt: skip
                return t
        return ""

    def office_write(self, app: str, text: str = "", title: str = "") -> dict[str, Any]:
        """«Excel’ni ochib o‘sha yerga yoz»: the given text, or NEXVARA's last answer, into a
        new Excel/Word file opened on the screen."""
        from nexvara.fileagent import write_to_office

        app = "word" if app.lower().startswith(("w", "v")) else "excel"
        body = (text or "").strip() or self._last_answer()
        if not body:
            return {"error": "Yoziladigan javob topilmadi: avval savol bering yoki matnni yozing"}
        fn = self._overrides.get("office_write")
        if fn is None:
            keep = bool(self.get_settings().get("keep_office_open", True))

            def fn(task: Any) -> dict[str, Any]:
                return write_to_office(task, body, app, title, keep_open=keep)

        name = "Excel" if app == "excel" else "Word"
        return self._runner.start(f"{name}’ga yozish", fn).snapshot()

    def official_document(self, title: str, body: str, kimga: str = "", kimdan: str = "",
                          signer: str = "", date: str = "") -> dict[str, Any]:  # fmt: skip
        """An ariza / xat the AI wrote, in the official layout (doctemplates), DOCX + PDF."""
        from nexvara import doctemplates
        from nexvara.core.task import UserError
        from nexvara.fileagent import free_name

        try:
            blocks = doctemplates.free_blocks(title, body, kimga, kimdan, signer, date)
        except UserError as e:
            return {"error": str(e)}
        name = re.sub(r"[\\/:*?\"<>|]", " ", title.strip().capitalize())[:60].strip() or "Hujjat"
        out = free_name(doctemplates.out_dir() / f"{name} {time.strftime('%Y%m%d-%H%M%S')}.docx")
        fake = self._overrides.get("doctemplate")

        def fn(task: Any) -> dict[str, Any]:
            if fake is not None:
                return fake(task, name, blocks, out)
            return doctemplates.write(task, name, blocks, out, keep_open=self._keep_open())

        return self._runner.start(name, fn).snapshot()

    def open_app(self, app: str) -> str:
        """«Excel’ni och»: start the program itself (an empty Excel/Word/PowerPoint window)."""
        from nexvara.agent.tools import ToolError
        from nexvara.knowledge.textnorm import fold

        programs = {"excel": ("Excel", "excel.exe"), "word": ("Word", "winword.exe"),
                    "powerpoint": ("PowerPoint", "powerpnt.exe"),
                    "notepad": ("Bloknot", "notepad.exe"), "calc": ("Kalkulyator", "calc.exe"),
                    "paint": ("Paint", "mspaint.exe")}  # fmt: skip
        aliases = {
            "microsoft excel": "excel",
            "ms excel": "excel",
            "microsoft word": "word",
            "ms word": "word",
            "microsoft powerpoint": "powerpoint",
            "power point": "powerpoint",
            "bloknot": "notepad",
            "kalkulyator": "calc",
        }
        key = fold(str(app)).strip()
        key = aliases.get(key, key)
        if key not in programs:
            raise ToolError(f"Bu dasturni ochishni bilmayman: {app}")
        name, exe = programs[key]
        fn = self._overrides.get("open_app") or os.startfile  # Windows finds it via App Paths
        try:
            fn(exe)
        except OSError as e:
            raise ToolError(f"{name} ochilmadi: kompyuterda o‘rnatilmagan bo‘lishi mumkin") from e
        return f"{name} ochildi."

    def open_file(self, path: str) -> bool:
        p = Path(path)
        if not p.is_absolute() or not p.exists():
            return False
        if os.name == "nt":
            os.startfile(str(p))  # noqa: S606 - the user's own file, opened on request
        return True

    # ----- chat: "hisobot fayllarini top" -----
    def _chat_find_files(self, text: str) -> dict[str, Any] | None:
        from nexvara import fileagent
        from nexvara.knowledge.textnorm import fold

        f = fold(text)
        if not re.search(r"\bfayl\w*", f) or not re.search(r"\b(top|qidir|izla)\w*", f):
            return None
        words = re.sub(
            r"\b(fayl\w*|top\w*|qidir\w*|izla\w*|menga|iltimos|kompyuter\w*|ichida\w*|"
            r"barcha|hamma|nomli|degan|qaysi|qayerda|shu|bu|ni|dan)\b", " ", f
        )  # fmt: skip
        words = re.sub(r"\s+", " ", words).strip()
        if not words:
            return {"reply": "Qaysi faylni qidiray? Nomidan bir so‘z yozing (masalan «hisobot "
                    "fayllarini top»)."}  # fmt: skip
        found = fileagent.search(words, limit=10)
        if not found:
            return {"reply": f"«{words}» nomli fayl topilmadi. Fayllar bo‘limida boshqa papkani "
                    "tanlab qidirib ko‘ring."}  # fmt: skip
        lines = [f"• {x.name} — {x.folder}" for x in found]
        ctx = getattr(self, "_ctx", None)
        if ctx is not None:
            ctx.set_files([x.path for x in found])  # "topilgan fayllarni ZIP qil"
        return {"reply": f"«{words}» bo‘yicha topildi ({len(found)}):\n" + "\n".join(lines),
                "files": [x.path for x in found]}  # fmt: skip
