"""Bulk Office -> PDF from the Files page, with real Word and Excel."""

import os

import pytest
from tests.office_fixtures import make_letter_docx, make_sales_xlsx

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]


def test_bulk_pdf(tmp_path, monkeypatch):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    docx = make_letter_docx(tmp_path / "Xat.docx")
    xlsx = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    (tmp_path / "Xat.pdf").write_bytes(b"%PDF old")  # must not be overwritten
    note = tmp_path / "eslatma.txt"
    note.write_text("x", encoding="utf-8")

    runner = TaskRunner()
    api = Api(runner)
    snap = api.files_to_pdf([str(docx), str(xlsx), str(note)])
    task = runner.get(snap["id"])
    assert task.wait(300)
    s = task.snapshot()
    assert s["status"] == "succeeded", (s["error"], s["steps"])
    made = sorted(os.path.basename(p) for p in s["result"]["files"])
    assert made == ["Savdo.pdf", "Xat (2).pdf"]
    assert (tmp_path / "Xat.pdf").read_bytes() == b"%PDF old"
    for p in s["result"]["files"]:
        with open(p, "rb") as f:
            assert f.read(4) == b"%PDF"
    assert any("eslatma.txt" in line for line in s["result"]["report"])
