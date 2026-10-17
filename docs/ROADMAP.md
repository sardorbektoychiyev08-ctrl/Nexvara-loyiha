# NEXVARA — Roadmap

Bosqichlar [MASTER_SPEC.md](MASTER_SPEC.md) 26-bo'limidan olingan. Holat belgilari spec 25-bo'limiga mos: **PASS** (amalda tekshirilgan), **FAIL**, **BLOCKED**, **NOT TESTED**, shuningdek **TODO** (boshlanmagan) va **IN PROGRESS**.

| # | Bosqich | Holat | Izoh |
|---|---|---|---|
| M0 | Environment | PASS | Audit [ARCHITECTURE.md](ARCHITECTURE.md) da. Node/Android toolchain yo'q, M8/M11 da kerak bo'ladi |
| M1 | Windows Shell | IN PROGRESS | PASS: oyna (ekranga moslashadi), 12 bo'limning hammasi ishlaydi (smoke har sahifani ochib JS xatolarini tekshiradi), sozlamalar va tarix saqlanadi, ish stolida yorliq. Qolgan: birinchi ishga tushirish ustasi |
| M2 | Core Agent | IN PROGRESS | PASS: tool reyestri (36 asbob, tekshiruv, xavfli amallarga tasdiq), suhbat konteksti, bir xabarda bir nechta topshiriq, «xuddi shunday», AI tool-calling planner (soxta provayder bilan), Memory↔Teach↔Office. 12 bo'lim: 11 REAL IMPLEMENTED, Home N/A; haqiqiy Office bilan yakuniy integratsiya PASS ([SECTIONS_STATUS.md](SECTIONS_STATUS.md), [AGENT.md](AGENT.md)). Haqiqiy AI kaliti bilan: NOT TESTED |
| M3 | Excel Live Automation | IN PROGRESS | PASS: jadval demo, ops (sort/filter/dublikat/format/shartli format/grafik/pivot/CSV/PDF/20k qator), dashboard, UI tugmalari, ruscha Office. Qolgan: mavjud faylni tahlil, xato formulalar, fayllarni birlashtirish, print, data validation |
| M4 | Word va PowerPoint | IN PROGRESS | PASS: Word hisobot (15 tekshiruv), PowerPoint taqdimot (11 tekshiruv), UI tugmalari, ruscha Office. Qolgan: mavjud fayl/shablonni tahrirlash, tarjima/qayta yozish (M7 dan keyin), SmartArt |
| M5 | File, Vision, Web, Computer Control | IN PROGRESS | File Agent PASS: qidiruv, info+SHA-256, nusxa/ko'chirish (ustiga yozmaydi), nomlash va ommaviy nomlash, ZIP (xavfli arxivdan himoya), zaxira/versiya/tiklash, papkani tartiblash, Savatga o'chirish, Office→PDF ommaviy (haqiqiy Word/Excel), jurnal. OCR: darsliklar uchun PASS. Vision (AI), Web research, Computer control: TODO |
| M6 | Memory, Teach, Workflow | PASS | Darsliklar kutubxonasi, AI'siz test va mavzu: PASS. Memory: eslatmalar, suhbatlar tarixi, oxirgi fayllar, o'zbekcha qidiruv, tahrir/o'chirish, zaxira/tiklash: PASS. Teach: qoidalar (Excel/Word/PowerPoint/testlar/Word shablon), tasdiq bilan, versiyalar, buyruqlarga qo'llanadi: PASS. Workflow: qadamlar, tasdiq, pauza, qayta urinish, papka kuzatish (haqiqiy Excel bilan), kunlik jadval, tarix, shablonlar: PASS |
| M7 | Model Router | IN PROGRESS | PASS (soxta provayder bilan): 4 provayder (Anthropic SDK; OpenAI, Gemini, DeepSeek — HTTPS), arzon/o'rtacha/kuchli darajalar, kalitlar Credential Manager'da, xarajat hisobi, kunlik/oylik limit, qimmat so'rovda tasdiq. Chatda erkin buyruqni tushunish, darsliklar bo'yicha savol-javob, AI test (Word). Haqiqiy kalit bilan sinov: foydalanuvchi kalit kiritgach |
| M8 | NEXVARA BI | PASS | Node'siz: Python ETL + ilova ichida SVG grafiklar. XLSX/CSV/JSON/XML/TXT/papka, tozalash, formula ustun, kalit bo'yicha birlashtirish, qatorlarni qo'shish, avtomatik dashboard, KPI/ustunli/chiziqli/doiraviy/nuqtali/jadval, filtr, sana, sahifalar, eksport. Barcha amallar chatdan ham (vidjet tahrirlash, ETL qadamlari). Ma'lumot bazasiga ulanish: TODO |
| M9 | Google Login va Sync | IN PROGRESS | Windows OAuth/OIDC (soxta Google bilan PASS), client JSON import (Desktop turi tekshiriladi), Drive ruxsati ixtiyoriy. Sync: papka (AES-GCM) va telefon `/api/v1/sync` PASS; Google Drive — soxta Drive bilan PASS. Haqiqiy Google/Drive: BLOCKED (foydalanuvchi Google Cloud client yaratib o'zi kiradi). Tarix sync: TODO |
| M10 | Windows Release | IN PROGRESS | PASS: 1.0.0 haqiqiy o'rnatildi (per-user, o'zbekcha installer, Start Menu, ish stoli yorlig'i); 1.0.0 → 1.0.1 haqiqiy yangilandi; vaqtinchalik papkada 0.1.0 → 1.0.0 → rollback 0.1.0 → 1.0.0 → o'chirish, ma'lumotlar saqlanadi (14/14); ishga tushganda «Yangilash» xabari; installer nusxasi rollback uchun; ma'lumotlar zaxirasi/tiklash skripti ([RELEASE.md](RELEASE.md)). Mahalliy kanal `D:\NEXVARA\releases`. BLOCKED: Authenticode imzo; https server yo'q (internet yangilanishi NOT TESTED) |
| M11 | Android Mobile | BLOCKED → Codex | Windows tomoni tayyor: API v1 shartnomasi ([api/openapi.yaml](api/openapi.yaml)), demo server, topshiriq [ANDROID_HANDOFF.md](ANDROID_HANDOFF.md). JDK + Android SDK o'rnatish kerak |
| M12 | Windows-Mobile E2E | IN PROGRESS | Brauzer orqali boshqarish PASS. API v1 (envelope, xato kodlari, sertifikat pin, token almashtirish/muddat/chiqish, long-poll, SHA-256 fayl, tezlik cheklovi): PASS. Haqiqiy telefon: NOT TESTED. Native ilova: M11 |
| M13 | Final Personal Release | TODO | |

## Yaqin navbat

1. M11 (Codex): Android APK — [ANDROID_HANDOFF.md](ANDROID_HANDOFF.md); sinxron uchun `/api/v1/sync` tayyor.
2. Foydalanuvchi: Google Cloud Desktop client JSON → Sozlamalar → import → o'zi kiradi (keyin haqiqiy login va Drive sinxron sinovi).
3. M7: foydalanuvchi kaliti bilan haqiqiy AI planner sinovi (ruxsat bilan).
4. Vazifalar tarixini sinxronlash.
5. M5: Vision, Web research, Computer control.
