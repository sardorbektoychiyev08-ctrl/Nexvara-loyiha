"""Ready office documents filled from the phone: ariza, tushuntirish xati, ma’lumotnoma,
xizmat xati, buyruq, tavsifnoma. Word writes them live on the PC screen, then DOCX + PDF.

`render()` is plain data (testable without Word); `write()` drives Word.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.core.task import UserError

F = tuple[str, str, str]  # key, label, example

TEMPLATES: dict[str, dict[str, Any]] = {
    "ariza_umumiy": {
        "title": "Ariza (umumiy)",
        "group": "Ariza",
        "fields": [
            ("kimga", "Kimga (tashkilot, lavozim, ism)", "21-maktab direktori A. Karimovga"),
            ("kimdan", "Kimdan (lavozim va to‘liq ism)", "o‘qituvchi Toychiyeva Nilufardan"),
            (
                "murojaat",
                "Aniq iltimos",
                "Menga ish joyimdan ma’lumotnoma berishingizni so‘rayman.",
            ),
            ("arizachi", "Imzo yonidagi F.I.Sh.", "Toychiyeva Nilufar"),
        ],
    },
    "ariza_tatil": {
        "title": "Ariza (ta’til)",
        "group": "Ariza",
        "fields": [
            ("kimga", "Kimga (lavozim, ism)", "Maktab direktori A. Karimovga"),
            (
                "kimdan",
                "Kimdan (lavozim va to‘liq ism)",
                "fizika o‘qituvchisi Toychiyeva Nilufardan",
            ),
            ("boshlanish", "Boshlanish sanasi (kun.oy.yil)", "20.10.2026"),
            ("kunlar", "Kalendar kunlar soni", "3"),
            ("tatil_turi", "Ta’til turi", "ish haqi saqlanmaydigan ta’til"),
            ("sabab", "Sabab", "oilaviy sharoit"),
            ("arizachi", "Imzo yonidagi F.I.Sh.", "Toychiyeva Nilufar"),
        ],
    },
    "ariza_ishga": {
        "title": "Ariza (ishga qabul)",
        "group": "Ariza",
        "fields": [
            ("kimga", "Kimga", "Maktab direktori A. Karimovga"),
            ("kimdan", "Kimdan (to‘liq ism)", "Toychiyeva Nilufardan"),
            ("lavozim", "Lavozim nomi", "fizika fani o‘qituvchisi"),
            ("boshlanish", "Ish boshlash sanasi (kun.oy.yil)", "01.11.2026"),
            ("arizachi", "Imzo yonidagi F.I.Sh.", "Toychiyeva Nilufar"),
        ],
    },
    "tushuntirish": {
        "title": "Tushuntirish xati",
        "group": "Xat",
        "fields": [
            ("kimga", "Kimga", "Maktab direktori A. Karimovga"),
            ("kimdan", "Kimdan", "fizika o‘qituvchisi N. Toychiyevadan"),
            ("voqea", "Nima haqida", "17.10.2026 kuni darsga kechikkanim"),
            ("sabab", "Sabab", "jamoat transporti kechikdi"),
        ],
    },
    "malumotnoma": {
        "title": "Ma’lumotnoma",
        "group": "Hujjat",
        "fields": [
            ("tashkilot", "Tashkilot", "21-umumta’lim maktabi"),
            ("kimga", "Kim haqida", "Toychiyeva Nilufar"),
            ("lavozim", "Lavozimi", "fizika fani o‘qituvchisi"),
            ("qachondan", "Qachondan ishlaydi", "2018-yil"),
            ("maqsad", "Qayerga beriladi", "talab qilingan joyga"),
        ],
    },
    "xizmat_xati": {
        "title": "Xizmat xati",
        "group": "Xat",
        "fields": [
            ("kimga", "Kimga", "Tuman XTB mudiri"),
            ("kimdan", "Kimdan", "21-maktab direktori"),
            ("mavzu", "Mavzu", "o‘quv qurollari bilan ta’minlash"),
            (
                "matn",
                "Asosiy matn",
                "Maktabimiz fizika xonasi uchun 10 ta laboratoriya to‘plami "
                "zarur. Ko‘maklashishingizni so‘raymiz.",
            ),
        ],
    },
    "buyruq": {
        "title": "Buyruq",
        "group": "Hujjat",
        "fields": [
            ("tashkilot", "Tashkilot", "21-umumta’lim maktabi"),
            ("raqam", "Buyruq raqami", "45"),
            ("mavzu", "Mavzu", "fan haftaligini o‘tkazish to‘g‘risida"),
            ("asos", "Asos", "maktab yillik ish rejasi"),
            (
                "bandlar",
                "Bandlar (har qatorda bittadan)",
                "Fizika fani haftaligi 21–26-oktabr kunlari o‘tkazilsin.\nMas’ul: N. Toychiyeva.",
            ),
            ("rahbar", "Rahbar", "Direktor A. Karimov"),
        ],
    },
    "tavsifnoma": {
        "title": "Tavsifnoma (o‘quvchi)",
        "group": "Hujjat",
        "fields": [
            ("kimga", "O‘quvchi", "Aliyev Vali"),
            ("sinf", "Sinf", "7-B"),
            ("tashkilot", "Maktab", "21-umumta’lim maktabi"),
            (
                "matn",
                "Tavsif",
                "Darslarga muntazam qatnashadi, fizika faniga qiziqishi yuqori, "
                "jamoat ishlarida faol.",
            ),
            ("rahbar", "Sinf rahbari", "N. Toychiyeva"),
        ],
    },
}


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": k,
            "title": v["title"],
            "group": v["group"],
            "fields": [{"key": a, "label": b, "example": c} for a, b, c in v["fields"]],
        }
        for k, v in TEMPLATES.items()
    ]


_MONTHS = (
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentabr",
    "oktabr",
    "noyabr",
    "dekabr",
)


def _start_date(value: str) -> str:
    """A date with an Uzbek ablative suffix, without the erroneous '20.10.2026 dan'."""
    try:
        date = datetime.strptime(value, "%d.%m.%Y")
    except ValueError as e:
        raise UserError("Sanani kun.oy.yil shaklida kiriting, masalan 20.10.2026") from e
    return f"{date.year}-yil {date.day}-{_MONTHS[date.month - 1]}dan"


def _sentence(value: str) -> str:
    value = value.strip()
    return value if value.endswith((".", "!", "?")) else value + "."


def render(tid: str, fields: dict[str, str]) -> list[tuple[str, str]]:
    """[(kind, text)] with kind: right (address block), title, body, list, sign."""
    t = TEMPLATES.get(tid)
    if t is None:
        raise LookupError("Shablon topilmadi")
    if not isinstance(fields, dict):
        raise UserError("Hujjat maydonlari noto‘g‘ri")
    f = {}
    for k, _l, _e in t["fields"]:
        raw = fields.get(k)
        value = "" if raw is None else str(raw)
        value = re.sub(r"[\x00-\x08\x0b-\x1f]", "", value).strip()
        if k not in ("matn", "bandlar"):
            value = re.sub(r"\s+", " ", value)
        f[k] = value[: 1500 if k in ("matn", "bandlar") else 250]
    missing = [lab for k, lab, _e in t["fields"] if not f[k]]
    if missing:
        raise UserError("To‘ldiring: " + ", ".join(missing))
    today = time.strftime("%d.%m.%Y")
    sign = ("sign", f"{today}\t______________ (imzo)")
    if tid == "ariza_umumiy":
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "ARIZA"),
            ("body", _sentence(f["murojaat"])),
            ("sign", f"{today}\t______________  {f['arizachi']}"),
        ]
    if tid == "ariza_tatil":
        try:
            days = int(f["kunlar"])
        except ValueError as e:
            raise UserError("Ta’til kunlari butun son bo‘lishi kerak") from e
        if not 1 <= days <= 365:
            raise UserError("Ta’til kunlari 1 dan 365 gacha bo‘lishi kerak")
        start = _start_date(f["boshlanish"])
        leave = f["tatil_turi"].rstrip(". ")
        if not leave.lower().endswith("ta’til") and not leave.lower().endswith("ta'til"):
            raise UserError("Ta’til turini aniq yozing, masalan «mehnat ta’tili»")
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "ARIZA"),
            (
                "body",
                f"Menga {start} boshlab {days} kalendar kun muddatga {leave} "
                f"berishingizni so‘rayman. Sabab: {_sentence(f['sabab'])}",
            ),
            ("sign", f"{today}\t______________  {f['arizachi']}"),
        ]
    if tid == "ariza_ishga":
        start = _start_date(f["boshlanish"])
        position = re.sub(r"\s+lavozimi(?:ga)?$", "", f["lavozim"], flags=re.IGNORECASE)
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "ARIZA"),
            (
                "body",
                f"Meni {start} boshlab {position} lavozimiga ishga qabul qilishingizni so‘rayman.",
            ),
            ("sign", f"{today}\t______________  {f['arizachi']}"),
        ]
    if tid == "tushuntirish":
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "TUSHUNTIRISH XATI"),
            (
                "body",
                f"{f['voqea'].rstrip('. ')} yuzasidan quyidagilarni ma’lum qilaman: "
                f"{_sentence(f['sabab'])}",
            ),
            sign,
        ]
    if tid == "malumotnoma":
        return [
            ("title", f["tashkilot"].upper()),
            ("title", "MA’LUMOTNOMA"),
            (
                "body",
                f"Ushbu ma’lumotnoma {f['kimga']} haqiqatan ham {f['tashkilot']}da "
                f"{f['qachondan']}dan buyon {f['lavozim']} lavozimida ishlayotganini tasdiqlaydi.",
            ),
            ("body", f"Ma’lumotnoma {f['maqsad']} taqdim etish uchun berildi."),
            sign,
        ]
    if tid == "xizmat_xati":
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "XIZMAT XATI"),
            ("body", f"Mavzu: {f['mavzu']}."),
            ("body", f["matn"]),
            sign,
        ]
    if tid == "buyruq":
        items = [x.strip() for x in f["bandlar"].splitlines() if x.strip()]
        return [
            ("title", f["tashkilot"].upper()),
            ("title", f"BUYRUQ № {f['raqam']}"),
            ("body", f"{today}"),
            ("title", f["mavzu"].capitalize()),
            ("body", f"Asos: {f['asos']}."),
            ("body", "BUYURAMAN:"),
            *[("list", x) for x in items],
            ("sign", f"{f['rahbar']}            ______________"),
        ]
    if tid == "tavsifnoma":
        return [
            ("title", "TAVSIFNOMA"),
            ("body", f"{f['tashkilot']} {f['sinf']} sinf o‘quvchisi {f['kimga']}ga"),
            ("body", f["matn"]),
            ("sign", f"Sinf rahbari: {f['rahbar']}   ______________   {today}"),
        ]
    raise LookupError("Shablon topilmadi")


def out_dir() -> Path:
    p = config.data_dir() / "Hujjatlar"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write(
    task: Any,
    tid: str,
    blocks: list[tuple[str, str]],
    out: Path,
    visible: bool = True,
    keep_open: bool = True,
) -> dict[str, Any]:
    from nexvara.skills.word import ops
    from nexvara.skills.word.ops import WordSession

    with task.step("Word’ni ochish"), WordSession(visible=visible, keep_open=keep_open) as w:
        doc = w.new_document()
        with task.step("Hujjatni yozish") as s:
            ops.page_setup(doc)
            item_no = 0
            for kind, text in blocks:
                task.check_cancelled()
                if kind == "right":
                    para = ops.add_paragraph(doc, text, align="right", size=14)
                    para.Range.ParagraphFormat.LeftIndent = ops.cm_to_pt(7)
                    para.Range.ParagraphFormat.SpaceAfter = 0
                elif kind == "title":
                    para = ops.add_paragraph(doc, text, align="center", bold=True, size=14)
                    para.Range.ParagraphFormat.SpaceBefore = 16
                    para.Range.ParagraphFormat.SpaceAfter = 16
                elif kind == "list":
                    item_no += 1
                    para = ops.add_paragraph(doc, f"{item_no}. {text}", size=14)
                    para.Range.ParagraphFormat.LeftIndent = ops.cm_to_pt(1)
                elif kind == "sign":
                    para = ops.add_paragraph(doc, text, align="left", size=12)
                    para.Range.ParagraphFormat.SpaceBefore = 22
                    para.Range.ParagraphFormat.TabStops.Add(ops.cm_to_pt(16), 2, 0)
                else:
                    para = ops.add_paragraph(doc, text, align="justify", size=14)
                    para.Range.ParagraphFormat.FirstLineIndent = ops.cm_to_pt(1.25)
                    para.Range.ParagraphFormat.SpaceAfter = 8
                para.Range.Font.Name = "Times New Roman"
                para.Range.ParagraphFormat.LineSpacingRule = 1  # 1.5 lines
            s.detail = f"{len(blocks)} ta qism"
        with task.step("Saqlash: DOCX va PDF"):
            docx = w.save_as(doc, out)
            pdf = ops.export_pdf(doc, out.with_suffix(".pdf"))
            if not docx.is_file() or pdf.read_bytes()[:5] != b"%PDF-":
                raise RuntimeError("Hujjat yoki PDF saqlanmadi")
        if visible:
            w.show()
    return {"path": str(docx), "pdf": str(pdf), "report": [TEMPLATES[tid]["title"]],
            "checks": [{"name": "DOCX va PDF saqlandi", "ok": True}]}  # fmt: skip
