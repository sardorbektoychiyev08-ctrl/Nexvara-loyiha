"""«Excel’ni ochib o‘sha yerga yoz»: an answer into a new Excel/Word file, in real Office
(NEXVARA_RUN_OFFICE=1). Files go to a temporary «Documents», not the owner's."""

import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]

ANSWER = """6-sinf informatika testi
1. Kompyuterning «miyasi» qaysi qurilma?
A) Monitor
B) Protsessor
C) Sichqoncha
D) Printer
Javob: B
2. Axborot o‘lchov birligi?
A) Metr
B) Bayt
C) Litr
D) Gramm
Javob: B"""


def _run(tmp_path, monkeypatch, text, app):
    from nexvara.core.task import TaskRunner
    from nexvara.fileagent import write_to_office

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    t = TaskRunner().start("w", lambda task: write_to_office(task, text, app, "Informatika",
                                                             keep_open=False))  # fmt: skip
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    out = Path(snap["result"]["path"])
    assert out.exists() and out.parent == tmp_path / "Documents" / "NEXVARA"
    return out


def test_test_answer_becomes_an_excel_table(tmp_path, monkeypatch):
    from nexvara.skills.excel.bridge import ExcelSession

    out = _run(tmp_path, monkeypatch, ANSWER, "excel")
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(out)
        ws = wb.Worksheets(1)
        head = [ws.Cells(1, c).Value for c in range(1, 8)]
        row1 = [ws.Cells(2, c).Value for c in range(2, 8)]
        last = ws.Cells(3, 7).Value
        wb.Close(False)
        del ws, wb
    assert head == ["№", "Savol", "A", "B", "C", "D", "Javob"]
    assert row1 == ["Kompyuterning «miyasi» qaysi qurilma?", "Monitor", "Protsessor",
                    "Sichqoncha", "Printer", "B"]  # fmt: skip
    assert last == "B"


def test_answer_into_word(tmp_path, monkeypatch):
    from nexvara.skills.word.ops import WordSession

    out = _run(tmp_path, monkeypatch, "Salom!\nBugun kasrlarni o‘rganamiz.", "word")
    with WordSession(visible=False) as wd:
        doc = wd.open_document(out)
        text = doc.Content.Text
        doc.Close(False)
        del doc
    assert "Informatika" in text and "Bugun kasrlarni o‘rganamiz." in text
