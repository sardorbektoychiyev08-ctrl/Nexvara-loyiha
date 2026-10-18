"""Workflows: saved sequences of NEXVARA commands.

A step is one chat command ("{fayl} ni och, jadvalni formatla, PDF qilib saqla"), an
approval point (the run waits for the user's "Tasdiqlash"), or a pause in seconds.
A workflow starts by hand, when a new file appears in a folder, or daily at a set time.

Rules: a step that would spend money (an AI confirmation) or asks a question stops the
run instead of answering for the user; a file is processed once (idempotency by path,
size and time); every run is kept with its log.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nexvara import config

STEP_KINDS = ("command", "approve", "wait")
TRIGGERS = ("manual", "folder", "daily", "weekly")
WEEKDAYS = ("Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya")  # Monday = 0, as time.localtime()
TICK_SECONDS = 15
STABLE_SECONDS = 5  # a new file must be unchanged this long (still being copied otherwise)

TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Kelgan Excel hisobotlarni tayyorlash",
        "steps": [{"kind": "command", "text": "{fayl} ni och, dublikatlarni o‘chir, "
                   "jadvalni formatla, jami qo‘sh, diagramma qo‘sh, PDF qilib saqla"}],
        "trigger": {"type": "folder", "folder": "", "ext": ".xlsx"},
    },
    {
        "name": "Word hujjatlarni PDF qilish",
        "steps": [
            {"kind": "command", "text": "{fayl} ni och, sahifa raqamini qo‘y, PDF qilib saqla"}
        ],
        "trigger": {"type": "folder", "folder": "", "ext": ".docx"},
    },
    {
        "name": "Haftalik hisobot (har juma 17:00)",
        "steps": [{"kind": "command",
                   "text": "Hisobotlar papkasidagi Excel fayllardan haftalik hisobot qil"}],
        "trigger": {"type": "weekly", "days": [4], "time": "17:00"},
    },
    {
        "name": "Haftalik test (tasdiq bilan)",
        "steps": [
            {"kind": "approve", "text": "Test tuzishni boshlaymi?"},
            {"kind": "command", "text": "7-sinf fizika 20 ta test 2 variant"},
        ],
        "trigger": {"type": "manual"},
    },
]  # fmt: skip

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY,
    wf_id INTEGER NOT NULL,
    task_id TEXT NOT NULL DEFAULT '',
    started REAL NOT NULL,
    finished REAL,
    status TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT '',
    log TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS workflow_seen (
    wf_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    PRIMARY KEY (wf_id, key)
);
"""


@dataclass
class Step:
    kind: str
    text: str = ""
    seconds: int = 0


@dataclass
class Workflow:
    name: str
    steps: list[Step]
    trigger: dict[str, Any] = field(default_factory=lambda: {"type": "manual"})
    retries: int = 1  # extra attempts for a failed command step
    on_error: str = "stop"  # stop | continue
    enabled: bool = True
    id: int = 0
    last_daily: str = ""  # date of the last daily run (YYYY-MM-DD)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Workflow:
        steps = [Step(str(s.get("kind", "command")), str(s.get("text", "")).strip(),
                      int(s.get("seconds") or 0)) for s in d.get("steps") or []]  # fmt: skip
        return cls(
            name=str(d.get("name") or "").strip(),
            steps=steps,
            trigger=dict(d.get("trigger") or {"type": "manual"}),
            retries=int(d.get("retries", 1)),
            on_error=str(d.get("on_error") or "stop"),
            enabled=bool(d.get("enabled", True)),
            id=int(d.get("id") or 0),
            last_daily=str(d.get("last_daily") or ""),
        )

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Workflow nomini yozing")
        if not self.steps:
            raise ValueError("Kamida bitta qadam qo‘shing")
        for i, s in enumerate(self.steps, 1):
            if s.kind not in STEP_KINDS:
                raise ValueError(f"{i}-qadam: noma’lum tur")
            if s.kind == "command" and not s.text:
                raise ValueError(f"{i}-qadam: buyruq bo‘sh")
            if s.kind == "wait" and not 1 <= s.seconds <= 3600:
                raise ValueError(f"{i}-qadam: kutish 1–3600 soniya")
        if not 0 <= self.retries <= 5:
            raise ValueError("Qayta urinish 0–5")
        if self.on_error not in ("stop", "continue"):
            raise ValueError("Xatoda: stop yoki continue")
        t = self.trigger.get("type", "manual")
        if t not in TRIGGERS:
            raise ValueError("Noma’lum ishga tushirish turi")
        if t == "folder":
            folder = str(self.trigger.get("folder") or "")
            if not folder or not Path(folder).is_dir():
                raise ValueError("Kuzatiladigan papkani tanlang")
            if not any("{fayl}" in s.text for s in self.steps if s.kind == "command"):
                raise ValueError(
                    "Papka kuzatilsa, buyruqda {fayl} bo‘lishi kerak (yangi fayl o‘rni)"
                )
        if t == "weekly":
            days = self.trigger.get("days")
            if not isinstance(days, list) or not days or not all(d in range(7) for d in days):
                raise ValueError("Hafta kunlarini tanlang")
        if t in ("daily", "weekly"):
            hhmm = str(self.trigger.get("time") or "")
            try:
                h, m = (int(x) for x in hhmm.split(":"))
                assert 0 <= h < 24 and 0 <= m < 60
            except (ValueError, AssertionError):
                raise ValueError("Vaqtni SS:DD ko‘rinishida yozing, masalan 08:30") from None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.data_dir() / "app.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    def save(self, wf: Workflow) -> Workflow:
        wf.validate()
        now = time.time()
        data = wf.to_dict()
        with self._lock, self._db() as db:
            if wf.id:
                n = db.execute(
                    "UPDATE workflows SET data = ?, updated = ? WHERE id = ?",
                    (json.dumps(data, ensure_ascii=False), now, wf.id),
                ).rowcount
                if not n:
                    raise LookupError("workflow topilmadi")
            else:
                cur = db.execute(
                    "INSERT INTO workflows (data, created, updated) VALUES ('{}', ?, ?)", (now, now)
                )
                wf.id = int(cur.lastrowid)
                db.execute(
                    "UPDATE workflows SET data = ? WHERE id = ?",
                    (json.dumps(wf.to_dict(), ensure_ascii=False), wf.id),
                )
        if wf.trigger.get("type") == "folder":
            self.mark_existing(wf)  # only files that arrive from now on
        return wf

    def get(self, wf_id: int) -> Workflow:
        with self._db() as db:
            r = db.execute("SELECT id, data FROM workflows WHERE id = ?", (wf_id,)).fetchone()
        if r is None:
            raise LookupError("workflow topilmadi")
        return Workflow.from_dict({**json.loads(r[1]), "id": r[0]})

    def all(self) -> list[Workflow]:
        with self._db() as db:
            rows = db.execute("SELECT id, data FROM workflows ORDER BY id").fetchall()
        return [Workflow.from_dict({**json.loads(d), "id": i}) for i, d in rows]

    def delete(self, wf_id: int) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM workflows WHERE id = ?", (wf_id,))
            db.execute("DELETE FROM workflow_seen WHERE wf_id = ?", (wf_id,))

    def set_last_daily(self, wf: Workflow, day: str) -> None:
        wf.last_daily = day
        with self._lock, self._db() as db:
            db.execute(
                "UPDATE workflows SET data = ? WHERE id = ?",
                (json.dumps(wf.to_dict(), ensure_ascii=False), wf.id),
            )

    # ----- runs -----
    def start_run(self, wf_id: int, trigger: str) -> int:
        with self._lock, self._db() as db:
            cur = db.execute(
                "INSERT INTO workflow_runs (wf_id, started, status, trigger) VALUES (?, ?, ?, ?)",
                (wf_id, time.time(), "running", trigger),
            )
            return int(cur.lastrowid)

    def update_run(self, run_id: int, **fields: Any) -> None:
        sets, args = [], []
        for k, v in fields.items():
            sets.append(f"{k} = ?")
            args.append(json.dumps(v, ensure_ascii=False) if k == "log" else v)
        with self._lock, self._db() as db:
            db.execute(f"UPDATE workflow_runs SET {', '.join(sets)} WHERE id = ?", (*args, run_id))

    def runs(self, wf_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = (
            "SELECT id, wf_id, task_id, started, finished, status, trigger, log FROM workflow_runs"
        )
        args: tuple = ()
        if wf_id:
            sql += " WHERE wf_id = ?"
            args = (wf_id,)
        with self._db() as db:
            rows = db.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
        return [
            {"id": r[0], "wf_id": r[1], "task_id": r[2], "started": r[3], "finished": r[4],
             "status": r[5], "trigger": r[6], "log": json.loads(r[7] or "[]")}
            for r in rows
        ]  # fmt: skip

    # ----- folder idempotency -----
    @staticmethod
    def file_key(p: Path) -> str:
        st = p.stat()
        return f"{str(p).lower()}|{st.st_size}|{int(st.st_mtime)}"

    def seen(self, wf_id: int, key: str) -> bool:
        with self._db() as db:
            return (
                db.execute(
                    "SELECT 1 FROM workflow_seen WHERE wf_id = ? AND key = ?", (wf_id, key)
                ).fetchone()
                is not None
            )

    def mark(self, wf_id: int, key: str) -> None:
        with self._lock, self._db() as db:
            db.execute("INSERT OR IGNORE INTO workflow_seen VALUES (?, ?)", (wf_id, key))

    def mark_existing(self, wf: Workflow) -> None:
        for p in folder_files(wf):
            self.mark(wf.id, self.file_key(p))


def folder_files(wf: Workflow) -> list[Path]:
    folder = Path(str(wf.trigger.get("folder") or ""))
    if not folder.is_dir():
        return []
    exts = tuple(
        e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
        for e in str(wf.trigger.get("ext") or "").replace(",", " ").split()
    )
    out = []
    for p in folder.iterdir():
        if not p.is_file() or p.name.startswith(("~$", ".")):
            continue
        if "_NEXVARA" in p.stem:  # our own outputs must not trigger the workflow again
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        out.append(p)
    return sorted(out)


# ---------------- running ----------------


class RunControl:
    """Pause/resume/approval for one running workflow."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        self.resume = threading.Event()
        self.resume.set()
        self.approved = threading.Event()
        self.waiting_approval = ""
        self.paused = False
        self.task_id = ""
        self.name = ""


class WorkflowEngine:
    """Runs workflows through the app's own chat (`execute(text)` -> chat reply dict) so a
    workflow step behaves exactly like the same command typed by the user."""

    def __init__(self, store: WorkflowStore, runner: Any, execute: Any) -> None:
        self.store = store
        self.runner = runner
        self.execute = execute
        self.controls: dict[int, RunControl] = {}
        self._busy: set[int] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ----- control -----
    def approve(self, run_id: int) -> bool:
        c = self.controls.get(run_id)
        if c is None or not c.waiting_approval:
            return False
        c.approved.set()
        return True

    def pause(self, run_id: int) -> bool:
        c = self.controls.get(run_id)
        if c is None:
            return False
        c.paused = True
        c.resume.clear()
        return True

    def resume(self, run_id: int) -> bool:
        c = self.controls.get(run_id)
        if c is None:
            return False
        c.paused = False
        c.resume.set()
        return True

    def active(self) -> list[dict[str, Any]]:
        return [
            {
                "run_id": c.run_id,
                "task_id": c.task_id,
                "name": c.name,
                "paused": c.paused,
                "waiting_approval": c.waiting_approval,
            }
            for c in self.controls.values()
        ]

    # ----- start -----
    def start(self, wf: Workflow, file: str = "", trigger: str = "qo‘lda") -> dict[str, Any]:
        with self._lock:
            if wf.id in self._busy:
                raise RuntimeError(f"«{wf.name}» hozir bajarilmoqda")
            self._busy.add(wf.id)
        run_id = self.store.start_run(wf.id, trigger)
        control = RunControl(run_id)
        self.controls[run_id] = control

        def fn(task: Any) -> dict[str, Any]:
            try:
                return self._run(task, wf, file, control)
            finally:
                with self._lock:
                    self._busy.discard(wf.id)
                self.controls.pop(run_id, None)

        title = f"Workflow: {wf.name}" + (f" · {Path(file).name}" if file else "")
        task = self.runner.start(title, fn, timeout=6 * 3600)
        control.task_id, control.name = task.id, wf.name
        self.store.update_run(run_id, task_id=task.id)
        return {"run_id": run_id, "task": task.snapshot()}

    def _wait(self, task: Any, control: RunControl) -> None:
        """Honour pause (between steps) and cancel."""
        while not control.resume.wait(0.3):
            task.check_cancelled()
        task.check_cancelled()

    def _run(self, task: Any, wf: Workflow, file: str, control: RunControl) -> dict[str, Any]:
        log: list[dict[str, Any]] = []
        status = "succeeded"
        outputs: list[str] = []

        def note(i: int, ok: bool, text: str) -> None:
            log.append({"step": i, "ok": ok, "text": text, "ts": time.time()})
            self.store.update_run(control.run_id, log=log)

        try:
            for i, step in enumerate(wf.steps, 1):
                self._wait(task, control)
                if step.kind == "wait":
                    with task.step(f"{i}. {step.seconds} soniya kutish"):
                        end = time.monotonic() + step.seconds
                        while time.monotonic() < end:
                            task.check_cancelled()
                            time.sleep(0.2)
                    note(i, True, "kutildi")
                    continue
                if step.kind == "approve":
                    with task.step(f"{i}. Tasdiq: {step.text or 'davom etaymi?'}") as s:
                        control.waiting_approval = step.text or "Davom etaymi?"
                        s.detail = "Workflows bo‘limida «Tasdiqlash» tugmasini bosing"
                        while not control.approved.wait(0.3):
                            task.check_cancelled()
                        control.approved.clear()
                        control.waiting_approval = ""
                        s.detail = "tasdiqlandi"
                    note(i, True, "tasdiqlandi")
                    continue
                text = step.text.replace("{fayl}", f"«{file}»" if file else "shu fayl")
                ok, detail, out = self._command(task, i, text, wf.retries)
                outputs += out
                note(i, ok, detail)
                if not ok:
                    status = "failed"
                    if wf.on_error == "stop":
                        raise RuntimeError(f"{i}-qadam bajarilmadi: {detail}")
        except Exception as e:
            from nexvara.core.task import TaskCancelled

            status = "cancelled" if isinstance(e, TaskCancelled) else "failed"
            if not log or log[-1].get("text") != str(e):
                note(len(log) + 1, False, str(e) or "to‘xtatildi")
            raise
        finally:
            self.store.update_run(control.run_id, status=status, finished=time.time(), log=log)
        report = [f"{len(wf.steps)} ta qadam", *(f"Natija: {o}" for o in outputs)]
        if status == "failed":
            report.append("Ba’zi qadamlar bajarilmadi (xatoda davom etish yoqilgan)")
        return {"report": report, "path": outputs[-1] if outputs else "", "log": log}

    def _command(self, task: Any, i: int, text: str, retries: int) -> tuple[bool, str, list[str]]:
        from nexvara.core.task import Status

        detail = ""
        for attempt in range(retries + 1):
            name = f"{i}. {text[:80]}" + (f" (urinish {attempt + 1})" if attempt else "")
            with task.step(name) as s:
                ok, detail, outs, final = self._attempt(task, text)
                s.detail = detail[:200]
            if ok:
                return True, detail, outs
            s.status = Status.FAILED
            if final:
                break  # a misunderstood command will not improve on retry
        return False, detail, []

    def _attempt(self, task: Any, text: str) -> tuple[bool, str, list[str], bool]:
        """(ok, detail, output files, final: retrying cannot help)."""
        out = self.execute(text)
        reply = out.get("reply", "")
        if out.get("confirm"):
            return False, f"tasdiq so‘radi — workflow o‘zi javob bermaydi: {reply[:150]}", [], True
        sub = out.get("task")
        if not sub:
            failed = (
                out.get("unhandled")
                or reply.startswith(("Buni tushunmadim", "Qaysi"))
                or ("topilmadi" in reply)
            )
            if failed:
                return False, reply[:300] or "buyruq tushunilmadi", [], True
            return True, reply[:300], [], True
        sub_task = self.runner.get(sub["id"])
        while not sub_task.wait(0.5):
            task.check_cancelled()
        snap = sub_task.snapshot()
        if snap["status"] == "succeeded":
            res = snap.get("result") or {}
            outs = [res[k] for k in ("path", "pdf") if res.get(k)]
            return True, ", ".join(Path(o).name for o in outs) or "bajarildi", outs, True
        return False, f"xato: {snap.get('error') or snap['status']}", [], False

    # ----- triggers -----
    def start_watching(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="workflows", daemon=True)
            self._thread.start()

    def stop_watching(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        import logging

        while not self._stop.wait(TICK_SECONDS):
            try:
                self.tick()
            except Exception:
                logging.getLogger(__name__).exception("workflow tick failed")

    def tick(self, now: float | None = None) -> list[dict[str, Any]]:
        """Start whatever is due: new files in watched folders, daily schedules."""
        now = now or time.time()
        started = []
        for wf in self.store.all():
            if not wf.enabled or wf.id in self._busy:
                continue
            t = wf.trigger.get("type")
            if t == "folder":
                for p in folder_files(wf):
                    try:
                        key = self.store.file_key(p)
                        fresh = now - p.stat().st_mtime < STABLE_SECONDS
                    except OSError:
                        continue
                    if fresh or self.store.seen(wf.id, key):
                        continue
                    self.store.mark(wf.id, key)  # before running: never twice
                    started.append(self.start(wf, str(p), f"yangi fayl: {p.name}"))
                    break  # one file per tick; the rest follow on the next ticks
            elif t in ("daily", "weekly"):
                lt = time.localtime(now)
                today = time.strftime("%Y-%m-%d", lt)
                h, m = (int(x) for x in str(wf.trigger.get("time")).split(":"))
                if t == "weekly" and lt.tm_wday not in (wf.trigger.get("days") or []):
                    continue
                if wf.last_daily != today and (lt.tm_hour, lt.tm_min) >= (h, m):
                    self.store.set_last_daily(wf, today)
                    when = "har kuni" if t == "daily" else WEEKDAYS[lt.tm_wday]
                    started.append(self.start(wf, "", f"{when} {h:02d}:{m:02d}"))
        return started
