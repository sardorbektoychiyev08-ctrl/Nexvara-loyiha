"""A drawing into an existing Word document, in real Word (visible), with its measurements.
Run with NEXVARA_RUN_OFFICE=1 (Word windows will appear)."""

import os

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Word",
    ),
]


SPEC = {
    "title": "Plastina",
    "width": 120,
    "height": 80,
    "shapes": [
        {"type": "rect", "x": 10, "y": 10, "width": 100, "height": 60, "w": 0.7},
        {"type": "circle", "cx": 60, "cy": 40, "r": 15},
        {"type": "dim", "x1": 10, "y1": 70, "x2": 110, "y2": 70, "offset": 8},
    ],
}


def test_drawing_goes_to_the_end_of_a_word_document(tmp_path):
    from nexvara import cad, drawing
    from nexvara.app.api_drawing import _word_insert
    from nexvara.skills.word import ops

    docx = tmp_path / "Hisobot.docx"
    with ops.WordSession(visible=True, keep_open=False) as w:
        d = w.new_document()
        ops.add_paragraph(d, "Oylik hisobot")
        ops.add_paragraph(d, "Bu yerda matn bor.")
        w.save_as(d, docx)
        del d
    p = tmp_path / "Plastina.dxf"
    p.write_text(drawing.to_dxf(SPEC), encoding="utf-8")
    doc = cad.read(p)
    cad.render(doc, None, tmp_path / "c.png", dpi=200)
    _word_insert(docx, tmp_path / "c.png", "Plastina", cad.measurements(doc), keep_open=False)
    with ops.WordSession(visible=True, keep_open=False) as w:
        d = w.open_document(docx)
        text = d.Content.Text
        shapes, tables = d.InlineShapes.Count, d.Tables.Count
        pic_w = d.InlineShapes(1).Width if shapes else 0
        page = d.Sections(1).PageSetup
        usable = page.PageWidth - page.LeftMargin - page.RightMargin
        cells = d.Tables(1).Range.Text if tables else ""
        d.Close(0)
        del d
    assert "Oylik hisobot" in text and "Bu yerda matn bor." in text  # the old text stays
    assert "Chizma: Plastina" in text
    assert shapes == 1 and abs(pic_w - usable) < 6  # the picture fills the page width
    assert tables == 1 and "Aylanalar diametri" in cells and "Ø30" in cells
