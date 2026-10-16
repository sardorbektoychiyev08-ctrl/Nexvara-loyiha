"""Bridge exposed to the web UI as `window.pywebview.api`.

Every public method must return JSON-serialisable data.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from nexvara import __version__
from nexvara.core.task import TaskFn, TaskRunner


def _excel_demo(task: Any) -> dict[str, Any]:
    from nexvara.skills.excel.demo import run_demo

    return run_demo(task)


class Api:
    def __init__(self, runner: TaskRunner | None = None, excel_demo: TaskFn = _excel_demo) -> None:
        self._runner = runner or TaskRunner()
        self._excel_demo = excel_demo

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
                "bo'limidagi Excel sinovini ishga tushirishingiz mumkin."
            )
        }

    def run_excel_demo(self) -> dict[str, Any]:
        task = self._runner.start("Excel: 10 qatorli jadval", self._excel_demo)
        return task.snapshot()

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
