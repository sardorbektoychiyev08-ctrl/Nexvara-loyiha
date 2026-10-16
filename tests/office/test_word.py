"""Real-Word tests. Run with NEXVARA_RUN_OFFICE=1."""

import os

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Word",
    ),
]


@pytest.fixture
def word():
    from nexvara.skills.word.ops import WordSession

    with WordSession(visible=False) as session:
        yield session


def test_word_report_end_to_end(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.skills.word.demo import run_word_report

    out = tmp_path / "hisobot.docx"
    task = TaskRunner().start("word", lambda t: run_word_report(t, out, keep_open=False, pause=0))
    assert task.wait(300), "Word task did not finish in 300s"
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    checks = snap["result"]["checks"]
    assert all(c["ok"] for c in checks), [c for c in checks if not c["ok"]]
    assert len(checks) == 15
    assert out.is_file() and out.with_suffix(".pdf").is_file()


def test_word_refuses_overwrite_before_starting(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.skills.word.demo import run_word_report

    out = tmp_path / "exists.docx"
    out.write_bytes(b"keep")
    task = TaskRunner().start("word", lambda t: run_word_report(t, out, keep_open=False))
    assert task.wait(60)
    assert task.snapshot()["status"] == "failed"
    assert "FileExistsError" in task.error
    assert task.steps == []
    assert out.read_bytes() == b"keep"


def test_find_replace_really_replaces(word):
    """Regression: named args to Find.Execute are ignored by Word; replacement must happen."""
    from nexvara.skills.word import ops

    doc = word.new_document()
    ops.add_paragraph(doc, "A {X} B {X} C")
    assert ops.find_replace(doc, "{X}", "yes") == 2
    assert str(doc.Content.Text).strip() == "A yes B yes C"
    assert ops.find_replace(doc, "{X}", "no") == 0


def test_styles_and_lists_are_language_independent(word):
    from nexvara.skills.word import ops

    doc = word.new_document()
    ops.add_heading(doc, "Bob 1", 1)
    ops.add_bullets(doc, ["a", "b"])
    ops.add_heading(doc, "Bo'lim", 2)
    ops.add_paragraph(doc, "oddiy")
    assert ops.outline(doc) == [(1, "Bob 1"), (2, "Bo'lim")]
    # The paragraph after a list must not inherit bullets.
    last = doc.Paragraphs(doc.Paragraphs.Count)
    assert last.Range.ListFormat.ListType == 0  # wdListNoNumbering


def test_table_shape_and_numbers(word):
    from nexvara.skills.word import ops

    doc = word.new_document()
    t = ops.add_table(doc, [["Nomi", "Summa"], ["A", 1234567], ["B", 0.5]], numeric_columns=(2,))
    assert (t.Rows.Count, t.Columns.Count) == (3, 2)
    assert ops.cell_text(t, 2, 2) == "1\u00a0234\u00a0567"
    assert ops.cell_text(t, 3, 2) == "0,50"
    assert t.Cell(2, 2).Range.ParagraphFormat.Alignment == ops.ALIGN["center"]
    with pytest.raises(ValueError):
        ops.add_table(doc, [["a\tb"]])
