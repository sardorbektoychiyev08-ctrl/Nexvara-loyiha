"""First-start guide: shown once on a new PC, never to someone who already used NEXVARA."""

import sqlite3


def _api(tmp_path, monkeypatch, **over):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    office = {"excel": True, "word": True, "powerpoint": False}
    return Api(overrides={"onboarding_force": True, "office_installed": lambda: office, **over})


def test_new_pc_sees_the_guide_once(tmp_path, monkeypatch):
    api = _api(tmp_path, monkeypatch)
    st = api.onboarding_status()
    assert st["show"] and st["office"] == {"excel": True, "word": True, "powerpoint": False}
    assert api.onboarding_status()["show"]  # still there until finished or skipped
    api.onboarding_done()
    assert api.onboarding_status() == {"show": False}
    assert api.get_settings()["onboarding"]["done"] is True


def test_existing_user_is_never_interrupted(tmp_path, monkeypatch):
    from nexvara.app.api_onboarding import used_before

    api = _api(tmp_path, monkeypatch)
    assert used_before() is False  # nothing yet
    db = tmp_path / "data" / "app.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE chat_log (id INTEGER PRIMARY KEY, ts REAL, role TEXT, text TEXT)")
    con.commit()
    assert used_before() is False  # an empty table: still a new PC
    con.execute("INSERT INTO chat_log (ts, role, text) VALUES (1, 'user', 'salom')")
    con.commit()
    con.close()
    assert used_before() is True
    assert api.onboarding_status() == {"show": False}
    assert api.get_settings()["onboarding"]["done"] is True  # remembered


def test_tests_and_self_tests_never_see_it(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    assert Api().onboarding_status() == {"show": False}
