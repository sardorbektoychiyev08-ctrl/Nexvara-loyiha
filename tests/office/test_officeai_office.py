"""Translate / rewrite in real Word and PowerPoint with a fake AI (upper-casing), so the Office
part — reading paragraphs, table cells and text boxes, writing a new file — is checked for
real without any paid call. NEXVARA_RUN_OFFICE=1 (Word and PowerPoint windows will appear)."""

import hashlib
import json
import os

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]

JOB = {"mode": "translate", "lang": "English"}


def upper(system, user):
    return json.dumps([x.upper() for x in json.loads(user)], ensure_ascii=False)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def go(fn):
    from nexvara.core.task import TaskRunner

    t = TaskRunner().start("ai", fn)
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    return snap["result"]


def test_word_body_and_table_cells(tmp_path):
    from nexvara import officeai
    from nexvara.skills.word import ops
    from nexvara.skills.word.ops import WordSession

    src = tmp_path / "Xat.docx"
    with WordSession(visible=False) as w:
        d = w.new_document()
        ops.add_heading(d, "Ota-onalar yig‘ilishi", 1)
        ops.add_paragraph(d, "Yig‘ilish ertaga soat 15:00 da bo‘ladi.")
        ops.add_table(d, [["Mavzu", "Vaqt"], ["Baholar", "15:00"]])
        w.save_as(d, src)
        w.disown(d)
        d.Close(0)
        del d
    before = digest(src)
    res = go(lambda task: officeai.run(task, src, JOB, upper, keep_open=False))
    assert digest(src) == before  # the original is untouched
    with WordSession(visible=False) as w:
        d = w.open_document(res["path"])
        text = d.Content.Text
        cell = d.Tables(1).Cell(2, 1).Range.Text
        style = d.Paragraphs(1).Style.NameLocal
        tables = d.Tables.Count
        d.Close(0)
        del d
    assert "OTA-ONALAR YIG‘ILISHI" in text and "YIG‘ILISH ERTAGA SOAT 15:00" in text
    assert cell.startswith("BAHOLAR") and tables == 1
    assert res["path"].endswith("Xat_EN.docx") and style  # the heading keeps its style


def test_powerpoint_text_boxes(tmp_path):
    from nexvara import officeai
    from nexvara.skills.powerpoint import ops
    from nexvara.skills.powerpoint.ops import PowerPointSession

    src = tmp_path / "Taqdimot.pptx"
    with PowerPointSession(visible=True) as pp:
        p = pp.new_presentation()
        ops.add_title_slide(p, "Nyuton qonunlari", "7-sinf fizika")
        ops.add_bullets_slide(p, "Birinchi qonun", ["Inersiya", "Kuch va tezlanish"])
        pp.save_as(p, src)
        del p
    before = digest(src)
    res = go(lambda task: officeai.run(task, src, JOB, upper, keep_open=False))
    assert digest(src) == before
    with PowerPointSession(visible=True) as pp:
        p = pp.open_presentation(res["path"])
        texts = officeai.ppt_texts(p)
        slides = p.Slides.Count
        del p
    joined = " ".join(texts)
    assert slides == 2 and "NYUTON QONUNLARI" in joined and "INERSIYA" in joined
