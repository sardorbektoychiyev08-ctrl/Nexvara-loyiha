"""Real-PowerPoint tests. Run with NEXVARA_RUN_OFFICE=1 (PowerPoint windows will appear)."""

import os

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real PowerPoint",
    ),
]


def test_presentation_end_to_end(tmp_path):
    from nexvara.core.task import TaskRunner
    from nexvara.skills.powerpoint.demo import run_presentation

    out = tmp_path / "taqdimot.pptx"
    task = TaskRunner().start("ppt", lambda t: run_presentation(t, out, keep_open=False, pause=0))
    assert task.wait(300), "PowerPoint task did not finish in 300s"
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    checks = snap["result"]["checks"]
    assert all(c["ok"] for c in checks), [c for c in checks if not c["ok"]]
    assert len(checks) == 11
    assert out.is_file() and out.with_suffix(".pdf").is_file()


def test_layout_check_catches_overflow_and_overlap():
    """Negative test: the quality check must actually report bad slides."""
    from nexvara.skills.powerpoint import ops

    with ops.PowerPointSession(visible=False) as pp:
        pres = pp.new_presentation()
        slide = pres.Slides.Add(1, ops.LAYOUT_BLANK)
        a = slide.Shapes.AddTextbox(ops.MSO_TEXTBOX, 100, 100, 200, 20)
        a.TextFrame.AutoSize = 0  # ppAutoSizeNone
        a.TextFrame.TextRange.Text = "juda uzun matn " * 40
        a.Height = 20
        slide.Shapes.AddShape(ops.MSO_SHAPE_RECTANGLE, 150, 105, 100, 50)
        slide.Shapes.AddShape(ops.MSO_SHAPE_RECTANGLE, 900, 500, 200, 100)  # off-slide
        problems = ops.layout_problems(slide)
        del a, slide, pres

    joined = "; ".join(problems)
    assert "sig'madi" in joined, joined
    assert "ustma-ust" in joined, joined
    assert "tashqarida" in joined, joined


def test_session_never_closes_users_presentation():
    """PowerPoint is single-instance: our session must leave the user's work alone."""
    import pythoncom
    import win32com.client

    from nexvara.skills.powerpoint import ops

    pythoncom.CoInitialize()
    user_app = win32com.client.DispatchEx("PowerPoint.Application")
    user_pres = user_app.Presentations.Add(ops.MSO_TRUE)  # stands in for the user's own deck
    user_name = str(user_pres.FullName)
    try:
        with ops.PowerPointSession(visible=False) as pp:
            mine = pp.new_presentation()
            mine.Slides.Add(1, ops.LAYOUT_BLANK)
            del mine
        names = [
            str(user_app.Presentations(i).FullName)
            for i in range(1, user_app.Presentations.Count + 1)
        ]
        assert names == [user_name], names
    finally:
        user_pres.Close()
        del user_pres
        if user_app.Presentations.Count == 0:
            user_app.Quit()
        del user_app
        pythoncom.CoUninitialize()


def test_chart_slide_rejects_bad_series():
    from nexvara.skills.powerpoint import ops

    with pytest.raises(ValueError):
        ops.add_chart_slide(None, "x", ["a", "b"], {"s": [1]})
    with pytest.raises(ValueError):
        ops.add_chart_slide(None, "x", ["a"], {"s": [1]}, kind="radar")
