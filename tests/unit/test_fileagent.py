"""File Agent on a temporary folder: nothing is overwritten, everything is logged."""

from __future__ import annotations

import os
import zipfile

import pytest

from nexvara import fileagent


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    root = tmp_path / "ish"
    (root / "ichki").mkdir(parents=True)
    (root / "Hisobot 2026.xlsx").write_bytes(b"excel")
    (root / "ichki" / "hisobot-yanvar.docx").write_bytes(b"word")
    (root / "rasm.png").write_bytes(b"png")
    (root / "Xat.txt").write_text("salom", encoding="utf-8")
    return root


def test_search_by_words_and_extension(box):
    names = {f.name for f in fileagent.search("hisobot", box)}
    assert names == {"Hisobot 2026.xlsx", "hisobot-yanvar.docx"}
    assert [f.name for f in fileagent.search("hisobot", box, (".docx",))] == ["hisobot-yanvar.docx"]
    assert [f.name for f in fileagent.search("hisobot 2026", box)] == ["Hisobot 2026.xlsx"]
    assert {f.name for f in fileagent.search("", box, ("png", "txt"))} == {"rasm.png", "Xat.txt"}


def test_info_hash(box):
    i = fileagent.info(box / "Xat.txt")
    assert i["size"] == 5 and len(i["sha256"]) == 64
    with pytest.raises(FileNotFoundError):
        fileagent.info(box / "yoq.txt")


def test_copy_move_never_overwrite(box, tmp_path):
    dst = tmp_path / "nusxa"
    first = fileagent.copy_to([str(box / "Xat.txt")], dst)
    second = fileagent.copy_to([str(box / "Xat.txt")], dst)
    assert [os.path.basename(p) for p in first + second] == ["Xat.txt", "Xat (2).txt"]
    moved = fileagent.move_to([str(box / "rasm.png")], dst)
    assert not (box / "rasm.png").exists() and os.path.isfile(moved[0])
    actions = [x["action"] for x in fileagent.recent_log()]
    assert actions[:3] == ["move", "copy", "copy"]


def test_rename_rules(box):
    new = fileagent.rename(str(box / "Xat.txt"), "Maktub")
    assert new.endswith("Maktub.txt")  # extension kept
    with pytest.raises(ValueError):
        fileagent.rename(new, "a/b")
    (box / "Boshqa.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        fileagent.rename(str(box / "Boshqa.txt"), "Maktub.txt")
    out = fileagent.rename_batch([str(box / "Maktub.txt"), str(box / "Boshqa.txt")], "Xat_{n}")
    assert [os.path.basename(p) for p in out] == ["Xat_1.txt", "Xat_2.txt"]


def test_zip_and_safe_unzip(box, tmp_path):
    z = fileagent.make_zip([str(box / "Xat.txt"), str(box / "ichki")])
    with zipfile.ZipFile(z) as f:
        assert sorted(f.namelist()) == ["Xat.txt", "ichki/hisobot-yanvar.docx"]
    folder = fileagent.unzip(z)
    assert os.path.isfile(os.path.join(folder, "ichki", "hisobot-yanvar.docx"))
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as f:
        f.writestr("../tashqarida.txt", "x")
    with pytest.raises(ValueError, match="Xavfli"):
        fileagent.unzip(str(evil))
    assert not (tmp_path / "tashqarida.txt").exists()


def test_backup_versions_restore(box):
    f = box / "Xat.txt"
    fileagent.backup([str(f)])
    f.write_text("o‘zgargan", encoding="utf-8")
    vers = fileagent.versions(str(f))
    assert len(vers) == 1
    out = fileagent.restore(vers[0]["path"], str(f))
    assert f.read_text(encoding="utf-8") == "salom"
    assert out["previous_saved_as"]  # the changed version was kept too
    assert len(fileagent.versions(str(f))) == 2
    with pytest.raises(ValueError):
        fileagent.restore(str(box / "rasm.png"), str(f))  # only NEXVARA backups


def test_tidy(box):
    plan = fileagent.tidy_plan(box)
    assert {p["name"]: p["to"] for p in plan} == {
        "Hisobot 2026.xlsx": "Jadvallar", "rasm.png": "Rasmlar", "Xat.txt": "Hujjatlar",
    }  # fmt: skip
    assert fileagent.tidy(box) == {"Jadvallar": 1, "Rasmlar": 1, "Hujjatlar": 1}
    assert (box / "Rasmlar" / "rasm.png").is_file()
    assert (box / "ichki" / "hisobot-yanvar.docx").is_file()  # subfolders are left alone


@pytest.mark.skipif(os.name != "nt", reason="Windows Recycle Bin")
def test_recycle(box):
    assert fileagent.recycle([str(box / "Xat.txt")]) == 1
    assert not (box / "Xat.txt").exists()


def test_api_files_and_chat(box):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    runner = TaskRunner()
    api = Api(runner, overrides={"files_to_pdf": lambda t: {"path": "x"}})
    r = api.files_search("hisobot", str(box))
    assert r["ok"] and len(r["files"]) == 2
    assert not api.files_search("", "")["ok"]
    assert not api.files_rename(str(box / "Xat.txt"), "a:b")["ok"]
    snap = api.files_to_pdf([str(box / "Hisobot 2026.xlsx")])
    assert runner.get(snap["id"]).wait(5)
    assert api.chat("fayl top")["reply"].startswith("Qaysi faylni")


def test_answer_text_becomes_a_test_table():
    from nexvara.fileagent import test_rows

    text = """6-sinf informatika testi
1. Kompyuterning «miyasi» qaysi qurilma?
A) Monitor
B) Protsessor
C) Sichqoncha
D) Printer
Javob: B
2) Axborot o‘lchov birligi?
a) Metr
b) Bayt
c) Litr
d) Gramm
To‘g‘ri javob: b"""
    rows = test_rows(text)
    assert rows[0] == ["№", "Savol", "A", "B", "C", "D", "Javob"]
    assert rows[1] == ["1", "Kompyuterning «miyasi» qaysi qurilma?", "Monitor", "Protsessor",
                       "Sichqoncha", "Printer", "B"]  # fmt: skip
    assert rows[2][1:3] == ["Axborot o‘lchov birligi?", "Metr"] and rows[2][6] == "B"
    assert test_rows("Salom! Bugun nima qilamiz?") is None


def test_write_answer_commands_and_last_answer(tmp_path):
    from nexvara.agent.nlu import parse
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore

    assert parse("exselni ochib osha yerga yoz")[0].args == {"app": "excel"}
    assert parse("buni Word’ga yoz")[0].args == {"app": "word"}
    assert parse("Savdo.xlsx ni och") is None
    mem = MemoryStore(tmp_path / "app.db")
    mem.log_chat("user", "test tuz")
    mem.log_chat("nexvara", "1. Savol?\nA) x\nB) y")
    mem.log_chat("user", "exselni ochib osha yerga yoz")
    mem.log_chat("nexvara", "Bu ish pullik AI orqali bajariladi … Davom etaymi?")
    api = Api(TaskRunner(), overrides={"memory": mem})
    assert api._last_answer() == "1. Savol?\nA) x\nB) y"  # the prompt is skipped
    api._overrides["office_write"] = lambda task: {"files": []}
    snap = api.office_write("exsel")
    assert "id" in snap and "Excel" in snap["title"]
    assert "error" in Api(TaskRunner(), overrides={"memory": MemoryStore(tmp_path / "b.db")}
                          ).office_write("word")  # fmt: skip


def test_open_app_commands(tmp_path, monkeypatch):
    """«Excel’ni och» (live 2026-10-22: «Buni tushunmadim») just starts the program."""
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.agent.nlu import parse
    from nexvara.agent.typos import fix
    from nexvara.app.api import Api

    for text, app in [
        ("exelni och", "excel"),
        ("Excel’ni ochib ber", "excel"),
        ("word dasturini och", "word"),
        ("pauerpointni och", "powerpoint"),
        ("iltimos wordni ishga tushir", "word"),
        ("kalkulyatorni och", "calc"),
        ("noutbukimdagi exselni och", "excel"),
    ]:
        assert parse(fix(text))[0].tool == "app.open", text
        assert parse(fix(text))[0].args == {"app": app}, text
    assert parse("exselni ochib osha yerga yoz")[0].tool == "office.write"
    assert parse("Savdo.xlsx ni och") is None
    started: list[str] = []
    api = Api(overrides={"open_app": started.append})
    assert api.chat("exelni och")["reply"] == "Excel ochildi."
    assert started == ["excel.exe"]
    assert api.open_app("Excel") == "Excel ochildi."
    assert api.open_app(" Microsoft PowerPoint ") == "PowerPoint ochildi."
    assert started == ["excel.exe", "excel.exe", "powerpnt.exe"]

    def missing(exe):
        raise FileNotFoundError(exe)

    api._overrides["open_app"] = missing
    assert "o‘rnatilmagan" in api.chat("PowerPointni och")["reply"]


def test_tab_and_markdown_tables_become_columns():
    # Live 2026-10-24: an AI sales table was written into one «Matn» column.
    tab = "Mahsulot\tNarxi\tSoni\tJami\nDaftar\t5 000\t10\t=B2*C2\nRuchka\t3000\t20\t=B3*C3"
    assert fileagent.grid_rows(tab) == [
        ["Mahsulot", "Narxi", "Soni", "Jami"],
        ["Daftar", 5000, 10, "=B2*C2"],
        ["Ruchka", 3000, 20, "=B3*C3"],
    ]
    md = "Jadval:\n| Fan | Baho |\n|---|:---:|\n| Fizika | 4,5 |\n| Ona tili |\nOxiri"
    assert fileagent.grid_rows(md) == [["Fan", "Baho"], ["Fizika", 4.5], ["Ona tili", ""]]
    assert fileagent.grid_rows("Oddiy matn\nikkinchi qator") is None
