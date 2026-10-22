"""AI-first chat routing. All providers here are in-memory fakes: no paid call is possible."""

from __future__ import annotations

import json
import time
from pathlib import Path

import openpyxl
import pytest

from nexvara import photodoc
from nexvara.agent import tools
from nexvara.ai.keys import MemoryKeyStore
from nexvara.ai.providers import AiError, Provider, Reply
from nexvara.ai.router import AiRouter, Ledger
from nexvara.appdata import Settings


class FakeProvider(Provider):
    def __init__(self, replies=(), error: Exception | None = None):
        self.replies = list(replies)
        self.error = error
        self.calls: list[dict] = []

    def complete(self, model, system, messages, max_tokens, effort="medium"):
        self.calls.append({"system": system, "messages": messages, "model": model})
        if self.error:
            raise self.error
        text = self.replies.pop(0) if self.replies else '{"kind":"chat"}'
        return Reply(text, model, 100, 20)

    def list_models(self):
        return ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]


def _api(tmp_path: Path, replies=(), error: Exception | None = None, enabled: bool = True):
    from nexvara.app.api import Api

    fake = FakeProvider(replies, error)
    router = AiRouter(
        Settings(tmp_path / "settings.json"),
        MemoryKeyStore({"anthropic": "sk-ant-fake-only"}),
        Ledger(tmp_path / "usage.db"),
        factory=lambda _name, _key: fake,
    )
    router.settings.update({"ai": {"enabled": enabled, "ai_first": True, "confirm_over_usd": 1.0}})
    api = Api(
        overrides={
            "ai_router": router,
            "open_app": lambda app: f"{app} ochildi",
            "ocr": lambda _p, _lang: "Sana | Summa\n22.10.2026 | 1250",
        }
    )
    return api, fake, router


@pytest.mark.parametrize(
    ("message", "tool_name", "args"),
    [
        ("noutbukimdagi exselni och", "app.open", {"app": "excel"}),
        (
            "qara men hali senga yoz demadim tozala yozganlaringni",
            "files.recycle",
            {"paths": ["@prev"]},
        ),
        (
            "jadvalni chiroyliroq qilib tuz",
            "photo.to_office",
            {"target": "excel", "request": "jadvalni chiroyliroq qilib tuz"},
        ),
        (
            "bugungi sanadagini exselga jadval qilib tushib ber",
            "photo.to_office",
            {"target": "excel", "request": "faqat bugungi sana"},
        ),
        (
            "hozir qilgan ishingni ko‘ryabsanmi",
            "photo.compare_table",
            {"request": "hozirgi natijani tekshir"},
        ),
        (
            "qara jadvalda xatoliklar bor ko‘rgin",
            "photo.compare_table",
            {"request": "xatolarni top"},
        ),
        ("Excel’ni och", "app.open", {"app": "excel"}),
        (
            "Hisobot.xlsx ni och, B ustun bo‘yicha sarala",
            "nexvara.command",
            {"text": "Hisobot.xlsx ni och, B ustun bo‘yicha sarala"},
        ),
        (
            "7-sinf fizika 20 ta test",
            "education.test",
            {"request": "7-sinf fizika 20 ta test"},
        ),
    ],
)
def test_planner_is_first_and_selects_expected_tool(tmp_path, message, tool_name, args):
    plan = {"kind": "tools", "calls": [{"tool": tool_name, "args": args}], "say": "tushundim"}
    api, fake, _router = _api(tmp_path, [json.dumps(plan, ensure_ascii=False)])
    photo = tmp_path / "jadval.jpg"
    photo.write_bytes(b"\xff\xd8 fake")
    result = tmp_path / "jadval_NEXVARA.xlsx"
    photodoc.write_excel([["Sana", "Summa"], ["22.10.2026", "1250"]], result)
    api.set_context_file(str(photo))
    api._ctx.result = str(result)

    out = api.chat(message)

    assert fake.calls, message
    assert tool_name in fake.calls[0]["system"]
    assert fake.calls[0]["messages"][0]["content"].rstrip().endswith(message)
    if tool_name == "photo.compare_table":
        assert out.get("confirm") and api._pending[out["confirm"]][0] == "compare_table"
    elif tool_name in tools.CREATES_NEW:  # makes something new: runs without «Ha» for the plan
        assert not (out.get("confirm") and api._pending[out["confirm"]][0] == "tools"), out
    else:
        assert out.get("confirm")
        kind, calls = api._pending[out["confirm"]]
        assert kind == "tools" and calls[0].tool == tool_name


def test_small_talk_also_goes_to_planner_first(tmp_path):
    api, fake, _router = _api(tmp_path, ['{"kind":"chat"}', "Salom, ishlaringiz yaxshimi?"])
    out = api.chat("salom")
    assert out["reply"].startswith("Salom")
    assert len(fake.calls) == 2
    assert "ASBOBLAR" in fake.calls[0]["system"]


def test_ai_disabled_keeps_old_handler_silently(tmp_path):
    """AI switched off by the owner: the old chain, no «AI hozir ishlamayapti» line."""
    api, fake, _router = _api(tmp_path, enabled=False)
    out = api.chat("Excel’ni och")
    assert out["reply"] == "Excel ochildi."
    assert fake.calls == [] and "ai_fallback" not in out


@pytest.mark.parametrize(
    "error",
    [
        AiError("Provayder serveri hozir band (503).", retryable=True),
        AiError("Gemini bepul chegarasi tugadi.", retryable=True),
    ],
)
def test_provider_failure_falls_back_to_old_chain(tmp_path, error):
    api, fake, _router = _api(tmp_path, error=error)
    out = api.chat("Excel’ni och")
    assert fake.calls and "Excel" in out["reply"]
    assert out["reply"].endswith("AI hozir ishlamayapti, oddiy rejimda bajardim")


def test_ai_table_json_builds_typed_office_free_workbook(tmp_path):
    raw = json.dumps(
        {
            "title": "Bugungi savdo",
            "rows": [
                ["Sana", "Mahsulot", "Summa", ""],
                ["2026-10-22", "Daftar", 1250.5, ""],
                ["", "", "", ""],
            ],
            "merges": ["A2:A3", "noto‘g‘ri"],
            "formulas": {"C3": "=SUM(C2:C2)", "bad": "=1"},
        },
        ensure_ascii=False,
    )
    data = photodoc.parse_ai_table(raw)
    assert data.title == "Bugungi savdo"
    assert data.rows[1][2] == 1250.5
    assert data.rows[1][0].isoformat() == "2026-10-22"
    assert len(data.rows[0]) == 3 and data.merges == ["A2:A3"]
    assert data.formulas == {"C3": "=SUM(C2:C2)"}

    out = photodoc.write_excel(data.rows, tmp_path / "ai.xlsx", data.title, data.merges)
    ws = openpyxl.load_workbook(out).active
    assert ws["A1"].font.bold and ws.freeze_panes == "A2"
    assert ws["A2"].value.date().isoformat() == "2026-10-22"
    assert ws["C2"].value == 1250.5 and ws["C2"].number_format == "#,##0.00"
    assert list(ws.merged_cells.ranges)[0].coord == "A2:A3"


def test_unclear_plan_after_yes_falls_back_to_old_chain(tmp_path):
    """Live-like: the plan's price was confirmed with «Ha», then the AI did not answer with a
    plan — the old chain handles the message instead of «AI javobini tushunib bo‘lmadi»."""
    api, fake, router = _api(tmp_path)
    router.settings.update({"ai": {"confirm_over_usd": 0.0}})
    ask = api.chat("Excel’ni och")
    assert ask.get("confirm")
    fake.replies = ["bu reja emas"]
    out = api.confirm_ai(ask["confirm"], True)
    assert out["reply"].startswith("Excel ochildi"), out


def test_ariza_is_written_in_official_layout_without_asking(tmp_path):
    """Live 2026-10-22: «ishdan bo‘shash haqida ariza yozib ber» was plain lines under a Word
    heading, after a «Davom etaymi?» full of raw tool arguments."""
    plan = {
        "kind": "tools",
        "say": "Arizani tayyorlayman.",
        "calls": [{"tool": "document.official", "args": {
            "title": "Ariza",
            "kimga": "[Tashkilot] rahbari [F.I.Sh.]ga",
            "kimdan": "[lavozim] [F.I.Sh.]dan",
            "body": "Meni [sana]dan o‘z xohishimga ko‘ra egallab turgan lavozimimdan ozod "
                    "etishingizni so‘rayman.",
        }}],
    }  # fmt: skip
    api, fake, _router = _api(tmp_path, [json.dumps(plan)])
    written = {}

    def doc(task, name, blocks, out):
        written.update(name=name, blocks=blocks)
        return {"path": str(out)}

    api._overrides["doctemplate"] = doc
    out = api.chat("menga ishdan bo‘shash haqida ariza yozib ber")
    assert not out.get("confirm") and "rasmiy" in out["reply"], out
    api._runner.get(out["task"]["id"]).wait(10)
    kinds = [k for k, _t in written["blocks"]]
    assert kinds == ["right", "right", "title", "body", "sign"]
    assert written["blocks"][2][1] == "ARIZA" and "\t" in written["blocks"][-1][1]


def test_question_about_a_document_with_fish_is_answered(tmp_path):
    """Live 2026-10-22: «F.I.Sh.: [Ism-familiyangiz]» in the history blocked every later
    question («So‘rov yuborilmadi»). Now the unsure part is hidden and the question goes."""
    api, fake, _router = _api(tmp_path, ['{"kind": "chat"}', "Ha, rasmiy ariza shunday yoziladi."])
    api._ctx.add_turn("nexvara", "ARIZA\nMeni ozod etishingizni so‘rayman.\nF.I.Sh.: [Ism]")
    out = api.chat("rasmiy hujjatlar shunday yoziladimi")
    assert out["reply"].startswith("Ha, rasmiy ariza"), out


def _docx(path: Path, lines: list[str]) -> None:
    import zipfile

    body = "".join(f"<w:p><w:r><w:t>{x}</w:t></w:r></w:p>" for x in lines)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{body}</w:body></w:document>")


def test_made_document_is_checked_and_fixed(tmp_path):
    """«Bajar → tekshir → tuzat»: the AI reads the finished ariza back, finds a mistake and a
    corrected new file is made; the second file is checked again and passes."""

    def plan(body):
        return json.dumps(
            {
                "kind": "tools",
                "calls": [
                    {
                        "tool": "document.official",
                        "args": {
                            "title": "Ariza",
                            "kimga": "Direktorga",
                            "kimdan": "O‘qituvchidan",
                            "body": body,
                        },
                    }
                ],
            }
        )

    api, fake, _router = _api(tmp_path, [
        plan("Meni ishdan ozod qilishingizni so‘rayman."),
        json.dumps({"ok": False, "problems": ["Qaysi sanadan ekani yozilmagan"],
                    "fixed_request": "Ariza: 1-noyabrdan ozod etish"}),
        plan("Meni 2026-yil 1-noyabrdan ishdan ozod etishingizni so‘rayman."),
        json.dumps({"ok": True, "problems": [], "fixed_request": ""}),
    ])  # fmt: skip
    made = []

    def doc(task, name, blocks, out):
        _docx(out.with_name(f"ariza{len(made)}.docx"), [t for _k, t in blocks])
        made.append(blocks)
        return {"path": str(out.with_name(f"ariza{len(made) - 1}.docx"))}

    api._overrides["doctemplate"] = doc
    out = api.chat("1-noyabrdan ishdan bo‘shash haqida ariza yoz")
    assert out.get("task"), out
    replies = []
    for _ in range(200):
        replies += [e["reply"]["reply"] for e in api.ui_events() if e["kind"] == "nexvara_reply"]
        if any(r.startswith("✔ Tekshirdim") for r in replies):
            break
        time.sleep(0.05)
    assert any("kamchilik topildi" in r and "Tuzatyapman" in r for r in replies), replies
    assert any(r.startswith("✔ Tekshirdim") for r in replies), replies
    assert len(made) == 2 and "1-noyabrdan" in made[1][3][1]
    checked = [c for c in fake.calls if "sifat nazoratchisi" in c["system"]]
    assert len(checked) == 2 and "Meni ishdan ozod" in checked[0]["messages"][0]["content"]


def test_document_text_reads_word_excel_powerpoint(tmp_path):
    from nexvara.ai import verify

    _docx(tmp_path / "a.docx", ["ARIZA", "so‘rayman"])
    assert "ARIZA\nso‘rayman" in verify.document_text(tmp_path / "a.docx")
    photodoc.write_excel([["Sana", "Summa"], ["22.10.2026", "1250"]], tmp_path / "b.xlsx")
    assert "Sana | Summa" in verify.document_text(tmp_path / "b.xlsx")
    assert verify.outputs({"path": "x.docx", "pdf": "x.pdf"}) == ["x.docx"]
