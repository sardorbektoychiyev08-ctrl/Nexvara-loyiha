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


def test_ai_test_in_word_with_fake_provider(data_dir, tmp_path):
    """The whole "AI bilan test" path in real Word; the provider is a fake (no paid call)."""
    import json

    import pymupdf

    from nexvara.ai.keys import MemoryKeyStore
    from nexvara.ai.providers import Provider, Reply
    from nexvara.ai.router import AiRouter, Ledger
    from nexvara.app.api import Api
    from nexvara.appdata import Settings
    from nexvara.core.task import TaskRunner

    questions = []

    class Fake(Provider):
        calls = 0

        def complete(self, model, system, messages, max_tokens, effort="medium"):
            Fake.calls += 1
            return Reply(json.dumps(questions), model, 2000, 1500)

        def list_models(self):  # the account's models (the key check needs a real list)
            return ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]

    router = AiRouter(
        Settings(tmp_path / "s.json"), MemoryKeyStore(), Ledger(tmp_path / "a.db"),
        factory=lambda n, k: Fake(),
    )  # fmt: skip
    router.save_key("anthropic", "sk-ant-fake-0123456789")
    router.settings.update({"ai": {"enabled": True}})  # the user switches AI on
    # a price question even for a cheap test (the owner's threshold is $0.05)
    router.settings.update({"ai": {"confirm_over_usd": 0.0}})
    runner = TaskRunner()
    api = Api(runner, output_dir=tmp_path / "out", keep_office_open=False,
              overrides={"ai_router": router})  # fmt: skip
    assert runner.get(api.index_library()["id"]).wait(120)

    from nexvara.knowledge.service import TestRequest, topic_material

    _book, pages, _topic = topic_material(TestRequest(7, "Fizika", "kuch", 6, 1))
    evidence = next(text for page, text in pages if page == 3).splitlines()[2]
    questions = [
        {"q": f"AI savol {i}: kuch qanday kattalik?", "options": ["Vektor", "Skalyar",
         "O‘zgarmas", "O‘lchovsiz"], "answer": 0, "page": 3, "evidence": evidence}
        for i in range(10)
    ]  # fmt: skip
    ask = api.chat("AI bilan 7-sinf fizika kuch 6 ta test tuz")
    assert ask.get("confirm") and "$" in ask["reply"] and Fake.calls == 0  # price, then «Ha»
    reply = api.confirm_ai(ask["confirm"], True)
    assert "task" in reply, reply
    task = runner.get(reply["task"]["id"])
    assert task.wait(300)
    snap = task.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert snap["title"].startswith("AI test")
    res = snap["result"]
    assert all(c["ok"] for c in res["checks"]), res["checks"]
    assert res["questions"] == 6 and Fake.calls == 1
    assert router.ledger.today() > 0
    with pymupdf.open(res["pdf"]) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
    assert "AI yordamida" in text and "AI ishlatilmasdan" not in text


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


def test_picture_questions_in_word(tmp_path, monkeypatch):
    """A textbook with figures: the test gets "Rasmda nima tasvirlangan?" questions with the
    picture embedded and the caption hidden from the picture."""
    import pymupdf
    from tests.textbook_fixture import PAGES

    from nexvara.core.task import TaskRunner
    from nexvara.knowledge.service import TestRequest, index_library
    from nexvara.knowledge.testdoc import run_make_test
    from nexvara.skills.png_chart import bar_chart_png

    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    books = tmp_path / "data" / "Darsliklar" / "7-sinf"
    books.mkdir(parents=True)
    png = bar_chart_png([3, 5, 2, 4], tmp_path / "chart.png", width=400, height=240)
    captions = {
        1: "1-rasm. Ikki aravachaning to'qnashishi",
        2: "2-rasm. Prujinaning cho'zilishi",
        3: "3-rasm. Gidravlik press sxemasi",
    }
    doc = pymupdf.open()
    for i, text in enumerate(PAGES):
        page = doc.new_page(width=595, height=842)
        y = 80
        for line in text.split("\n"):
            page.insert_text((40, y), line, fontsize=10)
            y += 16
        if i in captions:
            page.insert_image(pymupdf.Rect(150, 420, 450, 600), filename=str(png))
            page.insert_text((150, 618), captions[i], fontsize=10)
    doc.save(str(books / "Fizika.pdf"))

    runner = TaskRunner()
    assert runner.start("index", index_library).wait(120)
    req = TestRequest(7, "Fizika", "tezlik va kuch", count=8, variants=1)
    t = runner.start("test", lambda task: run_make_test(task, req, keep_open=False, pause=0))
    assert t.wait(300)
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    res = snap["result"]
    assert res["pictures"] >= 1, res
    assert all(c["ok"] for c in res["checks"]), res["checks"]
    with pymupdf.open(res["pdf"]) as out:
        text = "".join(p.get_text() for p in out)
        assert "Rasmda nima tasvirlangan?" in text
        assert sum(len(p.get_images()) for p in out) == res["pictures"]
    assert not list((tmp_path / "data" / "tmp").glob("*")), "temp pictures must be cleaned up"
