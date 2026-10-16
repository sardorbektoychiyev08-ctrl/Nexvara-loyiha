"""Windows built-in OCR on an image-only PDF (skipped where Windows OCR is unavailable)."""

import pytest

from nexvara.knowledge import ocr
from nexvara.knowledge.ingest import ingest_folder
from nexvara.knowledge.store import Library

pytestmark = pytest.mark.skipif(not ocr.available(), reason="Windows OCR not available")

LINES = [
    "1-§. BOSIM",
    "Bosim deb sirtga tik ta'sir etuvchi kuchning shu sirt yuziga nisbatiga aytiladi.",
    "Paskal qonuni suyuqlik va gazlarda bosim har tomonga bir xil uzatilishini ifodalaydi.",
    "Atmosfera bosimini Torrichelli 1643-yilda tajribada o'lchagan.",
]


def scanned_pdf(path, pages=4):
    """Pages that are pictures of text: no text layer at all."""
    import pymupdf

    src = pymupdf.open()
    for _ in range(pages):
        page = src.new_page(width=595, height=842)
        y = 80
        for line in LINES:
            page.insert_text((40, y), line, fontsize=13)
            y += 30
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
        img_page = out.new_page(width=595, height=842)
        img_page.insert_image(img_page.rect, pixmap=pix)
    out.save(str(path))
    return path


def test_pick_language():
    assert ocr.pick_language("fizika_8_uzb.pdf", ["en-US", "ru"]) == "en-US"
    assert ocr.pick_language("rus_tili_5_uzb.pdf", ["en-US", "ru"]) == "ru"
    assert ocr.pick_language("x.pdf", []) is None


def test_scanned_pdf_is_read_by_ocr_and_indexed(tmp_path):
    root = tmp_path / "Darsliklar" / "7-sinf"
    root.mkdir(parents=True)
    pdf = scanned_pdf(root / "Fizika.pdf")
    import pymupdf

    with pymupdf.open(str(pdf)) as d:
        assert d[0].get_text().strip() == ""  # really image-only

    lib = Library(tmp_path / "t.db")
    rep = ingest_folder(tmp_path / "Darsliklar", lib)
    assert rep.ocr == ["Fizika.pdf"] and rep.added == ["Fizika.pdf"], rep
    (book,) = lib.books()
    assert book.note.startswith("OCR")
    text = lib.page_text(book.id, 1)
    assert "Paskal qonuni" in text and "1643" in text
    assert lib.search("Torrichelli", 7, "Fizika")
    lib.close()
