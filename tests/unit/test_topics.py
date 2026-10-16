import pytest
from tests.textbook_fixture import write_pdf

from nexvara.knowledge.ingest import ingest_folder
from nexvara.knowledge.service import parse_topic_request
from nexvara.knowledge.store import Library, find_sections
from nexvara.knowledge.topics import (
    display_title,
    find_topic,
    paragraphs,
    parse_toc,
    preview,
    section_starts,
)


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / "Darsliklar" / "7-sinf"
    root.mkdir(parents=True)
    write_pdf(root / "Fizika.pdf")
    library = Library(tmp_path / "t.db")
    ingest_folder(tmp_path / "Darsliklar", library)
    yield library
    library.close()


def test_find_sections_joins_wrapped_caps_and_skips_contents_lines():
    page = "11-§. XIVA XONLIGI USTIDAN\nROSSIYA IMPERIYASI PROTEKTORATI\nMatn boshlanadi."
    assert find_sections(page) == ["11-§. XIVA XONLIGI USTIDAN ROSSIYA IMPERIYASI PROTEKTORATI"]
    assert find_sections("12-§. Qo‘qon xonligi . . . . . . . . . 39") == []


def test_display_title():
    assert display_title("7-§. TOSHKENTNING BOSIB OLINISHI") == "7-§. Toshkentning bosib olinishi"
    assert display_title("7-§. Toshkent") == "7-§. Toshkent"


def test_parse_toc_both_layouts():
    text = (
        "MUNDARIJA\n"
        "11-§. Tekis harakatda yo‘l ................. 44\n"
        "12-§. Erkin tushish\n"
        "........................................ 47\n"
        "13-§. Uzun sarlavha birinchi qator\n"
        "ikkinchi qator ................ 51\n"
        "14-§. Raqamsiz"
    )
    assert parse_toc([text]) == [
        (11, "11-§. Tekis harakatda yo‘l", 44),
        (12, "12-§. Erkin tushish", 47),
        (13, "13-§. Uzun sarlavha birinchi qator ikkinchi qator", 51),
    ]


def test_section_starts_and_topic_by_title(lib):
    (book,) = lib.books()
    assert [p for p, _t in section_starts(lib, book)] == [2, 3, 4]
    t = find_topic(lib, 7, "Fizika", "bosim")
    assert (t.title, t.start_page, t.end_page, t.matched_by) == ("3-§. Bosim", 4, 4, "sarlavha")
    assert "Paskal qonuni" in t.text and "Tezlik" not in t.text
    assert t.pages_label == "4-bet"


def test_topic_by_text_and_slicing(lib):
    t = find_topic(lib, 7, "Fizika", "Nyuton")
    assert t.title == "2-§. Tezlik va kuch" and t.matched_by == "matn"
    assert "Isaak Nyuton" in t.text and "Bosim -" not in t.text
    kinds = [k for k, _ in paragraphs(t.text)]
    assert kinds[0] == "heading" and kinds.count("para") >= 5
    assert preview(t, 60).endswith("…")


def test_topic_errors(lib):
    with pytest.raises(LookupError):
        find_topic(lib, 7, "Fizika", "fotosintez")
    with pytest.raises(LookupError):
        find_topic(lib, 9, "Kimyo", "bosim")
    with pytest.raises(ValueError):
        find_topic(lib, 7, "Fizika", " ")


def test_generic_subject_matches_specific_book(tmp_path):
    lib = Library(tmp_path / "t.db")
    page = "7-§. Toshkentning bosib olinishi\nToshkent 1865-yilda olindi."
    lib.add_book(path="a", sha256="1", title="t", grade=9, subject="O‘zbekiston tarixi",
                 year=2024, pages=[page])  # fmt: skip
    t = find_topic(lib, 9, "Tarix", "Toshkent")
    assert t.book.subject == "O‘zbekiston tarixi" and t.start_page == 1
    lib.close()


@pytest.mark.parametrize(
    ("text", "grade", "subject", "topic"),
    [
        ("7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber", 7, "Fizika", "nyuton qonunlari"),
        ("menga 9-sinf tarixdan Jadidlar mavzusi kerak", 9, "Tarix", "jadidlar"),
        ("O‘zbekiston tarixi 9 sinf Toshkentning bosib olinishi bo‘limini ko‘rsat", 9,
         "O‘zbekiston tarixi", "toshkentning bosib olinishi"),
    ],
)  # fmt: skip
def test_parse_topic_request(text, grade, subject, topic):
    r = parse_topic_request(text)
    assert (r.grade, r.subject, r.topic) == (grade, subject, topic)


def test_topic_request_needs_grade_or_subject_and_yields_to_tests():
    assert parse_topic_request("menga yordam kerak") is None
    assert parse_topic_request("7-sinf fizika bosim 10 ta test") is None
