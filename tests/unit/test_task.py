import threading

import pytest

from nexvara.core.task import Status, TaskCancelled, TaskRunner


def test_success_records_steps_and_result():
    def fn(task):
        with task.step("a"):
            pass
        with task.step("b") as s:
            s.detail = "done"
        return {"x": 1}

    t = TaskRunner().start("ok", fn)
    assert t.wait(5)
    snap = t.snapshot()
    assert snap["status"] == "succeeded"
    assert snap["result"] == {"x": 1}
    assert [(s["name"], s["status"]) for s in snap["steps"]] == [
        ("a", "succeeded"),
        ("b", "succeeded"),
    ]
    assert snap["steps"][1]["detail"] == "done"
    assert snap["finished_at"] is not None


def test_failure_marks_step_and_task():
    def fn(task):
        with task.step("boom"):
            raise RuntimeError("bad thing")

    t = TaskRunner().start("fail", fn)
    assert t.wait(5)
    assert t.status is Status.FAILED
    assert "bad thing" in t.error
    assert t.steps[0].status is Status.FAILED
    assert "RuntimeError" in t.steps[0].detail


def test_cancel_stops_before_next_step():
    started = threading.Event()
    release = threading.Event()

    def fn(task):
        with task.step("first"):
            started.set()
            release.wait(5)
        with task.step("second"):
            pass

    runner = TaskRunner()
    t = runner.start("cancel", fn)
    assert started.wait(5)
    t.cancel()
    release.set()
    assert t.wait(5)
    assert t.status is Status.CANCELLED
    assert [s.name for s in t.steps] == ["first"]


def test_check_cancelled_raises():
    runner = TaskRunner()
    gate = threading.Event()
    t = runner.start("x", lambda task: gate.wait(5) and task.check_cancelled())
    t.cancel()
    gate.set()
    assert t.wait(5)
    assert t.status is Status.CANCELLED
    with pytest.raises(TaskCancelled):
        t.check_cancelled()


def test_runner_lookup_and_order():
    runner = TaskRunner()
    a = runner.start("a", lambda t: None)
    b = runner.start("b", lambda t: None)
    a.wait(5)
    b.wait(5)
    assert runner.get(a.id) is a
    assert runner.get("missing") is None
    assert {t.id for t in runner.list()} == {a.id, b.id}
