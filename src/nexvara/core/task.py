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


class UserError(Exception):
    """A problem the user can fix (file not found, column missing...). Shown without a
    technical prefix."""


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
        """Block until the task is finished (or given up by the watchdog). False on timeout."""
        if self._thread is None:
            return True
        deadline = None if timeout is None else time.monotonic() + timeout
        while self._thread.is_alive() and not self.done:
            left = None if deadline is None else deadline - time.monotonic()
            if left is not None and left <= 0:
                return False
            self._thread.join(0.2 if left is None else min(0.2, left))
        if self._thread.is_alive():
            return True  # given up by the watchdog
        # The worker may have just returned; let it publish its final status.
        for _ in range(50):
            if self.done:
                break
            time.sleep(0.01)
        return True

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


DEFAULT_TIMEOUT = 600.0  # seconds; Office work that takes longer is treated as hung


class TaskRunner:
    """Starts tasks in background threads and keeps them for status queries."""

    def __init__(self, timeout: float | None = DEFAULT_TIMEOUT) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self.timeout = timeout

    def start(self, title: str, fn: TaskFn, timeout: float | None = None) -> Task:
        """Run `fn` in a thread. After `timeout` seconds a hung task is marked failed
        (and asked to cancel) so the UI never waits forever on a stuck Office call."""
        task = Task(title)
        limit = timeout if timeout is not None else self.timeout
        finish_lock = threading.Lock()

        def finish(status: Status, error: str = "", result: dict | None = None) -> None:
            with finish_lock:
                if task.done:
                    return  # the watchdog already gave up on this task
                if result is not None:
                    task.result = result
                task.error = error
                task.status = status
                task.finished_at = time.time()

        def run() -> None:
            task.status = Status.RUNNING
            try:
                finish(Status.SUCCEEDED, result=fn(task) or {})
            except TaskCancelled:
                finish(Status.CANCELLED)
            except Exception as e:
                log.exception("Task %s (%s) failed", task.id, title)
                friendly = isinstance(e, UserError | LookupError)
                finish(Status.FAILED, str(e) if friendly else f"{type(e).__name__}: {e}")

        def watchdog() -> None:
            if task._thread is not None:
                task._thread.join(limit)
                if task._thread.is_alive():
                    log.error("Task %s (%s) timed out after %ss", task.id, title, limit)
                    task.cancel()
                    finish(
                        Status.FAILED,
                        f"Vaqt tugadi ({int(limit // 60) or 1} daqiqa): dastur javob bermadi. "
                        "Office oynasida ochiq dialog yo‘qligini tekshiring va qayta urinib "
                        "ko‘ring.",
                    )

        with self._lock:
            self._tasks[task.id] = task
        task._thread = threading.Thread(target=run, name=f"task-{task.id}", daemon=True)
        task._thread.start()
        if limit:
            threading.Thread(target=watchdog, name=f"watchdog-{task.id}", daemon=True).start()
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> list[Task]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
