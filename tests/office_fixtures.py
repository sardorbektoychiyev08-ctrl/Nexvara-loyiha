"""Real Office files for command tests, created through COM (no third-party writers)."""

from __future__ import annotations

from pathlib import Path

SALES_HEADERS = ["Hudud", "Mahsulot", "Soni", "Summa"]
SALES_ROWS = [
    ["Toshkent", "Daftar", 120, 540000],
    ["Samarqand", "Ruchka", 300, 450000],
    ["  Buxoro ", "Daftar", 80, 360000],  # extra spaces: "tozala" must fix
    ["Toshkent", "Printer", 2, 3100000],
    ["Farg‘ona", "Ruchka", 150, 225000],
    ["Samarqand", "Ruchka", 300, 450000],  # exact duplicate of row 2
    ["Toshkent", "Kalkulyator", 10, 950000],
    ["Buxoro", "Printer", 1, 1550000],
]


def make_sales_xlsx(path: Path) -> Path:
    from nexvara.skills.excel import ops
    from nexvara.skills.excel.bridge import ExcelSession

    with ExcelSession(visible=False) as xl:
        wb = xl.new_workbook()
        ws = wb.Worksheets(1)
        ws.Name = "Savdo"
        ops.write_rows(ws, [SALES_HEADERS, *SALES_ROWS])
        xl.save_as(wb, path)
        wb.Close(SaveChanges=False)
        del ws, wb
    return path


def make_letter_docx(path: Path) -> Path:
    from nexvara.skills.word import ops
    from nexvara.skills.word.ops import WordSession

    with WordSession(visible=False) as w:
        doc = w.new_document()
        ops.add_paragraph(doc, "Maktab direktori Aliyev A.ga", align="right")
        ops.add_heading(doc, "Ariza", 1)
        ops.add_paragraph(
            doc, "Men, Aliyev Vali, farzandimni 7-sinfga qabul qilishingizni so‘rayman."
        )
        ops.add_heading(doc, "Ilova", 2)
        ops.add_paragraph(doc, "Tug‘ilganlik haqida guvohnoma nusxasi.")
        w.save_as(doc, path)
        w.disown(doc)
        doc.Close(0)
        del doc
    return path
