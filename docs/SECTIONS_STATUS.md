# 12 bo'lim va Core Agent: holat (2026-10-17, 2-tekshiruv)

"Bo'lim ochiladi" ≠ "bo'lim chatdagi tabiiy til buyrug'ini bajaradi". Bu jadvalda faqat
**chatga yozilgan gap** orqali haqiqatan bajariladigan narsa hisobga olingan. Har bo'lim uchun
[tests/unit/test_sections_chat.py](../tests/unit/test_sections_chat.py) gapni `Api.chat` ga
yuboradi va natijani (vazifa, saqlangan yozuv, sozlama) tekshiradi. Telefon (`/api/v1/chat`)
xuddi shu yo'ldan o'tadi.

Belgilar: **REAL IMPLEMENTED** — chatdan ishlaydi va sinalgan; **PARTIAL** — bir qismi chatdan,
qolgani faqat tugmalar orqali; **BLOCKED** — tashqi narsa kerak; **NOT TESTED** — haqiqiy
muhitda sinalmagan.

| # | Bo'lim | Chatdan nima ishlaydi (misol) | Faqat tugma orqali | Holat |
|---|---|---|---|---|
| 1 | Home | — (umumiy ko'rinish sahifasi, buyruq qabul qilmaydi) | — | REAL IMPLEMENTED (sahifa) · chat N/A |
| 2 | AI Chat | AI'siz yo'naltiruvchi barcha bo'limlarga yuboradi; tushunilmasa aniq aytadi | — | REAL IMPLEMENTED (AI'siz) · haqiqiy AI kaliti bilan NOT TESTED |
| 3 | Office Agent | «Hisobot.xlsx ni och, B ustun bo'yicha saralab, PDF qilib saqla» (Excel/Word/PowerPoint) | demo tugmalari | REAL IMPLEMENTED (haqiqiy Office testlari avval PASS) |
| 4 | Darsliklar va testlar | «7-sinf fizika Nyuton qonunlari 20 ta test», «... mavzusini chiqarib ber», taqdimot | darslik yuklash, Telegram kirish | REAL IMPLEMENTED · Telegram haqiqiy hisob bilan NOT TESTED |
| 5 | Files | qidiruv (papka, tur), ma'lumot, nusxa, ko'chirish, nomlash, ommaviy nomlash, ZIP/ochish, zaxira, versiyalar, tiklash⚠, tartiblash⚠, Savatga⚠, ommaviy PDF; «topilgan fayllar», «uni» | — | REAL IMPLEMENTED |
| 6 | NEXVARA BI | yaratish va saqlash, ro'yxat, ochish, filtr («faqat Toshkent»), ko'rsatkichlar (KPI javobi chatda), vidjet qo'shish, Excel/CSV/PDF/PNG eksport, o'chirish⚠ | ETL qadamlari (formula ustun, birlashtirish), vidjetni tahrirlash | PARTIAL (asosiy amallar chatdan) |
| 7 | Workflows | yaratish (qadamlar, kutish, tasdiq, har kuni SS:DD, papka kuzatish, xatoda davom), qayta yaratib tahrirlash, ro'yxat, ishga tushirish, pauza, davom, tasdiqlash, to'xtatish, yoqish/o'chirish, tarix, o'chirish⚠ | — | REAL IMPLEMENTED |
| 8 | Teach NEXVARA | «Har doim Excel raqamlarini markazga joyla» → tasdiq → qoida | versiyalar, yoqish/o'chirish | REAL IMPLEMENTED |
| 9 | Memory | «Eslab qol: ...», «nimalarni eslab qolgansan?», «xotiradan maktab haqida top» (yangi) | tahrir, o'chirish, zaxira/tiklash | REAL IMPLEMENTED (saqlash, eslash, qidiruv) |
| 10 | Tasks / History | «oxirgi vazifalarni ko'rsat» (yangi) | bekor qilish (tugma yoki telefon) | REAL IMPLEMENTED (ko'rish) |
| 11 | Devices | «telefon ulanishini yoq / o'chir», «telefon ulanganmi» (yangi) | QR skanerlash, qurilmani uzish | REAL IMPLEMENTED · haqiqiy telefon bilan NOT TESTED |
| 12 | Settings | mavzu, savollar/variantlar soni, Office oynasi, AI yoqish/o'chirish (kalit bo'lsa), kunlik/oylik limit, tasdiq chegarasi, telefon porti, yangilanish kanali va tekshiruvi, sinxron papkasi/yoqish/Drive, «sinxronla» | AI kalitlari (ataylab: faqat Sozlamalar → AI; chatga yozilgan kalit rad etiladi va saqlanmaydi), Google kirish (faqat foydalanuvchi brauzerda) | REAL IMPLEMENTED |

⚠ = bajarishdan oldin «Davom etaymi?» so'raladi.

## Core Agent

| Modul | Holat | Izoh |
|---|---|---|
| Tool reyestri (36 asbob, tur tekshiruvi, xavfli amallarga tasdiq) | REAL IMPLEMENTED | [AGENT.md](AGENT.md); unit testlar PASS |
| Suhbat konteksti («uni», «shu fayl», «topilgan fayllar», «shu papka», «xuddi shunday … bilan ham») | REAL IMPLEMENTED | unit + UI testlar PASS |
| Bir xabarda bir nechta topshiriq (zanjir, natija keyingi qadamga o'tadi) | REAL IMPLEMENTED | Office klauzalari bitta buyruq bo'lib qoladi |
| AI tool-calling planner (JSON, 4 provayder uchun bir xil) | REAL IMPLEMENTED (soxta provayder bilan) | haqiqiy kalit bilan NOT TESTED (pullik chaqiruv qilinmadi) |
| Memory ↔ Teach ↔ Office | REAL IMPLEMENTED | yo'lli eslatmalar buyruqlarda nom sifatida ishlaydi; Teach qoidalari Office/zanjir/workflow'da; AI'ga mos eslatma va qoidalar |
| Sinxronlash: papka (shifrlangan), telefon `/api/v1/sync` | REAL IMPLEMENTED | 2 qurilma, ziddiyat, o'chirish, xavfsizlik testlari PASS |
| Sinxronlash: Google Drive appDataFolder | PARTIAL | soxta Drive bilan PASS; haqiqiy Drive BLOCKED (Google Cloud client + Drive API yoqilishi kerak) |
| Ikki haqiqiy kompyuter o'rtasida sinxron | NOT TESTED | ikkinchi kompyuter kerak |
| Vazifalar tarixini sinxronlash | TODO | yo'llar kompyuterga xos |

## Integratsiyalar

| Modul | Holat | Izoh |
|---|---|---|
| Telefon API v1 (`remote_v1.py`, `protocol.py`) | REAL IMPLEMENTED | 13 marshrut, envelope + xato kodlari, sertifikat pin (QR'da `fp`), token almashtirish (yumshoq), 30 kunlik muddat, chiqish, long-poll, SHA-256 bilan fayl, tezlik cheklovi, eski baza migratsiyasi. HTTPS bilan 10 unit test PASS |
| Haqiqiy telefon bilan ulanish | NOT TESTED | Foydalanuvchi telefoni kerak |
| Native Android ilova | BLOCKED → Codex | JDK/Android SDK o'rnatilmagan; shartnoma va topshiriq tayyor: [ANDROID_HANDOFF.md](ANDROID_HANDOFF.md), [api/](api/) |
| Google login (Windows, OAuth/OIDC + PKCE) | REAL IMPLEMENTED (soxta Google bilan) | 8 unit test PASS: PKCE, state, nonce, RS256 imzo, aud, refresh, invalid_grant, revoke |
| Google client JSON import (Desktop turi tekshiriladi) | REAL IMPLEMENTED | Sozlamalar → «Client JSON faylini tanlash»; NEXVARA o'zi kirmaydi |
| Google login haqiqiy hisob bilan | BLOCKED | Foydalanuvchi Google Cloud'da Desktop OAuth client yaratib, o'zi kirishi kerak: [GOOGLE_LOGIN.md](GOOGLE_LOGIN.md) |
| Windows installer (PyInstaller + Inno Setup) | REAL IMPLEMENTED | Build, jim o'rnatish, o'rnatilgan exe smoke PASS, o'chirish PASS, `D:\NEXVARA` tegilmadi |
| Updater (imzoli manifest, SHA-256, tiklash, rollback) | REAL IMPLEMENTED | 6 unit test PASS; haqiqiy kalit + haqiqiy installer bilan papka kanali orqali qayta o'rnatish PASS |
| Updater https kanali | NOT TESTED | https server yo'q (kod bor) |
| .exe raqamli imzosi (Authenticode) | BLOCKED | Kod imzolash sertifikati kerak |
| Push bildirishnoma (FCM) | BLOCKED | Firebase loyihasi kerak; v1 long-poll ishlatadi |
