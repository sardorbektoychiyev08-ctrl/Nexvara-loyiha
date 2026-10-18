"""Ready office documents filled from the phone: ariza, tushuntirish xati, ma’lumotnoma,
xizmat xati, buyruq, tavsifnoma. Word writes them live on the PC screen, then DOCX + PDF.

`render()` is plain data (testable without Word); `write()` drives Word.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.core.task import UserError

F = tuple[str, str, str]  # key, label, example

TEMPLATES: dict[str, dict[str, Any]] = {
    "ariza_tatil": {
        "title": "Ariza (ta’til)",
        "group": "Ariza",
        "fields": [
            ("kimga", "Kimga (lavozim, ism)", "Maktab direktori A. Karimovga"),
            ("kimdan", "Kimdan (lavozim, ism)", "fizika o‘qituvchisi N. Toychiyevadan"),
            ("kunlar", "Necha kun", "3"),
            ("boshlanish", "Qachondan", "20.10.2026"),
            ("sabab", "Sabab", "oilaviy sharoit"),
        ],
    },
    "ariza_ishga": {
        "title": "Ariza (ishga qabul)",
        "group": "Ariza",
        "fields": [
            ("kimga", "Kimga", "Maktab direktori A. Karimovga"),
            ("kimdan", "Kimdan", "Toychiyeva Nilufardan"),
            ("lavozim", "Lavozim", "fizika fani o‘qituvchisi"),
            ("boshlanish", "Qachondan", "01.11.2026"),
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


def render(tid: str, fields: dict[str, str]) -> list[tuple[str, str]]:
    """[(kind, text)] with kind: right (address block), title, body, list, sign."""
    t = TEMPLATES.get(tid)
    if t is None:
        raise LookupError("Shablon topilmadi")
    f = {
        k: re.sub(r"[\x00-\x08\x0b-\x1f]", "", str(fields.get(k, "")).strip())[:1500]
        for k, _l, _e in t["fields"]
    }
    missing = [lab for k, lab, _e in t["fields"] if not f[k]]
    if missing:
        raise UserError("To‘ldiring: " + ", ".join(missing))
    today = time.strftime("%d.%m.%Y")
    sign = ("sign", f"{today}                                        ______________ (imzo)")
    if tid == "ariza_tatil":
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "ARIZA"),
            (
                "body",
                f"Sizdan {f['boshlanish']} dan boshlab {f['kunlar']} kunlik ta’til berishingizni "
                f"so‘rayman. Sabab: {f['sabab']}.",
            ),
            sign,
        ]
    if tid == "ariza_ishga":
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "ARIZA"),
            (
                "body",
                f"Meni {f['boshlanish']} dan boshlab {f['lavozim']} lavozimiga ishga qabul "
                "qilishingizni so‘rayman.",
            ),
            sign,
        ]
    if tid == "tushuntirish":
        return [
            ("right", f["kimga"]),
            ("right", f["kimdan"]),
            ("title", "TUSHUNTIRISH XATI"),
            (
                "body",
                f"Men {f['voqea']} bo‘yicha quyidagilarni ma’lum qilaman: {f['sabab']}. "
                "Bunday holat takrorlanmasligiga harakat qilaman.",
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
            for kind, text in blocks:
                task.check_cancelled()
                if kind == "right":
                    ops.add_paragraph(doc, text, align="right", size=13)
                elif kind == "title":
                    ops.add_paragraph(doc, text, align="center", bold=True, size=14)
                elif kind == "list":
                    ops.add_bullets(doc, [text], numbered=True)
                elif kind == "sign":
                    ops.add_paragraph(doc, "")
                    ops.add_paragraph(doc, text, align="left", size=12)
                else:
                    ops.add_paragraph(doc, text, align="justify", size=13)
            s.detail = f"{len(blocks)} ta qism"
        with task.step("Saqlash: DOCX va PDF"):
            docx = w.save_as(doc, out)
            pdf = ops.export_pdf(doc, out.with_suffix(".pdf"))
        if visible:
            w.show()
    return {"path": str(docx), "pdf": str(pdf), "report": [TEMPLATES[tid]["title"]]}
