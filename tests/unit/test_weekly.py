"""«Haftalik hisobot»: this week's Excel files in a folder become one PDF (no Excel needed)."""

from __future__ import annotations

import os
import time

import pytest

from nexvara import weekly
from nexvara.core.task import UserError


def _xlsx(path, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_report_sums_this_weeks_files(tmp_path):
    folder = tmp_path / "Hisobotlar"
    folder.mkdir()
    _xlsx(folder / "Dushanba.xlsx", [["Hudud", "Summa"], ["Toshkent", 100], ["Buxoro", 50],
                                     ["JAMI", 150]])  # fmt: skip
    _xlsx(folder / "Juma.xlsx", [["Hudud", "Summa"], ["Samarqand", 25]])
    old = folder / "Eski.xlsx"
    _xlsx(old, [["Hudud", "Summa"], ["Xiva", 999]])
    past = time.time() - 30 * 86400
    os.utime(old, (past, past))
    res = weekly.build(folder, tmp_path / "out")
    assert res["files"] == 2 and res["totals"] == {"Summa": 175}  # JAMI row and old file skipped
    import fitz

    text = "".join(p.get_text() for p in fitz.open(res["path"]))
    assert "Haftalik hisobot" in text and "Dushanba.xlsx" in text and "Eski.xlsx" not in text
    with pytest.raises(UserError, match="o‘zgargan Excel fayl yo‘q"):
        weekly.build(tmp_path / "out", tmp_path / "x")


def test_chat_and_workflow_template(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    folder = tmp_path / "data" / "Hisobotlar"
    folder.mkdir(parents=True)
    _xlsx(folder / "Savdo.xlsx", [["Mahsulot", "Soni"], ["Daftar", 3], ["Ruchka", 4]])
    api = Api(output_dir=tmp_path / "out")
    out = api.chat("Hisobotlar papkasidagi Excel fayllardan haftalik hisobot qil")
    task = api._runner.get(out["task"]["id"])
    assert task.wait(60) and task.status == "succeeded", task.error
    assert task.result["path"].endswith(".pdf") and task.result["totals"] == {"Soni": 7}
    tpl = next(t for t in api.wf_templates() if "Haftalik hisobot" in t["name"])
    assert tpl["trigger"] == {"type": "weekly", "days": [4], "time": "17:00"}
