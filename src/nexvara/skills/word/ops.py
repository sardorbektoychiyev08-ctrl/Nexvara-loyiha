"""Word session and document operations over COM (Word 2016+, any UI language).

Styles are set through WdBuiltinStyle numbers, never by name: on a Russian Word
"Heading 1" is called "Заголовок 1", but -2 is Heading 1 everywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nexvara.skills.common import bring_to_front, validate_output_path
from nexvara.skills.excel.table import excel_color
from nexvara.skills.office_session import OfficeSession

# WdBuiltinStyle
STYLE_NORMAL = -1
STYLE_HEADING = {1: -2, 2: -3, 3: -4}
STYLE_TITLE = -63
STYLE_SUBTITLE = -75
STYLE_LIST_BULLET = -49
STYLE_LIST_NUMBER = -50

ALIGN = {"left": 0, "center": 1, "right": 2, "justify": 3}
ORIENTATION = {"portrait": 0, "landscape": 1}
WD_PAPER_A4 = 7
WD_HEADER_FOOTER_PRIMARY = 1
WD_PAGE_NUMBER_CENTER = 1
WD_SEPARATE_BY_TABS = 1
WD_AUTOFIT_CONTENT = 1
WD_AUTOFIT_WINDOW = 2
WD_CELL_ALIGN_VCENTER = 1
WD_REPLACE_ALL = 2
WD_FIND_STOP = 0
WD_DO_NOT_SAVE = 0
WD_FORMAT_DOCX = 16
WD_EXPORT_PDF = 17
WD_WINDOW_MAXIMIZE = 1
WD_ALERTS_NONE = 0
WD_ALERTS_ALL = -1

HEADER_FILL = "#6366F1"


def cm_to_pt(cm: float) -> float:
    # Application.CentimetersToPoints fails over out-of-process COM, so convert here.
    return cm * 72 / 2.54


# NOTE: Word ignores *named* arguments over late-bound COM (Range=..., Replace=... are
# silently dropped), so every Word call below passes arguments positionally.


class WordSession(OfficeSession):
    prog_id = "Word.Application"

    def _collection(self) -> Any:
        return self.app.Documents

    def _close_doc(self, doc: Any) -> None:
        doc.Close(WD_DO_NOT_SAVE)

    def _quit(self) -> None:
        self.app.Quit(WD_DO_NOT_SAVE)

    def _prepare(self) -> None:
        self.app.Visible = self.visible

    def show(self) -> None:
        if not self.visible or self.app.Documents.Count == 0:
            return
        self.app.WindowState = WD_WINDOW_MAXIMIZE
        bring_to_front(self.app.ActiveWindow.Hwnd)

    def new_document(self) -> Any:
        return self.own(self.app.Documents.Add())

    def open_document(self, path: str | Path) -> Any:
        return self.own(self.app.Documents.Open(str(Path(path).resolve())))

    def save_as(self, doc: Any, path: str | Path, overwrite: bool = False) -> Path:
        target = validate_output_path(path, (".docx",), overwrite)
        target.parent.mkdir(parents=True, exist_ok=True)
        old = str(doc.FullName)
        self.app.DisplayAlerts = WD_ALERTS_NONE
        try:
            doc.SaveAs2(str(target), WD_FORMAT_DOCX)
        finally:
            self.app.DisplayAlerts = WD_ALERTS_ALL
        if old in self._owned:
            self._owned[self._owned.index(old)] = str(doc.FullName)
        return target


# ---------- text ----------


def _last_empty_paragraph(doc: Any) -> Any:
    """Range of an empty last paragraph, creating one if needed."""
    rng = doc.Paragraphs.Last.Range
    if rng.Text not in ("\r", ""):
        doc.Content.InsertParagraphAfter()
        rng = doc.Paragraphs.Last.Range
    # A new paragraph inherits the previous one's style (e.g. a bullet list); start clean.
    rng.Style = STYLE_NORMAL
    rng.ListFormat.RemoveNumbers()
    return rng


def add_paragraph(
    doc: Any,
    text: str,
    style: int = STYLE_NORMAL,
    *,
    bold: bool | None = None,
    align: str | None = None,
    size: float | None = None,
) -> Any:
    """Append a paragraph and return it for immediate formatting.

    The returned object tracks Word's *last* paragraph, so don't keep it for later use
    (anchor later edits by text instead, e.g. add_comment(doc, "some words", ...)).
    """
    rng = _last_empty_paragraph(doc)
    rng.InsertBefore(text)
    para = doc.Paragraphs.Last
    para.Style = style
    if bold is not None:
        para.Range.Font.Bold = bold
    if align is not None:
        para.Alignment = ALIGN[align]
    if size is not None:
        para.Range.Font.Size = size
    return para


def add_heading(doc: Any, text: str, level: int = 1) -> Any:
    if level not in STYLE_HEADING:
        raise ValueError(f"heading level must be one of {sorted(STYLE_HEADING)}")
    return add_paragraph(doc, text, STYLE_HEADING[level])


def add_bullets(doc: Any, items: list[str], numbered: bool = False) -> None:
    style = STYLE_LIST_NUMBER if numbered else STYLE_LIST_BULLET
    for item in items:
        add_paragraph(doc, item, style)


def _find_execute(
    rng: Any, find: str, match_case: bool, replace_with: str = "", replace: int = 0
) -> bool:
    # Named arguments to Find.Execute are silently ignored over late-bound COM, so pass all
    # positionally: FindText, MatchCase, MatchWholeWord, MatchWildcards, MatchSoundsLike,
    # MatchAllWordForms, Forward, Wrap, Format, ReplaceWith, Replace.
    return bool(
        rng.Find.Execute(
            find, match_case, False, False, False, False, True, WD_FIND_STOP, False,
            replace_with, replace,
        )
    )  # fmt: skip


def find_replace(doc: Any, find: str, replace: str, match_case: bool = True) -> int:
    """Replace all occurrences in the body; returns how many were replaced."""
    if not find:
        raise ValueError("find text must not be empty")

    def count() -> int:
        text = str(doc.Content.Text)
        return text.count(find) if match_case else text.lower().count(find.lower())

    before = count()
    if before:
        _find_execute(doc.Content, find, match_case, replace, WD_REPLACE_ALL)
        left = count() if find not in replace else 0
        if left:
            raise RuntimeError(f"Word left {left} of {before} occurrences of {find!r}")
    return before


def add_comment(doc: Any, anchor_text: str, text: str) -> Any:
    """Attach a comment to the first occurrence of `anchor_text`.

    Anchoring by text (not by a saved Paragraph) because Word paragraph objects
    obtained while appending drift to whatever paragraph is last.
    """
    rng = doc.Content
    if not _find_execute(rng, anchor_text, True):
        raise ValueError(f"text not found for comment: {anchor_text!r}")
    return doc.Comments.Add(rng, text)


def add_picture(doc: Any, image: str | Path, width_cm: float | None = None) -> Any:
    p = Path(image)
    if not p.is_file():
        raise FileNotFoundError(p)
    rng = _last_empty_paragraph(doc)
    # FileName, LinkToFile, SaveWithDocument, Range
    shape = doc.InlineShapes.AddPicture(str(p.resolve()), False, True, rng)
    if width_cm:
        ratio = shape.Height / shape.Width
        shape.Width = cm_to_pt(width_cm)
        shape.Height = shape.Width * ratio
    doc.Paragraphs.Last.Alignment = ALIGN["center"]
    return shape


# ---------- tables ----------


def add_table(
    doc: Any,
    rows: list[list[Any]],
    *,
    numeric_columns: tuple[int, ...] = (),
    header: bool = True,
) -> Any:
    """Append a table (first row = header). One ConvertToTable call keeps big tables fast."""
    if not rows or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError("rows must be a non-empty rectangle")
    cells = [[_cell_text(v) for v in r] for r in rows]
    if any("\t" in c or "\r" in c for r in cells for c in r):
        raise ValueError("cell text must not contain tab or newline characters")
    text = "\r".join("\t".join(r) for r in cells)
    rng = _last_empty_paragraph(doc)
    rng.InsertBefore(text)
    table = rng.ConvertToTable(WD_SEPARATE_BY_TABS, len(rows), len(rows[0]))
    if table.Columns.Count != len(rows[0]) or table.Rows.Count != len(rows):
        raise RuntimeError(
            f"Word built a {table.Rows.Count}x{table.Columns.Count} table, "
            f"expected {len(rows)}x{len(rows[0])}"
        )
    table.Borders.Enable = True
    table.Range.Cells.VerticalAlignment = WD_CELL_ALIGN_VCENTER
    table.Range.ParagraphFormat.SpaceAfter = 0
    if header:
        hdr = table.Rows(1)
        hdr.HeadingFormat = True
        hdr.Range.Font.Bold = True
        hdr.Range.Font.Color = excel_color("#FFFFFF")
        hdr.Shading.BackgroundPatternColor = excel_color(HEADER_FILL)
        hdr.Range.ParagraphFormat.Alignment = ALIGN["center"]
    for c in numeric_columns:
        for r in range(2 if header else 1, len(rows) + 1):
            table.Cell(r, c).Range.ParagraphFormat.Alignment = ALIGN["center"]
    table.AutoFitBehavior(WD_AUTOFIT_CONTENT)
    table.AutoFitBehavior(WD_AUTOFIT_WINDOW)
    # Word keeps an empty paragraph after a table; the next add_paragraph() reuses it.
    return table


def _cell_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return f"{v:,}".replace(",", " ")
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return str(v)


def cell_text(table: Any, row: int, col: int) -> str:
    """Cell text without Word's end-of-cell marker."""
    return str(table.Cell(row, col).Range.Text).rstrip("\r\x07")


# ---------- page layout ----------


def page_setup(
    doc: Any,
    *,
    orientation: str = "portrait",
    margins_cm: tuple[float, float, float, float] = (2.0, 1.5, 2.0, 3.0),
) -> None:
    """A4; margins = (top, right, bottom, left) in cm (Uzbek office standard by default)."""
    ps = doc.PageSetup
    ps.PaperSize = WD_PAPER_A4
    ps.Orientation = ORIENTATION[orientation]
    ps.TopMargin, ps.RightMargin, ps.BottomMargin, ps.LeftMargin = (cm_to_pt(m) for m in margins_cm)


def set_header(doc: Any, text: str) -> None:
    rng = doc.Sections(1).Headers(WD_HEADER_FOOTER_PRIMARY).Range
    rng.Text = text
    rng.ParagraphFormat.Alignment = ALIGN["right"]
    rng.Font.Size = 9


def add_page_numbers(doc: Any) -> None:
    footer = doc.Sections(1).Footers(WD_HEADER_FOOTER_PRIMARY)
    footer.PageNumbers.Add(WD_PAGE_NUMBER_CENTER, True)


TOC_MARKER = "{MUNDARIJA}"


def add_toc_placeholder(doc: Any) -> Any:
    """Mark where the table of contents goes; call add_toc() once headings exist."""
    return add_paragraph(doc, TOC_MARKER)


def add_toc(doc: Any, levels: tuple[int, int] = (1, 2)) -> Any:
    """Replace the TOC placeholder with a table of contents built from heading styles."""
    rng = doc.Content
    if not _find_execute(rng, TOC_MARKER, True):
        raise ValueError("no TOC placeholder; call add_toc_placeholder() first")
    rng.Text = ""
    # Range, UseHeadingStyles, UpperHeadingLevel, LowerHeadingLevel
    toc = doc.TablesOfContents.Add(rng, True, levels[0], levels[1])
    toc.Update()
    return toc


# ---------- checks / export ----------


def outline(doc: Any) -> list[tuple[int, str]]:
    """(level, text) for every heading paragraph (OutlineLevel is language-independent)."""
    out = []
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        lvl = int(p.OutlineLevel)
        if 1 <= lvl <= 9:
            out.append((lvl, str(p.Range.Text).strip()))
    return out


def spelling_error_count(doc: Any) -> int:
    return int(doc.SpellingErrors.Count)


def export_pdf(doc: Any, path: str | Path, overwrite: bool = False) -> Path:
    target = validate_output_path(path, (".pdf",), overwrite)
    doc.ExportAsFixedFormat(str(target), WD_EXPORT_PDF)
    return target
