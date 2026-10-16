import threading

from nexvara import __version__
from nexvara.app.api import Api
from nexvara.core.task import TaskRunner


def test_get_info():
    info = Api().get_info()
    assert info["version"] == __version__
    assert info["ai_connected"] is False


def test_chat_without_provider_is_explicit():
    api = Api()
    assert api.chat("   ") == {"reply": ""}
    assert "ulanmagan" in api.chat("salom")["reply"]


def test_run_excel_demo_goes_through_runner():
    runner = TaskRunner()

    def fake_demo(task):
        with task.step("Excel'ni ochish"):
            pass
        return {"path": "C:\\x.xlsx", "checks": []}

    api = Api(runner, excel_demo=fake_demo)
    snap = api.run_excel_demo()
    assert runner.get(snap["id"]).wait(5)
    final = api.get_task(snap["id"])
    assert final["status"] == "succeeded"
    assert final["result"]["path"] == "C:\\x.xlsx"
    assert [t["id"] for t in api.list_tasks()] == [snap["id"]]


def test_cancel_task():
    gate = threading.Event()

    def slow(task):
        gate.wait(5)
        task.check_cancelled()

    runner = TaskRunner()
    api = Api(runner, excel_demo=slow)
    snap = api.run_excel_demo()
    assert api.cancel_task(snap["id"]) is True
    gate.set()
    runner.get(snap["id"]).wait(5)
    assert api.get_task(snap["id"])["status"] == "cancelled"
    assert api.cancel_task(snap["id"]) is False
    assert api.cancel_task("missing") is False


def test_reveal_file_rejects_bad_paths(tmp_path):
    api = Api()
    assert api.reveal_file("relative.xlsx") is False
    assert api.reveal_file(str(tmp_path / "missing.xlsx")) is False
