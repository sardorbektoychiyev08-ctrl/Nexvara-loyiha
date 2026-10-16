"""Real Excel tests. They open Excel on screen, so they only run when asked:

$env:NEXVARA_RUN_OFFICE = "1"; .venv\\Scripts\\python -m pytest -m office
"""

import os

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Excel",
    ),
]


def test_excel_demo_end_to_end(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.skills.excel.demo import run_demo

    out = tmp_path / "nexvara-test.xlsx"
    task = TaskRunner().start("excel live", lambda t: run_demo(t, out, keep_open=False, pause=0.2))
    assert task.wait(180), "Excel task did not finish in 180s"

    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert out.is_file()
    assert all(c["ok"] for c in snap["result"]["checks"]), snap["result"]["checks"]
    assert [s["name"] for s in snap["steps"]] == [
        "Excel'ni ochish",
        "Yangi workbook yaratish",
        "10 qatorli jadvalni kiritish",
        "Formatlash",
        "Saqlash",
        "Qayta ochib tekshirish",
    ]


def test_excel_refuses_silent_overwrite(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.skills.excel.demo import run_demo

    out = tmp_path / "exists.xlsx"
    out.write_bytes(b"do not touch")
    task = TaskRunner().start(
        "excel overwrite", lambda t: run_demo(t, out, keep_open=False, pause=0)
    )
    assert task.wait(180)
    assert task.snapshot()["status"] == "failed"
    assert "FileExistsError" in task.error
    assert task.steps == [], "Excel must not even start when the target is unusable"
    assert out.read_bytes() == b"do not touch"


def test_ui_button_runs_real_excel(tmp_path):
    """Opens the NEXVARA window and clicks "Excel'da jadval yaratish" for real."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "nexvara.app.main", "--selftest-excel", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST PASS [run-excel]" in proc.stdout
    assert "SELFTEST PASS [run-dashboard]" in proc.stdout
    assert "SELFTEST PASS [run-word]" in proc.stdout
    assert "SELFTEST PASS [run-ppt]" in proc.stdout
    assert len(list(tmp_path.glob("nexvara-jadval-*.xlsx"))) == 1
    assert len(list(tmp_path.glob("nexvara-dashboard-*.xlsx"))) == 1
    assert len(list(tmp_path.glob("nexvara-hisobot-*.docx"))) == 1
    assert len(list(tmp_path.glob("nexvara-taqdimot-*.pptx"))) == 1


def test_formulas_are_locale_independent(tmp_path):
    """Formulas are written in English and Excel shows them in its own UI language.

    On a Russian Office UI, FormulaLocal must read =СУММ(...) while Formula stays =SUM(...).
    """
    from nexvara.skills.excel.bridge import ExcelSession

    with ExcelSession(visible=False) as xl:
        lang = xl.app.LanguageSettings
        ui_lang = lang.LanguageID(2)  # msoLanguageIDUI
        del lang
        wb = xl.new_workbook()
        ws = wb.Worksheets(1)
        ws.Range("A1:A3").Value = [[1.5], [2.25], [3]]
        cell = ws.Range("A4")
        cell.Formula = "=SUM(A1:A3)"
        formula, local, value = cell.Formula, cell.FormulaLocal, cell.Value
        del cell, ws, wb

    assert formula == "=SUM(A1:A3)"
    assert value == 6.75
    if ui_lang == 1049:  # Russian
        assert local.startswith("=СУММ("), local


def test_excel_dashboard_end_to_end(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.skills.excel.dashboard import run_dashboard

    out = tmp_path / "dashboard.xlsx"
    task = TaskRunner().start(
        "dashboard", lambda t: run_dashboard(t, out, keep_open=False, pause=0)
    )
    assert task.wait(300), "dashboard task did not finish in 300s"
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert out.is_file()
    checks = snap["result"]["checks"]
    assert all(c["ok"] for c in checks), [c for c in checks if not c["ok"]]
    assert len(checks) == 14
