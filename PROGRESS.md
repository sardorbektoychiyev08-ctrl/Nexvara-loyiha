# PROGRESS — ish jurnali

Claude Code va Codex shu faylni ishni boshlashda o'qiydi va yakunida **yuqoriga** yangi yozuv qo'shadi (qoidalar: [AGENTS.md](AGENTS.md)).

---

## 2026-10-16 (5) — Claude Code — "Shu mavzu kerak": darslikdan mavzuni chiqarish

**Foydalanuvchi talabi:** test bilan cheklanmasin; "shu mavzu kerak" desam, mavzuni chiqarib bersin.

**Qilindi:**
- `knowledge/topics.py`: mavzu = §-bo'lim (sarlavhasidan keyingi § gacha). Avval bo'lim sarlavhalari bo'yicha qidiradi (o'zbekcha qo'shimchalar hisobga olinadi), topilmasa matn bo'yicha qidirib, shu sahifa tegishli bo'limni oladi. Kolontitullar va bet raqamlari olib tashlanadi, ko'p qatorli KATTA HARFLI sarlavhalar birlashtirib o'qishga qulay qilinadi.
- Ba'zi darsliklarda § sarlavhasi rasm sifatida chizilgan (matn qatlamida yo'q). Bunday bo'limlar **mundarija** (`N-§. ... 75`) va bosma bet siljishi (masalan, PDF 62 = kitob 69) orqali joylashtiriladi. 7-sinf fizikada 46 dan 44 ta bo'lim topildi.
- Mundarija qatorlari va mundarija sahifalari bo'lim deb olinmaydi. Baza sxemasi versiyasi 3: eski indeks "Yangilash"da o'zi qayta quriladi.
- Umumiy fan nomi ("tarixdan") kutubxonadagi aniq fanga mos keladi ("O‘zbekiston tarixi", "Jahon tarixi").
- `knowledge/topicdoc.py`: natija ikki xil. **Word** (tahrirlanadigan matn: sarlavha, manba "kitob, 65–70-betlar", paragraflar) va **asl sahifalar PDF** (kitobning o'sha betlari: rasm, formula, jadval bilan). Qayta ochib 4 ta tekshiruv. Fayllar `D:\NEXVARA\Mavzular` da.
- Chat: "7-sinf fizika Nyuton qonunlari mavzusini chiqarib ber" yozilsa, chatda mavzu nomi, betlar va qisqa ko'rinish chiqadi, so'ng Word va PDF yaratiladi. Test so'rovlari ustuvor; mavzu so'rovi uchun sinf yoki fan aytilishi shart (oddiy suhbat adashib so'rov deb olinmasligi uchun).
- UI: "Mavzuni chiqarish" tugmasi; natija panelida "Asl sahifalar (PDF)" va "Kitobda ochish (N-bet)" tugmalari.

**Haqiqiy darslik bilan sinov** (eduportal sinov nusxalari, kutubxonaga qo'shilmagan): "Nyuton qonunlari" → 19-§. Nyutonning birinchi qonuni (65–70-betlar); "tarixdan Jadidlar" → 9-sinf O‘zbekiston tarixi, Jadidlar bo'limi; "Toshkentning bosib olinishi" → 7-§ (23–26-betlar); kitobda yo'q mavzu → "topilmadi".

**Ma'lum kamchilik:** sarlavhasi rasm bo'lgan bo'limda Word matni boshida oldingi bo'limning oxirgi qatorlari bo'lishi mumkin, chunki chegarani matndan aniqlab bo'lmaydi. Asl sahifalar PDF'i baribir to'g'ri betlarni beradi.

**Testlar** (`.\scripts\test.ps1 -Office`):
| Test | Natija |
|---|---|
| ruff check + format | PASS |
| Unit testlar (75 ta; +11 mavzu testi) | PASS |
| Office testlari (30 ta; +mavzu Word/PDF, chat orqali mavzu, UI'da "Mavzuni chiqarish") | PASS |
| Oyna smoke | PASS |
| Haqiqiy yangi darsliklar bilan | BLOCKED: foydalanuvchi hali PDF qo'shmagan |

---

## 2026-10-16 (4) — Claude Code — Darsliklar kutubxonasi va AI'siz test tuzish

**Foydalanuvchi talabi:** NEXVARA xotirasiga maktab darsliklarini yuklash va "test tuzib ber" deyilganda test tuzish. Qarorlar (foydalanuvchi tanlovi): manba — faqat **yangi** darsliklar (foydalanuvchi o'zi qo'shadi), barcha sinf/fanlar, til — o'zbek (lotin), AI hozircha ulanmaydi (oddiy avtomatik testlar).

**Manbalar tekshiruvi:**
- `eduportal.uz` (vazirlikning eski rasmiy portali, ©2017): 6–11-sinf, 96 ta o'zbekcha PDF, 1,4 GB, 2017–2019 nashrlari. 1–5-sinf sahifalari server xatosi beradi. Foydalanuvchi eski nashrni **rad etdi**, shuning uchun hech narsa yuklab olinmadi.
- Yangi (2025–2026) darsliklarni Respublika ta'lim markazi Telegram orqali tarqatadi, ularni avtomatik yuklab bo'lmaydi. Foydalanuvchi PDF'larni o'zi `D:\NEXVARA\Darsliklar` papkasiga tashlaydi.
- Sifat sinovi uchun eduportal'dan faqat 2 ta PDF (7-sinf fizika, 9-sinf tarix) vaqtinchalik papkaga yuklandi. Ular kutubxonaga ham, Git'ga ham qo'shilmagan.

**Qilindi** (`src/nexvara/knowledge/`, `config.py`):
- `config.py`: ma'lumotlar `D:\NEXVARA` da (`NEXVARA_DATA` bilan o'zgartiriladi): `Darsliklar\`, `Testlar\`, `nexvara.db`. Repozitoriyadan tashqarida.
- `textnorm.py`: PDF artefaktlarini tozalash: `o‘`/`g‘`/tutuq (U+FFFD → ‘/’), yumshoq defis, satr oxiridagi bo'g'in ko'chirish; sarlavha qatorlari gaplarga qo'shilmaydi.
- `catalog.py`: fayl nomi, papka va kitob boshidan sinf, fan (28 ta fan) va nashr yili aniqlanadi.
- `store.py`: SQLite + FTS5 (o'zbekcha qo'shimchalar uchun prefiks qidiruv), bo'limlar (§, mavzu, bob). Bir fanning bir nechta nashri bo'lsa, eng yangisi ishlatiladi.
- `ingest.py`: papkani indekslash. Yangi, o'zgargan, dublikat, o'chirilgan fayllar aniqlanadi. Skaner (matnsiz) va kirill yozuvidagi PDF'lar alohida ro'yxatda ko'rsatiladi (OCR keyinroq, M5).
- `quiz.py`: AI'siz savollar: ta'rif → qaysi atama (A–D, chalg'ituvchilar shu darslikdagi boshqa atamalardan), yil/raqam (formulali gaplarsiz), bo'sh joyni to'ldirish, to'g'ri/noto'g'ri, moslashtirish. Seed bilan deterministik, yetarli matn bo'lmasa ochiq aytadi.
- `service.py` + `testdoc.py`: chat buyrug'ini tushunish ("7-sinf fizika Nyuton qonunlari 20 ta test 2 variant"). Word'da test yaratiladi: har variant alohida sahifada, F.I.Sh./sinf/sana qatori, oxirida javoblar kaliti (manba sahifasi bilan), DOCX + PDF, qayta ochib 5 ta tekshiruv.
- UI: "Darsliklar va testlar" bo'limi (papka, yangilash, kitoblar jadvali, muammoli fayllar, test formasi). Chat ham test buyrug'ini qabul qiladi.

**Sifat (haqiqiy darslik bilan sinov, 9-sinf tarix va 7-sinf fizika):** tarixda savollar asosan mantiqli (yillar, atamalar: Kontributsiya, Vassal, Uyezd, Volost, Katorga). Fizikada ham ta'riflar topiladi (Sanoq jism, Kinematika, Moddiy nuqta), lekin ba'zi savollarda shovqin qoladi. Natija "o'qituvchi tahrirlaydigan qoralama"; Word hujjat oxirida bu haqida ogohlantirish bor. Haqiqiy A–D savollar uchun AI rejimi (M7) kerak.

**Topilgan va tuzatilgan xatolar:** `o‘` tiklangandan keyin yana buzilardi; " - " birlashtirish ta'riflarni buzardi (olib tashlandi); chat'da task snapshot'idagi bo'sh `error` maydoni xato deb o'qilardi; `count: 0` jimgina 20 ga aylanardi.

**Testlar** (`.\scripts\test.ps1 -Office`, foydalanuvchi ruxsati bilan):
| Test | Natija |
|---|---|
| ruff check + format | PASS |
| Unit testlar (64 ta; sintetik darslik + o'zimiz yasagan PDF) | PASS |
| Office testlari (28 ta; jumladan kutubxona: indekslash → Word test 2 variant, chat orqali test, topilmagan mavzu, UI'da "Yangilash" + "Test tuzish") | PASS |
| Oyna smoke | PASS |
| Haqiqiy yangi (2025–2026) darsliklar bilan | BLOCKED: foydalanuvchi hali PDF qo'shmagan |
| Skaner (matnsiz) PDF'lar | NOT TESTED: aniqlanadi va ro'yxatda ko'rsatiladi, OCR yo'q |

**Keyingi qadam:** foydalanuvchi darsliklarni `D:\NEXVARA\Darsliklar` ga qo'shgach, haqiqiy natijani tekshirish va filtrlarni sozlash; AI rejimi (M7) ulanganda savol sifatini oshirish; OCR (M5).

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
