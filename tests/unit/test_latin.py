"""Uzbek is always written in the Latin alphabet: Cyrillic Uzbek from an AI answer or a textbook
is converted; Russian (and an explicit request for it) is left alone."""

from __future__ import annotations

import pytest

from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import Provider, Reply
from nexvara.ai.router import LATIN_RULE, AiRouter, Ledger
from nexvara.appdata import Settings
from nexvara.knowledge import textnorm


@pytest.mark.parametrize(
    ("cyr", "lat"),
    [
        ("Ўзбекистон Республикаси", "O‘zbekiston Respublikasi"),
        ("Ер шари ва ой", "Yer shari va oy"),
        ("цех, концерт, Цельсий", "sex, konsert, Selsiy"),
        ("ЯНГИ ЙИЛ", "YANGI YIL"),
        ("Шаҳло ғалаба қилди", "Shahlo g‘alaba qildi"),
        ("маъно, юлдуз, ёз", "ma’no, yulduz, yoz"),
        ("Mixed: 7-sinf, Ўқувчи", "Mixed: 7-sinf, O‘quvchi"),
    ],
)  # fmt: skip
def test_cyrillic_uzbek_to_latin(cyr, lat):
    assert textnorm.cyr_to_latin(cyr) == lat


def test_russian_is_not_touched():
    ru = "Это проверка: как дела у нас в школе?"
    assert not textnorm.is_uzbek_cyrillic(ru)
    assert textnorm.to_latin_if_uzbek(ru) == ru
    assert textnorm.is_uzbek_cyrillic("Бу ўқувчилар учун тест")
    assert textnorm.to_latin_if_uzbek("O‘zbekcha matn") == "O‘zbekcha matn"


class Echo(Provider):
    def __init__(self, answer):
        self.answer, self.systems = answer, []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.systems.append(system)
        return Reply(self.answer, model, 100, 50)

    def list_models(self):
        return []


def _router(tmp_path, answer):
    pro = Echo(answer)
    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore({"openai": "sk-test-openai-123456"}),
                 Ledger(tmp_path / "l.db"), factory=lambda n, k: pro)  # fmt: skip
    r.settings.update({"ai": {"enabled": True}})
    return r, pro


def test_ai_is_told_latin_and_a_cyrillic_answer_is_converted(tmp_path):
    r, pro = _router(tmp_path, "Нютон қонунлари: жисм тинч ҳолатда қолади.")
    reply = r.complete(
        "chat", "sys", [{"role": "user", "content": "Nyuton qonunlari nima?"}], approved=True
    )
    assert reply.text == "Nyuton qonunlari: jism tinch holatda qoladi."
    assert LATIN_RULE.strip() in pro.systems[0]


def test_an_explicit_russian_request_keeps_russian(tmp_path):
    r, pro = _router(tmp_path, "Законы Ньютона описывают движение тел.")
    reply = r.complete(
        "chat", "sys", [{"role": "user", "content": "Rus tiliga tarjima qil: ..."}], approved=True
    )
    assert reply.text == "Законы Ньютона описывают движение тел."
    assert "TIL QOIDASI" not in pro.systems[0]


def test_uzbek_textbook_in_cyrillic_is_indexed_in_latin(tmp_path):
    import fitz

    from nexvara.knowledge.ingest import ingest_folder
    from nexvara.knowledge.store import Library

    root = tmp_path / "Darsliklar" / "7-sinf"
    root.mkdir(parents=True)
    pages = [
        "7-синф ФИЗИКА\nУмумий ўрта таълим мактабларининг 7-синфи учун дарслик\nТошкент - 2019",
        "1-§. МЕХАНИК ҲАРАКАТ\nЖисмнинг бошқа жисмларга нисбатан вазиятининг вақт ўтиши билан "
        "ўзгариши механик ҳаракат деб аталади. Ҳаракат қайси жисмга нисбатан кузатилаётган бўлса, "
        "ўша жисм саноқ жисми деб аталади. Траектория ва йўл тушунчалари ҳам шу ерда берилади.",
        "2-§. ТЕЗЛИК\nТезлик — жисмнинг вақт бирлиги ичида босиб ўтган йўлига сон жиҳатдан тенг "
        "катталик. Тезлик бирлиги метр тақсим секунд. Текис ҳаракатда тезлик ўзгармайди ва йўл "
        "вақтга тўғри пропорционал бўлади.",
        "3-§. КУЧ\nКуч — жисмларнинг ўзаро таъсир ўлчови. Куч бирлиги Нютон. Куч таъсирида "
        "жисмнинг тезлиги ўзгаради. Бир нечта куч бир вақтда таъсир қилиши мумкин ва уларнинг "
        "тенг таъсир этувчиси топилади.",
    ]
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(40, 40, 560, 800), text, fontsize=11,
                            fontfile="C:/Windows/Fonts/arial.ttf", fontname="ar")  # fmt: skip
    doc.save(str(root / "Fizika.pdf"))
    ru = tmp_path / "Darsliklar" / "8-sinf"
    ru.mkdir()
    doc = fitz.open()
    for _ in range(4):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(40, 40, 560, 800), "Физика 8 класс. Это учебник для школ "
                            "с русским языком обучения. Механическое движение и его виды. " * 3,
                            fontsize=11, fontfile="C:/Windows/Fonts/arial.ttf",
                            fontname="ar")  # fmt: skip
    doc.save(str(ru / "Fizika.pdf"))
    lib = Library(tmp_path / "t.db")
    rep = ingest_folder(tmp_path / "Darsliklar", lib)
    books = {b.grade: b for b in lib.books(status=None)}
    assert books[7].status == "ok" and "lotinga" in books[7].note
    hits = lib.search("sanoq jismi", 7, "Fizika")
    assert hits and "sanoq jismi deb ataladi" in hits[0].text and "MEXANIK HARAKAT" in hits[0].text
    assert books[8].status == "cyrillic" and rep.cyrillic == ["Fizika.pdf"]
    lib.close()
