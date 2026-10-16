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
        return {
            "reply": (
                "AI provayder hali ulanmagan (M7 bosqichi). Hozircha Office Agent "
                "bo'limidagi Excel, Word va PowerPoint vazifalarini ishga tushirishingiz mumkin."
            )
        }

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
