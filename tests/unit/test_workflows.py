"""Workflow engine with a fake command executor (no Office)."""

from __future__ import annotations

import os
import time

import pytest

from nexvara.core.task import TaskRunner
from nexvara.workflows import Workflow, WorkflowEngine, WorkflowStore


class Fake:
    """Stands in for the chat: records commands, can start a sub-task or fail."""

    def __init__(self, runner, fail_times=0):
        self.runner = runner
        self.calls = []
        self.fail_times = fail_times

    def __call__(self, text):
        self.calls.append(text)
        if "tushunarsiz" in text:
            return {"reply": "Buni tushunmadim."}
        if "pullik" in text:
            return {"reply": "Davom etaymi?", "confirm": "t1"}
        if "fayl" in text or "«" in text:
            fail = self.fail_times > 0
            self.fail_times -= 1

            def fn(task):
                if fail:
                    raise RuntimeError("Excel band")
                return {"path": "D:/natija_NEXVARA.xlsx"}

            return {"reply": "ok", "task": self.runner.start("sub", fn).snapshot()}
        return {"reply": f"Bajarildi: {text}"}


@pytest.fixture
def env(tmp_path):
    runner = TaskRunner()
    fake = Fake(runner)
    store = WorkflowStore(tmp_path / "app.db")
    return runner, fake, store, WorkflowEngine(store, runner, fake)


def wf(**kw):
    d = {"name": "Sinov", "steps": [{"kind": "command", "text": "salom"}]}
    d.update(kw)
    return Workflow.from_dict(d)


def finish(runner, out, timeout=10):
    t = runner.get(out["task"]["id"])
    assert t.wait(timeout)
    return t.snapshot()


def test_validation(tmp_path):
    with pytest.raises(ValueError, match="nom"):
        wf(name="").validate()
    with pytest.raises(ValueError, match="qadam"):
        wf(steps=[]).validate()
    with pytest.raises(ValueError, match="papka"):
        wf(trigger={"type": "folder", "folder": str(tmp_path / "yoq")}).validate()
    with pytest.raises(ValueError, match="fayl"):
        wf(trigger={"type": "folder", "folder": str(tmp_path)}).validate()
    with pytest.raises(ValueError, match="SS:DD"):
        wf(trigger={"type": "daily", "time": "25:00"}).validate()
    wf(trigger={"type": "daily", "time": "08:30"}).validate()


def test_run_steps_and_history(env):
    runner, fake, store, eng = env
    w = store.save(wf(steps=[{"kind": "command", "text": "salom"},
                             {"kind": "command", "text": "«D:/a.xlsx» ni formatla"}]))  # fmt: skip
    snap = finish(runner, eng.start(w))
    assert snap["status"] == "succeeded", snap
    assert snap["result"]["path"] == "D:/natija_NEXVARA.xlsx"
    run = store.runs(w.id)[0]
    assert run["status"] == "succeeded" and [x["ok"] for x in run["log"]] == [True, True]


def test_retry_then_success(env):
    runner, fake, store, eng = env
    fake.fail_times = 1
    w = store.save(wf(steps=[{"kind": "command", "text": "«x.xlsx» ni och"}], retries=1))
    snap = finish(runner, eng.start(w))
    assert snap["status"] == "succeeded"
    assert [s["status"] for s in snap["steps"]] == ["failed", "succeeded"]


def test_stop_or_continue_on_error(env):
    runner, fake, store, eng = env
    steps = [{"kind": "command", "text": "tushunarsiz narsa"}, {"kind": "command", "text": "salom"}]
    w = store.save(wf(name="A", steps=steps))
    snap = finish(runner, eng.start(w))
    assert snap["status"] == "failed" and fake.calls == ["tushunarsiz narsa"]  # no retry, stopped
    w2 = store.save(wf(name="B", steps=steps, on_error="continue"))
    snap = finish(runner, eng.start(w2))
    assert snap["status"] == "succeeded" and fake.calls[-1] == "salom"
    assert store.runs(w2.id)[0]["status"] == "failed"  # the run remembers the failed step


def test_paid_step_is_not_answered(env):
    runner, fake, store, eng = env
    w = store.save(wf(steps=[{"kind": "command", "text": "pullik savol"}], retries=3))
    snap = finish(runner, eng.start(w))
    assert snap["status"] == "failed" and "tasdiq" in snap["error"]
    assert fake.calls == ["pullik savol"]


def test_approval_and_pause(env):
    runner, fake, store, eng = env
    w = store.save(wf(steps=[{"kind": "approve", "text": "Boshlaymi?"},
                             {"kind": "wait", "seconds": 1},
                             {"kind": "command", "text": "salom"}]))  # fmt: skip
    out = eng.start(w)
    run_id = out["run_id"]
    time.sleep(0.5)
    assert eng.active()[0]["waiting_approval"] == "Boshlaymi?"
    assert fake.calls == []
    with pytest.raises(RuntimeError, match="bajarilmoqda"):
        eng.start(w)  # one run of a workflow at a time
    eng.pause(run_id)
    assert eng.approve(run_id)
    time.sleep(1.6)
    assert fake.calls == []  # paused before the command step
    eng.resume(run_id)
    snap = finish(runner, out)
    assert snap["status"] == "succeeded" and fake.calls == ["salom"]
    assert eng.active() == []


def test_cancel_while_waiting(env):
    runner, fake, store, eng = env
    w = store.save(wf(steps=[{"kind": "approve"}, {"kind": "command", "text": "salom"}]))
    out = eng.start(w)
    time.sleep(0.3)
    runner.get(out["task"]["id"]).cancel()
    snap = finish(runner, out)
    assert snap["status"] == "cancelled" and fake.calls == []
    assert store.runs(w.id)[0]["status"] == "cancelled"


def test_folder_trigger_once_per_file(env, tmp_path):
    runner, fake, store, eng = env
    folder = tmp_path / "kelgan"
    folder.mkdir()
    (folder / "eski.xlsx").write_bytes(b"1")  # there before: not processed
    trigger = {"type": "folder", "folder": str(folder), "ext": ".xlsx"}
    store.save(wf(steps=[{"kind": "command", "text": "{fayl} ni formatla"}], trigger=trigger))
    new = folder / "yangi.xlsx"
    new.write_bytes(b"2")
    (folder / "yangi_NEXVARA.xlsx").write_bytes(b"3")  # our own output: ignored
    (folder / "rasm.png").write_bytes(b"4")
    later = time.time() + 10
    assert eng.tick(now=time.time()) == []  # still being copied (too fresh)
    started = eng.tick(now=later)
    assert len(started) == 1
    finish(runner, started[0])
    assert fake.calls == [f"«{new}» ni formatla"]
    assert eng.tick(now=later + 20) == []  # never twice
    os.utime(new, (later, later))  # the file changed: it is new work
    started = eng.tick(now=later + 30)
    assert len(started) == 1
    finish(runner, started[0])


def test_daily_trigger(env):
    runner, fake, store, eng = env
    w = store.save(wf(trigger={"type": "daily", "time": "08:30"}))
    day = time.mktime((2026, 10, 16, 8, 0, 0, 0, 0, -1))
    assert eng.tick(now=day) == []
    started = eng.tick(now=day + 3600)
    assert len(started) == 1
    finish(runner, started[0])
    assert eng.tick(now=day + 7200) == []  # once a day
    assert store.get(w.id).last_daily == "2026-10-16"


def test_api(tmp_path):
    from nexvara.app.api import Api

    store = WorkflowStore(tmp_path / "app.db")
    api = Api(overrides={"workflow_store": store})
    assert len(api.wf_templates()) >= 3
    assert not api.wf_save({"name": "", "steps": []})["ok"]
    r = api.wf_save(
        {"name": "Salom", "steps": [{"kind": "command", "text": "nimalarni eslab qolding"}]}
    )
    assert r["ok"] and r["workflows"][0]["name"] == "Salom"
    out = api.wf_run(r["id"])
    assert out["ok"]
    assert api._runner.get(out["task"]["id"]).wait(10)
    assert api.wf_list()[0]["last_run"]["status"] == "succeeded"
    assert api.wf_delete(r["id"]) == []
    assert Api().wf_list() == []  # plain tests never touch the user's workflows


def test_daily_workflow_saved_after_its_time_waits_for_tomorrow(tmp_path):
    # Live 2026-10-24: made at 22:50 «har kuni 18:00», it ran at once on the next start.
    store = WorkflowStore(tmp_path / "app.db")
    past = time.strftime("%H:%M", time.localtime(time.time() - 3600))
    if past > time.strftime("%H:%M"):
        pytest.skip("just after midnight")
    wf = store.save(
        Workflow.from_dict(
            {
                "name": "Kech",
                "trigger": {"type": "daily", "time": past},
                "steps": [{"kind": "command", "text": "salom"}],
            }
        )
    )
    assert store.get(wf.id).last_daily == time.strftime("%Y-%m-%d")
