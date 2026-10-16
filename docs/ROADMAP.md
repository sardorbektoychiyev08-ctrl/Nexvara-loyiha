# NEXVARA — Roadmap

Bosqichlar [MASTER_SPEC.md](MASTER_SPEC.md) 26-bo'limidan olingan. Holat belgilari spec 25-bo'limiga mos: **PASS** (amalda tekshirilgan), **FAIL**, **BLOCKED**, **NOT TESTED**, shuningdek **TODO** (boshlanmagan) va **IN PROGRESS**.

| # | Bosqich | Holat | Izoh |
|---|---|---|---|
| M0 | Environment | PASS | Audit [ARCHITECTURE.md](ARCHITECTURE.md) da. Node/Android toolchain yo'q, M8/M11 da kerak bo'ladi |
| M1 | Windows Shell | IN PROGRESS | PASS: oyna (ekranga moslashadi), 12 bo'limning hammasi ishlaydi (smoke har sahifani ochib JS xatolarini tekshiradi), sozlamalar va tarix saqlanadi, ish stolida yorliq. Qolgan: birinchi ishga tushirish ustasi |
| M2 | Core Agent | IN PROGRESS | Task runner + cancel + vaqt chegarasi: PASS. AI'siz buyruq rejalashtiruvchi (o'zbekcha → Excel/Word/PowerPoint amallari, tekshiruv bilan): PASS. AI planner, replanning: TODO (M7) |
| M3 | Excel Live Automation | IN PROGRESS | PASS: jadval demo, ops (sort/filter/dublikat/format/shartli format/grafik/pivot/CSV/PDF/20k qator), dashboard, UI tugmalari, ruscha Office. Qolgan: mavjud faylni tahlil, xato formulalar, fayllarni birlashtirish, print, data validation |
| M4 | Word va PowerPoint | IN PROGRESS | PASS: Word hisobot (15 tekshiruv), PowerPoint taqdimot (11 tekshiruv), UI tugmalari, ruscha Office. Qolgan: mavjud fayl/shablonni tahrirlash, tarjima/qayta yozish (M7 dan keyin), SmartArt |
| M5 | File, Vision, Web, Computer Control | IN PROGRESS | File Agent PASS: qidiruv, info+SHA-256, nusxa/ko'chirish (ustiga yozmaydi), nomlash va ommaviy nomlash, ZIP (xavfli arxivdan himoya), zaxira/versiya/tiklash, papkani tartiblash, Savatga o'chirish, Office→PDF ommaviy (haqiqiy Word/Excel), jurnal. OCR: darsliklar uchun PASS. Vision (AI), Web research, Computer control: TODO |
| M6 | Memory, Teach, Workflow | PASS | Darsliklar kutubxonasi, AI'siz test va mavzu: PASS. Memory: eslatmalar, suhbatlar tarixi, oxirgi fayllar, o'zbekcha qidiruv, tahrir/o'chirish, zaxira/tiklash: PASS. Teach: qoidalar (Excel/Word/PowerPoint/testlar/Word shablon), tasdiq bilan, versiyalar, buyruqlarga qo'llanadi: PASS. Workflow: qadamlar, tasdiq, pauza, qayta urinish, papka kuzatish (haqiqiy Excel bilan), kunlik jadval, tarix, shablonlar: PASS |
| M7 | Model Router | IN PROGRESS | PASS (soxta provayder bilan): 4 provayder (Anthropic SDK; OpenAI, Gemini, DeepSeek — HTTPS), arzon/o'rtacha/kuchli darajalar, kalitlar Credential Manager'da, xarajat hisobi, kunlik/oylik limit, qimmat so'rovda tasdiq. Chatda erkin buyruqni tushunish, darsliklar bo'yicha savol-javob, AI test (Word). Haqiqiy kalit bilan sinov: foydalanuvchi kalit kiritgach |
| M8 | NEXVARA BI | PASS | Node'siz: Python ETL + ilova ichida SVG grafiklar. XLSX/CSV/JSON/XML/TXT/papka, tur aniqlash, tozalash, formula, birlashtirish, avtomatik dashboard (sof foyda, oylik o'sish), KPI/ustunli/chiziqli/doiraviy/nuqtali/jadval, filtr, sana, drill-down, sahifalar, saqlash, PNG/PDF/Excel/CSV eksport. Ma'lumot bazasiga ulanish: TODO |
| M9 | Google Login va Sync | TODO | |
| M10 | Windows Release | TODO | PyInstaller + installer (Inno Setup yoki shunga o'xshash) |
| M11 | Android Mobile | TODO | JDK + Android SDK o'rnatish kerak |
| M12 | Windows-Mobile E2E | IN PROGRESS | Telefon brauzeri orqali boshqarish PASS (QR + bir martalik kod, HTTPS, tokenlar xeshlangan va haftalik almashadi, uzish, idempotent so'rovlar, navbat, fayl yuborish/yuklab olish). Native Android ilova (M11) va Google login (M9): TODO |
| M13 | Final Personal Release | TODO | |

## Yaqin navbat

1. M7: foydalanuvchi kaliti bilan haqiqiy AI sinovi.
2. M10: o'rnatuvchi (.exe), avtomatik yangilanish.
3. M5: Vision (rasm/skrinshot tahlili AI bilan), Web research, Computer control.
4. M3/M4: formula xatolarini topish, fayllarni birlashtirish, data validation; Word/PowerPoint shablonlarini chuqurroq tahrirlash.
5. M9/M11: Google login va native Android ilova (Android SDK va Google Cloud loyihasi kerak).
