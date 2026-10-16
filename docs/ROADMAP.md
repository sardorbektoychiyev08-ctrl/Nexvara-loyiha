# NEXVARA — Roadmap

Bosqichlar [MASTER_SPEC.md](MASTER_SPEC.md) 26-bo'limidan olingan. Holat belgilari spec 25-bo'limiga mos: **PASS** (amalda tekshirilgan), **FAIL**, **BLOCKED**, **NOT TESTED**, shuningdek **TODO** (boshlanmagan) va **IN PROGRESS**.

| # | Bosqich | Holat | Izoh |
|---|---|---|---|
| M0 | Environment | PASS | Audit [ARCHITECTURE.md](ARCHITECTURE.md) da. Node/Android toolchain yo'q, M8/M11 da kerak bo'ladi |
| M1 | Windows Shell | IN PROGRESS | Oyna, navigatsiya, chat UI, task paneli, dark/light: smoke PASS. Birinchi ishga tushirish ustasi va sozlamalarni saqlash qolgan |
| M2 | Core Agent | IN PROGRESS | Task runner + cancel + vaqt chegarasi: PASS. AI'siz buyruq rejalashtiruvchi (o'zbekcha → Excel/Word/PowerPoint amallari, tekshiruv bilan): PASS. AI planner, replanning: TODO (M7) |
| M3 | Excel Live Automation | IN PROGRESS | PASS: jadval demo, ops (sort/filter/dublikat/format/shartli format/grafik/pivot/CSV/PDF/20k qator), dashboard, UI tugmalari, ruscha Office. Qolgan: mavjud faylni tahlil, xato formulalar, fayllarni birlashtirish, print, data validation |
| M4 | Word va PowerPoint | IN PROGRESS | PASS: Word hisobot (15 tekshiruv), PowerPoint taqdimot (11 tekshiruv), UI tugmalari, ruscha Office. Qolgan: mavjud fayl/shablonni tahrirlash, tarjima/qayta yozish (M7 dan keyin), SmartArt |
| M5 | File, Vision, Web, Computer Control | TODO | |
| M6 | Memory, Teach, Workflow | IN PROGRESS | Darsliklar kutubxonasi (SQLite FTS5), AI'siz test tuzish va mavzuni chiqarish (Word + asl sahifalar PDF): PASS (sintetik darslik). Haqiqiy yangi darsliklar bilan: BLOCKED (PDF yo'q). Memory/Teach/Workflow: TODO |
| M7 | Model Router | IN PROGRESS | PASS (soxta provayder bilan): 4 provayder (Anthropic SDK; OpenAI, Gemini, DeepSeek — HTTPS), arzon/o'rtacha/kuchli darajalar, kalitlar Credential Manager'da, xarajat hisobi, kunlik/oylik limit, qimmat so'rovda tasdiq. Chatda erkin buyruqni tushunish, darsliklar bo'yicha savol-javob, AI test (Word). Haqiqiy kalit bilan sinov: foydalanuvchi kalit kiritgach |
| M8 | NEXVARA BI | TODO | Node.js + React/ECharts o'rnatish kerak bo'lishi mumkin |
| M9 | Google Login va Sync | TODO | |
| M10 | Windows Release | TODO | PyInstaller + installer (Inno Setup yoki shunga o'xshash) |
| M11 | Android Mobile | TODO | JDK + Android SDK o'rnatish kerak |
| M12 | Windows-Mobile E2E | TODO | |
| M13 | Final Personal Release | TODO | |

## Yaqin navbat

1. M3: mavjud faylni ochib tahlil/tozalash, formula xatolarini topish, fayllarni birlashtirish, print sozlamalari, data validation.
2. M4: mavjud Word/PowerPoint fayli va shablonlarni tahrirlash; vazifa watchdog/timeout.
3. M2: agent tsikli uchun "tool" interfeysi: har bir Excel amali alohida, sxemali tool bo'ladi (keyin AI planner ularni chaqiradi).
4. M1: sozlamalar fayli (`%APPDATA%\NEXVARA`), birinchi ishga tushirish ustasi.
5. M7: model router skeleti va xarajat hisobi (avval soxta/offline provayder bilan testlar).
