"""Final integration on real, visible Excel / Word / PowerPoint, driven only through the chat:
Memory alias + Teach rule + a two-step chain + Files, a Workflow created and run by chat,
bulk PDF of all three Office formats, and a BI dashboard from the Excel result.

Only throwaway files in tmp_path are used; the originals must stay byte-identical.
Run with NEXVARA_RUN_OFFICE=1 (scripts/test.ps1 -Office)."""

import hashlib
import os
from pathlib import Path

import pytest
from tests.office_fixtures import make_letter_docx, make_sales_xlsx

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore
    from nexvara.workflows import WorkflowStore

    work = tmp_path / "Sinov"
    work.mkdir()
    db = tmp_path / "app.db"
    api = Api(
        TaskRunner(timeout=900),
        keep_office_open=False,
        overrides={"memory": MemoryStore(db), "workflow_store": WorkflowStore(db)},
    )
    return api, work


def finish(api, reply, timeout=600):
    assert reply.get("task"), reply
    t = api._runner.get(reply["task"]["id"])
    assert t.wait(timeout), "task did not finish"
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    return snap


def test_excel_memory_teach_chain_files_bi(env):
    api, work = env
    src = make_sales_xlsx(work / "Oylik.xlsx")
    before = digest(src)
    arxiv = work / "Arxiv"

    r = api.chat(f"Eslab qol: oylik hisobotim {src}")
    api.confirm_ai(r["confirm"])
    r = api.chat("Har doim Excel jadvalini formatla")
    assert r.get("confirm"), r
    api.confirm_ai(r["confirm"])

    r = api.chat(
        f"oylik hisobotimni och, jami qo‘sh va PDF qilib saqla, keyin uni {arxiv} ga ko‘chir"
    )
    assert r.get("plan") and len(r["plan"]) == 2, r
    snap = finish(api, r)
    assert digest(src) == before, "the original workbook must not change"
    assert (work / "Oylik_NEXVARA.xlsx").is_file()
    assert list(arxiv.glob("Oylik_NEXVARA*.pdf")), list(work.rglob("*"))
    assert any("O‘rgatilgan qoidalar" in x for x in snap["result"]["replies"]), snap["result"]

    # BI on the Excel result (openpyxl, no Office), then a KPI answer in chat.
    r = api.chat(f"{work / 'Oylik_NEXVARA.xlsx'} dan dashboard yarat va «Oylik» deb saqla")
    assert "saqlandi" in r["reply"], r
    assert "ta qator" in api.chat("«Oylik» dashboardi ko‘rsatkichlarini ayt")["reply"]


def test_word_workflow_by_chat(env):
    api, work = env
    src = make_letter_docx(work / "Ariza.docx")
    before = digest(src)
    r = api.chat(f"«Ariza PDF» workflow yarat: {src} ni och, «Aliyev» so‘zini «Valiyev» ga "
                 "almashtir va PDF qilib saqla")  # fmt: skip
    assert "saqlandi" in r["reply"], r
    snap = finish(api, api.chat("«Ariza PDF» workflowini ishga tushir"))
    assert digest(src) == before
    assert (work / "Ariza_NEXVARA.docx").is_file() and (work / "Ariza_NEXVARA.pdf").is_file()
    assert "succeeded" in api.chat("«Ariza PDF» workflowi tarixini ko‘rsat")["reply"], snap


def test_bulk_pdf_all_three_formats_by_chat(env):
    api, work = env
    from nexvara.core.task import TaskRunner
    from nexvara.skills.powerpoint.demo import run_presentation

    make_sales_xlsx(work / "Jadval.xlsx")
    make_letter_docx(work / "Xat.docx")
    t = TaskRunner().start(
        "ppt", lambda task: run_presentation(task, work / "Slayd.pptx", keep_open=False, pause=0)
    )
    assert t.wait(600) and t.snapshot()["status"] == "succeeded", t.snapshot()["error"]
    before = {p.name: digest(p) for p in work.iterdir() if p.is_file()}
    r = api.chat(f"{work} papkasidagi barcha fayllarni PDF qil")
    assert "3 ta fayl" in r["reply"], r
    finish(api, r)
    for stem in ("Jadval", "Xat", "Slayd"):
        assert (work / f"{stem}.pdf").is_file(), stem
    assert {n: digest(work / n) for n in before} == before  # sources untouched
