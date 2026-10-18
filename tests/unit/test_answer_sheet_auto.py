"""Every A/B/C/D test gets a printable answer sheet with its keys."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace


class _Task:
    @contextlib.contextmanager
    def step(self, name):
        yield SimpleNamespace(detail="")


def test_answer_sheet_is_made_with_the_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path))
    from nexvara import omr
    from nexvara.app.api import _with_answer_sheet
    from nexvara.knowledge.testdoc import variant_label

    res = {"book": "7-sinf fizika", "topic": "Nyuton qonunlari", "sheet_ready": True,
           "answers": ["ABCDA", "BCDAB"]}  # fmt: skip
    out = _with_answer_sheet(_Task(), res)
    assert out["sheet"].endswith(".pdf") and (tmp_path / "Javob varaqalari").is_dir()
    s = omr.get_set(out["sheet_id"])
    assert s["keys"] == {"1": "ABCDA", "2": "BCDAB"} and s["variants"] == 2
    assert variant_label(1) == "A variant" and variant_label(2) == "B variant"


def test_no_sheet_for_open_questions_or_too_many(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path))
    from nexvara.app.api import _with_answer_sheet

    assert "sheet" not in _with_answer_sheet(_Task(), {"sheet_ready": False, "answers": ["A"]})
    many = {"sheet_ready": True, "answers": ["A" * 61]}
    assert "sheet" not in _with_answer_sheet(_Task(), many)
    five = {"sheet_ready": True, "answers": ["AB"] * 5}  # the sheet has 4 variant bubbles
    assert "sheet" not in _with_answer_sheet(_Task(), five)
