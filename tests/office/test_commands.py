"""Uzbek commands executed in real Excel / Word / PowerPoint. Run with NEXVARA_RUN_OFFICE=1."""

import hashlib
import os

import pytest
from tests.office_fixtures import SALES_ROWS, make_letter_docx, make_sales_xlsx
from tests.textbook_fixture import write_pdf

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(fn, *args, timeout=300, **kw):
    from nexvara.core.task import TaskRunner

    t = TaskRunner().start("cmd", lambda task: fn(task, *args, keep_open=False, pause=0, **kw))
    assert t.wait(timeout), "task did not finish"
    return t


def test_excel_multi_step_command_keeps_original(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.skills.excel.bridge import ExcelSession

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    before = digest(src)
    plan = parse_command(
        "Savdo.xlsx ni och, tozala, dublikatlarni o‘chir, jami qo‘sh, Summa bo‘yicha kamayish "
        "tartibida sarala, jadvalni formatla, jami qo‘sh, Hudud bo‘yicha diagramma qo‘sh va PDF "
        "qilib saqla"
    )
    t = run(run_excel_plan, plan, src)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert all(c["ok"] for c in snap["result"]["checks"])
    assert digest(src) == before, "the original file must not change"
    out = tmp_path / "Savdo_NEXVARA.xlsx"
    assert out.is_file() and (tmp_path / "Savdo_NEXVARA.pdf").is_file()

    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(out)
        ws = wb.Worksheets(1)
        first_col = [ws.Cells(r, 1).Value for r in range(1, 12)]
        amounts = [ws.Cells(r, 4).Value for r in range(2, 9)]
        cats = list(ws.ChartObjects(1).Chart.SeriesCollection(1).XValues)
        total = ws.Cells(9, 4).Value
        del ws, wb
    assert first_col.count("JAMI") == 1  # "jami" twice -> still one total row
    assert amounts == sorted(amounts, reverse=True) and len(amounts) == 7
    unique = {r[3] for r in SALES_ROWS[:5] + SALES_ROWS[6:]}
    assert total == sum(unique)
    assert "JAMI" not in cats and set(cats) == {"Toshkent", "Samarqand", "Buxoro", "Farg‘ona"}


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("Savdo.xlsx da Hudud ustunida Toshkentni filtrla", "3 ta qator"),
        ("Savdo.xlsx da Summa 1000000 dan katta qatorlarni filtrla", "2 ta qator"),
    ],
)
def test_excel_filters(tmp_path, command, expected):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    t = run(run_excel_plan, parse_command(command), src)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", snap["error"]
    assert any(expected in line for line in snap["result"]["report"]), snap["result"]["report"]


def test_excel_unknown_column_is_a_clear_message(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    t = run(run_excel_plan, parse_command("Savdo.xlsx da Narx bo‘yicha sarala"), src)
    assert t.snapshot()["status"] == "failed"
    assert t.error.startswith("Ustun topilmadi: «narx»") and "Summa" in t.error


def test_excel_overwrite_makes_backup(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    before = digest(src)
    t = run(run_excel_plan, parse_command("Savdo.xlsx ni formatla va ustiga saqla"), src)
    assert t.snapshot()["status"] == "succeeded", t.error
    assert digest(src) != before
    backups = list(tmp_path.glob("Savdo.bak-*.xlsx"))
    assert len(backups) == 1 and digest(backups[0]) == before


def test_word_command(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.word_exec import run_word_plan

    src = make_letter_docx(tmp_path / "ariza.docx")
    before = digest(src)
    plan = parse_command(
        'ariza.docx da "Aliyev Vali" ni "Karimov Olim" ga almashtir, shriftni Times New Roman 14 '
        "qil, qator oralig‘ini 1,5 qil, xatboshi 1,25 sm, sahifa raqamlarini qo‘y, mundarija "
        "qo‘sh va PDF ga saqla"
    )
    t = run(run_word_plan, plan, src)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert len(snap["result"]["checks"]) == 8 and all(c["ok"] for c in snap["result"]["checks"])
    assert digest(src) == before
    assert (tmp_path / "ariza_NEXVARA.pdf").is_file()


def test_word_missing_text_is_reported(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.word_exec import run_word_plan

    src = make_letter_docx(tmp_path / "ariza.docx")
    t = run(run_word_plan, parse_command('ariza.docx da "Yo‘q" ni "X" ga almashtir'), src)
    assert t.snapshot()["status"] == "failed" and t.error == "Hujjatda «Yo‘q» topilmadi"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    books = tmp_path / "data" / "Darsliklar" / "7-sinf"
    books.mkdir(parents=True)
    write_pdf(books / "Fizika.pdf")
    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import index_library

    assert TaskRunner().start("index", index_library).wait(120)
    return tmp_path / "data"


def test_topic_presentation_then_pdf_command(data_dir):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.ppt_exec import run_ppt_plan, run_topic_presentation
    from nexvara.knowledge.topicdoc import TopicRequest

    t = run(run_topic_presentation, TopicRequest(7, "Fizika", "tezlik va kuch"))
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    res = snap["result"]
    assert res["slides"] >= 4 and all(c["ok"] for c in res["checks"])
    pptx = os.path.basename(res["path"])

    # And an existing presentation -> PDF by command.
    from pathlib import Path

    plan = parse_command(f"{pptx} ni PDF ga aylantir")
    t2 = run(run_ppt_plan, plan, Path(res["path"]))
    assert t2.snapshot()["status"] == "succeeded", t2.error
    assert t2.result["path"].endswith("_NEXVARA.pdf")


def test_chat_runs_a_command_and_remembers_the_file(tmp_path):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    runner = TaskRunner()
    api = Api(runner, keep_office_open=False)
    assert api.set_context_file(str(src))["path"] == str(src)

    reply = api.chat("shu faylni formatla, jami qo‘sh va saqla")
    assert "task" in reply, reply
    task = runner.get(reply["task"]["id"])
    assert task.wait(300) and task.snapshot()["status"] == "succeeded", task.error
    assert api.get_context_file() == str(src)
    assert "Qaysi Excel fayli" in api.__class__(TaskRunner()).chat("jadvalni formatla")["reply"]


def test_chat_command_in_real_ui(tmp_path):
    """Opens NEXVARA, types a command into the chat, waits for "Tayyor ✓"."""
    import subprocess
    import sys

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    proc = subprocess.run(
        [sys.executable, "-m", "nexvara.app.main", "--selftest-chat", str(src)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=400,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST PASS [chat]" in proc.stdout
    assert (tmp_path / "Savdo_NEXVARA.xlsx").is_file()
