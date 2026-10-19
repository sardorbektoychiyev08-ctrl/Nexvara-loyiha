# ruff: noqa: E501 - the book text is data
"""The illustrated NEXVARA user guide (Uzbek) as Word + PDF, built in real Word.

    python scripts\\guide_shots.py D:\\NEXVARA\\Qollanma\\rasmlar     # desktop screenshots
    python scripts\\make_guide.py  D:\\NEXVARA\\Qollanma              # the book

Phone pictures (20_tel_*.png ...) are taken from a real phone with adb and put in the same
`rasmlar` folder. The text follows docs/QOLLANMA.md.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nexvara import __version__  # noqa: E402
from nexvara.skills.word import ops  # noqa: E402
from nexvara.skills.word.ops import WordSession  # noqa: E402

H1, H2, P, B, N, IMG, TWO, TAB, BRK, TIP = (
    "h1", "h2", "p", "b", "n", "img", "two", "tab", "brk", "tip")  # fmt: skip

BOOK: list[tuple[Any, ...]] = [
    (H1, "1. NEXVARA nima?"),
    (P, "NEXVARA — kompyuteringizdagi yordamchi. Siz unga oddiy o‘zbek tilida buyruq yozasiz yoki "
        "aytasiz, u esa ishni o‘zi bajaradi: Excel jadvalini tartibga soladi, Word hujjatini "
        "rasmiylashtiradi, PowerPoint taqdimot tayyorlaydi, darslikdan test tuzadi, hisobot va "
        "chizma qiladi. Hammasi kompyuter ekranida ko‘rinib turadi — nima bo‘layotganini o‘zingiz "
        "kuzatasiz."),
    (P, "Telefondagi NEXVARA ilovasi orqali buyruqni telefondan ham berasiz, kompyuter ekranini "
        "ko‘rasiz, fayllarni telefonga olasiz."),
    (B, ["Office: Excel, Word, PowerPoint ishlari", "O‘qituvchi uchun: darslikdan test, mavzu, "
         "javob varaqasi, jurnal", "Fayllar: qidirish, ZIP, PDF, ko‘chirish, zaxira",
         "NEXVARA BI: jadvaldan chiroyli hisobot paneli", "Chizmalar: AutoCAD (DXF), PDF, Word",
         "Telefon: masofadan boshqarish, sensorli panel, fayllar",
         "AI (ixtiyoriy): murakkab buyruqlar, tarjima, rasm, ovoz, internetdan qidirish"]),
    (TIP, "Eslab qoling: NEXVARA hech qachon faylingiz ustidan yozmaydi. Natija har doim yangi "
          "faylga saqlanadi (masalan «Baholar_NEXVARA.xlsx»), asl fayl o‘zgarmaydi."),
    (BRK,),
    (H1, "2. O‘rnatish va birinchi ishga tushirish"),
    (N, ["«NEXVARA-Setup-…exe» faylini ishga tushiring. Windows «noma’lum nashriyotchi» desa: "
         "«Batafsil» → «Baribir ishga tushirish».",
         "O‘rnatish tugagach, ish stolidagi NEXVARA belgisini bosing.",
         "Birinchi marta ochilganda qisqa yordamchi chiqadi — 4 qadam."]),
    (IMG, "01_yordamchi_1.png", 13, "1-rasm. Yordamchi: kompyuterda Office bor-yo‘qligi tekshiriladi"),
    (P, "Ikkinchi qadamda telefonni ulashni yoqasiz va NEXVARA Windows bilan birga ishga "
        "tushishini belgilaysiz. Har bir qadamni «O‘tkazib yuborish» mumkin — keyin Sozlamalardan "
        "qilasiz."),
    (IMG, "02_yordamchi_2.png", 13, "2-rasm. Yordamchi: telefon va Windows bilan birga ishga tushish"),
    (TIP, "Sizning ma’lumotlaringiz D:\\NEXVARA papkasida saqlanadi (D: disk bo‘lmasa — "
          "Hujjatlar\\NEXVARA). Dastur yangilansa ham ular joyida qoladi."),
    (BRK,),
    (H1, "3. Bosh sahifa va menyu"),
    (P, "Chap tomonda menyu bor. Bosh sahifada Office holati, AI provayderi, bugungi vazifalar va "
        "AI xarajatlari ko‘rinadi."),
    (IMG, "03_bosh_sahifa.png", 16, "3-rasm. Bosh sahifa"),
    (TAB, [["Bo‘lim", "Nima uchun"],
           ["AI suhbat", "Buyruq yozish yoki aytish — eng ko‘p ishlatiladigan joy"],
           ["Office yordamchisi", "Excel, Word, PowerPoint namunaviy ishlari"],
           ["Darsliklar va testlar", "Darslik yuklash, mavzudan test tuzish"],
           ["Fayllar", "Qidirish, nusxalash, ko‘chirish, ZIP, PDF, zaxira"],
           ["NEXVARA BI", "Jadval yoki bazadan hisobot paneli"],
           ["Chizmalar", "Chizish, AutoCAD (DXF), PDF, Word, albom"],
           ["Ish jarayonlari", "Takrorlanadigan ishlarni avtomatlashtirish"],
           ["NEXVARA’ga o‘rgatish", "«Excel’da doim shunday qil» kabi qoidalar"],
           ["Xotira", "NEXVARA eslab qolgan narsalar"],
           ["Vazifalar va tarix", "Bajarilgan va bajarilayotgan ishlar"],
           ["Qurilmalar", "Telefonni ulash va ruxsatlar"],
           ["Sozlamalar", "AI, sinxronlash, yangilanish, mavzu"]]),
    (BRK,),
    (H1, "4. AI suhbat — buyruq berish"),
    (P, "Pastdagi maydonga buyruqni yozing va «Yuborish» ni bosing. Buyruqni oddiy gap bilan "
        "yozasiz, fayl nomini ham yozing. Bir gapda bir nechta ishni vergul bilan sanash mumkin."),
    (IMG, "04_suhbat.png", 16, "4-rasm. AI suhbat: buyruq va javoblar"),
    (H2, "Tugmalar"),
    (TAB, [["Tugma", "Vazifasi"],
           ["🎤 Gapirish", "Buyruqni ovoz bilan aytasiz"],
           ["🔊 Ovozli javob", "Javobni ovoz chiqarib o‘qib beradi"],
           ["🖼️ Rasm", "Kompyuterdagi rasm haqida savol"],
           ["📷 Kamera", "Kameradan rasm olish"],
           ["✨ Rasm yaratish", "AI rasm chizadi (narxini aytib, «Ha» kutadi)"],
           ["🎧 Jonli suhbat", "Gapirasiz — u ovoz bilan javob beradi"],
           ["🧠 AI tanlash", "AUTO yoki qo‘lda model tanlash"]]),
    (H2, "Buyruq namunalari"),
    (B, ["Baholar.xlsx ni och, jadvalni formatla, B ustun bo‘yicha sarala va PDF qil",
         "7-sinf fizika «Nyuton qonunlari» mavzusidan 20 ta test, 2 variant",
         "Hisobot.docx dagi sarlavhalarni rasmiy ko‘rinishga keltir",
         "hisobot fayllarini top, keyin topilgan fayllarni ZIP qil",
         "internetdan qidir: Toshkentda ertaga ob-havo"]),
    (H2, "🧠 menyusi: AUTO yoki qo‘lda"),
    (P, "AUTO — NEXVARA o‘zi eng arzon (yoki bepul) AI modelini tanlaydi. Qo‘lda — siz tanlagan "
        "model ishlatiladi va hech qachon almashtirilmaydi."),
    (IMG, "05_ai_menyu.png", 16, "5-rasm. 🧠 menyusi: har bir yo‘nalish uchun AUTO yoki qo‘lda"),
    (TIP, "Pullik AI so‘rovidan oldin NEXVARA narxini aytadi va «Ha» deyishingizni kutadi. Ism, "
          "telefon, manzil, karta raqami kabi shaxsiy ma’lumotlar AI’ga yuborilmaydi — "
          "kompyuterda yashiriladi."),
    (BRK,),
    (H1, "5. Office yordamchisi"),
    (P, "Bu sahifada Excel, Word va PowerPoint uchun tayyor namunalar bor. Asosiy ishlar esa AI "
        "suhbat orqali buyruq bilan bajariladi — Office ekranda ochiladi, siz kuzatib turasiz."),
    (IMG, "06_office.png", 16, "6-rasm. Office yordamchisi"),
    (H2, "Excel"),
    (B, ["Savdo.xlsx ni och, tozala, dublikatlarni o‘chir, jami qo‘sh",
         "Summa ustunini pul formatiga o‘tkaz, 1000000 dan katta kataklarni qizil bilan belgila",
         "Baho ustuniga faqat 2 dan 5 gacha butun son kiritilsin",
         "Holat ustuniga tanlash ro‘yxati: Bajarildi, Jarayonda, Bekor",
         "Yanvar.xlsx va Fevral.xlsx ni bitta faylga varaq qilib yig‘",
         "Baholar.xlsx ni tekshir (xato formulalar, bo‘sh qatorlar)"]),
    (H2, "Word"),
    (B, ["Hisobot.docx ni och, matnni kenglik bo‘yicha tekisla, sahifa raqamlarini qo‘y",
         "Hisobot.docx ni och, jarayon sxemasi qo‘sh: Reja, Bajarish, Nazorat",
         "Xat.docx ni ingliz tiliga tarjima qil (AI, yangi faylga)",
         "Hisobot.docx ni rasmiy uslubda qayta yoz (AI)"]),
    (H2, "PowerPoint"),
    (B, ["7-sinf fizika Nyuton qonunlari bo‘yicha taqdimot tayyorla",
         "Taqdimot.pptx ni och, slayd raqamlarini qo‘y va o‘tish effekti qo‘sh",
         "Dars.pptx ni och, aylana sxema qo‘sh: Rejalash, Bajarish, Tekshirish",
         "Taqdimot.pptx ni rus tiliga o‘gir (AI)"]),
    (BRK,),
    (H1, "6. Darsliklar va testlar"),
    (P, "Darslik PDF faylini qo‘shasiz — NEXVARA uni o‘qib, mavzularga ajratadi. Keyin mavzudan "
        "test, savollar, javob varaqasi tuzadi. Oddiy testlar AI’siz va bepul."),
    (IMG, "07_darsliklar.png", 16, "7-rasm. Darsliklar va testlar"),
    (B, ["7-sinf fizika «Nyuton qonunlari» mavzusidan 20 ta test, 2 variant",
         "7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber",
         "AI bilan 5-sinf matematika «Kasrlar» bo‘yicha uyga vazifa va javoblarini tuz"]),
    (BRK,),
    (H1, "7. Fayllar"),
    (P, "Fayl nomidagi so‘zni yozib qidirasiz. Topilgan fayllarni belgilab: ochish, nusxalash, "
        "ko‘chirish, nomlash, ZIP qilish, PDF’ga aylantirish, zaxira olish mumkin."),
    (IMG, "08_fayllar.png", 16, "8-rasm. Fayllar: qidirish va amallar"),
    (TIP, "O‘chirish faqat Savatga va faqat tasdiqdan keyin. Bir xil nomli fayl bo‘lsa, yangi nom "
          "beriladi — hech narsa ustidan yozilmaydi."),
    (BRK,),
    (H1, "8. NEXVARA BI — hisobot paneli"),
    (P, "«Fayl tanlash» ni bosib Excel, CSV yoki ma’lumotlar bazasini (SQLite, Access) "
        "tanlaysiz — NEXVARA o‘zi panel tuzadi: jami summalar, grafiklar, filtrlar. Panelni "
        "saqlash, PDF/Excel qilib eksport qilish mumkin."),
    (IMG, "09_bi.png", 16, "9-rasm. NEXVARA BI: savdo hisoboti paneli"),
    (B, ["Savdo.xlsx dan dashboard qil", "Oylik hisobot panelini 2-sahifada och",
         "Foyda = Daromad - Xarajat ustunini qo‘sh"]),
    (BRK,),
    (H1, "9. Chizmalar"),
    (P, "Chizmalar bo‘limida chizasiz yoki chatda so‘raysiz: «100x60 plastina, markazida 20 mm "
        "teshik chizib ber». Natija AutoCAD DXF (mm), PDF, rasm va Word bo‘lib saqlanadi. Word "
        "faylida chizma ostida o‘lchamlar jadvali bo‘ladi."),
    (IMG, "10_chizma.png", 16, "10-rasm. Chizmalar: to‘rtburchak, teshik va o‘lchamlar"),
    (B, ["chizma.dxf ni PDF qil", "chizma.dxf ni Word qil",
         "chizma.dxf ni Hisobot.docx ga qo‘y (chizma hujjat oxiriga qo‘shiladi)",
         "«Albom» tugmasi — bir nechta chizmani bitta PDF’ga yig‘adi"]),
    (BRK,),
    (H1, "10. Ish jarayonlari, o‘rgatish va xotira"),
    (H2, "Ish jarayonlari"),
    (P, "Har kuni yoki papkaga yangi fayl tushganda o‘zi bajariladigan ishlar. Masalan: "
        "«Hisobotlar papkasiga yangi Excel tushsa — formatla va PDF qil»."),
    (IMG, "11_ish_jarayonlari.png", 15, "11-rasm. Ish jarayonlari"),
    (H2, "NEXVARA’ga o‘rgatish"),
    (P, "O‘z odatlaringizni o‘rgatasiz: «Excel’da raqamlarni doim markazga joyla», «Word’da "
        "shrift doim Times New Roman 14». Keyingi buyruqlarda shu qoida qo‘llanadi."),
    (IMG, "12_orgatish.png", 15, "12-rasm. NEXVARA’ga o‘rgatish"),
    (H2, "Xotira"),
    (P, "NEXVARA siz aytgan muhim narsalarni eslab qoladi: «maktabim 21-maktab», «fanim "
        "fizika». «… ni unut» desangiz — o‘chiradi."),
    (IMG, "13_xotira.png", 15, "13-rasm. Xotira"),
    (BRK,),
    (H1, "11. Vazifalar va tarix"),
    (P, "Har bir ish bosqichma-bosqich ko‘rinadi. Ishni to‘xtatish, davom ettirish yoki bekor "
        "qilish, natija faylini ochish shu yerda."),
    (IMG, "14_vazifalar.png", 16, "14-rasm. Vazifalar va tarix"),
    (BRK,),
    (H1, "12. Telefon"),
    (H2, "Telefonni ulash (bir marta)"),
    (N, ["Kompyuterda: Qurilmalar → «Telefondan boshqarish» → Yoqish. QR kod chiqadi.",
         "Telefonda NEXVARA ilovasini oching → «QR kodni skanerlash».",
         "Telefon va kompyuter bitta Wi‑Fi’da (yoki USB orqali) bo‘lsin. «Xavfsiz emas» desa: "
         "«Qo‘shimcha» → «Davom etish»."]),
    (IMG, "15_qurilmalar.png", 15, "15-rasm. Kompyuterda: Qurilmalar va QR kod"),
    (TWO, ["20_tel_boglash.png", "21_tel_bosh.png"], 5.0,
     "16-rasm. Telefonda: ulash sahifasi va ulangandan keyingi bosh sahifa"),
    (H2, "Kompyuter ekrani va sensorli panel"),
    (P, "«Ekran» bo‘limida kompyuter ekrani jonli ko‘rinadi. Sichqoncha belgisini bossangiz "
        "(barmoq izi so‘raladi) — boshqarish rejimi: ekrandagi joyga bosish yoki «Sensorli panel» "
        "— telefon noutbuk paneli kabi ishlaydi."),
    (TWO, ["22_tel_ekran.png", "23_tel_sensorli.png"], 5.0,
     "17-rasm. Kompyuter ekrani va sensorli panel"),
    (TAB, [["Sensorli panelda", "Natija"],
           ["Barmoqni suring", "Kursor yuradi"], ["Bir bosish", "Chap tugma"],
           ["Ikki marta bosish", "Ochish"], ["Uzoq bosish", "O‘ng tugma"],
           ["Ikki barmoq yuqoriga/pastga", "Aylantirish"],
           ["«Ushlab sudrash»", "Narsani sudrab ko‘chirish"]]),
    (TIP, "Boshqarish uchun kompyuterda Qurilmalar → «Telefon sichqoncha va klaviaturani "
          "boshqarishi mumkin» yoqilgan bo‘lishi kerak."),
    (H2, "Kompyuterdagi fayllar telefonda"),
    (P, "Fayllar → «Kompyuterdan qidirish»: faylni topasiz, kompyuterda ochasiz yoki telefonga "
        "olasiz. Bir nechta faylni belgilab — ZIP qilish, PDF qilish yoki ko‘chirish."),
    (TWO, ["24_tel_fayllar.png", "25_tel_kochirish.png"], 5.0,
     "18-rasm. Kompyuter fayllari: qidirish va ko‘chirish"),
    (H2, "Telefonda chizish"),
    (P, "Chizma bo‘limida barmoq bilan chizasiz — NEXVARA chiziqlarni tekislaydi. Saqlaganda "
        "kompyuterda DXF, PDF, Word va rasm paydo bo‘ladi, ularni telefonga olish mumkin."),
    (TWO, ["26_tel_chizma.png", "27_tel_saqlandi.png"], 5.0,
     "19-rasm. Telefonda chizma va saqlash"),
    (BRK,),
    (H1, "13. Uydan tashqarida ishlatish (Tailscale)"),
    (P, "Oddiy holatda telefon kompyuterga faqat bitta Wi‑Fi’da ulanadi. Boshqa joydan (ishxona, "
        "mobil internet) ishlatish uchun bepul Tailscale dasturi kerak."),
    (N, ["Kompyuterga va telefonga Tailscale o‘rnating.",
         "Ikkalasida bitta hisob bilan kiring.",
         "Kompyuterda NEXVARA → Qurilmalar → «Tailscale uchun ruxsat berish» (chiqsa) → "
         "Windows so‘rovida «Ha».",
         "Telefon bir marta uydagi Wi‑Fi’da ulansin — keyin istalgan joydan ishlaydi."]),
    (TIP, "Tailscale doim yoqiq tursa zarari yo‘q: oddiy internet unga bog‘liq emas, batareyani "
          "kam sarflaydi. Kompyuter yoqilgan va NEXVARA ochiq bo‘lishi kerak."),
    (BRK,),
    (H1, "14. Sozlamalar"),
    (IMG, "16_sozlamalar.png", 16, "20-rasm. Sozlamalar"),
    (H2, "AI"),
    (B, ["Kalit kiritish: OpenAI, Gemini (bepul daraja bor), Claude, DeepSeek.",
         "Kalit Windows himoyalangan xotirasida saqlanadi, faylga yozilmaydi.",
         "Kunlik va oylik limit — NEXVARA undan oshmaydi.",
         "«Bepul rejim» — Gemini’ning bepul darajasi."]),
    (H2, "Sinxronlash"),
    (P, "Bir nechta kompyuteringiz bo‘lsa: eslatmalar, qoidalar va (xohlasangiz) suhbat tarixi "
        "parol bilan shifrlanib, OneDrive yoki Google Drive orqali almashadi."),
    (H2, "Yangilanish"),
    (P, "Yangi versiya chiqsa, bosh sahifada «Yangilash» chiqadi — bosasiz, dastur o‘zi "
        "yangilanib qayta ochiladi. Yangilanish imzo bilan tekshiriladi. Ma’lumotlar har hafta "
        "avtomatik zaxiralanadi (D:\\NEXVARA-zaxira)."),
    (BRK,),
    (H1, "15. Muammo bo‘lsa"),
    (TAB, [["Muammo", "Nima qilish kerak"],
           ["Telefon «Aloqa yo‘q»", "Kompyuterda NEXVARA ochiqmi, «Telefondan boshqarish» "
            "yoqilganmi? Telefon Wi‑Fi’da yoki Tailscale yoqiqmi?"],
           ["QR kod ishlamadi", "Qurilmalar → «Yangi kod», qayta skanerlang"],
           ["«Buning uchun AI kerak»", "Sozlamalar → AI: kalit kiriting, «AI yoqilgan»"],
           ["«Limit tugadi»", "Sozlamalar → AI: limitni oshiring yoki ertaga urining"],
           ["Office oynasi qotib qoldi", "Vazifalar → «Bekor qilish», Office’ni yopib qayta urining"],
           ["Windows «noma’lum nashriyotchi»", "«Batafsil» → «Baribir ishga tushirish»"],
           ["Chizma PDF’da ko‘rinmaydi", "Fayl DXF ekanini tekshiring (DWG’ni AutoCAD’da DXF qiling)"]]),
    (P, "Har qanday ishni NEXVARA bekor qilish mumkin, asl fayllar esa hech qachon "
        "o‘zgartirilmaydi — qo‘rqmasdan sinab ko‘ring."),
]


def _page_break(doc: Any) -> None:
    """A new page after the last paragraph: InsertBreak replaces its range, so it goes into a
    fresh empty paragraph collapsed to its start."""
    ops.add_paragraph(doc, "")
    rng = doc.Paragraphs(doc.Paragraphs.Count).Range
    rng.Collapse(1)  # wdCollapseStart
    rng.InsertBreak(7)  # wdPageBreak


def _caption(doc: Any, text: str) -> None:
    p = ops.add_paragraph(doc, text, align="center", size=9)
    p.Range.Font.Italic = True
    p.Range.Font.Color = 0x6B6B6B


def _picture_cell(doc: Any, cell: Any, image: Path, width_cm: float) -> None:
    rng = cell.Range
    rng.MoveEnd(1, -1)
    shape = doc.InlineShapes.AddPicture(str(image), False, True, rng)  # positional
    ratio = shape.Height / shape.Width
    shape.Width = ops.cm_to_pt(width_cm)
    shape.Height = shape.Width * ratio
    cell.Range.ParagraphFormat.Alignment = 1  # center


def build(out_dir: Path) -> tuple[Path, Path]:
    shots = out_dir / "rasmlar"
    docx, pdf = out_dir / "NEXVARA-qollanma.docx", out_dir / "NEXVARA-qollanma.pdf"
    with WordSession(visible=True, keep_open=False) as w:
        doc = w.new_document()
        ops.page_setup(doc, margins_cm=(2.0, 2.0, 2.0, 2.0))
        # cover
        for _ in range(3):
            ops.add_paragraph(doc, "")
        ops.add_paragraph(doc, "NEXVARA", bold=True, align="center", size=40)
        ops.add_paragraph(doc, "Foydalanish kitobi", align="center", size=22)
        ops.add_paragraph(doc, "Rasmlar bilan, qadam-baqadam", align="center", size=14)
        ops.add_paragraph(doc, "")
        ops.add_picture(doc, shots / "03_bosh_sahifa.png", width_cm=16)
        ops.add_paragraph(doc, "")
        ops.add_paragraph(doc, f"Windows dasturi {__version__} · telefon ilovasi 1.6.0 · "
                          "2026-yil oktabr", align="center", size=11)  # fmt: skip
        _page_break(doc)
        ops.add_paragraph(doc, "Mundarija", bold=True, size=18)
        ops.add_toc_placeholder(doc)
        _page_break(doc)
        for item in BOOK:
            kind = item[0]
            if kind == H1:
                ops.add_heading(doc, item[1], 1)
            elif kind == H2:
                ops.add_heading(doc, item[1], 2)
            elif kind == P:
                ops.add_paragraph(doc, item[1], align="justify")
            elif kind == B:
                ops.add_bullets(doc, item[1])
            elif kind == N:
                for k, line in enumerate(item[1], 1):  # numbering restarts in every list
                    q = ops.add_paragraph(doc, f"{k}. {line}")
                    q.Range.ParagraphFormat.LeftIndent = ops.cm_to_pt(0.8)
                    q.Range.ParagraphFormat.FirstLineIndent = ops.cm_to_pt(-0.6)
            elif kind == IMG:
                ops.add_picture(doc, shots / item[1], width_cm=item[2])
                _caption(doc, item[3])
            elif kind == TWO:
                t = ops.add_table(doc, [["", ""]], header=False)
                t.Borders.Enable = False
                for k, name in enumerate(item[1], 1):
                    _picture_cell(doc, t.Cell(1, k), shots / name, item[2])
                ops.add_paragraph(doc, "")
                _caption(doc, item[3])
            elif kind == TAB:
                ops.add_table(doc, item[1])
                ops.add_paragraph(doc, "")
            elif kind == TIP:
                p = ops.add_paragraph(doc, "💡 " + item[1], size=11)
                p.Range.Font.Color = 0x8B4A1F  # dark blue (BGR)
                p.Range.ParagraphFormat.LeftIndent = ops.cm_to_pt(0.6)
            elif kind == BRK:
                _page_break(doc)
        ops.add_toc(doc, (1, 1))
        ops.set_header(doc, "NEXVARA — foydalanish kitobi")
        ops.add_page_numbers(doc)
        doc.TablesOfContents(1).Update()
        saved = w.save_as(doc, docx, overwrite=True)
        ops.export_pdf(doc, pdf, overwrite=True)
        pages = doc.ComputeStatistics(2)  # wdStatisticPages
        w.disown(doc)
        doc.Close(0)
        del doc
    print(f"Tayyor: {saved} va {pdf}, {pages} sahifa")
    return saved, pdf


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\NEXVARA\Qollanma"))
