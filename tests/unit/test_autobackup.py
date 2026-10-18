"""Weekly automatic backup: what is copied, verification, pruning, chat commands."""

from __future__ import annotations

import sqlite3
import time

from nexvara import autobackup
from nexvara.appdata import Settings


def _data(tmp_path):
    data = tmp_path / "NEXVARA"
    (data / "Darsliklar").mkdir(parents=True)
    (data / "Darsliklar" / "fizika.pdf").write_bytes(b"%PDF big book")
    (data / "bi").mkdir()
    (data / "bi" / "savdo.nxbi").write_text("{}", encoding="utf-8")
    (data / "settings.json").write_text("{}", encoding="utf-8")
    (data / "logs").mkdir()
    (data / "logs" / "app.log").write_text("x", encoding="utf-8")
    with sqlite3.connect(data / "app.db") as db:
        db.execute("CREATE TABLE t (x)")
        db.execute("INSERT INTO t VALUES (42)")
    return data


def test_backup_copies_small_data_only_and_verifies(tmp_path):
    data = _data(tmp_path)
    res = autobackup.backup(data, tmp_path / "zaxira", keep=4)
    assert res["verify_errors"] == []
    dest = tmp_path / "zaxira" / res["path"].split("\\")[-1].split("/")[-1]
    got = {p.relative_to(dest / "data").as_posix() for p in (dest / "data").rglob("*")
           if p.is_file()}  # fmt: skip
    assert got == {"app.db", "settings.json", "bi/savdo.nxbi"}  # no textbooks, no logs
    with sqlite3.connect(dest / "data" / "app.db") as db:
        assert db.execute("SELECT x FROM t").fetchone() == (42,)
    (dest / "data" / "settings.json").write_text("changed", encoding="utf-8")
    assert autobackup.verify(dest) == ["settings.json"]


def test_prune_keeps_newest_and_never_touches_other_folders(tmp_path):
    data = _data(tmp_path)
    root = tmp_path / "zaxira"
    (root / "20261017-160705").mkdir(parents=True)  # a manual full backup
    made = []
    for _ in range(3):
        made.append(autobackup.backup(data, root, keep=2))
        time.sleep(1.05)  # folder names have one-second resolution
    left = sorted(p.name for p in root.iterdir())
    assert len([x for x in left if x.startswith("auto-")]) == 2
    assert "20261017-160705" in left
    assert made[-1]["removed"]


def test_due_weekly_and_switch(tmp_path):
    now = time.time()
    assert autobackup.due({"backup": {"auto": True, "last": 0}}, now)
    assert not autobackup.due({"backup": {"auto": True, "last": now - 3600}}, now)
    assert autobackup.due({"backup": {"auto": True, "last": now - 8 * 86400}}, now)
    assert not autobackup.due({"backup": {"auto": False, "last": 0}}, now)


def test_chat_commands(tmp_path, monkeypatch):
    data = _data(tmp_path)
    monkeypatch.setenv("NEXVARA_DATA", str(data))
    from nexvara.app.api import Api

    bk = autobackup.AutoBackup(Settings(data / "settings.json"))
    api = Api(overrides={"backup": bk})
    assert "Hali zaxira qilinmagan" in api.chat("zaxira qachon qilingan?")["reply"]
    r = api.chat("zaxira qil")
    assert r["reply"].startswith("✅ Zaxira tayyor") and "MB" in r["reply"], r
    assert bk.settings.load()["backup"]["last"] > 0
    assert not bk.tick()  # a week has not passed
    assert "Oxirgisi" in api.chat("zaxira holati")["reply"]
    assert "o‘chirildi" in api.chat("avtomatik zaxirani o‘chir")["reply"]
    assert bk.settings.load()["backup"]["auto"] is False
    assert "yoqildi" in api.chat("avtomatik zaxirani yoq")["reply"]
