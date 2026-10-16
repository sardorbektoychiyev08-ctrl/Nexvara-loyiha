import pytest
from tests.textbook_fixture import PAGES, write_pdf

from nexvara.knowledge import catalog, textnorm
from nexvara.knowledge.ingest import ingest_folder
from nexvara.knowledge.quiz import LETTERS, build_quiz, extract_definitions, extract_facts
from nexvara.knowledge.service import TestRequest, parse_test_request
from nexvara.knowledge.store import Library, find_sections, fts_query

# ---------- text normalisation ----------


def test_normalize_repairs_apostrophes_and_hyphens():
    raw = "bo\ufffdlgan ma\ufffdlumot O'zbekiston tezla\u00ad\nnish bi-\nlan"
    assert textnorm.normalize(raw) == "bo‘lgan ma’lumot O‘zbekiston tezlanish bilan"


def test_fold_and_sentences_skip_headings():
    assert textnorm.fold("O‘zbekiston ma’lumot") == "ozbekiston malumot"
    text = "XIX ASR OXIRI\nXiva xonligi nazorat qilindi.\nAtamalar izohi\nVassal – tobelik."
    assert textnorm.sentences(text) == ["Xiva xonligi nazorat qilindi.", "Vassal – tobelik."]


def test_is_cyrillic():
    assert textnorm.is_cyrillic("Ўзбекистон тарихи дарслиги")
    assert not textnorm.is_cyrillic("O‘zbekiston tarixi darsligi")


# ---------- catalog ----------


@pytest.mark.parametrize(
    ("name", "grade", "subject"),
    [
        ("7-sinf Fizika.pdf", 7, "Fizika"),
        ("fizika_7_uzb.pdf", 7, "Fizika"),
        ("ozbekiston_tarixi_9_uzb.pdf", 9, "O‘zbekiston tarixi"),
        ("11 sinf Ona tili.pdf", 11, "Ona tili"),
        ("Jismoniy tarbiya 5-sinf.pdf", 5, "Jismoniy tarbiya"),
        ("Algebra (8).pdf", 8, "Algebra"),
    ],
)
def test_describe_from_file_name(tmp_path, name, grade, subject):
    info = catalog.describe(tmp_path / name, "", None)
    assert (info.grade, info.subject) == (grade, subject)


def test_describe_falls_back_to_book_text(tmp_path):
    info = catalog.describe(tmp_path / "kitob.pdf", "KIMYO\n8-sinf uchun darslik\n2023", None)
    assert (info.grade, info.subject, info.year) == (8, "Kimyo", 2023)


def test_folder_gives_grade(tmp_path):
    root = tmp_path
    info = catalog.describe(root / "10-sinf" / "Biologiya.pdf", "", root)
    assert (info.grade, info.subject) == (10, "Biologiya")


# ---------- store / search ----------


def test_sections_and_query():
    assert find_sections("1-§. MEXANIK HARAKAT\nmatn") == ["1-§. MEXANIK HARAKAT"]
    assert find_sections("IV bob. Harakat qonunlari") == ["IV bob. Harakat qonunlari"]
    assert fts_query("Kasrlarni qo‘shish") == '"kasrla"* "qosh"*'


def test_library_search_prefers_newest_edition(tmp_path):
    lib = Library(tmp_path / "t.db")
    pages_old = ["Eski nashr: bosim va kuch haqida."]
    pages_new = ["Yangi nashr: bosim va kuch haqida."]
    lib.add_book(path="a", sha256="1", title="old", grade=7, subject="Fizika", year=2017,
                 pages=pages_old)  # fmt: skip
    lib.add_book(path="b", sha256="2", title="new", grade=7, subject="Fizika", year=2024,
                 pages=pages_new)  # fmt: skip
    hits = lib.search("bosim", 7, "Fizika")
    assert [h.book.year for h in hits] == [2024]
    assert len(lib.search("bosim", 7, "Fizika", newest_only=False)) == 2
    assert lib.grades_subjects() == {7: ["Fizika", "Fizika"]} or lib.grades_subjects() == {
        7: ["Fizika"]
    }
    lib.close()


def test_ingest_pdf_folder(tmp_path):
    root = tmp_path / "Darsliklar"
    (root / "7-sinf").mkdir(parents=True)
    write_pdf(root / "7-sinf" / "Fizika.pdf")
    write_pdf(root / "nusxa.pdf")  # identical bytes -> duplicate
    lib = Library(tmp_path / "t.db")

    rep = ingest_folder(root, lib)
    assert rep.added == ["Fizika.pdf"] and len(rep.duplicates) == 1, rep
    (book,) = lib.books()
    assert (book.grade, book.subject, book.year, book.pages) == (7, "Fizika", 2024, len(PAGES))
    assert any("MEXANIK" in t for _, t in lib.sections(book.id))
    assert lib.search("Nyuton", 7, "Fizika")[0].page_no == 3

    rep2 = ingest_folder(root, lib)
    assert rep2.unchanged == ["Fizika.pdf"] and not rep2.added
    (root / "7-sinf" / "Fizika.pdf").unlink()
    (root / "nusxa.pdf").unlink()
    rep3 = ingest_folder(root, lib)
    assert rep3.removed == ["Fizika.pdf"] and lib.books() == []
    lib.close()


# ---------- quiz ----------


def _pages():
    return [(i + 1, textnorm.normalize(t)) for i, t in enumerate(PAGES)]


def test_definitions_and_facts_from_synthetic_book():
    defs = {d.term: d for d in extract_definitions(_pages())}
    for term in ("Mexanik harakat", "Sanoq jismi", "Tezlik", "Kuch", "Massa", "Bosim"):
        assert term in defs, sorted(defs)
    years = {f.answer for f in extract_facts(_pages()) if f.kind == "year"}
    assert {"1638", "1687", "1643"} <= years


def test_build_quiz_is_valid_and_deterministic():
    q1 = build_quiz(_pages(), 12, seed=7)
    q2 = build_quiz(_pages(), 12, seed=7)
    assert [q.text for q in q1.questions] == [q.text for q in q2.questions]
    assert 8 <= len(q1.questions) <= 12
    kinds = {q.kind for q in q1.questions}
    assert "mcq" in kinds and "match" in kinds
    for q in q1.questions:
        if q.kind == "mcq":
            assert len(q.options) == 4 and len(set(q.options)) == 4
            assert q.answer in LETTERS
            assert q.options[LETTERS.index(q.answer)] not in q.text  # answer not leaked
        if q.kind == "match":
            assert len(q.pairs) == 4 and q.answer.count("-") == 4
        assert q.source.endswith("-bet")


def test_quiz_reports_shortfall():
    r = build_quiz([(1, "Juda qisqa matn.")], 10)
    assert r.questions == [] and "0 ta savol" in r.note


# ---------- request parsing ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("7-sinf fizika Nyuton qonunlari 20 ta test tuzib ber",
         TestRequest(7, "Fizika", "nyuton qonunlari", 20, 1)),
        ("9 sinf o‘zbekiston tarixi Buxoro amirligi bo‘yicha 15 ta savol 2 variant",
         TestRequest(9, "O‘zbekiston tarixi", "buxoro amirligi", 15, 2)),
        ("Algebra 8-sinf kasrlar mavzusidan test", TestRequest(8, "Algebra", "kasrlar", 20, 1)),
    ],
)  # fmt: skip
def test_parse_test_request(text, expected):
    assert parse_test_request(text) == expected


def test_non_test_message_is_not_a_request():
    assert parse_test_request("salom, qandaysan?") is None


def test_request_validation():
    with pytest.raises(ValueError):
        TestRequest(7, "Fizika", count=0).validate()
    with pytest.raises(ValueError):
        TestRequest(12, "Fizika").validate()
    with pytest.raises(ValueError):
        TestRequest(7, "Fizika", variants=9).validate()
