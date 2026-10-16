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
  config.py               # Ma'lumotlar papkasi: D:\NEXVARA (Darsliklar, Testlar, nexvara.db)
  knowledge/
    textnorm.py           # PDF matnini tozalash (o‘/g‘, defis, sarlavhalar), gaplarga ajratish
    catalog.py            # Sinf / fan / yil aniqlash
    store.py              # SQLite + FTS5: kitoblar, sahifalar, bo'limlar, qidiruv (eng yangi nashr)
    ingest.py             # Papkani indekslash (yangi/o'zgargan/dublikat/o'chirilgan/skaner)
    quiz.py               # AI'siz savollar: ta'rif, yil/raqam, bo'sh joy, to'g'ri/noto'g'ri, moslash
    service.py            # Chat buyrug'ini tushunish, test so'rovi, kutubxona amallari
    testdoc.py            # Word'da test: variantlar + javoblar kaliti, DOCX/PDF, tekshiruv
    figures.py            # Rasm izohlari + rasmni qirqish (izoh yashiriladi) rasmli savollar uchun
    topics.py             # Mavzu = §-bo'lim: sarlavha/matn bo'yicha topish, mundarija + bet siljishi
    topicdoc.py           # Mavzu: Word matni + asl sahifalar PDF, tekshiruv
  sources/
    eduportal.py          # Vazirlik portali: 205 ta rasmiy (eski) o'zbekcha darslik yuklovchi
    telegram_rtm.py       # RTM rasmiy Telegram kanali: yangi darsliklar (foydalanuvchi hisobi bilan)
  knowledge/ocr.py        # Windows o'zidagi OCR (skaner PDF'lar uchun), PyMuPDF bilan
  agent/
    parse.py              # O'zbekcha buyruq -> reja (amallar, fayl, ilova); AI'siz
    files.py              # Faylni nomi bo'yicha topish; xavfsiz chiqish yo'li (_NEXVARA), .bak
    excel_exec.py         # Excel rejasini bajarish + har qadam tekshiruvi
    word_exec.py          # Word rejasini bajarish + tekshiruv
    ppt_exec.py           # Mavzudan dars taqdimoti; .pptx -> PDF
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
- **Buyruqlar (AI'siz)**: `agent/parse.py` qoidaga asoslangan reja tuzadi; keyin M7 dagi AI planner xuddi shu amallar (tool'lar) to'plamidan foydalanadi. Asl fayllar o'zgartirilmaydi.
- **Vaqt chegarasi**: har vazifa sukut bo'yicha 10 daqiqa; osilgan COM chaqiruvi UI'ni bloklamaydi.
- **Task modeli**: har bir vazifa alohida thread'da ishlaydi. Qadamlar (`task.step(...)`) UI'ga jonli ko'rinadi. Bekor qilish kooperativ: har bir qadam boshida tekshiriladi.
- **UI <-> backend**: UI har 300 ms'da `get_task` snapshot'ini so'raydi. Bu oddiy va ishonchli; keyinchalik push-hodisalarga o'tkazish mumkin.
- **AI (ixtiyoriy, M7)**: `ai/providers.py` (Anthropic rasmiy SDK orqali; OpenAI, Gemini, DeepSeek bir xil `chat/completions` formatida urllib bilan), `ai/router.py` (vazifa → daraja → model, narx taxmini, limit, tasdiq, `ai_usage` daftari), `ai/features.py` (buyruqni tushunish: AI erkin matnni AI'siz parser tushunadigan buyruqqa qayta yozadi, keyin odatdagi sinalgan ijrochilar ishlaydi; darsliklar bo'yicha savol-javob FTS qidiruv + manba bet bilan; AI test savollari JSON → o'sha Word chiqishi, rasmli savollar AI'siz qoladi). Kalit yo'q yoki AI o'chiq bo'lsa hech narsa yuborilmaydi.
- **Chat marshruti** (`Api._chat_inner`): Teach/eslab qol → BI ("... dan dashboard") → fayl qidirish ("... faylini top") → fayl nomli Office buyrug'i → test → taqdimot → mavzu → Office buyrug'i → AI (kalit bo'lsa). Har xabar `chat_log` ga yoziladi.
- **Memory va Teach** (`memory/`): `app.db` da `memory_items` + FTS, `chat_log` + FTS, `rules` + `rule_versions`. O'zbekcha qo'shimchalarni kesuvchi oddiy stemmer. Qoida AI'siz parser orqali tekshiriladi (tushunilmasa saqlanmaydi) va keyingi buyruq rejasiga saqlash/eksportdan oldin qo'shiladi; test qoidalari son/variant/AI ni to'ldiradi; Word shablon `WordSession.new_document()` da ishlatiladi. AI so'roviga faqat mos keladigan eslatmalar qo'shiladi.
- **File Agent** (`fileagent.py`): hech qachon ustiga yozmaydi ("Nom (2).ext"), o'chirish faqat Savatga (`SHFileOperation` + `FOF_ALLOWUNDO`), zaxiralar `D:\NEXVARA\Zaxira\Fayllar\<nom-hash>\`, tiklashdan oldin joriy fayl ham zaxiralanadi, jurnal `logs\file-ops.jsonl`.
- **Workflows** (`workflows.py`): qadam = chat buyrug'i / tasdiq / kutish. Buyruq chatdagidek bajariladi (AI'siz, pul sarflamaydi; tasdiq so'ralsa to'xtaydi). Papka kuzatish 15 s'da bir, fayl kalit = yo'l+hajm+vaqt (bir marta), `_NEXVARA` chiqishlar e'tiborsiz. Kunlik jadval `last_daily` bilan.
- **NEXVARA BI** (`bi/`): Node/React o'rniga Python ETL (`bi/data.py`: o'qish, tur, bosqichlar, xavfsiz formula — `eval` yo'q) + `bi/dash.py` (avtomatik dizayn, vidjet hisoblari, filtr, saqlash `D:\NEXVARA\BI\*.json`, eksport). UI `ui/bi.js` SVG'ni o'zi chizadi; PNG/PDF eksport sahifani bitta SVG qilib canvas orqali oladi.
- **Devices** (`remote.py`): `ThreadingHTTPServer` + TLS (o'z sertifikati), telefon sahifasi `ui/mobile.html`. Bir martalik 6 xonali kod (10 daqiqa, 5 xato → blok), token SHA-256 xeshi, haftalik almashinuv, `X-Request-Id` bilan idempotentlik, faqat NEXVARA yaratgan fayllarni yuklab berish.

## Ishga tushirish

```powershell
.\scripts\setup.ps1          # .venv yaratadi va bog'liqliklarni o'rnatadi
.\scripts\run.ps1            # NEXVARA oynasini ochadi
.\scripts\test.ps1           # lint + unit testlar + oyna smoke testi
.\scripts\test.ps1 -Office   # + haqiqiy Excel testi (ekranda Excel ochiladi)
```
