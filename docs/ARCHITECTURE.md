# NEXVARA — Arxitektura

Holat: v0.1.0 (M0 + M1 asosi + M3 boshlanishi). To'liq talablar: [MASTER_SPEC.md](MASTER_SPEC.md).

## Muhit (2026-10-16 audit)

| Komponent | Holat |
|---|---|
| Windows 11 Pro 10.0.26200 x64 | bor |
| Microsoft Office 2016 (MSI, 32-bit, 16.0.4266) | Excel/Word/PowerPoint COM ro'yxatdan o'tgan |
| Python 3.13 (64-bit, Microsoft Store) | bor |
| Git 2.55 | bor; remote: `github.com/sardorbektoychiyev08-ctrl/Nexvara-loyiha` |
| Node.js, .NET SDK, Java/Android SDK, Rust | **yo'q** |
| Disk | C: 51 GB bo'sh, D: 141 GB bo'sh |

## Stek tanlovi

**Python + pywin32 + pywebview (WebView2)**: bitta runtime, Office COM bilan bevosita ishlaydi.

Nima uchun spec'dagi "TypeScript/Node + Electron" emas:
- Mashinada Node yo'q, Python esa bor. Office COM baribir Python (pywin32) yoki .NET orqali bo'lishi kerak edi. Electron + Python esa ikki runtime, IPC qatlami va ~150 MB qo'shimcha installer degani.
- pywebview Windows'ning o'zidagi WebView2'dan foydalanadi: oyna yengil (Chromium bundle yo'q), UI esa oddiy HTML/CSS/JS.
- UI veb texnologiyada qolgani uchun keyin React/ECharts (NEXVARA BI, M8) qo'shish oson. Kerak bo'lsa, butun UI'ni Electron/Tauri'ga ko'chirish ham mumkin.
- Office 32-bit, Python 64-bit: COM out-of-process ishlagani uchun bu muammo emas, testda tasdiqlandi.

Android (M11) alohida: Kotlin + Jetpack Compose (spec bo'yicha).

## Kod tuzilmasi

Spec 22-bo'limiga ko'ra papkalar faqat haqiqiy kod paydo bo'lganda yaratiladi. Python paketi `src/nexvara/`:

```
src/nexvara/
  core/task.py            # Task state machine: Task, Step, Status, TaskRunner (thread), cancel
  skills/excel/
    table.py              # COM'siz yordamchilar: col_letter, excel_color, validate_save_path, TableSpec
    bridge.py             # ExcelSession (DispatchEx, visible, maximize, foreground), write/format/save
    demo.py               # Birinchi real test: 10 qatorli jadval -> saqlash -> qayta ochib tekshirish
    ops.py                # Agent tool'lari: write/read, sort, filter, dublikat, format, shartli format,
                          #   grafik, pivot, CSV/PDF eksport
    formulas.py           # SUMIFS/growth/lookup; XLOOKUP yo'q bo'lsa INDEX/MATCH
    dashboard.py          # Savdo dashboardi: ma'lumot, formulalar, KPI, 3 grafik, pivot, 14 tekshiruv
  skills/common.py        # bring_to_front, validate_output_path
  skills/office_session.py # Word/PowerPoint session: faqat o'z hujjatlarini yopadi
  skills/png_chart.py     # Tashqi kutubxonasiz PNG diagramma (Word/PPT rasmlari uchun)
  skills/word/
    ops.py                # WordSession + hujjat amallari (pozitsion COM argumentlar)
    demo.py               # Rasmiy hisobot: DOCX + PDF, 15 tekshiruv
  skills/powerpoint/
    ops.py                # PowerPointSession + slayd amallari
    layout.py             # Matn sig'ishi / ustma-ust / slayddan tashqari tekshiruvlari
    demo.py               # 6 slaydli taqdimot: PPTX + PDF, 11 tekshiruv
  app/
    main.py               # pywebview oynasi; --smoke va --selftest-excel (4 tugma) rejimlari
    api.py                # JS -> Python ko'prigi (window.pywebview.api)
    ui/                   # index.html, app.css, app.js
tests/
  unit/                   # Office'siz, har doim ishlaydi
  office/                 # Haqiqiy Excel; faqat NEXVARA_RUN_OFFICE=1 bo'lsa
scripts/                  # setup.ps1, run.ps1, test.ps1
docs/
```

Spec'dagi nomlar bilan moslik: `packages/core` -> `nexvara.core`, `skills/excel` -> `nexvara.skills.excel`, `apps/windows` -> `nexvara.app`. Keyingi skill'lar ham `nexvara/skills/<nom>/` ichiga qo'shiladi.

## Asosiy qarorlar

- **Live visible execution**: `ExcelSession` `DispatchEx` bilan *alohida* Excel jarayonini ochadi, shuning uchun foydalanuvchining ochiq kitoblariga tegilmaydi. Oyna `Visible=True` qilinadi, maksimal kattalashtiriladi va oldinga chiqariladi. Amallar COM orqali bajariladi va Excel oynasida jonli ko'rinadi.
- **Raqam formatlari va sanalar**: Excel 2016 + uz-Latn mintaqasida `NumberFormat` inglizcha kodni tarjima qilmaydi. Shuning uchun raqam formatlari Excel'ning o'z ajratgichlari bilan `NumberFormatLocal` orqali yoziladi. pywin32 naive `datetime` ni UTC ga siljitadi, shuning uchun sanalar seriya raqami sifatida yoziladi (`table.to_excel_value`).
- **Til mustaqilligi**: formulalar `Range.Formula` orqali yoziladi (inglizcha nomlar, lokalga bog'liq emas). Sheet nomi aniq beriladi (`Лист1`/`Sheet1` farqi muhim emas). Ekran koordinatalari ishlatilmaydi.
- **Xavfsiz saqlash**: `validate_save_path` nisbiy yo'lni, `.xlsx` bo'lmagan faylni va mavjud faylni (`overwrite=True` berilmasa) rad etadi. Overwrite qilishdan oldin `.bak-<vaqt>.xlsx` zaxira nusxasi olinadi.
- **Task modeli**: har bir vazifa alohida thread'da ishlaydi. Qadamlar (`task.step(...)`) UI'ga jonli ko'rinadi. Bekor qilish kooperativ: har bir qadam boshida tekshiriladi.
- **UI <-> backend**: UI har 300 ms'da `get_task` snapshot'ini so'raydi. Bu oddiy va ishonchli; keyinchalik push-hodisalarga o'tkazish mumkin.
- **AI**: hali ulanmagan (M7). Chat buni foydalanuvchiga ochiq aytadi. Pullik API chaqirilmaydi.

## Ishga tushirish

```powershell
.\scripts\setup.ps1          # .venv yaratadi va bog'liqliklarni o'rnatadi
.\scripts\run.ps1            # NEXVARA oynasini ochadi
.\scripts\test.ps1           # lint + unit testlar + oyna smoke testi
.\scripts\test.ps1 -Office   # + haqiqiy Excel testi (ekranda Excel ochiladi)
```
