import pytest

from nexvara.app.api import Api
from nexvara.appdata import DEFAULT_SETTINGS, History, Settings
from nexvara.core.task import TaskRunner


def test_settings_defaults_merge_and_validation(tmp_path):
    s = Settings(tmp_path / "settings.json")
    assert s.load() == DEFAULT_SETTINGS
    out = s.update({"theme": "light", "ai": {"daily_budget_usd": 2.5}, "junk": 1})
    assert out["theme"] == "light" and out["ai"]["daily_budget_usd"] == 2.5
    assert out["ai"]["monthly_budget_usd"] == DEFAULT_SETTINGS["ai"]["monthly_budget_usd"]
    assert "junk" not in out
    assert Settings(tmp_path / "settings.json").load()["theme"] == "light"  # persisted
    for bad in ({"theme": "pink"}, {"test_count": 0}, {"ai": {"provider": "x"}}):
        with pytest.raises(ValueError):
            s.update(bad)
    assert s.load()["theme"] == "light"  # a rejected change leaves the file intact


def test_settings_read_while_another_thread_saves(tmp_path, monkeypatch):
    """Windows briefly refuses to open the file while it is replaced: the reader waits, it
    never sees the defaults (AI «off») and never writes them over the owner's settings."""
    import threading
    from pathlib import Path

    s = Settings(tmp_path / "settings.json")
    s.update({"theme": "light", "ai": {"enabled": True}})
    real, busy = Path.read_text, {"n": 2}

    def flaky(self, *a, **k):
        if self.name == "settings.json" and busy["n"] > 0:
            busy["n"] -= 1
            raise PermissionError(13, "used by another process")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", flaky)
    assert s.load()["ai"]["enabled"] and busy["n"] == 0
    busy["n"] = 1
    assert s.update({"test_count": 7})["theme"] == "light"  # not the defaults
    monkeypatch.setattr(Path, "read_text", real)
    # and with real threads: many saves while another thread keeps reading
    seen, stop = [], threading.Event()

    def reader():
        while not stop.is_set():
            seen.append(s.load()["ai"]["enabled"])

    t = threading.Thread(target=reader)
    t.start()
    for i in range(150):
        Settings(s.path).update({"test_count": 10 + i % 5})
    stop.set()
    t.join()
    assert seen and all(seen) and s.load()["theme"] == "light"


def test_history_survives_and_is_trimmed(tmp_path):
    h = History(tmp_path / "app.db", keep=3)
    for i in range(5):
        h.save({"id": f"t{i}", "title": f"T{i}", "status": "succeeded", "created_at": i,
                "result": {"path": f"C:/x{i}"}, "steps": []})  # fmt: skip
    rows = History(tmp_path / "app.db").list()
    assert [r["id"] for r in rows] == ["t4", "t3", "t2"]
    assert rows[0]["result"] == {"path": "C:/x4"}
    h.clear()
    assert h.list() == []


def test_api_persists_finished_tasks(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path))
    runner = TaskRunner()
    api = Api(runner, overrides={"excel_demo": lambda t: {"path": "x"}}, persist=True)
    snap = api.run_excel_demo()
    assert runner.get(snap["id"]).wait(5)
    # A new app session (new Api, new runner) still sees the task.
    later = Api(TaskRunner(), persist=True)
    assert [t["id"] for t in later.list_tasks()] == [snap["id"]]
    assert later.list_tasks()[0]["status"] == "succeeded"
    assert later.save_settings({"theme": "light"})["ok"]
    assert later.get_settings()["theme"] == "light"
    assert not later.save_settings({"test_count": 99})["ok"]


def test_icon_is_a_valid_ico(tmp_path):
    from nexvara.app.shortcut import write_icon

    data = write_icon(tmp_path / "n.ico").read_bytes()
    assert data[:4] == b"\x00\x00\x01\x00" and data[22:30] == b"\x89PNG\r\n\x1a\n"
