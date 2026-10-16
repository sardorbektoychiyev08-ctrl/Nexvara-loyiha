"""Task state machine shared by the agent, the skills and the UI.

A task runs in a background thread and records its steps as it goes, so the UI
can poll a snapshot and show live progress. Cancellation is cooperative: the
running code calls ``check_cancelled()`` (``step()`` does it automatically).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

log = logging.getLogger(__name__)


class Status(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskCancelled(Exception):
    """Raised inside a task when the user asked to cancel it."""


@dataclass
class Step:
    name: str
    status: Status = Status.PENDING
    detail: str = ""
    started_at: float | None = None
    finished_at: float | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class Task:
    title: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: Status = Status.PENDING
    steps: list[Step] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise TaskCancelled()

    @contextmanager
    def step(self, name: str) -> Iterator[Step]:
        self.check_cancelled()
        s = Step(name, Status.RUNNING, started_at=time.time())
        with self._lock:
            self.steps.append(s)
        try:
            yield s
        except TaskCancelled:
            s.status = Status.CANCELLED
            raise
        except Exception as e:
            s.status = Status.FAILED
            s.detail = s.detail or f"{type(e).__name__}: {e}"
            raise
        else:
            s.status = Status.SUCCEEDED
        finally:
            s.finished_at = time.time()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the task thread ends. Returns False on timeout."""
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    @property
    def done(self) -> bool:
        return self.status in (Status.SUCCEEDED, Status.FAILED, Status.CANCELLED)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            steps = [s.snapshot() for s in self.steps]
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "steps": steps,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "cancel_requested": self.cancel_requested,
        }


TaskFn = Callable[[Task], dict[str, Any] | None]


class TaskRunner:
    """Starts tasks in background threads and keeps them for status queries."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def start(self, title: str, fn: TaskFn) -> Task:
        task = Task(title)

        def run() -> None:
            task.status = Status.RUNNING
            try:
                task.result = fn(task) or {}
                task.status = Status.SUCCEEDED
            except TaskCancelled:
                task.status = Status.CANCELLED
            except Exception as e:
                log.exception("Task %s (%s) failed", task.id, title)
                task.error = f"{type(e).__name__}: {e}"
                task.status = Status.FAILED
            finally:
                task.finished_at = time.time()

        with self._lock:
            self._tasks[task.id] = task
        task._thread = threading.Thread(target=run, name=f"task-{task.id}", daemon=True)
        task._thread.start()
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> list[Task]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
