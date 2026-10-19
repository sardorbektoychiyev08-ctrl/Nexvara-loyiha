"""Data Validation and several workbooks -> one, in real Excel (NEXVARA_RUN_OFFICE=1).
Temporary test files only; the originals must stay unchanged."""

import hashlib
import os

import pytest
from tests.office_fixtures import make_sales_xlsx

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_validation_rules_in_real_excel(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.core.task import TaskRunner
    from nexvara.skills.excel.bridge import ExcelSession

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    before = digest(src)
    plan = parse_command(
        "Savdo.xlsx ni och, Soni ustuniga faqat 1 dan 500 gacha butun son kiritilsin, "
        "Summa ustuniga faqat musbat son, Hudud ustuniga tanlash ro‘yxati: Toshkent, "
        "Samarqand, Buxoro, Farg‘ona, keyin saqla"
    )
    assert [a.kind for a in plan.actions].count("validate") == 3, plan.actions
    t = TaskRunner().start("v", lambda task: run_excel_plan(task, plan, src, keep_open=False,
                                                             pause=0))  # fmt: skip
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert all(c["ok"] for c in snap["result"]["checks"]), snap["result"]["checks"]
    assert digest(src) == before  # the original is untouched
    out = tmp_path / "Savdo_NEXVARA.xlsx"
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(out)
        ws = wb.Worksheets(1)
        soni, summa, hudud = (
            ws.Range("C2").Validation,
            ws.Range("D3").Validation,
            ws.Range("A2").Validation,
        )
        got = {
            "soni": (soni.Type, soni.Formula1, soni.Formula2),
            "summa": (summa.Type, summa.Operator, summa.Formula1),
            "hudud": (hudud.Type, hudud.InCellDropdown),
            "msg": soni.ErrorMessage,
            "items": hudud.Formula1,
        }
        wb.Close(False)
        del ws, wb
    assert got["soni"] == (1, "1", "500")  # whole number between 1 and 500
    assert got["summa"][0] == 2 and got["summa"][1] == 7 and got["summa"][2] == "0"
    assert got["hudud"] == (3, True) and "Samarqand" in got["items"] and "Farg" in got["items"]
    assert "1 dan 500 gacha" in got["msg"]


def test_several_workbooks_become_one_book(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.fileagent import combine_workbooks
    from nexvara.skills.excel.bridge import ExcelSession

    a = make_sales_xlsx(tmp_path / "Yanvar.xlsx")
    b = make_sales_xlsx(tmp_path / "Fevral.xlsx")
    before = (digest(a), digest(b))
    t = TaskRunner().start("c", lambda task: combine_workbooks(task, [str(a), str(b)],
                                                               keep_open=False))  # fmt: skip
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    out = snap["result"]["path"]
    assert (digest(a), digest(b)) == before
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(out)
        names = [wb.Worksheets(i).Name for i in range(1, wb.Worksheets.Count + 1)]
        cells = [wb.Worksheets(n).Range("D2").Value for n in names]
        wb.Close(False)
        del wb
    assert names == ["Yanvar", "Fevral"] and cells == [540000, 540000]
