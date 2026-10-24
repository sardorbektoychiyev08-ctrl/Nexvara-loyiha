"""Chat: translate / rewrite a Word or PowerPoint file with AI (mixed into app.api.Api).

The price is estimated from the file's own text (read from the .docx/.pptx XML, no Office
needed), then «Ha» is asked unless the request is free (Gemini free mode). The work is a task:
Office opens visibly, the result is a new file next to the original (nexvara/officeai.py).
"""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any

OFFICE_EXT = (".docx", ".pptx")
_FILE = re.compile(
    r"[«\"“]([^«»\"“”]+?\.(?:docx|pptx))[»\"”]|([\w\\/:.\-‘’()]+?\.(?:docx|pptx))\b", re.IGNORECASE
)


def xml_text_size(path: Path) -> int:
    """Characters of visible text in a .docx/.pptx (for the price, before Office opens)."""
    try:
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if re.fullmatch(
                r"word/document\.xml|ppt/slides/slide\d+\.xml", n)]  # fmt: skip
            text = "".join(re.sub(r"<[^>]+>", "", z.read(n).decode("utf-8", "ignore"))
                           for n in names)  # fmt: skip
    except (OSError, zipfile.BadZipFile):
        return 0
    return len(text)


class OfficeAiApi:
    _overrides: dict
    _pending: dict
    _context_file: str | None

    def _chat_officeai(self, text: str) -> dict[str, Any] | None:
        from nexvara import officeai
        from nexvara.agent import files
        from nexvara.ai.router import AiUnavailable, BudgetExceeded

        job = officeai.what_to_do(text)
        if job is None:
            return None
        from nexvara.agent.parse import find_file

        m = _FILE.search(text)
        cur = self._context_file
        name = (m.group(1) or m.group(2)) if m else (
            cur if cur and Path(cur).suffix.lower() in OFFICE_EXT else None)  # fmt: skip
        whole = find_file(text)  # «D:\…\Tushuntirish xati 2026….docx» with spaces, unquoted
        if m and whole and Path(whole).suffix.lower() in OFFICE_EXT and len(whole) > len(name):
            name = whole
        if not name:
            return None
        try:
            src = files.resolve(name, Path(cur).parent if cur else None)
        except LookupError as e:
            return {"reply": str(e)}
        if src.suffix.lower() not in OFFICE_EXT:
            return {"reply": "Tarjima va qayta yozish .docx va .pptx fayllar uchun"}
        need = self._need_ai()
        if need:
            return need
        size = xml_text_size(src)
        if not size:
            return {"reply": f"«{src.name}» ichida matn topilmadi"}
        router = self._router()
        try:
            est = router.estimate("balanced", officeai.system_prompt(job),
                                  [{"role": "user", "content": "x" * size}],
                                  expected_out=size // 3)  # fmt: skip
            router.check_budget(est, approved=True)  # limits stop it before asking
        except (AiUnavailable, BudgetExceeded) as e:
            return {"reply": str(e)}
        payload = {"path": str(src), "job": job}
        what = f"{job['lang']} tiliga tarjima" if job["mode"] == "translate" else "qayta yozish"
        if est.free:
            return self._run_officeai(payload)
        token = uuid.uuid4().hex[:12]
        self._pending[token] = ("officeai", payload)
        return {"reply": f"📄 «{src.name}» — {what} ({size} belgi): {est.describe()}.\n"
                "Matn AI’ga yuboriladi (shaxsiy ma’lumotlar yashiriladi). Natija yangi faylga "
                "yoziladi, asl fayl o‘zgarmaydi.\n\nDavom etaymi?", "confirm": token}  # fmt: skip

    def _run_officeai(self, payload: dict[str, Any]) -> dict[str, Any]:
        from nexvara import officeai

        src, job = Path(payload["path"]), payload["job"]
        router = self._router()
        keep = bool(self.get_settings().get("keep_office_open", True))
        runner = self._overrides.get("officeai_run") or officeai.run

        def ask(system: str, user: str) -> str:
            n = len(json.loads(user))

            def fits(t: str) -> bool:
                return officeai.parse_items(t, n) is not None

            msgs = [{"role": "user", "content": user}]
            return router.complete("translate", system, msgs, max_tokens=12000, approved=True,
                                   accept=fits).text  # fmt: skip

        def fn(task: Any) -> dict[str, Any]:
            return runner(task, src, job, ask, keep_open=keep)

        what = "Tarjima" if job["mode"] == "translate" else "Qayta yozish"
        snap = self._runner.start(f"{what}: {src.name}", fn).snapshot()
        return {"reply": f"{what} boshlandi — Office ekranda ochiladi, natija yangi faylda.",
                "task": snap}  # fmt: skip
