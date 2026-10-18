"""Professional Office commands in real Excel / Word / PowerPoint (NEXVARA_RUN_OFFICE=1).
Every file is a temporary test file; originals are checked to stay unchanged."""

import hashlib
import os
from pathlib import Path

import pytest
from tests.office_fixtures import SALES_ROWS, make_sales_xlsx

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Office",
    ),
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(fn, *args, timeout=300, **kw):
    from nexvara.core.task import TaskRunner

    t = TaskRunner().start("cmd", lambda task: fn(task, *args, keep_open=False, pause=0, **kw))
    assert t.wait(timeout), "task did not finish"
    return t


def ok(t):
    snap = t.snapshot()
    assert snap["status"] == "succeeded", (snap["error"], snap["steps"])
    assert all(c["ok"] for c in snap["result"]["checks"]), snap["result"]["checks"]
    return snap["result"]


# ---------------- Excel ----------------
def test_excel_professional_chain(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import ExcelSession

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    before = digest(src)
    plan = parse_command(
        "Savdo.xlsx ni och, tozala, dublikatlarni o‘chir, Narx = Summa / Soni ustunini qo‘sh, "
        "jami qo‘sh, o‘rtacha qatorini qo‘sh, eng katta va eng kichik qiymat qatorlarini qo‘sh, "
        "Summa ustunini pul formatiga o‘tkaz, Summa 1000000 dan katta kataklarni qizil bilan "
        "belgila, Soni ustuniga ma’lumot chiziqlari qo‘sh, Summa bo‘yicha kamayish tartibida "
        "sarala, varaq nomini «Hisobot» qil, ustunlar kengligini moslashtir, albom qilib bir "
        "sahifaga sig‘dir va PDF qilib saqla"
    )
    assert plan.unknown == [], plan.unknown
    res = ok(run(run_excel_plan, plan, src))
    assert digest(src) == before
    out = tmp_path / "Savdo_NEXVARA.xlsx"
    assert (tmp_path / "Savdo_NEXVARA.pdf").is_file()
    rows = [r for i, r in enumerate(SALES_ROWS) if i != 5]  # the exact duplicate is gone
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(out)
        ws = wb.Worksheets(1)
        name = str(ws.Name)
        values = ops.read_range(ws.UsedRange)
        summa_text = str(ws.Cells(2, 4).Text)
        orient = int(ws.PageSetup.Orientation)
        del ws, wb
    assert name == "Hisobot"
    head, body = values[0], values[1:]
    assert head[:5] == ["Hudud", "Mahsulot", "Soni", "Summa", "Narx"]
    data, footer = body[:7], body[7:11]
    assert [r[0] for r in footer] == ["JAMI", "O‘RTACHA", "MAKSIMUM", "MINIMUM"]
    sums = [r[3] for r in data]
    assert sums == sorted(sums, reverse=True)  # footers stayed under the data while sorting
    for r in data:
        assert r[4] == pytest.approx(r[3] / r[2])
    assert footer[0][3] == sum(r[3] for r in rows)
    assert footer[1][3] == pytest.approx(sum(r[3] for r in rows) / 7)
    assert footer[2][2] == max(r[2] for r in rows) and footer[3][2] == min(r[2] for r in rows)
    assert "so‘m" in summa_text and orient == 2
    assert any("ta katak belgilandi" in line for line in res["report"])


def test_excel_highlight_top_and_percent_and_delete(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command
    from nexvara.skills.excel.bridge import ExcelSession

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    plan = parse_command(
        "Savdo.xlsx da eng katta 3 ta Summani yashil bilan belgila, Ulush = Summa / 10000000 "
        "ustunini qo‘sh, Ulush ustunini foiz formatida qil, Mahsulot ustunini o‘chir, shriftni "
        "Arial 12 qil, «Toshkent» ni «Tashkent» ga almashtir va saqla"
    )
    assert plan.unknown == []
    ok(run(run_excel_plan, plan, src))
    with ExcelSession(visible=False) as xl:
        wb = xl.open_workbook(tmp_path / "Savdo_NEXVARA.xlsx")
        ws = wb.Worksheets(1)
        head = [ws.Cells(1, c).Value for c in range(1, 5)]
        pct = str(ws.Cells(2, 4).Text)
        names = {ws.Cells(r, 1).Value for r in range(2, 10)}
        font = str(ws.Cells(2, 1).Font.Name)
        del ws, wb
    assert head == ["Hudud", "Soni", "Summa", "Ulush"]
    assert pct.endswith("%") and font == "Arial"
    assert "Tashkent" in names and "Toshkent" not in names


def test_excel_clear_errors(tmp_path):
    from nexvara.agent.excel_exec import run_excel_plan
    from nexvara.agent.parse import parse_command

    src = make_sales_xlsx(tmp_path / "Savdo.xlsx")
    t = run(run_excel_plan, parse_command("Savdo.xlsx da Hudud ustunini pul formatiga o‘tkaz"), src)
    assert t.snapshot()["status"] == "failed" and "raqamli ustun emas" in t.error
    t = run(run_excel_plan, parse_command("Savdo.xlsx da Narx = Summa / Vazn ustunini qo‘sh"), src)
    assert t.snapshot()["status"] == "failed" and "«Vazn»" in t.error


# ---------------- Word ----------------
def make_messy_docx(path: Path) -> Path:
    from nexvara.skills.word import ops
    from nexvara.skills.word.ops import WordSession

    with WordSession(visible=False) as w:
        doc = w.new_document()
        ops.add_paragraph(doc, "Yillik  hisobot")
        ops.add_heading(doc, "Kirish", 1)
        ops.add_paragraph(doc, "Bu   hujjatda  ortiqcha bo‘sh joylar bor , va xatolar .")
        ops.add_paragraph(doc, "")
        ops.add_paragraph(doc, "")
        ops.add_heading(doc, "Natijalar", 1)
        ops.add_table(doc, [["Sinf", "O‘quvchi"], ["7-A", "28"], ["7-B", "31"]])
        ops.add_paragraph(doc, "Xulosa: reja bajarildi.")
        w.save_as(doc, path)
        w.disown(doc)
        doc.Close(0)
        del doc
    return path


def test_word_professional_chain(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.word_exec import run_word_plan
    from nexvara.skills.word.ops import WordSession

    src = make_messy_docx(tmp_path / "hisobot.docx")
    before = digest(src)
    plan = parse_command(
        "hisobot.docx ni och, ortiqcha bo‘sh joylarni tozala, birinchi qatorni sarlavha qil, "
        "matnni kenglik bo‘yicha tekisla, sarlavhalarni markazga tekisla, yuqori kolontitulga "
        "«5-maktab» yoz, sahifa raqamlarini qo‘y, pastki kolontitulga «Toshkent 2026» yoz, "
        "sahifani albom qil, chap chetini 3 sm, o‘ng chetini 1,5 sm qil, jadvallarni formatla, "
        "so‘zlarni sana va PDF qilib saqla"
    )
    assert plan.unknown == [], plan.unknown
    res = ok(run(run_word_plan, plan, src))
    assert digest(src) == before and (tmp_path / "hisobot_NEXVARA.pdf").is_file()
    assert any("so‘z" in line and "sahifa" in line for line in res["report"])
    with WordSession(visible=False) as w:
        doc = w.open_document(tmp_path / "hisobot_NEXVARA.docx")
        text = str(doc.Content.Text)
        first_level = int(doc.Paragraphs(1).OutlineLevel)
        footer = str(doc.Sections(1).Footers(1).Range.Text)
        numbers = int(doc.Sections(1).Footers(1).PageNumbers.Count)
        borders = bool(doc.Tables(1).Borders.Enable)
        w.disown(doc)
        doc.Close(0)
        del doc
    assert "  " not in text and " ," not in text and "Yillik hisobot" in text
    assert first_level == 1 and borders
    assert "Toshkent 2026" in footer and numbers >= 1  # the page number survived


# ---------------- PowerPoint ----------------
def make_deck(path: Path) -> Path:
    from nexvara.skills.powerpoint import ops
    from nexvara.skills.powerpoint.ops import PowerPointSession

    with PowerPointSession(visible=True) as pp:
        pres = pp.new_presentation()
        ops.add_title_slide(pres, "Hisobot 2025", "5-maktab")
        ops.add_bullets_slide(pres, "Natijalar 2025", ["O‘quvchilar: 640", "Bitiruvchilar: 52"])
        ops.add_table_slide(pres, "Sinflar", [["Sinf", "2025"], ["7-A", "28"]])
        pp.save_as(pres, path)
        pp.disown(pres)
        pres.Close()
        del pres
    return path


def test_powerpoint_commands(tmp_path):
    from nexvara.agent.parse import parse_command
    from nexvara.agent.ppt_exec import NUM_NAME, run_ppt_plan
    from nexvara.skills.powerpoint.ops import PowerPointSession

    src = make_deck(tmp_path / "dars.pptx")
    before = digest(src)
    plan = parse_command(
        "dars.pptx ni och, «2025» ni «2026» ga almashtir, shriftni Arial qil, barcha slaydlarga "
        "o‘tish effekti qo‘sh, slayd raqamlarini qo‘sh, slaydlarni tekshir va PDF qilib saqla"
    )
    assert plan.unknown == [], plan.unknown
    res = ok(run(run_ppt_plan, plan, src))
    assert digest(src) == before
    assert res["path"].endswith("dars_NEXVARA.pptx") and res["pdf"].endswith(".pdf")
    with PowerPointSession(visible=True) as pp:
        pres = pp.open_presentation(tmp_path / "dars_NEXVARA.pptx")
        texts = []
        for i in range(1, pres.Slides.Count + 1):
            shapes = pres.Slides(i).Shapes
            for j in range(1, shapes.Count + 1):
                sh = shapes(j)
                if sh.HasTextFrame and sh.TextFrame.HasText:
                    texts.append(str(sh.TextFrame.TextRange.Text))
                if sh.HasTable:
                    texts.append(str(sh.Table.Cell(1, 2).Shape.TextFrame.TextRange.Text))
        num = str(pres.Slides(3).Shapes(NUM_NAME).TextFrame.TextRange.Text)
        effect = int(pres.Slides(2).SlideShowTransition.EntryEffect)
        pp.disown(pres)
        pres.Close()
        del pres
    joined = " ".join(texts)
    assert "2025" not in joined and joined.count("2026") >= 3
    assert num == "3" and effect != 0
