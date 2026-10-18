"""Office rules from official sources reach the AI when the request is about an office document,
and «tekshir» is understood for Excel, Word and PowerPoint files."""

from __future__ import annotations

from nexvara.agent.parse import parse_command
from nexvara.ai import features
from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import Provider, Reply
from nexvara.ai.router import AiRouter, Ledger
from nexvara.appdata import Settings
from nexvara.knowledge import office_guide


class Spy(Provider):
    def __init__(self):
        self.systems = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.systems.append(system)
        return Reply("Tayyor", model, 100, 20)

    def list_models(self):
        return []


def _router(tmp_path):
    spy = Spy()
    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore({"openai": "sk-test-openai-123456"}),
                 Ledger(tmp_path / "l.db"), factory=lambda n, k: spy)  # fmt: skip
    r.settings.update({"ai": {"enabled": True}})
    return r, spy


def test_document_requests_carry_the_official_rules(tmp_path):
    r, spy = _router(tmp_path)
    features.chat_reply(r, "Direktor nomiga ta’til haqida ariza yoz")
    assert "VM 140" in spy.systems[-1] and "Times New Roman 14" in spy.systems[-1]
    features.chat_reply(r, "Taqdimot uchun 5 ta slayd rejasini tuz")
    assert "18 pt" in spy.systems[-1] and "VM 140" not in spy.systems[-1]
    features.chat_reply(r, "Salom, qalaysan?")
    assert "Rasmiy qoidalar" not in spy.systems[-1]


def test_rules_name_their_sources():
    assert set(office_guide.RULES) == {"excel", "word", "powerpoint"}
    assert all(u.startswith("https://") for u in office_guide.SOURCES.values())
    assert office_guide.apps_in("Hisobot.xlsx jadvalini tuzat") == ["excel", "word"]


def test_check_commands():
    for ctx, text in (("D:/a.xlsx", "jadvalni tekshir"), ("D:/a.docx", "hujjatni tekshir"),
                      ("D:/a.pptx", "slaydlarni tekshir")):  # fmt: skip
        assert [a.kind for a in parse_command(text, ctx).actions] == ["check"]
    assert [a.kind for a in parse_command("imlo xatolarini tekshir", "D:/a.docx").actions] == [
        "spelling"
    ]
