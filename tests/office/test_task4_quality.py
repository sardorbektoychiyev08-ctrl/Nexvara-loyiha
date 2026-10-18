"""Task 4 regressions against real, disposable Office documents."""

import hashlib
import os
from datetime import datetime

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(os.environ.get("NEXVARA_RUN_OFFICE") != "1", reason="real Office required"),
]


def _run(fn, *args):
    from nexvara.core.task import TaskRunner

    task = TaskRunner().start("quality", lambda t: fn(t, *args, keep_open=False, pause=0))
    assert task.wait(300), "Office command timed out"
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert all(item["ok"] for item in snap["result"]["checks"])
    return snap["result"]


@pytest.mark.parametrize("orders", ["jami qo‘sh, formatla", "formatla, jami qo‘sh"])
def test_excel_footer_border_in_both_orders(tmp_path, orders):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import ExcelSession

    src = tmp_path / "Savdo.xlsx"
    with ExcelSession(visible=False) as xl:
        wb = xl.new_workbook()
        ops.write_rows(wb.ActiveSheet, [["Hudud", "Summa"], ["Toshkent", 1200], ["Buxoro", 800]])
        xl.save_as(wb, src)
        wb.Close(SaveChanges=False)
    before = hashlib.sha256(src.read_bytes()).digest()
    plan = parse_command(f"Savdo.xlsx ni och, {orders}, PDF qilib saqla")
    assert not plan.unknown
    result = _run(run_excel_plan, plan, src)
    assert hashlib.sha256(src.read_bytes()).digest() == before
    assert result["pdf"]
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(result["path"])
        ws = wb.ActiveSheet
        assert ws.Cells(4, 1).Value == "JAMI"
        assert ws.Cells(4, 1).Borders(9).LineStyle == 1
        assert ws.Cells(4, 2).Borders(9).LineStyle == 1
        assert ws.Cells(1, 1).Font.Bold
        wb.Close(SaveChanges=False)
    import fitz

    with fitz.open(result["pdf"]) as pdf:
        drawings = pdf[0].get_drawings()
        assert any(d["type"] in ("s", "fs") for d in drawings)


def test_excel_merged_title_empty_column_dates_money_and_large_table(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import ExcelSession

    src = tmp_path / "Katta.xlsx"
    rows = [["F.I.Sh", "Sana", None, "Summa", "Izoh"]]
    rows += [
        [f"O‘quvchi {i}", datetime(2026, 10, 18), None, i * 100, "tayyor"] for i in range(1, 2002)
    ]
    with ExcelSession(visible=False) as xl:
        wb = xl.new_workbook()
        ws = wb.ActiveSheet
        ws.Range("A1:E1").Merge()
        ws.Cells(1, 1).Value = "Yillik hisobot"
        ops.write_rows(ws, rows, top=3)
        xl.save_as(wb, src)
        wb.Close(SaveChanges=False)
    result = _run(run_excel_plan, parse_command("Katta.xlsx ni och, jami qo‘sh"), src)
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(result["path"])
        ws = wb.ActiveSheet
        assert ws.Cells(1, 1).Value == "Yillik hisobot"
        assert ws.Cells(3, 4).Value == "Summa"
        assert ws.Cells(2005, 1).Value == "JAMI"
        assert ws.Cells(2005, 4).Value == sum(i * 100 for i in range(1, 2002))
        assert ws.Cells(2005, 3).Borders(9).LineStyle == 1
        assert ws.Cells(4, 2).NumberFormat is not None
        wb.Close(SaveChanges=False)


def test_create_named_excel_table_from_chat(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.skills.excel.bridge import ExcelSession

    plan = parse_command(
        "Excel’da 5 ustunli o‘quvchilar jadvali tuz: F.I.Sh, Sinf, Sana, Baho, Izoh"
    )
    target = tmp_path / "Oquvchilar.xlsx"
    result = _run(run_excel_plan, plan, target)
    assert result["path"] == str(target)
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(target)
        ws = wb.ActiveSheet
        assert [ws.Cells(1, i).Value for i in range(1, 6)] == [
            "F.I.Sh",
            "Sinf",
            "Sana",
            "Baho",
            "Izoh",
        ]
        assert ws.Cells(21, 5).Borders(9).LineStyle == 1
        wb.Close(SaveChanges=False)


def test_word_format_restores_table_borders(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.word_exec import run_word_plan
    from nexvara.skills.word.ops import WordSession

    src = tmp_path / "Hisobot.docx"
    with WordSession(visible=False) as word:
        doc = word.new_document()
        doc.Content.Text = "Yillik hisobot\r"
        table = doc.Tables.Add(doc.Range(doc.Content.End - 1, doc.Content.End - 1), 2, 2)
        table.Cell(1, 1).Range.Text = "Sinf"
        table.Cell(1, 2).Range.Text = "Soni"
        table.Cell(2, 1).Range.Text = "7-A"
        table.Cell(2, 2).Range.Text = "28"
        table.Borders.Enable = False
        word.save_as(doc, src)
        word.disown(doc)
        doc.Close(0)
    result = _run(run_word_plan, parse_command("Hisobot.docx ni rasmiy formatla"), src)
    with WordSession(visible=False) as word:
        doc = word.open_document(result["path"])
        assert bool(doc.Tables(1).Borders.Enable)
        assert bool(doc.Tables(1).Rows(1).Range.Font.Bold)
        word.disown(doc)
        doc.Close(0)


def test_powerpoint_long_replacement_fits_after_reopen(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.ppt_exec import run_ppt_plan
    from nexvara.skills.powerpoint import ops
    from nexvara.skills.powerpoint.ops import PowerPointSession

    src = tmp_path / "Dars.pptx"
    with PowerPointSession(visible=True) as pp:
        pres = pp.new_presentation()
        ops.add_title_slide(pres, "Dars", "Sinov")
        ops.add_bullets_slide(pres, "Natija", ["Qisqa matn"])
        pp.save_as(pres, src)
        pp.disown(pres)
        pres.Close()
        del pres
    longer = "O‘quvchilar bilan bajarilgan ishlar va olingan natijalar batafsil ko‘rib chiqildi"
    plan = parse_command(f"Dars.pptx da «Qisqa matn» ni «{longer}» ga almashtir")
    result = _run(run_ppt_plan, plan, src)
    with PowerPointSession(visible=True) as pp:
        pres = pp.open_presentation(result["path"])
        assert not [p for p in ops.layout_problems(pres.Slides(2)) if "matn sig'madi" in p]
        pp.disown(pres)
        pres.Close()
        del pres
