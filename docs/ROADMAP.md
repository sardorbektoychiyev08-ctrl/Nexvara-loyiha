# NEXVARA — Roadmap

Bosqichlar [MASTER_SPEC.md](MASTER_SPEC.md) 26-bo'limidan olingan. Holat belgilari spec 25-bo'limiga mos: **PASS** (amalda tekshirilgan), **FAIL**, **BLOCKED**, **NOT TESTED**, shuningdek **TODO** (boshlanmagan) va **IN PROGRESS**.

| # | Bosqich | Holat | Izoh |
|---|---|---|---|
| M0 | Environment | PASS | Audit [ARCHITECTURE.md](ARCHITECTURE.md) da. Node/Android toolchain yo'q, M8/M11 da kerak bo'ladi |
| M1 | Windows Shell | IN PROGRESS | PASS: oyna (ekranga moslashadi), 12 bo'limning hammasi ishlaydi (smoke har sahifani ochib JS xatolarini tekshiradi), sozlamalar va tarix saqlanadi, ish stolida yorliq. Qolgan: birinchi ishga tushirish ustasi |
| M2 | Core Agent | IN PROGRESS | Task runner + cancel + vaqt chegarasi: PASS. AI'siz buyruq rejalashtiruvchi: PASS. 12 bo'limning chat orqali bog'lanishi tekshirildi ([SECTIONS_STATUS.md](SECTIONS_STATUS.md)): 7 tasi REAL IMPLEMENTED, 4 tasi PARTIAL, Home N/A. AI planner, replanning: haqiqiy kalit bilan NOT TESTED |
| M3 | Excel Live Automation | IN PROGRESS | PASS: jadval demo, ops (sort/filter/dublikat/format/shartli format/grafik/pivot/CSV/PDF/20k qator), dashboard, UI tugmalari, ruscha Office. Qolgan: mavjud faylni tahlil, xato formulalar, fayllarni birlashtirish, print, data validation |
| M4 | Word va PowerPoint | IN PROGRESS | PASS: Word hisobot (15 tekshiruv), PowerPoint taqdimot (11 tekshiruv), UI tugmalari, ruscha Office. Qolgan: mavjud fayl/shablonni tahrirlash, tarjima/qayta yozish (M7 dan keyin), SmartArt |
| M5 | File, Vision, Web, Computer Control | IN PROGRESS | File Agent PASS: qidiruv, info+SHA-256, nusxa/ko'chirish (ustiga yozmaydi), nomlash va ommaviy nomlash, ZIP (xavfli arxivdan himoya), zaxira/versiya/tiklash, papkani tartiblash, Savatga o'chirish, Office→PDF ommaviy (haqiqiy Word/Excel), jurnal. OCR: darsliklar uchun PASS. Vision (AI), Web research, Computer control: TODO |
| M6 | Memory, Teach, Workflow | PASS | Darsliklar kutubxonasi, AI'siz test va mavzu: PASS. Memory: eslatmalar, suhbatlar tarixi, oxirgi fayllar, o'zbekcha qidiruv, tahrir/o'chirish, zaxira/tiklash: PASS. Teach: qoidalar (Excel/Word/PowerPoint/testlar/Word shablon), tasdiq bilan, versiyalar, buyruqlarga qo'llanadi: PASS. Workflow: qadamlar, tasdiq, pauza, qayta urinish, papka kuzatish (haqiqiy Excel bilan), kunlik jadval, tarix, shablonlar: PASS |
| M7 | Model Router | IN PROGRESS | PASS (soxta provayder bilan): 4 provayder (Anthropic SDK; OpenAI, Gemini, DeepSeek — HTTPS), arzon/o'rtacha/kuchli darajalar, kalitlar Credential Manager'da, xarajat hisobi, kunlik/oylik limit, qimmat so'rovda tasdiq. Chatda erkin buyruqni tushunish, darsliklar bo'yicha savol-javob, AI test (Word). Haqiqiy kalit bilan sinov: foydalanuvchi kalit kiritgach |
| M8 | NEXVARA BI | PASS | Node'siz: Python ETL + ilova ichida SVG grafiklar. XLSX/CSV/JSON/XML/TXT/papka, tur aniqlash, tozalash, formula, birlashtirish, avtomatik dashboard (sof foyda, oylik o'sish), KPI/ustunli/chiziqli/doiraviy/nuqtali/jadval, filtr, sana, drill-down, sahifalar, saqlash, PNG/PDF/Excel/CSV eksport. Ma'lumot bazasiga ulanish: TODO |
| M9 | Google Login va Sync | IN PROGRESS | Windows OAuth/OIDC (PKCE, state, nonce, RS256, refresh, logout/revoke): soxta Google bilan PASS. Haqiqiy Google: BLOCKED (Google Cloud loyihasi, [GOOGLE_LOGIN.md](GOOGLE_LOGIN.md)). Sync: TODO |
| M10 | Windows Release | IN PROGRESS | PASS: PyInstaller + Inno Setup installer (per-user, Start Menu, yorliq, uninstaller), o'rnatilgan exe smoke, imzoli yangilanish (Ed25519 + SHA-256), muvaffaqiyatsiz yangilanishni aniqlash, rollback, ma'lumotlar saqlanadi ([RELEASE.md](RELEASE.md)). BLOCKED: Authenticode imzo. NOT TESTED: https kanali |
| M11 | Android Mobile | IN PROGRESS | Windows API v1 shartnomasi ([api/openapi.yaml](api/openapi.yaml)); Kotlin/Compose Home, Chat, Tasks, Devices, QR pairing, TLS pin, AI tasdig‘i, long-poll vazifalar, bir nechta PC, shifrlangan chat navbati va tarixi, kamera, fayl almashinuvi; debug APK va 3 unit test PASS. Android 16 telefonda o‘rnatish, pairing, chat, tarix, fayl yuborish va kamera oynasini ochish PASS; surat yuborish va faylni olish NOT TESTED. Tafsilot: [ANDROID_PROGRESS.md](ANDROID_PROGRESS.md) |
| M12 | Windows-Mobile E2E | IN PROGRESS | Brauzer orqali boshqarish PASS. Windows API v1 testlari PASS; haqiqiy Android telefonidan demo Windows API bilan pairing va chat PASS. Haqiqiy ish stoli agenti bilan vazifalar NOT TESTED. Pause/resume API mavjud emas |
| M13 | Final Personal Release | TODO | |

## Yaqin navbat

1. M11 (Codex): Android APK — [ANDROID_HANDOFF.md](ANDROID_HANDOFF.md).
2. M7: foydalanuvchi kaliti bilan haqiqiy AI sinovi.
3. M9: foydalanuvchi Google Cloud client yaratgach haqiqiy login sinovi; keyin sync.
4. M12: haqiqiy telefon bilan ulanish sinovi.
5. M5: Vision, Web research, Computer control. Files/BI/Workflows/Settings bo'limlarining qolgan amallarini chatga ulash.
