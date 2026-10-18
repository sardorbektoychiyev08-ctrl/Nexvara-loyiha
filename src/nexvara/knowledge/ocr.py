"""OCR for scanned textbooks with the OCR engine built into Windows (no install, no API).

Windows ships recognizers per language; Uzbek Latin text is read well by the English one,
Cyrillic books by the Russian one. Pages are rendered with PyMuPDF.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

ZOOM = 2.5  # ~180 dpi: good accuracy at ~0.2 s per page


def available() -> list[str]:
    """Recognizer languages Windows offers ("en-US", "ru", ...); [] if OCR is unavailable."""
    try:
        import pymupdf  # noqa: F401
        from winrt.windows.media.ocr import OcrEngine

        return [lang.language_tag for lang in OcrEngine.available_recognizer_languages]
    except Exception as e:  # not Windows 10+, or packages missing
        log.info("OCR unavailable: %s", e)
        return []


def pick_language(file_name: str, langs: list[str]) -> str | None:
    want = "ru" if "rus" in file_name.lower() else "en"
    for lang in langs:
        if lang.lower().startswith(want):
            return lang
    return langs[0] if langs else None


async def _ocr_png(png: bytes, engine) -> str:
    from winrt.windows.graphics.imaging import (
        BitmapAlphaMode,
        BitmapDecoder,
        BitmapPixelFormat,
        SoftwareBitmap,
    )
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(png)
    await writer.store_async()
    await writer.flush_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bmp = await decoder.get_software_bitmap_async()
    if bmp.bitmap_pixel_format != BitmapPixelFormat.BGRA8:
        bmp = SoftwareBitmap.convert(bmp, BitmapPixelFormat.BGRA8, BitmapAlphaMode.PREMULTIPLIED)
    result = await engine.recognize_async(bmp)
    return "\n".join(line.text for line in result.lines)


def ocr_pdf(
    path: Path,
    language: str,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> list[str]:
    """Text of every page (raw OCR lines joined by newlines)."""
    import pymupdf
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    engine = OcrEngine.try_create_from_language(Language(language))
    if engine is None:
        raise RuntimeError(f"OCR tili mavjud emas: {language}")

    async def run() -> list[str]:
        out = []
        with pymupdf.open(str(path)) as doc:
            for i, page in enumerate(doc, start=1):
                if cancelled and cancelled():
                    break
                png = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM)).tobytes("png")
                try:
                    out.append(await _ocr_png(png, engine))
                except Exception as e:  # one bad page must not lose the book
                    log.warning("%s page %s OCR failed: %s", path.name, i, e)
                    out.append("")
                if progress:
                    progress(i, doc.page_count)
        return out

    return asyncio.run(run())


def _enhance(pix):
    """Grayscale, contrast stretched (2nd..98th percentile), small photos enlarged: Windows OCR
    reads phone photos of paper (grey, uneven light) much better this way."""
    import pymupdf

    if pix.n - pix.alpha != 1:
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    side = max(pix.width, pix.height)
    if side < 1800:  # small or cropped photo: twice the size gives the recognizer more pixels
        f = min(3.0, 2400 / side)
        pix = pymupdf.Pixmap(pix, int(pix.width * f), int(pix.height * f), None)
    while max(pix.width, pix.height) > 4500:
        pix.shrink(1)
    data = bytes(pix.samples)
    hist = [0] * 256
    for v in data[:: max(1, len(data) // 300_000)]:
        hist[v] += 1
    total, acc, lo, hi = sum(hist), 0, 0, 255
    for v, c in enumerate(hist):
        acc += c
        if acc <= total * 0.02:
            lo = v
        if acc <= total * 0.98:
            hi = v
    if hi - lo > 20:
        table = bytes(max(0, min(255, int((v - lo) * 255 / (hi - lo)))) for v in range(256))
        pix = pymupdf.Pixmap(pymupdf.csGRAY, pix.width, pix.height, data.translate(table), False)
    return pix


_LATIN = re.compile(r"^[A-Za-z‘’ʻʼ'`-]{2,}$")
_CYR = re.compile(r"^[Ѐ-ӿ-]{2,}$")


def score(text: str, script: str) -> int:
    """How much of `text` looks like real words of that script (garbage scores low)."""
    rx = _LATIN if script == "latin" else _CYR
    return sum(len(w) for w in re.findall(r"\S+", text) if rx.match(w.strip('.,;:!?()«»"')))


def tidy(text: str) -> str:
    """OCR lines → readable text: hyphenated words joined, wrapped lines merged into
    paragraphs, Uzbek o‘/g‘ apostrophes unified."""
    text = re.sub(r"(?<=[oOgG])['`’ʼʻ]", "‘", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    out: list[str] = []
    for line in (x.strip() for x in text.splitlines()):
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        ends = re.search(r"[.!?:;»\")]$", out[-1]) if out and out[-1] else True
        if not ends and (line[0].islower() or line[0] in ",;"):
            out[-1] += " " + line
        else:
            out.append(line)
    return "\n".join(out).strip()


def ocr_image(path: Path, language: str = "") -> str:
    """Text of a photo (a textbook page, a document) with the Windows OCR engine, offline.

    The photo is enhanced first; `language` "uz"/"en" = Latin, "ru" = Cyrillic, empty = both
    engines run and the result that reads as more real words wins."""
    import pymupdf
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    langs = available()
    if not langs:
        raise RuntimeError("Windows OCR mavjud emas")
    png = _enhance(pymupdf.Pixmap(Path(path).read_bytes())).tobytes("png")

    def run(tag: str) -> str:
        engine = OcrEngine.try_create_from_language(Language(tag))
        if engine is None:
            return ""
        return asyncio.run(_ocr_png(png, engine))

    want = ["ru"] if language == "ru" else ["en"] if language in ("uz", "en") else ["en", "ru"]
    best, best_score = "", -1
    for w in want:
        tag = next((x for x in langs if x.lower().startswith(w)), None)
        if tag is None:
            continue
        text = run(tag)
        sc = score(text, "cyrillic" if w == "ru" else "latin")
        if sc > best_score:
            best, best_score = text, sc
    return tidy(best)
