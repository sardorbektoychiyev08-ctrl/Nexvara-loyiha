"""First real Word task: an official report built live, saved as DOCX + PDF, reopened, verified."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from nexvara.core.task import Task
from nexvara.skills.common import validate_output_path
from nexvara.skills.excel.demo import PRODUCTS

TITLE = "Ofis jihozlari bo'yicha choraklik hisobot"
HEADINGS = [(1, "Kirish"), (1, "Xaridlar tahlili"), (2, "Mahsulotlar jadvali"),
            (2, "Diagramma"), (1, "Xulosa")]  # fmt: skip
DATE_MARK = "{SANA}"
TABLE_HEADERS = ["№", "Mahsulot", "Kategoriya", "Soni", "Narxi (so'm)", "Jami (so'm)"]
HEADER_TEXT = "NEXVARA — avtomatik hisobot"


def table_rows() -> list[list[Any]]:
    rows: list[list[Any]] = [TABLE_HEADERS]
    for i, (name, cat, qty, price) in enumerate(PRODUCTS, start=1):
        rows.append([i, name, cat, qty, price, qty * price])
    rows.append(
        ["", "JAMI", "", sum(p[2] for p in PRODUCTS), "", sum(p[2] * p[3] for p in PRODUCTS)]
    )
    return rows


def default_output_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.home() / "Documents" / "NEXVARA" / f"nexvara-hisobot-{stamp}.docx"


class VerificationError(Exception):
    pass


def run_word_report(
    task: Task,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.4,
) -> dict[str, Any]:
    from nexvara.skills.word.ops import WordSession

    out = Path(out_path) if out_path else default_output_path()
    validate_output_path(out, (".docx",))
    pdf = out.with_suffix(".pdf")
    validate_output_path(pdf, (".pdf",))

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with WordSession(visible=visible, keep_open=keep_open) as w:
        checks = _build_and_verify(task, w, out, pdf, beat, keep_open)
    return {"path": str(out), "pdf": str(pdf), "checks": checks}


def _build_and_verify(
    task: Task, w: Any, out: Path, pdf: Path, beat: Any, keep_open: bool
) -> list[dict[str, Any]]:
    # COM objects live only in this frame, so they are released before Word quits.
    from nexvara.skills.png_chart import bar_chart_png
    from nexvara.skills.word import ops

    today = time.strftime("%d.%m.%Y")
    rows = table_rows()

    with task.step("Word'ni ochish") as s:
        doc = w.new_document()
        w.show()
        s.detail = f"Word {w.version}"
    beat()

    with task.step("Sahifa sozlamalari"):
        ops.page_setup(doc)
        ops.set_header(doc, HEADER_TEXT)
        ops.add_page_numbers(doc)
    beat()

    with task.step("Sarlavha va bo'limlar"):
        ops.add_paragraph(doc, TITLE, ops.STYLE_TITLE, align="center")
        ops.add_paragraph(doc, f"Sana: {DATE_MARK}", align="right")
        ops.add_paragraph(doc, "Mundarija", bold=True, size=14)
        ops.add_toc_placeholder(doc)
        ops.add_heading(doc, HEADINGS[0][1], 1)
        ops.add_paragraph(
            doc,
            "Ushbu hisobot ofis jihozlari va kanselyariya mahsulotlari xaridini tahlil qiladi. "
            "Hujjat NEXVARA tomonidan avtomatik tayyorlandi, "
            "ma'lumotlar Excel jadvalidan olindi.",
            align="justify",
        )
        ops.add_heading(doc, HEADINGS[1][1], 1)
        ops.add_bullets(
            doc,
            [
                f"Jami {len(PRODUCTS)} turdagi mahsulot xarid qilindi.",
                "Eng katta xarajat texnika va ofis jihozlariga to'g'ri keldi.",
                "Kanselyariya mahsulotlari soni bo'yicha ko'pchilikni tashkil qiladi.",
            ],
        )
        w.show()
    beat()

    with task.step("Jadval") as s:
        ops.add_heading(doc, HEADINGS[2][1], 2)
        table = ops.add_table(doc, rows, numeric_columns=(1, 4, 5, 6))
        table.Rows(table.Rows.Count).Range.Font.Bold = True
        s.detail = f"{table.Rows.Count}×{table.Columns.Count}"
    beat()

    with task.step("Diagramma rasmi"):
        ops.add_heading(doc, HEADINGS[3][1], 2)
        with tempfile.TemporaryDirectory() as tmp:
            png = bar_chart_png([p[2] * p[3] for p in PRODUCTS], Path(tmp) / "chart.png")
            ops.add_picture(doc, png, width_cm=15)
        ops.add_paragraph(doc, "1-rasm. Mahsulotlar bo'yicha xarajat", align="center", size=9)
    beat()

    with task.step("Xulosa, izoh va mundarija") as s:
        ops.add_heading(doc, HEADINGS[4][1], 1)
        ops.add_paragraph(
            doc,
            "Xaridlar rejaga muvofiq amalga oshirildi. Keyingi chorakda texnika xaridini "
            "optimallashtirish tavsiya etiladi.",
            align="justify",
        )
        ops.add_comment(
            doc, "Ushbu hisobot", "NEXVARA: raqamlar Excel jadvali bilan solishtirildi."
        )
        replaced = ops.find_replace(doc, DATE_MARK, today)
        ops.add_toc(doc)
        s.detail = f"{replaced} ta {DATE_MARK} almashtirildi"
    beat()

    with task.step("Saqlash (DOCX + PDF)") as s:
        w.save_as(doc, out)
        ops.export_pdf(doc, pdf)
        s.detail = f"{out.name}, {pdf.name}"
        w.disown(doc)
        doc.Close(ops.WD_DO_NOT_SAVE)
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        doc2 = w.open_document(out)
        w.show()
        checks = verify_report(doc2, rows, today, pdf)
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o'tdi"
        if failed:
            raise VerificationError("Tekshiruv o'tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            w.disown(doc2)
            doc2.Close(ops.WD_DO_NOT_SAVE)
    return checks


def verify_report(doc: Any, rows: list[list[Any]], today: str, pdf: Path) -> list[dict[str, Any]]:
    from nexvara.skills.word import ops

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    first = str(doc.Paragraphs(1).Range.Text).strip()
    check("Sarlavha", first == TITLE, first)

    got = ops.outline(doc)
    check("Bo'lim sarlavhalari", got == HEADINGS, str(got))

    ok_toc = doc.TablesOfContents.Count == 1
    toc_text = str(doc.TablesOfContents(1).Range.Text) if ok_toc else ""
    check("Mundarija", ok_toc and all(h in toc_text for _, h in HEADINGS))

    ok_table = doc.Tables.Count == 1
    if ok_table:
        t = doc.Tables(1)
        shape_ok = t.Rows.Count == len(rows) and t.Columns.Count == len(rows[0])
        total = ops.cell_text(t, len(rows), 6)
        want = f"{rows[-1][5]:,}".replace(",", " ")
        check("Jadval o'lchami", shape_ok, f"{t.Rows.Count}×{t.Columns.Count}")
        check("Jadval JAMI", total == want, f"{total!r} (kutilgan {want!r})")
        check("Jadval sarlavhasi qalin", bool(t.Rows(1).Range.Font.Bold))
    else:
        check("Jadval o'lchami", False, f"{doc.Tables.Count} ta jadval")

    text = str(doc.Content.Text)
    check("Sana qo'yilgan", DATE_MARK not in text and f"Sana: {today}" in text)
    check("Rasm", doc.InlineShapes.Count == 1, str(doc.InlineShapes.Count))
    pic_ok = doc.InlineShapes.Count == 1
    if pic_ok:
        # The picture must sit right after the "Diagramma" heading, not at the top.
        start = doc.InlineShapes(1).Range.Start
        before = str(doc.Range(0, start).Text)
        pic_ok = before.rstrip("\r").endswith(HEADINGS[3][1])
    check("Rasm joyi", pic_ok)
    check("Izoh", doc.Comments.Count == 1, str(doc.Comments.Count))
    scope = str(doc.Comments(1).Scope.Text) if doc.Comments.Count else ""
    check("Izoh joyi", scope.startswith("Ushbu hisobot"), scope[:40])

    sec = doc.Sections(1)
    header = str(sec.Headers(ops.WD_HEADER_FOOTER_PRIMARY).Range.Text).strip()
    check("Yuqori kolontitul", header == HEADER_TEXT, header)
    check("Sahifa raqamlari", sec.Footers(ops.WD_HEADER_FOOTER_PRIMARY).PageNumbers.Count == 1)

    ps = doc.PageSetup
    check(
        "A4 va chetlar", abs(ps.PageWidth - 595.3) < 1 and abs(ps.LeftMargin - ops.cm_to_pt(3)) < 1
    )
    check("PDF", pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-", str(pdf))
    return checks
