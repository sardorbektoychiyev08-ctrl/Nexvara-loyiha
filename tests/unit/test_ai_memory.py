"""A month of chat memory for the AI, «… ni unut», and self-repair of failed commands
(fake provider: nothing is sent anywhere, nothing is paid)."""

from __future__ import annotations

import json
import time

import pytest

from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import Provider, Reply
from nexvara.ai.router import AiRouter, Ledger
from nexvara.appdata import Settings
from nexvara.memory.store import MemoryStore


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

    fake = FakeProvider()
    router = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore(), Ledger(tmp_path / "l.db"),
                      factory=lambda name, key: fake)  # fmt: skip
    router.save_key("anthropic", "sk-ant-test-1234567890")
    router.settings.update({"ai": {"enabled": True}})
    mem = MemoryStore(tmp_path / "app.db")
    work = tmp_path / "Ish"
    work.mkdir()
    api = Api(TaskRunner(), overrides={"memory": mem, "ai_router": router})
    api.fake, api.mem, api.work, api.router = fake, mem, work, router
    return api


def _age(mem, days):
    """Make every logged line `days` older."""
    with mem._db() as db:
        db.execute("UPDATE chat_log SET ts = ts - ?", (days * 86400,))


def test_store_recent_recall_summaries_and_forget(tmp_path):
    mem = MemoryStore(tmp_path / "app.db")
    mem.log_chat("user", "Savdo hisobotini qanday tuzaman?")
    mem.log_chat("nexvara", "Savdo.xlsx ni oching va jami qo‘shing.")
    _age(mem, 10)
    mem.log_chat("user", "Juda eski gap: arxiv")
    _age(mem, 40)  # this one and the first pair are now 40–50 days old
    mem.log_chat("user", "Fizika darsi qachon?")
    mem.log_chat("nexvara", "Ertaga 2-dars.")
    for i in range(20):
        mem.log_chat("user", f"oddiy xabar {i}")
    assert len(mem.recent_turns(15)) == 15
    assert mem.recent_turns(15)[-1]["text"] == "oddiy xabar 19"
    # older than 30 days is not recalled; within 60 days it is
    assert mem.recall("savdo hisoboti", days=30) == []
    got = mem.recall("savdo hisoboti", days=60)
    assert got and got[0]["user"].startswith("Savdo") and "jami" in got[0]["nexvara"]
    assert mem.recall("fizika darsi", days=30)  # 22 lines ago: outside the recent window
    summ = mem.day_summaries(days=60)
    assert any("Savdo hisobotini" in s for s in summ)
    assert mem.forget_chat("savdo hisoboti") == 1
    assert mem.forget_chat("savdo") == 1  # the answer that mentioned it
    assert mem.recall("savdo", days=60) == []


def test_ai_chat_gets_recent_and_month_old_conversation(env):
    api, mem = env, env.mem
    mem.log_chat("user", "Mening maktabim 5-maktab, hisobotni har juma topshiraman")
    mem.log_chat("nexvara", "Yaxshi, eslab turaman.")
    _age(mem, 12)
    api.fake.replies = ['{"kind": "chat"}', "Salom!"]
    api.chat("salom")
    api.fake.replies = ['{"kind": "chat"}', "Juma kuni."]
    api.chat("hisobotni qachon topshiraman?")
    sent = api.fake.calls[-1]["messages"][0]["content"]
    assert "Oxirgi suhbat" in sent and "salom" in sent.lower()  # the recent turn
    assert "har juma topshiraman" in sent  # the matching exchange from 12 days ago
    assert sent.rstrip().endswith("Yangi xabar: hisobotni qachon topshiraman?")
    # the planner sees them too
    planner = api.fake.calls[-2]["messages"][0]["content"]
    assert "har juma" in planner


def test_restart_keeps_the_conversation(env, tmp_path):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner

    api = env
    api.fake.replies = ['{"kind": "chat"}', "Bu 7-sinf fizikasi."]
    api.chat("7-sinf fizika darsligi haqida gaplashaylik")
    again = Api(TaskRunner(), overrides={"memory": api.mem, "ai_router": api.router})
    api.fake.replies = ['{"kind": "chat"}', "Ha."]
    again.chat("uni qisqaroq tushuntir")
    sent = api.fake.calls[-1]["messages"][0]["content"]
    assert "7-sinf fizika darsligi" in sent  # «uni» can be understood after a restart


def test_forget_in_chat(env):
    api, mem = env, env.mem
    mem.log_chat("user", "Nilufarning telefon raqami haqida")
    mem.log_chat("nexvara", "Yaxshi.")
    r = api.chat("Nilufarning telefon raqami haqidagi gaplarni unut")
    assert r["reply"].startswith("Unutdim") and "2 ta" in r["reply"], r  # with this message
    assert not mem.search("telefon raqami")
    api.fake.replies = ['{"kind": "chat"}', "Salom"]
    api.chat("salom")
    r = api.chat("buni unut")
    assert r["reply"].startswith("Unutdim")
    assert "unutma" not in r["reply"]
    assert "Xotira" in api.chat("hamma suhbatni unut")["reply"]  # never wiped from chat


def test_self_repair_replans_with_the_error(env):
    api, work = env, env.work
    (work / "Hisobot.xlsx").write_bytes(b"PK")
    bad = {
        "kind": "tools",
        "calls": [{"tool": "files.search", "args": {"folder": str(work / "Yoq")}}],
    }
    good = {
        "kind": "tools",
        "say": "papka nomini tuzatdim",
        "calls": [{"tool": "files.search", "args": {"folder": str(work), "ext": "xlsx"}}],
    }
    api.fake.replies = [json.dumps(bad), json.dumps(good)]
    r = api.chat("ish papkamdagi excellarni ko‘rsat")
    assert r.get("repaired") == 1, r
    assert "🔧" in r["reply"] and len(r["files"]) == 1
    repair_prompt = api.fake.calls[-1]
    assert "Oldingi urinish bajarilmadi" in repair_prompt["messages"][0]["content"]
    assert "tuzatilgan reja" in repair_prompt["system"]


def test_self_repair_stops_after_two_tries_and_can_be_switched_off(env):
    api = env
    bad = json.dumps({"kind": "tools", "calls": [{"tool": "os.format_disk"}]})
    api.fake.replies = [bad, bad, bad]
    r = api.chat("kompyuterimni tezlashtir")
    assert "2 marta" in r["reply"] and r.get("error"), r
    assert len(api.fake.calls) == 3  # the plan + 2 repairs, nothing more
    api.router.settings.update({"ai": {"self_repair": False}})
    api.fake.calls.clear()
    api.fake.replies = [bad]
    r = api.chat("kompyuterimni tezlashtir")
    assert "Noma’lum amal" in r["reply"] and len(api.fake.calls) == 1


def test_failed_office_task_is_repaired_in_the_background(env):
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner, UserError

    api = env
    work = api.work
    (work / "Savdo.xlsx").write_bytes(b"PK")
    tries = []

    def office(task):
        tries.append(task.title)
        if len(tries) == 1:
            raise UserError("«Narx» ustuni topilmadi. Ustunlar: Hudud, Summa")
        return {"path": str(work / "Savdo.xlsx")}

    api = Api(TaskRunner(), overrides={"memory": api.mem, "ai_router": api.router,
                                       "command": office})  # fmt: skip
    api.fake = env.fake
    api.fake.replies = [
        json.dumps(
            {
                "kind": "tools",
                "say": "Summa ustuni bo‘yicha",
                "calls": [
                    {
                        "tool": "nexvara.command",
                        "args": {
                            "text": f"{work / 'Savdo.xlsx'} ni och, Summa bo‘yicha saralab saqla"
                        },
                    }
                ],
            }
        )
    ]
    r = api.chat(f"{work / 'Savdo.xlsx'} ni och, Narx bo‘yicha saralab saqla")
    api._runner.get(r["task"]["id"]).wait(10)
    for _ in range(100):
        ev = [e for e in api.ui_events() if e["kind"] == "nexvara_reply"]
        if ev:
            break
        time.sleep(0.05)
    assert ev, "no repair reply"
    reply = ev[0]["reply"]
    assert "Narx" in reply["reply"] and "🔧" in reply["reply"]
    assert reply.get("confirm")  # the corrected command changes a file: «Ha» first
    assert "Oldingi urinish bajarilmadi" in api.fake.calls[-1]["messages"][0]["content"]
