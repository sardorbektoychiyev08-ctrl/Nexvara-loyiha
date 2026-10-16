# NEXVARA — Roadmap

Bosqichlar [MASTER_SPEC.md](MASTER_SPEC.md) 26-bo'limidan olingan. Holat belgilari spec 25-bo'limiga mos: **PASS** (amalda tekshirilgan), **FAIL**, **BLOCKED**, **NOT TESTED**, shuningdek **TODO** (boshlanmagan) va **IN PROGRESS**.

| # | Bosqich | Holat | Izoh |
|---|---|---|---|
| M0 | Environment | PASS | Audit [ARCHITECTURE.md](ARCHITECTURE.md) da. Node/Android toolchain yo'q, M8/M11 da kerak bo'ladi |
| M1 | Windows Shell | IN PROGRESS | Oyna, navigatsiya, chat UI, task paneli, dark/light: smoke PASS. Birinchi ishga tushirish ustasi va sozlamalarni saqlash qolgan |
| M2 | Core Agent | IN PROGRESS | Task state machine + runner + cancel: PASS. Planner, tool calling, replanning: TODO (M7 ga bog'liq) |
| M3 | Excel Live Automation | IN PROGRESS | Birinchi real test (10 qator, formula, format, saqlash, qayta tekshirish) yozildi. Real Excel natijasi PROGRESS.md da |
| M4 | Word va PowerPoint | TODO | |
| M5 | File, Vision, Web, Computer Control | TODO | |
| M6 | Memory, Teach, Workflow | TODO | SQLite |
| M7 | Model Router | TODO | API kalitlari kerak bo'ladi; foydalanuvchi tasdig'isiz pullik chaqiruv yo'q |
| M8 | NEXVARA BI | TODO | Node.js + React/ECharts o'rnatish kerak bo'lishi mumkin |
| M9 | Google Login va Sync | TODO | |
| M10 | Windows Release | TODO | PyInstaller + installer (Inno Setup yoki shunga o'xshash) |
| M11 | Android Mobile | TODO | JDK + Android SDK o'rnatish kerak |
| M12 | Windows-Mobile E2E | TODO | |
| M13 | Final Personal Release | TODO | |

## Yaqin navbat

1. M3: Excel skill'ni kengaytirish: mavjud faylni ochish, sort/filter, diagramma, conditional formatting, CSV/PDF eksport.
2. M2: agent tsikli uchun "tool" interfeysi: har bir Excel amali alohida, sxemali tool bo'ladi (keyin AI planner ularni chaqiradi).
3. M1: sozlamalar fayli (`%APPDATA%\NEXVARA`), birinchi ishga tushirish ustasi.
4. M7: model router skeleti va xarajat hisobi (avval soxta/offline provayder bilan testlar).
