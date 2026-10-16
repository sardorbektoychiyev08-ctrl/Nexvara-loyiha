"""Figures ("61-rasm. Tok kuchini o‘lchash") for picture questions.

A figure's caption is the answer to "what does the picture show?"; captions of other
figures in the same book are the distractors. The picture is cut out of the PDF page:
the raster image (or the cluster of vector drawings, for "chizma") nearest above or
beside its caption. Works for books with a text layer; scanned books have no captions
to anchor on and are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from nexvara.knowledge.textnorm import letter_ratio

# "61-rasm. Caption" — but not a reference in running text ("61-rasmdagi ...").
_CAPTION = re.compile(r"^\s*(\d{1,3})\s*-\s*rasm(?![a-zA-Z‘’'])\.?\s*(.*)$", re.IGNORECASE)
_DRAWING_WORDS = ("chizma", "sxema", "grafik", "diagramma", "jadval", "xarita")
MIN_SIDE = 40  # points; smaller images are icons
MAX_GAP = 220  # points between the picture and its caption


@dataclass
class Figure:
    number: int
    caption: str
    page: int  # 1-based
    image: Path | None = None

    @property
    def is_drawing(self) -> bool:
        c = self.caption.lower()
        return any(w in c for w in _DRAWING_WORDS)


def captions_in_text(page_no: int, text: str) -> list[Figure]:
    """'61-rasm. Ikki o‘tkazgichni' + next line 'ketma-ket ulash.' -> one caption."""
    lines = [ln.strip() for ln in text.split("\n")]
    out = []
    for i, line in enumerate(lines):
        m = _CAPTION.match(line)
        if not m:
            continue
        caption = m.group(2).strip()
        # A caption broken over lines continues until a full stop or a blank line.
        j = i + 1
        while caption and not caption.endswith((".", "!", "?")) and j < len(lines) and j <= i + 2:
            nxt = lines[j]
            if not nxt or _CAPTION.match(nxt) or len(nxt.split()) > 12:
                break
            caption = f"{caption} {nxt}"
            j += 1
        caption = caption.strip(" .")
        if len(caption.split()) >= 2 and letter_ratio(caption) > 0.6:
            out.append(Figure(int(m.group(1)), caption, page_no))
    # The same figure number can appear in running text ("61-rasmda ko‘rinib turibdi").
    seen, unique = set(), []
    for f in out:
        if f.number not in seen:
            seen.add(f.number)
            unique.append(f)
    return unique


def figures_in_pdf(pdf: Path, pages: list[int]) -> list[Figure]:
    """Captions on the given 1-based pages, read with PyMuPDF (the same text layer that
    is later used to locate the picture)."""
    import pymupdf

    from nexvara.knowledge.textnorm import normalize

    out: list[Figure] = []
    with pymupdf.open(str(pdf)) as doc:
        for p in pages:
            if 1 <= p <= doc.page_count:
                out += captions_in_text(p, normalize(doc[p - 1].get_text()))
    return out


def book_captions(pdf: Path) -> list[str]:
    """Every caption in the book: the distractor pool for picture questions."""
    import pymupdf

    with pymupdf.open(str(pdf)) as doc:
        return [f.caption for f in figures_in_pdf(pdf, list(range(1, doc.page_count + 1)))]


def _caption_rect(page, number: int):
    """Rectangle of the caption label "68-rasm." itself — not of a reference to it in the
    running text ("68-rasmda ko‘rsatilganidek ...")."""
    import pymupdf

    words = page.get_text("words")
    label = re.compile(rf"^{number}\s*-\s*rasm\.?$", re.IGNORECASE)
    split_num = re.compile(rf"^{number}-?$")
    for i, w in enumerate(words):
        token = w[4]
        nxt = words[i + 1][4] if i + 1 < len(words) else ""
        if label.match(token):
            # "68-rasm." or "68-rasm" followed by a capitalised caption word.
            if token.endswith(".") or nxt[:1].isupper():
                return pymupdf.Rect(w[:4])
        elif split_num.match(token) and re.match(r"^-?\s*rasm\.?$", nxt, re.IGNORECASE):
            return pymupdf.Rect(w[:4]) | pymupdf.Rect(words[i + 1][:4])
    return None


def _grow(rect, parts, cap, header_line: float = 0, touch: float = 15):
    """A picture is often several pieces (photo + arrows + labels): absorb every piece that
    touches the growing box, but never reach below the caption."""
    changed = True
    while changed:
        changed = False
        for r in parts:
            if r.y0 >= cap.y0 - 2 or r.is_empty or (r.width < 2 and r.height < 2):
                continue
            if r.y0 < header_line:  # never grow into the running header
                continue
            near = (
                r.x0 <= rect.x1 + touch
                and r.x1 >= rect.x0 - touch
                and r.y0 <= rect.y1 + touch
                and r.y1 >= rect.y0 - touch
            )
            if near and not rect.contains(r):
                grown = rect | r
                # Do not swallow a whole page of text boxes and borders.
                if grown.height <= 2.5 * max(rect.height, 80) and grown.width <= 1.5 * max(
                    rect.width, 120
                ):
                    rect, changed = grown, True
    return rect


def _picture_rect(page, cap):
    """Bounding box of the picture that belongs to a caption rectangle."""
    import pymupdf

    page_h = page.rect.height

    def near(r) -> float | None:
        if r.width < MIN_SIDE or r.height < MIN_SIDE:
            return None
        # Running headers/footers and banner decorations are not figures.
        if r.y1 < page_h * 0.1 or r.y0 > page_h * 0.92 or r.width > 6 * r.height:
            return None
        if r.y1 > cap.y1 + 10:  # picture must end above (or beside) the caption
            return None
        overlap = min(r.x1, cap.x1 + 150) - max(r.x0, cap.x0 - 150)
        if overlap <= 0:
            return None
        gap = cap.y0 - r.y1
        return gap if -40 <= gap <= MAX_GAP else None

    best, best_gap = None, None
    images = [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    drawings = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()]
    for r in images:
        g = near(r)
        if g is not None and (best_gap is None or g < best_gap):
            best, best_gap = r, g
    if best is not None:
        return _grow(best, images + drawings, cap, header_line=page_h * 0.1)
    # Vector drawing ("chizma"): union of the drawing paths just above the caption.
    rect = None
    for d in page.get_drawings():
        r = pymupdf.Rect(d["rect"])
        if r.y1 <= cap.y0 + 5 and cap.y0 - r.y1 <= MAX_GAP:
            overlap = min(r.x1, cap.x1 + 150) - max(r.x0, cap.x0 - 150)
            if overlap > 0:
                rect = r if rect is None else rect | r
    if rect is not None and rect.width >= MIN_SIDE and rect.height >= MIN_SIDE:
        return rect
    return None


def extract_figures(
    pdf: Path, figures: list[Figure], out_dir: Path, zoom: float = 2.0
) -> list[Figure]:
    """Cut each figure's picture out of the PDF into out_dir; returns those that worked."""
    import pymupdf

    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    with pymupdf.open(str(pdf)) as doc:
        for f in figures:
            if not 1 <= f.page <= doc.page_count:
                continue
            page = doc[f.page - 1]
            cap = _caption_rect(page, f.number)
            if cap is None:
                continue
            rect = _picture_rect(page, cap)
            if rect is None:
                continue
            rect = (rect + (-4, -4, 4, 4)) & page.rect
            path = out_dir / f"rasm_{f.page}_{f.number}.png"
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect)
            # The caption IS the answer: paint it out wherever it falls inside the crop.
            # Paint the caption's words tightly (a whole text block can overlap the picture).
            blocks = _caption_blocks(page, cap)
            word_rects = []
            for w in page.get_text("words"):
                r = pymupdf.Rect(w[:4])
                centre = (r.tl + r.br) / 2
                # Only real caption words: centre inside the caption block, word-sized
                # (a page watermark is one "word" as big as the page).
                if r.height < 40 and r.width < 300 and any(b.contains(centre) for b in blocks):
                    word_rects.append(r + (-1, -1, 1, 1))
            for word in word_rects:
                inside = word & rect
                if not inside.is_empty:
                    # A clipped pixmap keeps page coordinates (scaled): no offset to subtract.
                    box = inside * pymupdf.Matrix(zoom, zoom)
                    pix.set_rect(box.irect, (255, 255, 255))
            if not _looks_like_picture(page, rect, pix):
                continue  # a wrong picture is worse than no picture question
            pix.save(str(path))
            f.image = path
            done.append(f)
    return done


def _looks_like_picture(page, rect, pix) -> bool:
    """Reject crops that are mostly blank or mostly running text."""
    import pymupdf

    words = [w for w in page.get_text("words") if pymupdf.Rect(w[:4]).intersects(rect)]
    if len(words) > 40:
        return False
    samples = pix.samples
    n = pix.n
    step = max(1, (len(samples) // n) // 4000) * n  # ~4000 sampled pixels
    ink = total = 0
    for i in range(0, len(samples) - n + 1, step):
        total += 1
        if min(samples[i : i + 3]) < 235:  # not (near) white
            ink += 1
    return total > 0 and ink / total >= 0.05


def _caption_blocks(page, cap) -> list:
    """Text block(s) holding the caption (it may wrap onto the next line)."""
    import pymupdf

    blocks = []
    for x0, y0, x1, y1, *_ in page.get_text("blocks"):
        b = pymupdf.Rect(x0, y0, x1, y1)
        # Skip page-sized blocks (e.g. an invisible "http:eduportal.uz" watermark).
        if b.height < 80 and b.width < page.rect.width * 0.95:
            blocks.append(b)
    first = next((b for b in blocks if b.contains((cap.tl + cap.br) / 2)), None)
    if first is None:
        return [cap + (-2, -2, 200, 2)]
    out = [first]
    for b in blocks:  # a wrapped caption continues in the block right below
        if b is not first and abs(b.y0 - first.y1) < 4 and b.x0 < first.x1 and b.x1 > first.x0:
            out.append(b)
    return [b + (-2, -2, 2, 2) for b in out]
