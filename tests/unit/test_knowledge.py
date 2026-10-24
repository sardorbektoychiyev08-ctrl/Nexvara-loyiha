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
    assert fts_query("Kasrlarni qo‘shish") == '"kasrla"* AND "qosh"*'
    # «tizimi» finds an older book's «SISTEMASI» (live 2026-10-24)
    assert fts_query("qon tizimi") == '"qon"* AND ("tizi"* OR "sistem"*)'


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
        ("7-sinf fizika fanidan «Nyuton qonunlari» mavzusidan 20 ta test, 2 variant",
         TestRequest(7, "Fizika", "nyuton qonunlari", 20, 2)),
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


def test_current_edition_prefers_rtm_and_keeps_all_quarters(tmp_path):
    lib = Library(tmp_path / "t.db")
    old = ["Eski nashr: bosim haqida."]
    q1 = ["Yangi 1-chorak: bosim haqida."]
    q2 = ["Yangi 2-chorak: kuch haqida."]
    lib.add_book(path="e", sha256="1", title="eski", grade=7, subject="Fizika", year=2017,
                 pages=old, rank=0)  # fmt: skip
    lib.add_book(path="r1", sha256="2", title="1-chorak", grade=7, subject="Fizika", year=2025,
                 pages=q1, rank=2)  # fmt: skip
    lib.add_book(path="r2", sha256="3", title="2-chorak", grade=7, subject="Fizika", year=2026,
                 pages=q2, rank=2)  # fmt: skip
    assert {b.title for b in lib.current_edition(7, "Fizika")} == {"1-chorak", "2-chorak"}
    assert [h.book.title for h in lib.search("bosim", 7, "Fizika")] == ["1-chorak"]
    assert [h.book.title for h in lib.search("kuch", 7, "Fizika")] == ["2-chorak"]
    assert len(lib.search("bosim", 7, "Fizika", newest_only=False)) == 2
    lib.close()


def test_source_rank_from_folder(tmp_path):
    from nexvara.knowledge.ingest import source_rank

    assert source_rank(tmp_path / "rtm" / "7-sinf" / "a.pdf", tmp_path) == 2
    assert source_rank(tmp_path / "eduportal" / "7-sinf" / "a.pdf", tmp_path) == 0
    assert source_rank(tmp_path / "7-sinf" / "a.pdf", tmp_path) == 1


def test_picture_questions_use_captions_as_answers(tmp_path):
    import random

    from nexvara.knowledge.figures import captions_in_text
    from nexvara.knowledge.quiz import _short_caption, picture_questions

    text = (
        "Matn: 61-rasmda ko‘rsatilganidek, kuch ta’sir etadi.\n"
        "61-rasm. Ikki qayiqning bir-biriga\ntortilishi.\n"
        "62-rasm. Kuchlar muvozanati F\n"
        "63-rasm. Tok kuchini o‘lchash sxemasi"
    )
    figs = captions_in_text(5, text)
    assert [(f.number, f.caption) for f in figs] == [
        (61, "Ikki qayiqning bir-biriga tortilishi"),  # wrapped caption joined
        (62, "Kuchlar muvozanati F"),
        (63, "Tok kuchini o‘lchash sxemasi"),
    ]  # "61-rasmda ..." in running text is not a caption
    assert figs[2].is_drawing and not figs[0].is_drawing
    assert _short_caption("Kuchlar muvozanati F") == "Kuchlar muvozanati"
    assert _short_caption("Havo frontlari: a) sovuq front; b) iliq front") == "Havo frontlari"

    img = tmp_path / "r.png"
    img.write_bytes(b"png")
    figs[0].image = img
    pool = ["Kuchlar muvozanati F", "Tok kuchini o‘lchash sxemasi", "Prujinaning cho‘zilishi",
            "Erkin tushish tajribasi", "Ikki qayiqning bir-biriga tortilishi"]  # fmt: skip
    (q,) = picture_questions(figs, pool, random.Random(1))
    assert q.text == "Rasmda nima tasvirlangan?" and q.image == str(img)
    assert q.options[LETTERS.index(q.answer)] == "Ikki qayiqning bir-biriga tortilishi"
    assert len(set(q.options)) == 4 and q.source == "5-bet"
    assert picture_questions(figs[1:], pool, random.Random(1)) == []  # no picture -> no question


@pytest.mark.parametrize(
    ("name", "grade", "subject"),
    [
        ("MATEMATICS WORKBOOK G6 P2 UZB.pdf", 6, "Matematika"),
        ("Physics Grade 7 UZB.pdf", 7, "Fizika"),
        ("Science_5-sinf_uzb.pdf", 5, "Tabiiy fanlar"),
    ],
)
def test_english_named_rtm_files(tmp_path, name, grade, subject):
    info = catalog.describe(tmp_path / name, "", None)
    assert (info.grade, info.subject) == (grade, subject)


def test_test_request_with_typos_and_where_to_write():
    """Live 2026-10-21: «menga6-sinif … 20 talik» lost the grade and «Excel faylida» became
    the topic, so the textbook search failed and Word never opened."""
    from nexvara.knowledge.service import parse_test_request

    r = parse_test_request("menga6-sinif informatikasidan test tuz 20 talik")
    assert (r.grade, r.subject, r.topic, r.count) == (6, "Informatika", "", 20)
    r = parse_test_request("6-sinf informatika 20 ta test Excel faylida tuz")
    assert (r.grade, r.topic) == (6, "")
    r = parse_test_request("5-sinf matematika kasrlar 2 ta variant 10 talik test")
    assert (r.topic, r.count, r.variants) == ("kasrlar", 10, 2)


def test_typo_fixed_request_keeps_count_out_of_the_topic():
    from nexvara.agent.typos import fix
    from nexvara.knowledge.service import parse_test_request

    r = parse_test_request(fix("menga6-sinif informatikasidan test tuz 20 talik"))
    assert (r.grade, r.topic, r.count) == (6, "", 20)
    r = parse_test_request("8-sinf tarix 2 ta variant test 30 ta")
    assert (r.topic, r.count, r.variants) == ("", 30, 2)
