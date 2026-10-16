"""PowerPoint session and slide operations over COM (PowerPoint 2016+, any UI language).

Rules learned on Office 2016 (see AGENTS.md):
- every call passes arguments positionally (named args are unreliable over late binding);
- layouts are PpSlideLayout numbers, never localized names;
- charts need a presentation *with a window*, so presentations are always windowed;
- PowerPoint is single-instance: the session never closes the user's presentations.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import win32gui

from nexvara.skills.common import bring_to_front, validate_output_path
from nexvara.skills.excel.table import col_letter, excel_color
from nexvara.skills.office_session import OfficeSession
from nexvara.skills.powerpoint.layout import Box, find_overlaps, outside_slide, text_overflows

# PpSlideLayout
LAYOUT_TITLE = 1
LAYOUT_TEXT = 2
LAYOUT_TITLE_ONLY = 11
LAYOUT_BLANK = 12

MSO_TRUE = -1
MSO_FALSE = 0
MSO_TEXTBOX = 1  # msoTextOrientationHorizontal
MSO_SHAPE_RECTANGLE = 1
PP_WINDOW_MAXIMIZED = 3
PP_SAVE_PPTX = 24
PP_SAVE_PDF = 32
PP_EFFECT_FADE = 1793  # ppEffectFadeSmoothly
MSO_ANIM_FADE = 10
MSO_ANIM_TRIGGER_ON_CLICK = 1
XL_COLUMNS = 2
CHART_TYPES = {"column": 51, "bar": 57, "line": 65, "pie": 5, "doughnut": -4120}

SLIDE_W, SLIDE_H = 960.0, 540.0  # 16:9
MARGIN = 48.0
BAR_NAME = "NEXVARA_bar"

THEME = {
    "font": "Segoe UI",
    "title": "#0B1020",
    "text": "#1F2937",
    "accent": "#6366F1",
    "accent2": "#06B6D4",
    "background": "#FFFFFF",
}


class PowerPointSession(OfficeSession):
    prog_id = "PowerPoint.Application"

    def __init__(self, visible: bool = True, keep_open: bool = False) -> None:
        # PowerPoint cannot run hidden with charts; "visible=False" only skips focus-stealing.
        super().__init__(visible=visible, keep_open=keep_open)

    def _collection(self) -> Any:
        return self.app.Presentations

    def _close_doc(self, doc: Any) -> None:
        doc.Close()

    def show(self) -> None:
        if not self.visible:
            return
        self.app.WindowState = PP_WINDOW_MAXIMIZED
        self.app.ActiveWindow.Activate()
        # Application.HWND is not reachable over late-bound COM; find the frame window instead.
        hwnd = win32gui.FindWindow("PPTFrameClass", None)
        if hwnd:
            bring_to_front(hwnd)

    def new_presentation(self) -> Any:
        pres = self.own(self.app.Presentations.Add(MSO_TRUE))
        pres.PageSetup.SlideWidth = SLIDE_W
        pres.PageSetup.SlideHeight = SLIDE_H
        return pres

    def open_presentation(self, path: str | Path) -> Any:
        # FileName, ReadOnly, Untitled, WithWindow
        return self.own(self.app.Presentations.Open(str(Path(path).resolve()), 0, 0, MSO_TRUE))

    def save_as(self, pres: Any, path: str | Path, overwrite: bool = False) -> Path:
        target = validate_output_path(path, (".pptx",), overwrite)
        target.parent.mkdir(parents=True, exist_ok=True)
        old = str(pres.FullName)
        pres.SaveAs(str(target), PP_SAVE_PPTX)
        if old in self._owned:
            self._owned[self._owned.index(old)] = str(pres.FullName)
        return target


# ---------- theme ----------


def apply_theme(pres: Any) -> None:
    """Brand background and fonts on the slide master, so every layout inherits them."""
    master = pres.SlideMaster
    master.Background.Fill.Solid()
    master.Background.Fill.ForeColor.RGB = excel_color(THEME["background"])
    fonts = pres.SlideMaster.Theme.ThemeFontScheme
    fonts.MajorFont(1).Name = THEME["font"]  # msoThemeLatin
    fonts.MinorFont(1).Name = THEME["font"]


def _brand_bar(slide: Any) -> None:
    bar = slide.Shapes.AddShape(MSO_SHAPE_RECTANGLE, 0, 0, 10, SLIDE_H)
    bar.Name = BAR_NAME
    bar.Fill.ForeColor.RGB = excel_color(THEME["accent"])
    bar.Line.Visible = MSO_FALSE


def _style_title(shape: Any, size: float = 32) -> None:
    tr = shape.TextFrame.TextRange
    tr.Font.Name = THEME["font"]
    tr.Font.Bold = MSO_TRUE
    tr.Font.Size = size
    tr.Font.Color.RGB = excel_color(THEME["title"])


def _style_body(shape: Any, size: float = 20) -> None:
    tr = shape.TextFrame.TextRange
    tr.Font.Name = THEME["font"]
    tr.Font.Size = size
    tr.Font.Color.RGB = excel_color(THEME["text"])


def _place_title(slide: Any, title: str) -> Any:
    t = slide.Shapes.Placeholders(1)
    t.TextFrame.TextRange.Text = title
    t.Left, t.Top, t.Width, t.Height = MARGIN, 24, SLIDE_W - 2 * MARGIN, 64
    _style_title(t)
    return t


def content_top(slide: Any) -> float:
    t = slide.Shapes.Placeholders(1)
    return t.Top + t.Height + 16


# ---------- slides ----------


def add_title_slide(pres: Any, title: str, subtitle: str = "") -> Any:
    slide = pres.Slides.Add(pres.Slides.Count + 1, LAYOUT_TITLE)
    t = slide.Shapes.Placeholders(1)
    t.TextFrame.TextRange.Text = title
    _style_title(t, 40)
    sub = slide.Shapes.Placeholders(2)
    sub.TextFrame.TextRange.Text = subtitle
    _style_body(sub, 20)
    sub.TextFrame.TextRange.Font.Color.RGB = excel_color(THEME["accent"])
    _brand_bar(slide)
    return slide


def add_bullets_slide(pres: Any, title: str, bullets: Sequence[str]) -> Any:
    slide = pres.Slides.Add(pres.Slides.Count + 1, LAYOUT_TEXT)
    _place_title(slide, title)
    body = slide.Shapes.Placeholders(2)
    body.TextFrame.TextRange.Text = "\r".join(bullets)
    top = content_top(slide)
    body.Left, body.Top, body.Width, body.Height = (
        MARGIN,
        top,
        SLIDE_W - 2 * MARGIN,
        SLIDE_H - top - MARGIN,
    )
    _style_body(body)
    _brand_bar(slide)
    return slide


def add_table_slide(
    pres: Any, title: str, rows: Sequence[Sequence[Any]], numeric_columns: Sequence[int] = ()
) -> Any:
    slide = pres.Slides.Add(pres.Slides.Count + 1, LAYOUT_TITLE_ONLY)
    _place_title(slide, title)
    top = content_top(slide)
    n_rows, n_cols = len(rows), len(rows[0])
    height = min(SLIDE_H - top - MARGIN, 34 * n_rows)
    shape = slide.Shapes.AddTable(n_rows, n_cols, MARGIN, top, SLIDE_W - 2 * MARGIN, height)
    table = shape.Table
    for r, row in enumerate(rows, start=1):
        for c, v in enumerate(row, start=1):
            tr = table.Cell(r, c).Shape.TextFrame.TextRange
            tr.Text = _text(v)
            tr.Font.Size = 14
            tr.Font.Name = THEME["font"]
            if c in numeric_columns or r == 1:
                tr.ParagraphFormat.Alignment = 2  # ppAlignCenter
    for c in range(1, n_cols + 1):
        cell = table.Cell(1, c).Shape
        cell.Fill.ForeColor.RGB = excel_color(THEME["accent"])
        cell.TextFrame.TextRange.Font.Bold = MSO_TRUE
        cell.TextFrame.TextRange.Font.Color.RGB = excel_color("#FFFFFF")
    _brand_bar(slide)
    return slide


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}".replace(",", " ")
    return str(v)


def add_chart_slide(
    pres: Any,
    title: str,
    categories: Sequence[str],
    series: dict[str, Sequence[float]],
    kind: str = "column",
) -> Any:
    """Native PowerPoint chart (data lives in the embedded workbook)."""
    if kind not in CHART_TYPES:
        raise ValueError(f"chart kind must be one of {sorted(CHART_TYPES)}")
    if not series or any(len(v) != len(categories) for v in series.values()):
        raise ValueError("every series needs one value per category")
    slide = pres.Slides.Add(pres.Slides.Count + 1, LAYOUT_TITLE_ONLY)
    _place_title(slide, title)
    top = content_top(slide)
    # Style, Type, Left, Top, Width, Height, NewLayout
    shape = slide.Shapes.AddChart2(
        -1, CHART_TYPES[kind], MARGIN, top, SLIDE_W - 2 * MARGIN, SLIDE_H - top - MARGIN, True
    )
    chart = shape.Chart
    data = chart.ChartData
    data.Activate()
    wb = data.Workbook
    try:
        ws = wb.Worksheets(1)
        ws.UsedRange.ClearContents()
        names = list(series)
        block = [["", *names]] + [
            [cat, *[series[n][i] for n in names]] for i, cat in enumerate(categories)
        ]
        last_col, last_row = col_letter(len(names) + 1), len(categories) + 1
        ws.Range(f"A1:{last_col}{last_row}").Value = block
        # Source, PlotBy (positional; the string form is what PowerPoint charts accept)
        chart.SetSourceData(f"'{ws.Name}'!$A$1:${last_col}${last_row}", XL_COLUMNS)
        chart.HasTitle = False
        del ws
    finally:
        wb.Close()
        del wb
    _brand_bar(slide)
    return slide


def add_picture_slide(pres: Any, title: str, image: str | Path, caption: str = "") -> Any:
    p = Path(image)
    if not p.is_file():
        raise FileNotFoundError(p)
    slide = pres.Slides.Add(pres.Slides.Count + 1, LAYOUT_TITLE_ONLY)
    _place_title(slide, title)
    top = content_top(slide)
    cap_h = 30 if caption else 0
    avail_w, avail_h = SLIDE_W - 2 * MARGIN, SLIDE_H - top - MARGIN - cap_h
    # FileName, LinkToFile, SaveWithDocument, Left, Top
    pic = slide.Shapes.AddPicture(str(p.resolve()), MSO_FALSE, MSO_TRUE, MARGIN, top)
    scale = min(avail_w / pic.Width, avail_h / pic.Height, 1.0)
    pic.Width, pic.Height = pic.Width * scale, pic.Height * scale
    pic.Left = (SLIDE_W - pic.Width) / 2
    if caption:
        box = slide.Shapes.AddTextbox(MSO_TEXTBOX, MARGIN, pic.Top + pic.Height + 4, avail_w, cap_h)
        box.TextFrame.TextRange.Text = caption
        _style_body(box, 14)
        box.TextFrame.TextRange.ParagraphFormat.Alignment = 2
    _brand_bar(slide)
    return slide


def set_notes(slide: Any, text: str) -> None:
    slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = text


def notes(slide: Any) -> str:
    return str(slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text)


def set_transition(slide: Any, effect: int = PP_EFFECT_FADE) -> None:
    slide.SlideShowTransition.EntryEffect = effect


def animate(slide: Any, shape: Any, effect: int = MSO_ANIM_FADE) -> Any:
    # Shape, effectId, level, trigger
    return slide.TimeLine.MainSequence.AddEffect(shape, effect, 0, MSO_ANIM_TRIGGER_ON_CLICK)


def move_slide(pres: Any, from_index: int, to_index: int) -> None:
    pres.Slides(from_index).MoveTo(to_index)


def slide_title(slide: Any) -> str:
    try:
        return str(slide.Shapes.Placeholders(1).TextFrame.TextRange.Text)
    except Exception:
        return ""


# ---------- quality checks ----------


def layout_problems(slide: Any) -> list[str]:
    """Overflowing text, shapes outside the slide, and overlapping content shapes."""
    problems: list[str] = []
    boxes: list[Box] = []
    for i in range(1, slide.Shapes.Count + 1):
        sh = slide.Shapes(i)
        box = Box(str(sh.Name), sh.Left, sh.Top, sh.Width, sh.Height)
        if outside_slide(box, SLIDE_W, SLIDE_H):
            problems.append(f"{box.name}: slayddan tashqarida")
        if sh.HasTextFrame and sh.TextFrame.HasText:
            bound = sh.TextFrame.TextRange.BoundHeight
            if text_overflows(bound, sh.Height):
                problems.append(f"{box.name}: matn sig'madi ({bound:.0f} > {sh.Height:.0f})")
        if box.name != BAR_NAME:
            boxes.append(box)
    problems += [f"{a} ↔ {b}: ustma-ust" for a, b in find_overlaps(boxes)]
    return problems


def export_pdf(pres: Any, path: str | Path, overwrite: bool = False) -> Path:
    target = validate_output_path(path, (".pdf",), overwrite)
    # ExportAsFixedFormat fails in pywin32 (unconvertible optional args); SaveCopyAs works.
    pres.SaveCopyAs(str(target), PP_SAVE_PDF)
    return target
