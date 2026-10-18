"""OCR for scanned textbooks with the OCR engine built into Windows (no install, no API).

Windows ships recognizers per language; Uzbek Latin text is read well by the English one,
Cyrillic books by the Russian one. Pages are rendered with PyMuPDF.
"""

from __future__ import annotations

import asyncio
import logging
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


def ocr_image(path: Path, language: str = "") -> str:
    """Text of a photo (a textbook page, a document) with the Windows OCR engine.

    `language`: "uz"/"en" read Latin text (Uzbek Latin is read well by the English engine),
    "ru" Cyrillic; empty = Latin first, Cyrillic if that finds almost nothing."""
    import pymupdf
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    langs = available()
    if not langs:
        raise RuntimeError("Windows OCR mavjud emas")
    pix = pymupdf.Pixmap(Path(path).read_bytes())
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    while max(pix.width, pix.height) > 4000:
        pix.shrink(1)
    png = pix.tobytes("png")

    def run(tag: str) -> str:
        engine = OcrEngine.try_create_from_language(Language(tag))
        if engine is None:
            return ""
        return asyncio.run(_ocr_png(png, engine))

    want = ["ru"] if language == "ru" else ["en"] if language in ("uz", "en") else ["en", "ru"]
    best = ""
    for w in want:
        tag = next((x for x in langs if x.lower().startswith(w)), None)
        if tag is None:
            continue
        text = run(tag)
        if len(text.strip()) > len(best.strip()):
            best = text
        if language or len(best.strip()) > 40:
            break
    return best
