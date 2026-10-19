"""Files, NEXVARA BI, Workflows and Settings driven only by Uzbek chat messages.

Real files in a temp folder; Office, the Recycle Bin and paid AI are replaced by fakes.
Each case checks the effect on disk / in the stores, not just the reply text.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pytest

SALES_CSV = """Sana;Filial;Mahsulot;Daromad;Xarajat
05.01.2026;Toshkent;Daftar;1 200 000;700 000
20.01.2026;Samarqand;Ruchka;800 000;500 000
03.02.2026;Toshkent;Ruchka;1 500 000;800 000
01.03.2026;Buxoro;Kitob;2 000 000;900 000
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore
    from nexvara.workflows import WorkflowStore

    work = tmp_path / "Ish"
    work.mkdir()
    (work / "Hisobot.xlsx").write_bytes(b"PK excel")
    (work / "Xat.docx").write_bytes(b"PK word")
    (work / "savdo.csv").write_text(SALES_CSV, encoding="utf-8")
    db = tmp_path / "app.db"
    pdfs = []

    def fake_pdf(task):
        pdfs.append(task.title)
        return {"path": str(work / "Hisobot.pdf")}

    api = Api(TaskRunner(), overrides={
        "memory": MemoryStore(db), "workflow_store": WorkflowStore(db),
        "command": lambda t: {"path": str(work / "Hisobot.xlsx")},
        "files_to_pdf": fake_pdf,
    })  # fmt: skip
    api._context_file = str(work / "Hisobot.xlsx")
    return api, work, pdfs


def wait(api, reply):
    assert reply.get("task"), reply
    t = api._runner.get(reply["task"]["id"])
    assert t.wait(15)
    return t.snapshot()


# ---------------- Files ----------------


def test_files_copy_move_rename(env):
    api, work, _ = env
    arxiv = work / "Arxiv"
    r = api.chat(f"Hisobot.xlsx ni {arxiv} papkasiga nusxala")
    assert (arxiv / "Hisobot.xlsx").is_file() and (work / "Hisobot.xlsx").is_file(), r
    r = api.chat(f"Hisobot.xlsx ni {arxiv} ga nusxala")  # never overwrites
    assert len(list(arxiv.glob("Hisobot*.xlsx"))) == 2 and "ustiga yozilmadi" in r["reply"]
    api.chat(f"Xat.docx ni {arxiv} ga ko‘chir")
    assert (arxiv / "Xat.docx").is_file() and not (work / "Xat.docx").exists()
    r = api.chat("uni «Rasmiy xat» deb nomla")
    assert (arxiv / "Rasmiy xat.docx").is_file(), r


def test_files_zip_unzip_backup_restore(env):
    api, work, _ = env
    r = api.chat(f"{work / 'Hisobot.xlsx'} va {work / 'savdo.csv'} ni zip qil")
    z = Path(r["files"][0])
    assert zipfile.ZipFile(z).namelist() and z.suffix == ".zip"
    r = api.chat(f"{z} ni zipdan chiqar")
    assert "Chiqarildi" in r["reply"]
    api.chat("Hisobot.xlsx ning zaxira nusxasini ol")
    (work / "Hisobot.xlsx").write_bytes(b"PK buzildi")
    assert "1." in api.chat("Hisobot.xlsx versiyalarini ko‘rsat")["reply"]
    r = api.chat("Hisobot.xlsx ni zaxiradan tikla")
    assert r["confirm"] and (work / "Hisobot.xlsx").read_bytes() == b"PK buzildi"
    api.confirm_ai(r["confirm"])
    assert (work / "Hisobot.xlsx").read_bytes() == b"PK excel"


def test_files_tidy_and_recycle_need_confirmation(env, monkeypatch):
    api, work, _ = env
    from nexvara import fileagent

    r = api.chat(f"{work} papkasini turlarga ajratib tartibla")
    assert r["confirm"] and (work / "Hisobot.xlsx").is_file()
    api.confirm_ai(r["confirm"], yes=False)
    assert (work / "Hisobot.xlsx").is_file()  # "Yo‘q" = nothing moved
    r = api.chat(f"{work} papkasini turlarga ajratib tartibla")
    api.confirm_ai(r["confirm"])
    assert not (work / "Hisobot.xlsx").exists() and list(work.glob("*/Hisobot.xlsx"))
    gone = []
    monkeypatch.setattr(fileagent, "recycle", lambda paths: gone.extend(paths) or len(paths))
    target = next(work.glob("*/savdo.csv"))
    r = api.chat(f"{target} ni o‘chir")
    assert r["confirm"] and not gone
    assert "Savatga" in api.confirm_ai(r["confirm"])["reply"] and gone == [str(target)]


def test_files_search_folder_ext_then_pdf_found(env):
    api, work, pdfs = env
    r = api.chat(f"{work} papkasidan word fayllarini top")
    assert r["files"] == [str(work / "Xat.docx")]
    r = api.chat("topilgan fayllarni PDF qil")
    wait(api, r)
    assert pdfs and "1 ta fayl" in r["reply"]
    r = api.chat(f"{work} papkasidagi barcha fayllarni PDF qil")
    assert "2 ta fayl" in r["reply"]  # Hisobot.xlsx + Xat.docx (csv is not Office)


def test_files_batch_rename_found(env):
    api, work, _ = env
    api.chat(f"{work} papkasidan excel fayllarini top")
    (work / "Ikkinchi.xlsx").write_bytes(b"PK")
    api.chat(f"{work} papkasidan excel fayllarini top")
    r = api.chat("topilgan fayllarni «Oylik_{n}» deb nomla")
    assert "2 ta fayl nomlandi" in r["reply"], r
    assert sorted(p.name for p in work.glob("Oylik_*.xlsx")) == ["Oylik_1.xlsx", "Oylik_2.xlsx"]


# ---------------- NEXVARA BI ----------------


def test_bi_create_list_summary_export_delete(env):
    api, work, _ = env
    r = api.chat(f"{work / 'savdo.csv'} dan dashboard yarat va «Savdo 2026» deb saqla")
    assert r["bi_ui"]["open"] and "saqlandi" in r["reply"]
    assert "Savdo 2026" in api.chat("dashboardlarni ko‘rsat")["reply"]
    s = api.chat("«Savdo 2026» dashboardi ko‘rsatkichlarini ayt")["reply"]
    assert "4 ta qator" in s and "5 500 000" in s  # total revenue
    s = api.chat("«Savdo 2026» dashboard natijasi faqat Toshkent bo‘yicha")["reply"]
    assert "2 ta qator" in s and "Filial = Toshkent" in s
    r = api.chat("«Savdo 2026» dashboardini Excel ga eksport qil")
    assert Path(r["files"][0]).suffix == ".xlsx" and Path(r["files"][0]).is_file()
    r = api.chat("«Savdo 2026» dashboardini PDF qil")
    assert r["bi_ui"]["export"] == "pdf"  # drawn and saved by the page itself
    r = api.chat("«Savdo 2026» dashboardiga Filial bo‘yicha Xarajat doiraviy diagramma qo‘sh")
    assert "qo‘shildi" in r["reply"], r
    cfg = api.bi_open(api.bi_list()[0]["file"])["config"]
    w = cfg["pages"][0]["widgets"][-1]
    assert (w["type"], w["x"], w["y"]) == ("pie", "Filial", "Xarajat")
    assert (
        "ustuni topilmadi"
        in api.chat("«Savdo 2026» dashboardiga Filial bo‘yicha Soliq ustunli diagramma qo‘sh")[
            "reply"
        ]
    )
    r = api.chat("«Savdo 2026» dashboardini o‘chir")
    assert r["confirm"] and api.bi_list()
    api.confirm_ai(r["confirm"])
    assert api.bi_list() == []


# ---------------- Workflows ----------------


def test_workflow_create_run_history_enable_delete(env):
    api, work, _ = env
    r = api.chat(
        "«Kechki hisobot» workflow yarat: Hisobot.xlsx ni och va saqla; 1 soniya kut; "
        "keyin Hisobot.xlsx ni PDF qilib saqla. Har kuni soat 18:30 da"
    )
    wf = api.wf_list()[0]
    assert wf["trigger"] == {"type": "daily", "time": "18:30"}, r
    assert [s["kind"] for s in wf["steps"]] == ["command", "wait", "command"]
    assert "Kechki hisobot" in api.chat("workflowlar ro‘yxatini ko‘rsat")["reply"]
    snap = wait(api, api.chat("«Kechki hisobot» workflowini ishga tushir"))
    assert snap["status"] == "succeeded"
    assert "succeeded" in api.chat("«Kechki hisobot» workflowi tarixini ko‘rsat")["reply"]
    api.chat("«Kechki hisobot» workflowini o‘chirib qo‘y")
    assert api.wf_list()[0]["enabled"] is False
    api.chat("«Kechki hisobot» workflowini yoq")
    assert api.wf_list()[0]["enabled"] is True
    r = api.chat("«Kechki hisobot» workflowini butunlay o‘chir")
    assert r["confirm"]
    api.confirm_ai(r["confirm"])
    assert api.wf_list() == []


def test_workflow_folder_trigger_and_pause_resume_stop(env):
    api, work, _ = env
    inbox = work / "Kirish"
    inbox.mkdir()
    api.chat(f"«Kiruvchi» workflow yarat: {inbox} papkasiga yangi fayl tushganda shu faylni "
             "PDF qilib saqla")  # fmt: skip
    wf = api.wf_list()[0]
    assert wf["trigger"]["type"] == "folder" and "{fayl}" in wf["steps"][0]["text"]
    api.chat("«Sekin» workflow yarat: 30 soniya kut")
    r = api.chat("«Sekin» workflowini ishga tushir")
    time.sleep(0.5)
    assert "pauzada" in api.chat("«Sekin» workflowini pauza qil")["reply"]
    assert "davom" in api.chat("«Sekin» workflowini davom ettir")["reply"]
    api.chat("«Sekin» workflowini to‘xtat")
    assert api._runner.get(r["task"]["id"]).wait(10)
    assert api._runner.get(r["task"]["id"]).snapshot()["status"] == "cancelled"


# ---------------- Settings ----------------


def test_settings_by_chat(env):
    api, work, _ = env
    assert "Savollar soni" in api.chat("sozlamalarni ko‘rsat")["reply"]
    api.chat("savollar soni 25 bo‘lsin")
    api.chat("variantlar 3 ta bo‘lsin")
    api.chat("Office oynasi yopilsin")
    api.chat("kunlik limit 2.5 dollar")
    api.chat("oylik byudjet 20")
    api.chat("0.1 dollardan qimmat so‘rovda so‘ra")
    api.chat("telefon porti 8800")
    api.chat(f"yangilanish papkasi {work}")
    s = api.get_settings()
    assert (s["test_count"], s["test_variants"], s["keep_office_open"]) == (25, 3, False)
    assert (s["ai"]["daily_budget_usd"], s["ai"]["monthly_budget_usd"]) == (2.5, 20.0)
    assert s["ai"]["confirm_over_usd"] == 0.1 and s["remote"]["port"] == 8800
    assert s["update"]["channel"] == str(work)
    assert "kalit" in api.chat("AI ni yoq")["reply"] and not api.get_settings()["ai"]["enabled"]
    assert "60" in api.chat("savollar soni 500 bo‘lsin")["reply"]  # range is checked
    assert "o‘qilmadi" in api.chat("yangilanishni tekshir")["reply"]  # no latest.json there


def test_pasted_api_key_is_refused_and_not_logged(env):
    api, work, _ = env
    r = api.chat("mana kalitim sk-ant-api03-abcdefghijklmnopqrstuv")
    assert "Credential Manager" in r["reply"]
    assert not any("sk-ant" in m["text"] for m in api.memory_chat())


def test_several_excel_files_into_one_book_from_chat(env):
    api, folder = env[0], env[1]
    a, b = folder / "Yanvar.xlsx", folder / "Fevral.xlsx"
    for p in (a, b):
        p.write_bytes(b"xlsx")
    got = []
    api._overrides["excel_combine"] = lambda task: got.append(1) or {"path": str(folder / "Y.xlsx")}
    r = api.chat(f"«{a}» va «{b}» ni bitta faylga varaq qilib yig‘")
    assert "yig‘ilmoqda" in r["reply"] and r.get("task")
    assert api._runner.get(r["task"]["id"]).wait(10) and got == [1]
