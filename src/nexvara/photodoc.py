"""A photo of a paper table or document → Excel or Word («shu rasmni Excel qil»).

The text comes from the free offline OCR (or, after the user's «Ha», from a vision AI, which
writes table cells with ' | '). Rows are found from ' | ', tabs or wide gaps; a table becomes
an .xlsx with a bordered, bold header (openpyxl, no Excel window needed) or a Word table;
plain text becomes Word paragraphs. The result is saved next to the photo as
«<rasm>_NEXVARA.xlsx/.docx» — the photo is never changed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from nexvara.core.task import UserError

_SPLIT = re.compile(r"\s*\|\s*|\t+| {3,}")
_NUM = re.compile(r"^[+-]?\d{1,3}(?:[  ]?\d{3})*(?:[.,]\d+)?$|^[+-]?\d+(?:[.,]\d+)?$")
MAX_ROWS = 5000


def split_row(line: str) -> list[str]:
    line = line.strip().strip("|").strip()
    if not line:
        return []
    return [c.strip() for c in _SPLIT.split(line)]


def table_rows(text: str) -> list[list[str]] | None:
    """The table in OCR text, or None when it is ordinary text. Lines that are only
    separators (---|---) are skipped; short rows are padded to the widest common row."""
    rows = []
    for line in (text or "").splitlines():
        if re.fullmatch(r"[\s|:+\-=_]*", line):
            continue
        cells = split_row(line)
        if cells:
            rows.append(cells)
    multi = [r for r in rows if len(r) >= 2]
    if len(multi) < 2 or len(multi) < 0.6 * len(rows):
        return None
    width = max(len(r) for r in multi)
    # a one-cell first line is the title above the table; later one-cell lines are kept
    out = [r + [""] * (width - len(r)) for i, r in enumerate(rows) if len(r) >= 2 or i > 0]
    return out[:MAX_ROWS]


def number(cell: str) -> Any:
    """«1 250 000» / «12,5» → a real number for Excel; anything else stays text
    (leading zeros like «007» and phone-like numbers stay text)."""
    s = cell.strip()
    if not s or not _NUM.match(s) or (len(s) > 1 and s[0] == "0" and s[1].isdigit()):
        return cell
    s = s.replace(" ", "").replace(" ", "")
    if len(re.sub(r"\D", "", s)) > 15:
        return cell
    try:
        return int(s) if re.fullmatch(r"[+-]?\d+", s) else float(s.replace(",", "."))
    except ValueError:
        return cell


def write_excel(rows: list[list[str]], path: Path, title: str = "Jadval") -> Path:
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    from nexvara.skills.excel.bridge import BORDER_COLOR, HEADER_FILL, HEADER_FONT

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = re.sub(r"[\[\]:*?/\\]", "", title)[:31] or "Jadval"
    thin = Side(style="thin", color=BORDER_COLOR.lstrip("#"))
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for r, row in enumerate(rows, start=1):
        for c, cell in enumerate(row, start=1):
            v = cell if r == 1 else number(cell)
            x = ws.cell(row=r, column=c, value=v)
            x.border = border
            x.alignment = Alignment(vertical="center", wrap_text=r == 1,
                                    horizontal="center" if r == 1 or not isinstance(v, str)
                                    else "left")  # fmt: skip
            if r == 1:
                x.font = Font(bold=True, color=HEADER_FONT.lstrip("#"))
                x.fill = PatternFill("solid", fgColor=HEADER_FILL.lstrip("#"))
    for c in range(1, len(rows[0]) + 1):
        longest = max(len(str(row[c - 1])) for row in rows[:300])
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = min(
            max(8, longest + 3), 60
        )
    ws.freeze_panes = "A2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def write_word(text: str, rows: list[list[str]] | None, path: Path, title: str,
               visible: bool = True, keep_open: bool = True) -> Path:  # fmt: skip
    from nexvara.skills.word import ops

    with ops.WordSession(visible=visible, keep_open=keep_open) as w:
        doc = w.new_document()
        ops.add_paragraph(doc, title, ops.STYLE_HEADING[1], align="center")
        if rows:
            clean = [[c.replace("\t", " ") for c in r] for r in rows]
            ops.add_table(doc, clean)
        else:
            for para in re.split(r"\n\s*\n", text.strip()):
                line = " ".join(para.split())
                if line:
                    ops.add_paragraph(doc, line)
        w.show()
        saved = w.save_as(doc, path)
        del doc
    return saved


def output_for(image: str | Path, ext: str) -> Path:
    from nexvara.agent.files import output_path

    src = Path(image)
    if src.suffix.lower() == ".txt":  # the OCR text file next to the photo
        src = src.with_suffix(".jpg")
    return output_path(src, ext)


def convert(text: str, image: str | Path, to: str, task: Any = None, visible: bool = True,
            keep_open: bool = True) -> dict[str, Any]:  # fmt: skip
    if not (text or "").strip():
        raise UserError("Rasmda matn topilmadi: yaqinroq, yorug‘ joyda, tekis suratga oling.")
    rows = table_rows(text)
    title = Path(image).stem.replace("_", " ")[:60]
    if to == "excel":
        if rows is None:
            raise UserError(
                "Rasmda jadval topilmadi (ustunlar ajralmadi). Jadvalli rasm uchun "
                "«AI bilan Excel qil» deb yozing yoki Word’ga aylantiring."
            )
        out = write_excel(rows, output_for(image, ".xlsx"), title)
        return {"path": str(out), "rows": len(rows) - 1, "cols": len(rows[0]), "kind": "excel"}
    if to == "word":
        out = write_word(text, rows, output_for(image, ".docx"), title, visible, keep_open)
        return {"path": str(out), "rows": len(rows) - 1 if rows else 0, "kind": "word"}
    raise UserError("Faqat Excel yoki Word")
