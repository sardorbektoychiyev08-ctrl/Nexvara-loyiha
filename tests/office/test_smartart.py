"""SmartArt in real Word and PowerPoint, picked by layout Id (works in any Office language).
NEXVARA_RUN_OFFICE=1 (Word and PowerPoint windows will appear)."""

import hashlib
import os

import pytest
from tests.office_fixtures import make_letter_docx

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def go(fn):
    from nexvara.core.task import TaskRunner

    t = TaskRunner().start("s", fn)
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    return snap["result"]


def test_word_process_and_hierarchy(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.word_exec import run_word_plan
    from nexvara.skills.word.ops import WordSession

    src = make_letter_docx(tmp_path / "Ariza.docx")
    before = digest(src)
    plan = parse_command(
        "Ariza.docx ni och, jarayon sxemasi qo‘sh: Ariza, Ko‘rib chiqish, Qaror, keyin "
        "«Maktab boshqaruvi» ierarxiya sxemasi qo‘sh: Direktor, O‘rinbosar, O‘qituvchilar"
    )
    assert [a.kind for a in plan.actions].count("smartart") == 2, plan.actions
    go(lambda task: run_word_plan(task, plan, src, keep_open=False, pause=0))
    assert digest(src) == before
    out = tmp_path / "Ariza_NEXVARA.docx"
    with WordSession(visible=False) as w:
        d = w.open_document(out)
        arts = [d.InlineShapes(i) for i in range(1, d.InlineShapes.Count + 1)
                if d.InlineShapes(i).HasSmartArt]  # fmt: skip
        texts = [[str(s.SmartArt.AllNodes.Item(k).TextFrame2.TextRange.Text)
                  for k in range(1, s.SmartArt.AllNodes.Count + 1)] for s in arts]  # fmt: skip
        body = d.Content.Text
        d.Close(0)
        del arts, d
    assert texts == [
        ["Ariza", "Ko‘rib chiqish", "Qaror"],
        ["Direktor", "O‘rinbosar", "O‘qituvchilar"],
    ]
    assert "Maktab boshqaruvi" in body and "Men, Aliyev Vali" in body  # old text stays


def test_powerpoint_cycle_slide(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.ppt_exec import run_ppt_plan
    from nexvara.skills.powerpoint import ops
    from nexvara.skills.powerpoint.ops import PowerPointSession

    src = tmp_path / "Dars.pptx"
    with PowerPointSession(visible=True) as pp:
        p = pp.new_presentation()
        ops.add_title_slide(p, "Sifat sikli", "PDCA")
        pp.save_as(p, src)
        del p
    plan = parse_command("Dars.pptx ni och, aylana sxema qo‘sh: Rejalash, Bajarish, "
                         "Tekshirish, Yaxshilash")  # fmt: skip
    res = go(lambda task: run_ppt_plan(task, plan, src, keep_open=False))
    assert all(c["ok"] for c in res.get("checks", [])), res
    with PowerPointSession(visible=True) as pp:
        p = pp.open_presentation(tmp_path / "Dars_NEXVARA.pptx")
        slide = p.Slides(p.Slides.Count)
        art = next(slide.Shapes(i) for i in range(1, slide.Shapes.Count + 1)
                   if slide.Shapes(i).HasSmartArt)  # fmt: skip
        got = [str(art.SmartArt.AllNodes.Item(k).TextFrame2.TextRange.Text)
               for k in range(1, art.SmartArt.AllNodes.Count + 1)]  # fmt: skip
        n = p.Slides.Count
        del art, slide, p
    assert n == 2 and got == ["Rejalash", "Bajarish", "Tekshirish", "Yaxshilash"]
