# PROGRESS — ish jurnali

Claude Code va Codex shu faylni ishni boshlashda o'qiydi va yakunida **yuqoriga** yangi yozuv qo'shadi (qoidalar: [AGENTS.md](AGENTS.md)).

---

## 2026-10-16 (3) — Claude Code — GitHub (private), Word va PowerPoint Skills (M4)

**GitHub:**
- Foydalanuvchi GCM orqali `sardorbektoychiyev08-ctrl` hisobiga kirdi. GitHub API orqali tekshirildi: `Nexvara-loyiha` repozitoriyasi **private** (`"private": true`) va bo'sh edi.
- Push'dan oldin Git tarixi qayta tekshirildi: kalitlar, tokenlar, parollar, shaxsiy fayllar va Office/PDF fayllari yo'q.
- `main` push qilindi (940eaac). Ushbu bosqich `main` ga merge qilingandan keyin yana push qilindi.

**Tarmoqlar:** Claude: `claude/office-skills` (yangi). Codex: `codex/model-router`, `main` bilan tenglashtirildi, vazifasi AGENTS.md da. Codex o'z ishini shu tarmoqda boshlaydi.

**Word skill** (`skills/word/`):
- `ops.py`: sarlavhalar (uslublar raqamli konstanta orqali, ruscha Word'da ham ishlaydi), punktlar, jadval (ConvertToTable, sarlavha rangi, raqamlar markazda), rasm, izoh (matn bo'yicha bog'lanadi), header, sahifa raqamlari, mundarija (`{MUNDARIJA}` belgisi orqali), find/replace (natija qayta sanab tekshiriladi), A4 va chetlar (3/1,5/2/2 sm), DOCX/PDF.
- `demo.py`: rasmiy hisobot, 8 qadam, **15 tekshiruv**.

**PowerPoint skill** (`skills/powerpoint/`):
- `ops.py`: 16:9, brend mavzusi (master), sarlavha, punktlar, jadval, haqiqiy grafik (AddChart2 + ichki workbook), rasm, ma'ruzachi izohlari, o'tishlar, animatsiya, slaydlarni ko'chirish, PPTX/PDF.
- `layout.py`: matn sig'ishi, slayddan chiqib ketish va ustma-ust tushish tekshiruvi (salbiy test bilan isbotlangan).
- `demo.py`: 6 slayd, 8 qadam, **11 tekshiruv**.
- PowerPoint bitta nusxada ishlaydi. Session foydalanuvchining ochiq taqdimotlarini yopmasligi alohida test bilan tasdiqlandi.

**Office 2016 (ruscha) da topilgan va hal qilingan muammolar:**
1. Word COM'da **nomli argumentlar jimgina e'tiborsiz qoldiriladi** (`Find.Execute(Replace=...)`, `AddPicture(Range=...)`, `Comments.Add(Range=...)`): almashtirish bajarilmasdi, rasm sarlavha ichiga tushardi. Hammasi pozitsion argumentlarga o'tkazildi va regressiya testlari qo'shildi.
2. Word `Paragraphs.Last` obyekti "siljiydi": saqlangan paragraf keyin boshqa paragrafga ishora qiladi. Endi izohlar matn bo'yicha bog'lanadi.
3. `Application.CentimetersToPoints` COM orqali ishlamaydi. Hisob Python'da (`cm_to_pt`).
4. PowerPoint: grafik faqat oynali taqdimotda yaratiladi; `SetSourceData` uchun PlotBy argumenti kerak; `HWND` mavjud emas (oyna `PPTFrameClass` orqali topiladi); `ExportAsFixedFormat` pywin32'da ishlamaydi (`SaveCopyAs(..., 32)` ishlatiladi).

**UI:** Office Agent sahifasida 4 ta tugma bor: Excel jadval, Excel dashboard, Word hisobot, PowerPoint taqdimot. Self-test to'rttalasini ham haqiqiy UI orqali bosadi.

**Testlar** (`.\scripts\test.ps1 -Office`, foydalanuvchi ruxsati bilan):
| Test | Natija |
|---|---|
| ruff check + format | PASS |
| Unit testlar (41 ta) | PASS |
| Office testlari (24 ta: Excel 15, Word 5, PowerPoint 4) | PASS |
| UI self-test: 4 ta tugma (Excel 7/7, dashboard 14/14, Word 15/15, PowerPoint 11/11) | PASS (4 ishga tushirishdan 3 tasida) |
| UI self-test: PowerPoint tugmasi (birinchi ishga tushirish) | FAIL (1 marta): 8 qadamning hammasi o'tdi, lekin vazifa yakunlanmay osilib qoldi va PowerPoint jarayoni yetim qoldi. Sababi aniqlanmadi, keyingi 3 ta to'liq ishga tushirish PASS. Session yopilishiga log yozuvlari qo'shildi; takrorlansa joyi ko'rinadi |
| Oyna smoke | PASS |
| Office 2019/2021/365 | NOT TESTED |

**Keyingi qadam (Claude):** PowerPoint osilishini kuzatish va vazifalar uchun watchdog/timeout qo'shish; mavjud Word/PowerPoint faylini ochib tahrirlash (shablon); Excel'dagi qolgan ishlar (mavjud faylni tahlil, xato formulalar, fayllarni birlashtirish). Keyin M2 (agent tool sxemalari).
**Codex (`codex/model-router`):** M7 Model Router, faqat soxta provayder bilan, pullik API'siz.

---

## 2026-10-16 (2) — Claude Code — Excel skill 1–2-bosqich, UI sinovi, ruscha Office, tarmoqlar

**Qilindi:**
- **Git tarmoqlari**: `main` (faqat PASS), `claude/excel-skill`, `codex/model-router`. Qoidalar va Codex vazifasi AGENTS.md da.
- **GitHub push**: QILINMADI. Bu kompyuterda GitHub login'i yo'q; anonim tekshiruvda repo 404 qaytardi (private yoki hali yaratilmagan), lekin private ekanini login bilan tasdiqlab bo'lmadi. Foydalanuvchi talabi: faqat private repo'ga. Git tarixi tekshirildi: kalitlar, tokenlar, parollar, shaxsiy fayllar yo'q.
- **Ruscha Office**: bu kompyuterdagi Excel interfeysi ruscha (LanguageID 1049), Windows mintaqasi uz-Latn-UZ (o'nli `,`, guruh ` `, ro'yxat `;`). Hamma Office testlari shu muhitda o'tdi.
- **Topilgan va tuzatilgan 2 ta jiddiy xato:**
  1. Excel 2016 + uz-Latn: `Range.NumberFormat` inglizcha kodni tarjima qilmaydi, natijada `#,##0` → `1234567,891.00`. Birinchi demo jadvalda ham shu xato bor edi. Endi `ops.set_number_format` mahalliy ajratgichlar bilan `NumberFormatLocal` yozadi. Demo va dashboard ekrandagi matnni (`.Text`) ham tekshiradi.
  2. pywin32 naive `datetime` ni 5 soatga siljitardi (14:30 → 09:30), `date` turini esa umuman qabul qilmasdi. Endi sanalar Excel seriya raqami sifatida yoziladi.
- **`skills/excel/ops.py`**: katta jadvallarni bo'laklab yozish/o'qish, ko'p kalitli sort, AutoFilter (matn va son), RemoveDuplicates, trim, raqam/foiz/sana formatlari, shartli formatlash (qiymat bo'yicha rang, color scale, data bars), grafiklar (column/bar/line/pie/doughnut/area/scatter), PivotTable, UTF-8 CSV va PDF eksport.
- **`skills/excel/formulas.py`**: SUMIFS, o'sish, lookup. XLOOKUP bor-yo'qligi Excel'ning o'zida tekshiriladi; Office 2016 da u yo'q, shuning uchun INDEX/MATCH ishlatiladi.
- **`skills/excel/dashboard.py`**: savdo dashboardi: 144 qatorli ma'lumot varag'i, oylik/hudud/kategoriya SUMIFS jadvallari, 7 ta KPI (SUM, IF, AVERAGE, COUNTIF, lookup), 3 ta grafik, PivotTable, shartli formatlash. Natija qayta ochiladi va 14 ta tekshiruvdan o'tkaziladi (Python hisobi bilan solishtiriladi).
- **UI**: Office Agent sahifasiga "Excel dashboard yaratish" tugmasi qo'shildi. `--selftest-excel DIR` ikkala tugmani haqiqiy UI'da bosib, natijani tekshiradi.

**Testlar** (`.\scripts\test.ps1 -Office`, foydalanuvchi ruxsati bilan):
| Test | Natija |
|---|---|
| ruff check + format | PASS |
| Unit testlar (34 ta) | PASS |
| Real Excel testlari (15 ta): demo, overwrite, UI tugmalari, ruscha formula, dashboard, ops (sort, filter, dublikat, format, shartli format, grafik, pivot, CSV/PDF, 20 000 qator) | PASS |
| UI: "Excel'da jadval yaratish" tugmasi (6 qadam, 7/7 tekshiruv) | PASS |
| UI: "Excel dashboard yaratish" tugmasi (8 qadam, 14/14 tekshiruv) | PASS |
| Oyna smoke | PASS |
| Windows mintaqasi ru-RU bo'lgan kompyuterda | NOT TESTED (mintaqani o'zgartirish foydalanuvchi tizimiga aralashish bo'ladi) |
| Office 2019/2021/365 (XLOOKUP yo'li) | NOT TESTED (faqat Office 2016 bor) |
| GitHub push | BLOCKED (login yo'q, private ekanligi tasdiqlanmagan) |

**Ma'lum zararsiz shovqin:** office testlarida `Windows fatal exception: code 0x80010108`. Batafsil AGENTS.md da.

**Keyingi qadam (Claude, `claude/excel-skill`):** mavjud foydalanuvchi faylini ochib tahlil qilish (ustun turlarini aniqlash, tozalash), formula xatolarini (#DIV/0!, #N/A) topish, bir nechta faylni birlashtirish, print sozlamalari, data validation. Keyin M2 uchun Excel amallarini agent "tool" sxemalariga o'rash.
**Codex (`codex/model-router`):** AGENTS.md dagi M7 vazifasi; pullik API chaqirilmaydi.

---

## 2026-10-16 — Claude Code — v0.1.0: muhit, desktop oyna, birinchi real Excel sinovi

**Qilindi** (spec 29-bo'lim, 1–12-bandlar):
- Muhit tekshirildi: Windows 11, Office 2016 32-bit (Excel/Word/PowerPoint COM bor), Python 3.13. Node, .NET, Android SDK yo'q. Tafsilotlar: docs/ARCHITECTURE.md.
- Stek tanlandi: Python + pywin32 + pywebview. Sabablari ARCHITECTURE.md da.
- `docs/MASTER_SPEC.md` (spec to'liq), `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `AGENTS.md`, `CLAUDE.md`, `.env.example` yaratildi.
- `src/nexvara/core/task.py`: task state machine, background runner, kooperativ bekor qilish.
- `src/nexvara/skills/excel/`: alohida ko'rinadigan Excel jarayoni (foydalanuvchining ochiq fayllariga tegmaydi), jadval yozish, formatlash (raqamlar markazda, sarlavha rangli, chegaralar, autofit, freeze), xavfsiz saqlash (overwrite rad etiladi, overwrite bo'lsa avval backup olinadi), qayta ochib 6 ta tekshiruv.
- `src/nexvara/app/`: NEXVARA oynasi: 11 bandli navigatsiya, chat (AI ulanmaganini ochiq aytadi), Office Agent sahifasi, jonli task paneli (qadamlar, bekor qilish, natija faylini ko'rsatish), tarix, dark/light.
- `scripts/setup.ps1`, `run.ps1`, `test.ps1`.

**Testlar** (`.\scripts\test.ps1 -Office`, foydalanuvchi ruxsati bilan):
| Test | Natija |
|---|---|
| ruff check + format | PASS |
| Unit testlar (22 ta) | PASS |
| Haqiqiy Excel 2016: 10 qatorli jadval → format → saqlash → qayta ochib tekshirish (6/6) | PASS (5 marta ketma-ket) |
| Haqiqiy Excel: mavjud faylni overwrite qilmaslik | PASS |
| keep_open rejimi (Excel natija bilan ochiq qoladi) | PASS (qo'lda skript bilan) |
| Desktop oyna smoke (oyna ochiladi, UI chiziladi, JS→Python ko'prik) | PASS |
| UI'dagi "Excel'da jadval yaratish" tugmasini real Excel bilan bosish | NOT TESTED (API qismi fake bilan testlangan; tugmani foydalanuvchi sinab ko'rishi kerak) |
| Office ruscha interfeysda | NOT TESTED (kod lokalga bog'liq emas, lekin sinalmagan) |

**Topilgan va tuzatilgan:**
- COM havolalari Excel yopilgandan keyin bo'shatilgani uchun `RPC_E_DISCONNECTED` xatosi chiqardi. Endi COM obyektlari alohida funksiyada yashaydi va Excel yopilishidan oldin bo'shatiladi.
- Saqlash yo'li endi Excel ochilishidan oldin tekshiriladi.

**Keyingi qadam:** ROADMAP.md dagi "Yaqin navbat": Excel skill'ni kengaytirish (mavjud faylni ochish, sort/filter, diagramma, eksport) va agent uchun tool interfeysi.
