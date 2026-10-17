"""Core Agent: several tasks in one message, conversation context, the AI tool-calling
planner (fake provider, nothing paid) and the Memory ↔ Teach ↔ Office links."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import Provider, Reply
from nexvara.ai.router import AiRouter, Ledger
from nexvara.appdata import Settings


class FakeProvider(Provider):
    def __init__(self):
        self.replies: list[str] = []
        self.calls: list[dict] = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append({"system": system, "messages": messages})
        return Reply(self.replies.pop(0) if self.replies else '{"kind": "chat"}', model, 900, 120)

    def list_models(self):
        return ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore

    work = tmp_path / "Ish"
    work.mkdir()
    for n in ("Hisobot.xlsx", "Savdo.xlsx", "Oylik.xlsx"):
        (work / n).write_bytes(b"PK " + n.encode())
    commands = []

    def office(task):  # what the Office executor would produce: Hisobot.pdf next to the file
        commands.append(task.title)
        name = task.title.split(": ", 1)[-1]
        pdf = work / (Path(name).stem + ".pdf")
        pdf.write_bytes(b"%PDF")
        return {"path": str(work / name), "pdf": str(pdf)}

    fake = FakeProvider()
    router = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(), Ledger(tmp_path / "l.db"),
                      factory=lambda name, key: fake)  # fmt: skip
    mem = MemoryStore(tmp_path / "app.db")
    api = Api(TaskRunner(), overrides={"memory": mem, "command": office, "ai_router": router})
    api._context_file = str(work / "Hisobot.xlsx")
    api.fake, api.router, api.commands, api.work = fake, router, commands, work
    return api


def done(api, reply):
    assert reply.get("task"), reply
    t = api._runner.get(reply["task"]["id"])
    assert t.wait(20)
    return t.snapshot()


# ---------------- several tasks, references, repeat ----------------


def test_chain_with_reference_to_previous_result(env):
    api, work = env, env.work
    arxiv = work / "Arxiv"
    r = api.chat(f"Hisobot.xlsx ni PDF qilib saqla, keyin uni {arxiv} ga ko‘chir")
    assert r["plan"] and len(r["plan"]) == 2, r
    snap = done(api, r)
    assert snap["status"] == "succeeded", snap
    assert (arxiv / "Hisobot.pdf").is_file() and not (work / "Hisobot.pdf").exists()
    assert snap["result"]["path"].endswith("Hisobot.pdf")


def test_office_clauses_about_one_file_stay_one_command(env):
    api = env
    r = api.chat("Savdo.xlsx ni och, keyin B ustun bo‘yicha saralab, PDF qilib saqla")
    assert "plan" in r and not r["reply"].startswith("Ketma-ket"), r
    done(api, r)
    assert api.commands == ["Buyruq: Savdo.xlsx"]


def test_risky_step_in_a_chain_asks_first(env):
    api, work = env, env.work
    r = api.chat(f"{work / 'Oylik.xlsx'} ni zip qil; keyin {work / 'Oylik.xlsx'} ni o‘chir")
    assert r["confirm"] and "Savatga" in r["reply"] and "task" not in r
    assert "Bekor" in api.confirm_ai(r["confirm"], yes=False)["reply"]
    assert (work / "Oylik.xlsx").is_file() and not list(work.glob("*.zip"))


def test_found_files_and_repeat_last_command(env, monkeypatch):
    api, work = env, env.work
    r = api.chat(f"{work} papkasidan excel fayllarini top")
    assert len(r["files"]) == 3
    r = api.chat("topilgan fayllarni zip qil")
    assert Path(r["files"][0]).suffix == ".zip"
    done(api, api.chat("Hisobot.xlsx ni och, formatla va saqla"))
    r = api.chat("xuddi shunday Savdo.xlsx bilan ham qil")
    assert r["reply"].startswith("Takrorlayman") and "Savdo.xlsx" in r["reply"]
    done(api, r)
    assert api.commands[-1] == "Buyruq: Savdo.xlsx"


# ---------------- AI tool-calling planner (fake provider) ----------------


def test_ai_planner_runs_tool_calls_in_order(env):
    api, work = env, env.work
    api.router.save_key("anthropic", "sk-ant-test-1234567890")
    api.router.settings.update({"ai": {"enabled": True}})  # AI is switched on by the user
    arxiv = work / "Arxiv"
    api.fake.replies = ['{"kind": "chat"}', "Salom!"]
    api.chat("salom")  # an earlier turn the planner must see
    plan = {"kind": "tools", "say": "Excel fayllarni arxivlayman", "calls": [
        {"tool": "files.search", "args": {"folder": str(work), "ext": "xlsx"}},
        {"tool": "files.copy", "args": {"paths": ["topilgan fayllar"], "folder": str(arxiv)}},
        {"tool": "files.zip", "args": {"paths": [str(arxiv)], "invented": "x"}},
    ]}  # fmt: skip
    api.fake.replies = [json.dumps(plan)]
    r = api.chat("ish papkamdagi hamma excellarni arxivga olib qo‘y")
    assert r["reply"].startswith("Tushundim: Excel fayllarni arxivlayman"), r
    assert r["confirm"] and "to‘g‘rimi" in r["reply"] and not arxiv.exists()  # asks first
    snap = done(api, api.confirm_ai(r["confirm"]))
    assert snap["status"] == "succeeded" and len(list(arxiv.glob("*.xlsx"))) == 3
    assert list(work.glob("Arxiv*.zip"))
    sent = api.fake.calls[-1]
    assert "files.copy(" in sent["system"] and "workflow.create(" in sent["system"]
    assert "Hisobot.xlsx" in sent["system"]  # context: the current file
    assert "salom" in sent["messages"][0]["content"]  # earlier turns
    assert "sk-ant-test" not in json.dumps(api.fake.calls)  # the key is never in a prompt


def test_ai_planner_risky_and_unknown_tools(env):
    api, work = env, env.work
    api.router.save_key("anthropic", "sk-ant-test-1234567890")
    api.router.settings.update({"ai": {"enabled": True}})  # AI is switched on by the user
    api.fake.replies = [json.dumps({"kind": "tools", "calls": [
        {"tool": "files.recycle", "args": {"paths": [str(work / "Oylik.xlsx")]}}]})]  # fmt: skip
    r = api.chat("eski oylik faylidan qutulaylik")
    assert r["confirm"] and (work / "Oylik.xlsx").is_file()
    api.fake.replies = [json.dumps({"kind": "tools", "calls": [
        {"tool": "files.search", "args": {"folder": str(work), "ext": "xlsx"}}]})]  # fmt: skip
    r = api.chat("qanaqa excel fayllarim bor")
    assert "confirm" not in r and len(r["files"]) == 3  # a pure lookup runs at once
    api.fake.replies = [json.dumps({"kind": "tools", "calls": [{"tool": "os.format_disk"}]})]
    assert "Noma’lum amal" in api.chat("kompyuterimni tezlashtir")["reply"]
    api.fake.replies = ['{"kind": "command", "command": "Savdo.xlsx ni och va saqla"}']
    r = api.chat("menga savdo bo‘yicha yordam ber")  # the older one-command format still works
    assert "Tushundim" in r["reply"] and r.get("task")


# ---------------- Memory ↔ Teach ↔ Office ----------------


def test_memory_alias_teach_rule_and_office(env):
    api, work = env, env.work
    r = api.chat(f"Eslab qol: hisobot papkam {work}")
    api.confirm_ai(r["confirm"])
    r = api.chat("hisobot papkamdagi barcha fayllarni PDF qil")  # alias → folder → Files
    assert "3 ta fayl" in r["reply"] or r.get("task"), r
    r = api.chat(f"Eslab qol: oylik hisobotim {work / 'Oylik.xlsx'}")
    api.confirm_ai(r["confirm"])
    r = api.chat("Har doim Excel raqamlarini markazga joyla")
    api.confirm_ai(r["confirm"])
    r = api.chat("oylik hisobotimni och va saqla")  # alias → file → Office + Teach rule
    assert "Oylik.xlsx" in r["reply"] and "O‘rgatilgan qoidalar" in r["reply"], r
    api._context_file = str(work / "Savdo.xlsx")
    r = api.chat("Shu faylni eslab qol: savdo jadvali")
    assert str(work / "Savdo.xlsx") in r["reply"]
    api.confirm_ai(r["confirm"])
    assert any(str(work / "Savdo.xlsx") in f["text"] for f in api.memory_facts())


def test_planner_gets_rules_and_facts(env):
    api = env
    api.router.save_key("anthropic", "sk-ant-test-1234567890")
    api.router.settings.update({"ai": {"enabled": True}})  # AI is switched on by the user
    api.memory_add_fact("maktabim 21-maktab")
    r = api.chat("Har doim Excel raqamlarini markazga joyla")
    api.confirm_ai(r["confirm"])
    api.fake.replies = ['{"kind": "chat"}', "Albatta!"]
    api.chat("21-maktab uchun nima qila olasan")
    system = api.fake.calls[0]["system"]
    assert "markazga" in system and "21-maktab" in system
