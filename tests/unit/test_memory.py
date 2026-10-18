"""Memory (facts, chat log, search, backup) and Teach NEXVARA rules."""

from __future__ import annotations

import pytest

from nexvara.agent.parse import parse_command
from nexvara.memory import store as store_mod
from nexvara.memory.store import MemoryStore
from nexvara.memory.teach import apply_rules, defaults_for_tests, parse_teach, word_template


@pytest.fixture
def mem(tmp_path):
    return MemoryStore(tmp_path / "app.db")


def test_facts_crud_and_stem_search(mem):
    fid = mem.add_fact("Men 12-maktabda fizika o‘qituvchisiman")
    mem.add_fact("Sinfim: 7-B")
    assert [f["text"] for f in mem.search("maktabimizda")] == [
        "Men 12-maktabda fizika o‘qituvchisiman"
    ]
    assert mem.relevant_facts("fizikadan test kerak") == ["Men 12-maktabda fizika o‘qituvchisiman"]
    assert mem.relevant_facts("") == []
    mem.update_fact(fid, "Men 12-maktabda kimyo o‘qituvchisiman")
    assert mem.search("fizika") == []
    assert mem.search("kimyo")[0]["id"] == fid
    mem.delete_fact(fid)
    assert [f["text"] for f in mem.facts()] == ["Sinfim: 7-B"]
    with pytest.raises(ValueError):
        mem.add_fact("   ")
    with pytest.raises(LookupError):
        mem.update_fact(999, "x")


def test_chat_log_is_trimmed_and_searchable(mem, monkeypatch):
    monkeypatch.setattr(store_mod, "CHAT_KEEP", 3)
    for i in range(5):
        mem.log_chat("user", f"xabar {i} hisobot")
    assert [c["text"] for c in mem.chat()] == [
        "xabar 2 hisobot",
        "xabar 3 hisobot",
        "xabar 4 hisobot",
    ]
    assert len(mem.search("hisobot")) == 3
    mem.clear_chat()
    assert mem.chat() == [] and mem.search("hisobot") == []


def test_rules_have_versions(mem):
    r = mem.add_rule("excel", "jadvalni formatla")
    r2 = mem.update_rule(r.id, text="jadvalni formatla va jami qo‘sh")
    assert r2.version == 2
    mem.update_rule(r.id, enabled=False)
    assert mem.rules("excel", enabled_only=True) == []
    assert [v["version"] for v in mem.rule_versions(r.id)] == [1, 2]
    with pytest.raises(ValueError):
        mem.add_rule("paint", "x")


def test_backup_and_restore(mem, tmp_path):
    mem.add_fact("Ismim Sardor")
    r = mem.add_rule("word", "sahifa raqamini qo‘y")
    mem.update_rule(r.id, enabled=False)
    mem.log_chat("user", "salom")
    path = mem.export_file(tmp_path / "z" / "backup.json")
    fresh = MemoryStore(tmp_path / "other.db")
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert fresh.import_data(data) == {"facts": 1, "rules": 1}
    assert fresh.import_data(data) == {"facts": 0, "rules": 0}  # no duplicates
    assert fresh.rules()[0].enabled is False
    with pytest.raises(ValueError):
        fresh.import_data({"format": "boshqa"})


def test_parse_teach():
    r = parse_teach("Har doim Excel raqamlarini markazga joyla")
    assert (r.kind, r.app, r.error) == ("rule", "excel", "")
    assert r.actions == ["Jadvalni formatlash"]
    r = parse_teach("Excel jadvallarida doim sarlavhani qotir va jami qo‘sh")
    assert r.actions == ["Sarlavhani qotirish", "Jami qatorini qo‘shish"]
    r = parse_teach("testlar doim 30 ta savol 2 variant bo‘lsin")
    assert (r.app, r.actions) == ("test", ["testlar: 30 ta savol, 2 ta variant"])
    r = parse_teach("Eslab qol: men 12-maktabda fizika o‘qituvchisiman")
    assert (r.kind, r.text) == ("fact", "men 12-maktabda fizika o‘qituvchisiman")
    assert parse_teach("har doim Excel'da uchib yur").error
    assert parse_teach("salom qalaysan") is None
    assert parse_teach("Hisobot.xlsx ni har doim formatla") is None  # a file command
    assert parse_teach("Mana shu Word shablonini ishlat: D:\\Yoq\\x.dotx").error


def test_word_template_rule(mem, tmp_path):
    tpl = tmp_path / "maktab.dotx"
    tpl.write_bytes(b"x")
    r = parse_teach(f"Har doim mana shu Word shablonini ishlat: {tpl}")
    assert r.app == "word" and not r.error
    mem.add_rule("word", r.text)
    assert word_template(mem) == str(tpl)
    tpl.unlink()
    assert word_template(mem) is None  # a deleted template is ignored, not an error


def test_apply_rules(mem):
    mem.add_rule("excel", "jadvalni formatla va sarlavhani qotir")
    off = mem.add_rule("excel", "jami qo‘sh")
    mem.update_rule(off.id, enabled=False)
    mem.add_rule("word", "sahifa raqamini qo‘y")
    plan = parse_command("Hisobot.xlsx ni och, sarlavhani qotir, PDF qilib saqla")
    new, applied = apply_rules(plan, mem)
    kinds = [a.kind for a in new.actions]
    assert kinds == ["open", "freeze", "format", "pdf"]  # before export; no duplicate freeze
    assert len(applied) == 1 and "o‘rgatilgan" in new.actions[2].text
    word_plan = parse_command("Xat.docx ni och va saqla")
    assert [a.kind for a in apply_rules(word_plan, mem)[0].actions] == [
        "open",
        "page_numbers",
        "save",
    ]


def test_defaults_for_tests(mem):
    mem.add_rule("test", "30 ta savol 2 variant")
    assert defaults_for_tests(mem) == {"count": 30, "variants": 2}


def test_chat_teach_flow(mem, tmp_path):
    from nexvara.app.api import Api

    api = Api(overrides={"memory": mem, "command": lambda t: {"path": "x"}})
    out = api.chat("Eslab qol: mening ismim Sardor")
    assert "Saqlaymi" in out["reply"] and out["confirm"]
    assert mem.facts() == []  # nothing saved before "Ha"
    assert "Eslab qoldim" in api.confirm_ai(out["confirm"])["reply"]
    assert mem.facts()[0]["text"] == "mening ismim Sardor"

    out = api.chat("Har doim Excel raqamlarini markazga joyla")
    api.confirm_ai(out["confirm"])
    assert mem.rules("excel")[0].text == "raqamlarini markazga joyla"
    assert "ismim Sardor" in api.chat("nimalarni eslab qolding")["reply"]

    xlsx = tmp_path / "Hisobot.xlsx"
    xlsx.write_bytes(b"")
    reply = api.chat(f"{xlsx} ni och va saqla")["reply"]
    assert "Jadvalni formatlash" in reply and "O‘rgatilgan qoidalar" in reply

    params = {"count": 20, "variants": 1}
    mem.add_rule("test", "2 variant")
    api._apply_test_rules("7-sinf fizika 10 ta test", params)
    assert params == {"count": 20, "variants": 2}
    assert [c["role"] for c in mem.chat()][:2] == ["user", "nexvara"]


def test_api_teach_page(mem):
    from nexvara.app.api import Api

    api = Api(overrides={"memory": mem})
    assert not api.teach_preview("excel", "uchib yur")["ok"]
    assert api.teach_add("excel", "jadvalni formatla")["ok"]
    rid = api.teach_rules()[0]["id"]
    assert not api.teach_update(rid, text="nimadir tushunarsiz")["ok"]
    assert api.teach_update(rid, text="sarlavhani qotir")["rules"][0]["version"] == 2
    assert api.teach_update(rid, enabled=False)["rules"][0]["enabled"] is False
    assert len(api.teach_versions(rid)) == 2
    assert api.teach_delete(rid) == []
    plain = Api()  # tests without a memory never touch the user's data
    assert plain.memory_facts() == [] and plain.teach_rules() == []


def test_refusing_to_be_remembered_is_not_a_teach_request():
    from nexvara.memory.teach import parse_teach

    for no in ("Mening ismim Sardor. Buni eslab qol degan emasman, shunchaki gaplashyapmiz.",
               "Buni eslab qolish shart emas", "eslab qolma, bu sinov"):  # fmt: skip
        assert parse_teach(no) is None, no
    assert parse_teach("Eslab qol: maktabim 12-maktab").kind == "fact"
    assert parse_teach("Unutma, majlis juma kuni").kind == "fact"
