"""Real Word 2016 creates readable ready documents and matching PDFs."""

from __future__ import annotations

import os

import pytest

from nexvara import doctemplates
from nexvara.core.task import TaskRunner

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to open real Word",
    ),
]


@pytest.mark.parametrize("tid", list(doctemplates.TEMPLATES))
def test_ready_document_opens_and_pdf_contains_its_content(tid, tmp_path):
    import pymupdf

    fields = {key: example for key, _label, example in doctemplates.TEMPLATES[tid]["fields"]}
    blocks = doctemplates.render(tid, fields)
    out = tmp_path / f"{tid}.docx"
    task = TaskRunner().start(
        tid,
        lambda t: doctemplates.write(t, tid, blocks, out, visible=True, keep_open=False),
    )
    assert task.wait(120), f"{tid} vaqtida tugamadi"
    assert task.status == "succeeded", (task.error, task.snapshot()["steps"])
    result = task.result
    assert out.is_file() and out.stat().st_size > 1000
    with pymupdf.open(result["pdf"]) as pdf:
        assert pdf.page_count == 1, f"{tid}: namunaviy hujjat 1 sahifaga sig‘ishi kerak"
        text = pdf[0].get_text()
    for kind, value in blocks:
        if kind == "title":
            assert value in text, (tid, value, text)
    if tid.startswith("ariza_"):
        assert "ARIZA" in text and fields["arizachi"] in text
        assert "so‘rayman" in text
    if tid == "buyruq":
        assert "1." in text and "2." in text
