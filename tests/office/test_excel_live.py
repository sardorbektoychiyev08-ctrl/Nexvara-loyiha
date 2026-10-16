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
