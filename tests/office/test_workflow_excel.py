"""A folder-triggered workflow processing a new Excel file with real Excel."""

import os
import time

import pytest
from tests.office_fixtures import make_sales_xlsx

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Excel",
    ),
]


def test_new_file_in_folder_is_processed(tmp_path, monkeypatch):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.workflows import WorkflowStore

    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    inbox = tmp_path / "Kelgan"
    inbox.mkdir()
    runner = TaskRunner()
    api = Api(runner, keep_office_open=False,
              overrides={"workflow_store": WorkflowStore(tmp_path / "app.db")})  # fmt: skip
    r = api.wf_save({
        "name": "Hisobotlar",
        "steps": [{"kind": "command",
                   "text": "{fayl} ni och, jadvalni formatla, jami qo‘sh, PDF qilib saqla"}],
        "trigger": {"type": "folder", "folder": str(inbox), "ext": ".xlsx"},
    })  # fmt: skip
    assert r["ok"], r
    src = make_sales_xlsx(inbox / "Savdo oktabr.xlsx")
    later = time.time() + 30
    started = api._wf().tick(now=later)
    assert len(started) == 1
    task = runner.get(started[0]["task"]["id"])
    assert task.wait(300)
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    out = inbox / "Savdo oktabr_NEXVARA.xlsx"
    assert out.is_file() and (inbox / "Savdo oktabr_NEXVARA.pdf").is_file()
    assert src.is_file()  # the original is untouched
    # The outputs landed in the watched folder but never start the workflow again.
    assert api._wf().tick(now=later + 60) == []
    run = api.wf_runs(r["id"])[0]
    assert run["status"] == "succeeded" and "Savdo oktabr" in run["trigger"]
