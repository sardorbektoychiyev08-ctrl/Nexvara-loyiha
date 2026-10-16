"""A small synthetic textbook (written for tests, not copied from any real book) and a
dependency-free PDF writer, so the library pipeline can be tested without real textbooks."""

from __future__ import annotations

from pathlib import Path

PAGES = [
    """7-sinf FIZIKA
Umumiy o'rta ta'lim maktablarining 7-sinfi uchun darslik
Toshkent - 2024""",
    """1-§. MEXANIK HARAKAT
Jismning boshqa jismlarga nisbatan vaziyatining vaqt o'tishi bilan o'zgarishi mexanik harakat deb ataladi.
Harakat qaysi jismga nisbatan kuzatilayotgan bo'lsa, o'sha jism sanoq jismi deb ataladi.
Trayektoriya - moddiy nuqtaning harakat davomida chizgan chizig'i hisoblanadi.
Moddiy nuqta - o'lchamlari hisobga olinmaydigan darajada kichik deb qaraladigan jism.
Yo'l - jismning trayektoriya bo'ylab bosib o'tgan masofasining uzunligidir.
Galiley 1638-yilda erkin tushish haqidagi kitobini nashr etgan.""",
    """2-§. TEZLIK VA KUCH
Tezlik - jismning vaqt birligi ichida bosib o'tgan yo'liga son jihatdan teng kattalik.
Kuch deb bir jismning boshqa jismga ta'sirini tavsiflovchi vektor kattalikka aytiladi.
Massa - jismning inertligini tavsiflovchi fizik kattalik hisoblanadi.
Isaak Nyuton harakat qonunlarini 1687-yilda e'lon qilgan va ular mexanikaning asosi bo'ldi.
Inersiya - jismning tezligini o'zgarmas saqlash xususiyati deb tushuntiriladi.
Ishqalanish kuchi - bir jism ikkinchi jism sirtida harakatlanganda paydo bo'ladigan kuch.
Birinchi temir yo'l poyezdi 1825-yilda Angliyada yo'lga chiqqan edi.""",
    """3-§. BOSIM
Bosim - sirtga tik ta'sir etuvchi kuchning shu sirt yuziga nisbatiga teng kattalik.
Atmosfera bosimini birinchi bo'lib Torrichelli 1643-yilda tajribada o'lchagan.
Paskal qonuni suyuqlik va gazlarda bosim har tomonga bir xil uzatilishini ifodalaydi.
Arximed kuchi - suyuqlikka botirilgan jismni yuqoriga itaruvchi kuch hisoblanadi.
Gidravlik press 1795-yilda ixtiro qilingan va sanoatda keng tarqalgan.""",
]


def _pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, pages: list[str] = PAGES) -> Path:
    """Minimal multi-page PDF with Helvetica text (ASCII only)."""
    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    pages_id = len(objects) + 1 + 2 * len(pages)  # reserved after pages and their streams
    for text in pages:
        lines = text.split("\n")
        ops = ["BT", "/F1 10 Tf", "40 800 Td", "14 TL"]
        for line in lines:
            ops.append(f"({_pdf_escape(line)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_id, font, content)
            )
        )
    kids = " ".join(f"{i} 0 R" for i in page_ids).encode()
    assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))) == pages_id
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        xref,
    )
    path.write_bytes(bytes(out))
    return path
