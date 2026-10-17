"""Every one of the 12 sections, driven by a natural-language chat message.

Opening a page is not enough: each case types a sentence into Api.chat and checks the real
effect (a task started, a store changed, a setting saved). Office and paid AI are replaced
by fakes; docs/SECTIONS_STATUS.md lists what is still button-only.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore
    from nexvara.remote import DeviceStore
    from nexvara.workflows import WorkflowStore

    db = tmp_path / "app.db"
    xlsx = tmp_path / "Hisobot.xlsx"
    xlsx.write_bytes(b"PK")
    runs = []
    a = Api(TaskRunner(), overrides={
        "memory": MemoryStore(db), "workflow_store": WorkflowStore(db),
        "device_store": DeviceStore(db), "remote_port": 0, "remote_tls": False,
        "command": lambda t: runs.append(t.title) or {"path": str(xlsx)},
    })  # fmt: skip
    a.runs, a.xlsx = runs, xlsx
    yield a
    a.devices_stop()


def finish(api, reply):
    assert "task" in reply and reply["task"], reply
    assert api._runner.get(reply["task"]["id"]).wait(10)
    return api._runner.get(reply["task"]["id"]).snapshot()


def test_office_agent(api):
    r = api.chat(f"{api.xlsx} ni och, A ustun bo‘yicha saralab saqla")
    assert finish(api, r)["status"] == "succeeded" and api.runs


def test_ai_chat_without_key_is_explicit(api):
    r = api.chat("bugun ob-havo qanday")
    assert "API kalit" in r["reply"] and "task" not in r


def test_teach(api):
    r = api.chat("Har doim Excel raqamlarini markazga joyla")
    api.confirm_ai(r["confirm"])
    assert api.teach_rules()[0]["app"] == "excel"


def test_memory_save_and_recall(api):
    r = api.chat("Eslab qol: maktabimiz 21-maktab")
    api.confirm_ai(r["confirm"])
    assert "21-maktab" in api.chat("nimalarni eslab qolgansan?")["reply"]
    assert "21-maktab" in api.chat("xotiradan maktab haqida top")["reply"]


def test_workflows(api):
    step = {"kind": "command", "text": f"{api.xlsx} ni och va saqla"}
    saved = api.wf_save({"name": "Kunlik hisobot", "steps": [step]})
    assert saved["ok"]
    assert "Kunlik hisobot" in api.chat("workflowlarni ko‘rsat")["reply"]
    r = api.chat("«Kunlik hisobot» workflowini ishga tushir")
    assert finish(api, r)["status"] == "succeeded"
    assert "Qaysi workflow" in api.chat("Yo‘q nomli workflowni boshla")["reply"]


def test_history(api):
    finish(api, api.chat(f"{api.xlsx} ni och va saqla"))
    r = api.chat("oxirgi vazifalarni ko‘rsat")
    assert "Oxirgi vazifalar" in r["reply"] and "✓" in r["reply"]


def test_files(api, monkeypatch):
    from nexvara import fileagent

    seen = []
    monkeypatch.setattr(fileagent, "search", lambda q, limit=10: seen.append(q) or [])
    r = api.chat("hisobot fayllarini top")
    assert seen == ["hisobot"] and "topilmadi" in r["reply"]


def test_bi(api):
    r = api.chat(f"{api.xlsx} dan dashboard yarat")
    assert r["open_bi"] == str(api.xlsx)


def test_devices(api):
    r = api.chat("telefon ulanishini yoq")
    assert api.devices_status()["running"] and "Kod:" in r["reply"]
    assert "yoqilgan" in api.chat("telefon ulanganmi")["reply"]
    api.chat("telefon ulanishini o‘chir")
    assert not api.devices_status()["running"]


def test_settings_theme(api):
    r = api.chat("yorug‘ mavzuga o‘t")
    assert r["theme"] == "light" and api.get_settings()["theme"] == "light"
    api.chat("qorong‘i mavzu")
    assert api.get_settings()["theme"] == "dark"


def test_section_patterns_do_not_steal_other_commands(api):
    # A file command mentioning "oxirgi" or a test about a "mavzu" stays what it was.
    r = api.chat(f"oxirgi {api.xlsx} ni och va saqla")
    assert "task" in r
    assert api._chat_sections("7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber") is None
    assert api._chat_sections("Eslab qol: telefon raqamim 90") is None
