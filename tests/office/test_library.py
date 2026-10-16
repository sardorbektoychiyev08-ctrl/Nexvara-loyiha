"""Textbook library + test generation with real Word. Run with NEXVARA_RUN_OFFICE=1."""

import os

import pytest
from tests.textbook_fixture import write_pdf

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Word",
    ),
]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolated NEXVARA data folder with one synthetic 7th-grade physics textbook."""
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path))
    books = tmp_path / "Darsliklar" / "7-sinf"
    books.mkdir(parents=True)
    write_pdf(books / "Fizika.pdf")
    return tmp_path


def test_index_then_make_test_in_word(data_dir):
    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import TestRequest, index_library
    from nexvara.knowledge.testdoc import run_make_test

    runner = TaskRunner()
    t = runner.start("index", index_library)
    assert t.wait(120) and t.status.value == "succeeded", t.error
    assert t.result["books"] == 1

    req = TestRequest(7, "Fizika", "kuch massa bosim", count=8, variants=2)
    t = runner.start("test", lambda task: run_make_test(task, req, keep_open=False, pause=0))
    assert t.wait(300), "Word test did not finish"
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    res = snap["result"]
    assert all(c["ok"] for c in res["checks"]), res["checks"]
    assert res["variants"] == 2 and res["questions"] >= 5
    assert res["path"].startswith(str(data_dir / "Testlar"))
    assert os.path.isfile(res["path"]) and os.path.isfile(res["pdf"])


def test_chat_request_builds_a_test(data_dir, tmp_path):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    runner = TaskRunner()
    api = Api(runner, output_dir=tmp_path / "out", keep_office_open=False)
    idx = api.index_library()
    assert runner.get(idx["id"]).wait(120)

    reply = api.chat("7-sinf fizika Nyuton harakat qonunlari 6 ta test tuzib ber")
    assert "task" in reply, reply
    task = runner.get(reply["task"]["id"])
    assert task.wait(300)
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert snap["result"]["path"].startswith(str(tmp_path / "out"))


def test_missing_topic_is_reported_honestly(data_dir):
    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import TestRequest, index_library
    from nexvara.knowledge.testdoc import run_make_test

    runner = TaskRunner()
    assert runner.start("index", index_library).wait(120)
    req = TestRequest(7, "Fizika", "fotosintez xloroplast", count=5)
    t = runner.start("test", lambda task: run_make_test(task, req, keep_open=False))
    assert t.wait(60)
    assert t.snapshot()["status"] == "failed"
    assert "topilmadi" in t.error


def test_library_page_in_real_ui(data_dir, tmp_path):
    """Opens NEXVARA, presses "Yangilash" and submits the "Test tuzish" form for real."""
    import subprocess
    import sys

    out = tmp_path / "ui-out"
    proc = subprocess.run(
        [sys.executable, "-m", "nexvara.app.main", "--selftest-library", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=400,
        env={**os.environ, "NEXVARA_DATA": str(data_dir), "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SELFTEST PASS [lib-index]" in proc.stdout
    assert "SELFTEST PASS [t-topic-show]" in proc.stdout
    assert "SELFTEST PASS [t-make]" in proc.stdout
    assert len(list(out.glob("test_7-sinf_Fizika_*.docx"))) == 1


def test_show_topic_in_word_with_original_pages(data_dir):
    from pypdf import PdfReader

    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import index_library
    from nexvara.knowledge.topicdoc import TopicRequest, run_topic

    runner = TaskRunner()
    assert runner.start("index", index_library).wait(120)
    req = TopicRequest(7, "Fizika", "bosim")
    t = runner.start("topic", lambda task: run_topic(task, req, keep_open=False, pause=0))
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    res = snap["result"]
    assert all(c["ok"] for c in res["checks"]), res["checks"]
    assert res["title"] == "3-§. Bosim" and res["start_page"] == res["end_page"] == 4
    assert res["path"].startswith(str(data_dir / "Mavzular"))
    excerpt = PdfReader(res["excerpt"])
    assert len(excerpt.pages) == 1 and "Paskal" in excerpt.pages[0].extract_text()


def test_chat_topic_request(data_dir, tmp_path):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    runner = TaskRunner()
    api = Api(runner, output_dir=tmp_path / "out", keep_office_open=False)
    assert runner.get(api.index_library()["id"]).wait(120)

    reply = api.chat("7-sinf fizika bosim mavzusini chiqarib ber")
    assert "3-§. Bosim" in reply["reply"] and "4-bet" in reply["reply"], reply
    task = runner.get(reply["task"]["id"])
    assert task.wait(300) and task.snapshot()["status"] == "succeeded", task.error
    assert "topilmadi" in api.chat("7-sinf fizika fotosintez mavzusi kerak")["reply"]
