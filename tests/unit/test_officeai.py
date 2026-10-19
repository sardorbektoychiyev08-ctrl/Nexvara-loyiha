"""Translate / rewrite Word and PowerPoint with AI: chat, price and «Ha», batches, JSON check.
Fake providers only (nothing is paid); Office is replaced by a fake runner here."""

import json
import zipfile

import pytest
from test_ai_media import KEYS, make

from nexvara import officeai


def _docx(path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "word/document.xml", f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>'
        )
    return path


def test_batches_and_answers_are_checked():
    texts = ["Salom", "", "Xat " * 2000, "Rahmat"]
    groups = officeai.batches(texts)
    assert (
        groups == [[0], [2], [3]]
        or groups == [[0, 2], [3]]
        or [i for g in groups for i in g] == [0, 2, 3]
    )
    assert officeai.parse_items('Mana: ["a", "b"]', 2) == ["a", "b"]
    assert officeai.parse_items('["a"]', 2) is None and officeai.parse_items("yo‘q", 1) is None

    def ask(system, user):
        assert "English" in system and "⟦" in system  # markers must survive
        return json.dumps([x.upper() for x in json.loads(user)])

    out = officeai.transform(["salom", "", "rahmat"], {"mode": "translate", "lang": "English"}, ask)
    assert out == ["SALOM", "", "RAHMAT"]  # empty parts are never sent
    with pytest.raises(Exception, match="mos kelmadi"):
        officeai.transform(
            ["a", "b"], {"mode": "rewrite", "style": "x"}, lambda s, u: '["only one"]'
        )


def test_chat_asks_price_then_runs_a_task(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    r = make(tmp_path, {"openai": KEYS["openai"]})  # paid only: «Ha» is needed
    doc = _docx(tmp_path / "Xat.docx", ["Hurmatli ota-onalar!", "Yig‘ilish ertaga soat 15:00 da."])
    seen = {}

    def fake_run(task, src, job, ask, keep_open=True):
        seen["job"], seen["src"] = job, src
        seen["answer"] = ask("sys", json.dumps(["Salom"]))
        return {"path": str(src.with_name("Xat_EN.docx"))}

    api = Api(overrides={"ai_router": r, "officeai_run": fake_run})
    ask = api.chat(f"«{doc}» ni ingliz tiliga tarjima qil")
    assert ask.get("confirm") and "English tiliga tarjima" in ask["reply"] and "$" in ask["reply"]
    assert "job" not in seen  # nothing runs before «Ha»
    done = api.confirm_ai(ask["confirm"], True)
    assert api._runner.get(done["task"]["id"]).wait(10)
    assert seen["job"] == {"mode": "translate", "lang": "English"} and seen["src"] == doc
    assert r.ledger.today() > 0  # the AI call was recorded
    # a .docx that does not exist, and a request without a file, are not translated
    assert "topilmadi" in api.chat("Yoq.docx ni rus tiliga tarjima qil")["reply"].lower()


def test_text_size_from_the_file_itself(tmp_path):
    from nexvara.app.api_officeai import xml_text_size

    doc = _docx(tmp_path / "a.docx", ["abc", "de"])
    assert xml_text_size(doc) == 5
    (tmp_path / "b.docx").write_bytes(b"not a zip")
    assert xml_text_size(tmp_path / "b.docx") == 0
