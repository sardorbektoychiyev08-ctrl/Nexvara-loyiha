"""How office documents should be made — taken from official sources, used in two ways:

1. as rules in the AI's instructions when it writes or plans office work (`for_prompt`);
2. as automatic checks of a real file («hujjatni tekshir», agent/*_exec.py `check`).

Sources (checked 2026-10-18):
- Microsoft Support, "Make your Excel documents accessible to people with disabilities";
  "Make your Word documents accessible…"; "Make your PowerPoint presentations accessible…"
  (support.microsoft.com).
- O‘zbekiston Respublikasi Vazirlar Mahkamasining 1999-yil 29-martdagi 140-son qarori:
  davlat hokimiyati va boshqaruv organlarida ish yuritish va ijro nazorati bo‘yicha namunaviy
  yo‘riqnoma (lex.uz/acts/-863120): sana, imzo, adresat, ilova, ijrochi, tasdiqlash rekvizitlari.
- «Davlat tilida ish yuritish» o‘quv qo‘llanmasi: A4, Times New Roman 14, 1–1,5 qator, chetlar
  (amaliyotdagi tavsiya; qarorning o‘zida millimetrlar berilmagan).
"""

from __future__ import annotations

import re

SOURCES = {
    "ms_excel": "https://support.microsoft.com/en-us/office/make-your-excel-documents-accessible-"
    "to-people-with-disabilities-6cc05fc5-1314-48b5-8eb3-683e49b3e593",
    "ms_word": "https://support.microsoft.com/en-us/office/make-your-word-documents-accessible-"
    "to-people-with-disabilities-d9bf3683-87ac-47ea-b91a-78dcacb3c66d",
    "ms_ppt": "https://support.microsoft.com/en-us/office/make-your-powerpoint-presentations-"
    "accessible-to-people-with-disabilities-6f7772b2-2f33-4bd2-8ca7-dae3b2b3ef25",
    "vm140": "https://lex.uz/acts/-863120",
}

EXCEL = [
    "Jadval faqat ma’lumot uchun: birinchi qatorda ustun sarlavhalari, birlashtirilgan "
    "(merge) kataklar va butunlay bo‘sh qator/ustunlar bo‘lmasin; bo‘sh joyga «—» yoki «yo‘q» "
    "yoziladi (Microsoft).",
    "Varaqlarga tushunarli nom beriladi (Sheet1 emas), bo‘sh varaqlar o‘chiriladi; A1 katakda "
    "jadval nomi yoki qisqa izoh (Microsoft).",
    "Raqamlar matn sifatida emas, son sifatida yoziladi; pul, foiz va sana uchun raqam formati "
    "qo‘llanadi, yig‘indi va o‘rtacha formula bilan hisoblanadi (qo‘lda yozilmaydi).",
    "Diagramma va o‘qlarga aniq sarlavha, kerak bo‘lsa ma’lumot yorliqlari; ma’no faqat rang "
    "bilan berilmaydi (Microsoft).",
    "Sarlavha qatori qotiriladi, chop etishda sarlavha har sahifada takrorlanadi.",
]
WORD = [
    "Sarlavhalar o‘rnatilgan uslublar bilan (Sarlavha 1, 2, 3) tartib bilan beriladi, darajalar "
    "o‘tkazib yuborilmaydi; shunda mundarija avtomatik tuziladi (Microsoft).",
    "Oraliq bo‘sh qatorlar va ketma-ket bo‘sh joylar bilan emas, paragraf oralig‘i bilan "
    "beriladi; ro‘yxatlar o‘rnatilgan belgili yoki raqamli ro‘yxat bilan (Microsoft).",
    "Jadval oddiy bo‘ladi: sarlavha qatori belgilanadi, birlashtirilgan kataklar va bo‘sh qatorlar "
    "bo‘lmaydi (Microsoft).",
    "Rasmiy hujjat: A4, Times New Roman 14, qator oralig‘i 1–1,5, xatboshi 1,25 sm, chetlar "
    "chap 3, o‘ng 1,5, yuqori va past 2 sm (Davlat tilida ish yuritish qo‘llanmasi).",
    "Sana «2026-yil 18-oktabr» yoki «18.10.26» shaklida yoziladi; matnda birinchisi (VM 140-son "
    "qarori, 16-band).",
    "Adresat: tashkilot va bo‘lim bosh kelishikda, lavozim va familiya jo‘nalish kelishigida "
    "(«…direktori A.A. Aliyevga»), ko‘pi bilan to‘rt adresat (VM 140, 15-band).",
    "Imzo: lavozim, shaxsiy imzo, ism-sharif (ism bosh harfi va familiya); «uning o‘rniga» yoki "
    "lavozim oldidan qiya chiziq yozilmaydi (VM 140, 17-band).",
    "Ilova bo‘lsa: «Ilova: 10 varaqda, 2 nusxada»; ijrochining familiyasi va telefoni oxirgi "
    "sahifaning pastki chap burchagida (VM 140, 14- va 24-band).",
    "Tasdiqlanadigan hujjatda yuqori o‘ng burchakda «TASDIQLAYMAN», lavozim, imzo, ism-sharif "
    "va sana (VM 140, 20-band). Hujjat turi (buyruq, bayonnoma…) va qisqa sarlavha yoziladi "
    "(8- va 9-band). Muhim ma’lumot faqat kolontitulda bo‘lmasin (Microsoft).",
]
POWERPOINT = [
    "Har bir slaydning o‘z, takrorlanmaydigan sarlavhasi bo‘ladi (Microsoft).",
    "Matn kamida 18 pt, oddiy (sans serif) shrift, katta harflar va ortiqcha kursivdan qochiladi; "
    "matn chapga tekislanadi (Microsoft).",
    "Matn va fon orasida kuchli kontrast; ma’no faqat rang bilan berilmaydi; o‘rnatilgan maketlar "
    "ishlatiladi (Microsoft).",
    "Rasm, diagrammaga qisqa izoh (alt matn); bezak rasmlari «bezak» deb belgilanadi (Microsoft).",
    "Bir slaydda ko‘pi bilan 6 ta qisqa band; so‘zlar orasida ikkitadan ortiq bo‘sh joy va "
    "ketma-ket bo‘sh qatorlar bo‘lmaydi (Microsoft).",
]
RULES = {"excel": EXCEL, "word": WORD, "powerpoint": POWERPOINT}

_APP_WORDS = {
    "excel": r"excel|eksel|jadval|xlsx|hisob-kitob|formula|diagramma",
    "word": r"word|docx|hujjat|ariza|xat\b|buyruq|bayonnoma|ma[‘’']?lumotnoma|tavsifnoma|"
    r"dalolatnoma|hisobot|shartnoma|e[‘’']?lon",
    "powerpoint": r"powerpoint|pptx|taqdimot|slayd|prezentats",
}


def apps_in(text: str) -> list[str]:
    t = (text or "").lower()
    return [app for app, pat in _APP_WORDS.items() if re.search(pat, t)]


def for_prompt(text: str) -> str:
    """The rules for the office programs the request is about ("" when none)."""
    apps = apps_in(text)
    if not apps:
        return ""
    lines = ["", "Rasmiy qoidalar (Microsoft tavsiyalari va O‘zbekiston ish yuritish talablari):"]
    for app in apps:
        lines += [f"- {r}" for r in RULES[app]]
    return "\n".join(lines)
