"""Bridge exposed to the web UI as `window.pywebview.api`.

Every public method must return JSON-serialisable data.
"""

from __future__ import annotations

import importlib
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from nexvara import __version__
from nexvara.core.task import TaskFn, TaskRunner

# kind -> (task title, module, runner function). Every runner takes (task, out, keep_open=...)
# and its module has default_output_path().
OFFICE_TASKS: dict[str, tuple[str, str, str]] = {
    "excel_demo": ("Excel: 10 qatorli jadval", "nexvara.skills.excel.demo", "run_demo"),
    "excel_dashboard": (
        "Excel: savdo dashboardi",
        "nexvara.skills.excel.dashboard",
        "run_dashboard",
    ),
    "word_report": ("Word: rasmiy hisobot", "nexvara.skills.word.demo", "run_word_report"),
    "presentation": ("PowerPoint: taqdimot", "nexvara.skills.powerpoint.demo", "run_presentation"),
}


class Api:
    """`output_dir`/`keep_office_open` exist so the UI self-test can run the real
    button flow without leaving files in Documents or Office windows open."""

    def __init__(
        self,
        runner: TaskRunner | None = None,
        excel_demo: TaskFn | None = None,
        excel_dashboard: TaskFn | None = None,
        output_dir: Path | None = None,
        keep_office_open: bool = True,
        overrides: dict[str, TaskFn] | None = None,
    ) -> None:
        self._runner = runner or TaskRunner()
        self._output_dir = output_dir
        self._keep_office_open = keep_office_open
        self._overrides = dict(overrides or {})
        if excel_demo:
            self._overrides["excel_demo"] = excel_demo
        if excel_dashboard:
            self._overrides["excel_dashboard"] = excel_dashboard

    def _task_fn(self, kind: str) -> TaskFn:
        if kind in self._overrides:
            return self._overrides[kind]
        _title, module_name, fn_name = OFFICE_TASKS[kind]

        def run(task: Any) -> dict[str, Any]:
            module = importlib.import_module(module_name)
            out = module.default_output_path()
            if self._output_dir is not None:
                out = self._output_dir / out.name
            return getattr(module, fn_name)(task, out, keep_open=self._keep_office_open)

        return run

    def _start(self, kind: str) -> dict[str, Any]:
        task = self._runner.start(OFFICE_TASKS[kind][0], self._task_fn(kind))
        return task.snapshot()

    def get_info(self) -> dict[str, Any]:
        return {
            "version": __version__,
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "ai_connected": False,
        }

    def chat(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"reply": ""}
        from nexvara.knowledge.service import parse_test_request

        req = parse_test_request(text)
        if req is not None:
            what = " ".join(
                x for x in (f"{req.grade}-sinf" if req.grade else "", req.subject or "") if x
            )
            if not self.library_info()["books"]:
                return {
                    "reply": (
                        "Test tuzish uchun avval darsliklarni qo‘shing: «Darsliklar» bo‘limida "
                        "papkani oching, PDF darsliklarni tashlang va «Yangilash»ni bosing."
                    )
                }
            snap = self.make_test(
                {
                    "grade": req.grade,
                    "subject": req.subject,
                    "topic": req.topic,
                    "count": req.count,
                    "variants": req.variants,
                }
            )
            if "id" not in snap:  # request rejected before a task was started
                return {"reply": snap["error"]}
            topic = f", mavzu: «{req.topic}»" if req.topic else ""
            return {
                "reply": (
                    f"Tushundim: {what or 'darslik'}{topic}, {req.count} ta savol, "
                    f"{req.variants} ta variant. Word'da tuzyapman — jarayon o‘ng panelda."
                ),
                "task": snap,
            }
        return {
            "reply": (
                "AI provayder hali ulanmagan (M7 bosqichi). Hozir men test tuza olaman, masalan: "
                "«7-sinf fizika Nyuton qonunlari 20 ta test». Office Agent bo‘limida Excel, Word "
                "va PowerPoint vazifalari ham bor."
            )
        }

    # ----- textbook library -----
    def library_info(self) -> dict[str, Any]:
        from nexvara import config
        from nexvara.knowledge.service import open_library

        lib = open_library()
        try:
            ok = lib.books()
            other = [b for b in lib.books(status=None) if b.status != "ok"]
            return {
                "folder": str(config.textbooks_dir()),
                "books": [
                    {
                        "label": b.label(),
                        "grade": b.grade,
                        "subject": b.subject,
                        "year": b.year,
                        "pages": b.pages,
                        "file": Path(b.path).name,
                    }
                    for b in ok
                ],
                "problems": [{"file": Path(b.path).name, "note": b.note} for b in other],
                "catalog": {str(g): s for g, s in lib.grades_subjects().items()},
            }
        finally:
            lib.close()

    def open_library_folder(self) -> str:
        from nexvara import config

        folder = config.textbooks_dir()
        folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            subprocess.Popen(["explorer", str(folder)])
        return str(folder)

    def index_library(self) -> dict[str, Any]:
        from nexvara.knowledge.service import index_library

        fn = self._overrides.get("index_library", index_library)
        return self._runner.start("Darsliklarni indekslash", fn).snapshot()

    def make_test(self, params: dict[str, Any]) -> dict[str, Any]:
        from nexvara.knowledge.service import TestRequest

        def as_int(v: Any) -> int | None:
            return int(v) if v not in (None, "") else None

        try:
            req = TestRequest(
                grade=as_int(params.get("grade")),
                subject=params.get("subject") or None,
                topic=str(params.get("topic") or "").strip(),
                count=20 if as_int(params.get("count")) is None else as_int(params.get("count")),
                variants=1
                if as_int(params.get("variants")) is None
                else as_int(params.get("variants")),
            )
            req.validate()
        except (TypeError, ValueError) as e:
            return {"error": f"Noto‘g‘ri so‘rov: {e}"}
        if "make_test" in self._overrides:
            fn = self._overrides["make_test"]
        else:
            from nexvara.knowledge.testdoc import run_make_test

            def fn(task: Any) -> dict[str, Any]:
                out = None
                if self._output_dir is not None:
                    from nexvara.knowledge.service import default_test_path, make_quizzes

                    book, topic, _ = make_quizzes(req)
                    out = self._output_dir / default_test_path(book, topic).name
                return run_make_test(task, req, out, keep_open=self._keep_office_open)

        what = " ".join(
            x for x in (f"{req.grade}-sinf" if req.grade else "", req.subject or "") if x
        )
        title = f"Test: {what or 'darslik'}" + (f" · {req.topic}" if req.topic else "")
        return self._runner.start(title, fn).snapshot()

    def run_excel_demo(self) -> dict[str, Any]:
        return self._start("excel_demo")

    def run_excel_dashboard(self) -> dict[str, Any]:
        return self._start("excel_dashboard")

    def run_word_report(self) -> dict[str, Any]:
        return self._start("word_report")

    def run_presentation(self) -> dict[str, Any]:
        return self._start("presentation")

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = self._runner.get(task_id)
        return task.snapshot() if task else None

    def cancel_task(self, task_id: str) -> bool:
        task = self._runner.get(task_id)
        if task is None or task.done:
            return False
        task.cancel()
        return True

    def list_tasks(self) -> list[dict[str, Any]]:
        return [t.snapshot() for t in self._runner.list()]

    def reveal_file(self, path: str) -> bool:
        """Show a task's output file in Explorer. Only existing files are accepted."""
        p = Path(path)
        if not p.is_absolute() or not p.is_file():
            return False
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(p)])
        return True
