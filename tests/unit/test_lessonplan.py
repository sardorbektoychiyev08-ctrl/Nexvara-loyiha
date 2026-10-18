"""«Dars ishlanmasi»: the request is understood and the plan's content comes from the textbook."""

from __future__ import annotations

import pytest
from tests.textbook_fixture import write_pdf

from nexvara.knowledge.lessonplan import STAGES, lesson_content, parse_lesson_request


@pytest.mark.parametrize(
    ("text", "grade", "subject", "topic"),
    [
        ("7-sinf fizika Nyuton qonunlari dars ishlanmasi", 7, "Fizika", "nyuton qonunlari"),
        ("8-sinf tarix Amir Temur mavzusida dars konspekti", 8, "Tarix", "amir temur"),
        (
            "AI bilan 7-sinf fizika «Tezlik» uchun 45 daqiqalik dars rejasi tuz",
            7,
            "Fizika",
            "tezlik",
        ),
    ],
)
def test_requests(text, grade, subject, topic):
    req = parse_lesson_request(text)
    assert (req.grade, req.subject, req.topic) == (grade, subject, topic)


def test_not_a_lesson():
    assert parse_lesson_request("Bugun darsga borasanmi?") is None
    assert parse_lesson_request("dars ishlanmasi") is None  # no class or subject


def test_content_from_the_textbook(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    books = tmp_path / "data" / "Darsliklar" / "7-sinf"
    books.mkdir(parents=True)
    write_pdf(books / "Fizika.pdf")
    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import index_library
    from nexvara.knowledge.topicdoc import lookup

    assert TaskRunner().start("index", index_library).wait(120)
    topic = lookup(parse_lesson_request("7-sinf fizika mexanik harakat dars ishlanmasi"))
    data = lesson_content(topic)
    assert sum(m for _s, m in STAGES) == 45
    assert set(data["aims"]) == {"Ta’limiy", "Tarbiyaviy", "Rivojlantiruvchi"}
    assert any("Trayektoriya" in d.term or "Moddiy nuqta" in d.term for d in data["defs"])
    assert data["quiz"] and all(q.answer for q in data["quiz"])
    assert topic.pages_label in data["teach"]["Uyga vazifa"][0]
