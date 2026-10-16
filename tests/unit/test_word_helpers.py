import pytest

from nexvara.skills.common import validate_output_path
from nexvara.skills.png_chart import bar_chart_png
from nexvara.skills.word import ops


def test_cm_to_pt():
    assert ops.cm_to_pt(2.54) == pytest.approx(72)


def test_cell_text_formats_numbers_for_uzbek_locale():
    assert ops._cell_text(1234567) == "1\u00a0234\u00a0567"
    assert ops._cell_text(1234.5) == "1\u00a0234,50"
    assert ops._cell_text(None) == ""
    assert ops._cell_text("x") == "x"


def test_validate_output_path(tmp_path):
    assert validate_output_path(tmp_path / "a.docx", (".docx",)).name == "a.docx"
    with pytest.raises(ValueError):
        validate_output_path("a.docx", (".docx",))
    with pytest.raises(ValueError):
        validate_output_path(tmp_path / "a.doc", (".docx",))
    (tmp_path / "b.docx").write_text("x")
    with pytest.raises(FileExistsError):
        validate_output_path(tmp_path / "b.docx", (".docx",))


def test_png_chart(tmp_path):
    p = bar_chart_png([1, 3, 2], tmp_path / "c.png", width=120, height=60)
    data = p.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(data[16:20], "big") == 120
    with pytest.raises(ValueError):
        bar_chart_png([], tmp_path / "x.png")
