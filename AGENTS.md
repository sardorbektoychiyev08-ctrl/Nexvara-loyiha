# AGENTS.md — NEXVARA uchun AI agentlar qo'llanmasi

Bu loyihada **Claude Code** va **OpenAI Codex** navbatma-navbat ishlaydi: birining limiti tugasa, ikkinchisi davom ettiradi. Bir-biringizning xotirangizni ko'rmaysiz, shuning uchun **yagona haqiqat manbai shu repozitoriy**.

## Ishni boshlashdan oldin (majburiy)
0. Codex Windows ishini davom ettirsa: [HANDOFF_CODEX.md](HANDOFF_CODEX.md).
1. [PROGRESS.md](PROGRESS.md) ni o'qing: oxirgi holat, nima qilindi, keyingi qadam.
2. Kerak bo'lsa [docs/MASTER_SPEC.md](docs/MASTER_SPEC.md) (to'liq talablar), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/ROADMAP.md](docs/ROADMAP.md).
3. `git status` va `git log --oneline -10`: commit qilinmagan ish qolgan bo'lishi mumkin.

## Ish yakunida (majburiy)
1. Testlar: `.\scripts\test.ps1` (lint + unit + oyna smoke). Office'ga tegadigan o'zgarish bo'lsa, foydalanuvchi ruxsati bilan `-Office` bilan ham ishga tushiring.
2. [PROGRESS.md](PROGRESS.md) ning yuqorisiga yangi yozuv qo'shing: sana, kim (Claude/Codex), nima qilindi, test natijalari (PASS/FAIL/BLOCKED/NOT TESTED), keyingi qadam.
3. ROADMAP'dagi holatlarni yangilang.
4. Mantiqiy commit qiling. Push faqat foydalanuvchi tasdig'i bilan va maxfiy ma'lumot yo'qligini tekshirgandan keyin.

## Git tarmoqlari (Claude va Codex parallel ishlashi uchun)
- `main`: faqat testlardan o'tgan (PASS) kod. To'g'ridan-to'g'ri `main` ga commit qilinmaydi, faqat merge qilinadi.
- `claude/<mavzu>`: Claude Code ishlaydigan tarmoqlar (hozir: `claude/ai-router`).
- `codex/<mavzu>`: Codex ishlaydigan tarmoqlar (`codex/model-router` hozircha bo'sh, `main` bilan teng; Android uchun `codex/android-mobile`).
- Har agent **faqat o'z tarmog'ida** ishlaydi. Boshqa agentning tarmog'ini faqat limit tugab ish shu agentga o'tganda davom ettiradi, va bu PROGRESS.md da yoziladi.
- Merge qilishdan oldin: tarmoqqa `main` ni merge qiling, `.\scripts\test.ps1` (Office kodi o'zgargan bo'lsa `-Office` bilan) PASS bo'lsin, keyin `git checkout main && git merge --no-ff <tarmoq>`.
- Konfliktlarni kamaytirish uchun papka egaligi:
  - `src/nexvara/skills/` (excel, word, powerpoint, common), `tests/office/` → Claude (`claude/*`)
  - `src/nexvara/knowledge/` (darsliklar, testlar), `config.py` → Claude (`claude/*`)
  - `src/nexvara/agent/` (buyruqlar) → Claude (`claude/*`)
  - `src/nexvara/sources/` (darslik manbalari) → Claude (`claude/*`)
  - `src/nexvara/ai/` (provayderlar, router, xarajat, AI imkoniyatlari), `tests/unit/test_ai.py` → Claude (`claude/*`)
  - `src/nexvara/memory/`, `fileagent.py`, `workflows.py`, `bi/`, `remote.py`, `app/api_*.py`, `app/ui/bi.js`, `app/ui/mobile.html`, `tests/ui_scripts/` → Claude (`claude/*`)
  - `src/nexvara/agent/` (tools, nlu, context), `app/api_agent.py`, `app/api_sync.py`, `sync.py`, `docs/AGENT.md` → Claude (`claude/*`)
  - `src/nexvara/remote.py`, `remote_v1.py`, `protocol.py`, `devserver.py`, `docs/api/` (telefon API shartnomasi), `account.py`, `updater.py`, `installer/`, `scripts/build.ps1` → Claude (`claude/*`)
  - `android/` (native Android ilova, Kotlin + Compose) → Codex (`codex/android-mobile`). Topshiriq: [docs/ANDROID_HANDOFF.md](docs/ANDROID_HANDOFF.md). API o'zgarishi kerak bo'lsa PROGRESS.md da Claude'ga yozing
  - Umumiy fayllar (`PROGRESS.md`, `ROADMAP.md`, `pyproject.toml`, `app/`) → kichik, alohida commitlarda o'zgartiring; konflikt bo'lsa ikkala tomonning yozuvlarini saqlang.

## Hozirgi vazifalar taqsimoti
- **Claude**: Office skill'lari, darsliklar, buyruqlar va M7 (AI). Codex `codex/model-router` da hech narsa commit qilmagani uchun M7 ni Claude o'z zimmasiga oldi (2026-10-16): `src/nexvara/ai/`.
- **Codex**: limit tugaganda Claude'ning so'nggi `claude/*` tarmog'ini davom ettiradi (PROGRESS.md dagi oxirgi yozuvdan boshlab). Asosiy alohida vazifa: Android APK (`android/`, [docs/ANDROID_HANDOFF.md](docs/ANDROID_HANDOFF.md)).
- **AI qoidalari**: API kalitlar faqat Windows Credential Manager'da (`NEXVARA/ai/<provayder>`), hech qachon faylda yoki Git'da emas. Testlarda faqat soxta provayder; haqiqiy pullik chaqiruv faqat foydalanuvchi kalit kiritib, AI'ni o'zi yoqqanda. Har chaqiruv `app.db` dagi `ai_usage` jadvaliga yoziladi, kunlik/oylik limit va "qimmat so'rovda so'rash" chegarasi `settings.json` da.

## Foydalanuvchi haqida
- Dasturchi emas, o'zbek tilida yozadi. Javoblar o'zbekcha, sodda, texnik tafsilotsiz bo'lsin.
- Kod, test, build va hujjatlarni o'zingiz boshqaring.

## Qat'iy qoidalar (spec 0-bo'lim)
- Sinovdan o'tmagan narsani PASS demang. Test natijasini o'ylab topmang.
- Haqiqiy Office testlari ekranda Excel/Word ochadi: faqat foydalanuvchi ruxsati bilan (`NEXVARA_RUN_OFFICE=1`).
- API kalitlari va tokenlar faqat `.env` da (`.gitignore`'da). Pullik API'ni foydalanuvchi tasdig'isiz chaqirmang.
- O'chirish, overwrite va boshqa qaytarib bo'lmaydigan amallardan oldin tasdiq oling.
- `.gitignore` ni buzmang. Microsoft Power BI va NEXVARA ADMIN kodga kiritilmaydi.
- Office amallari standart holatda **ko'rinadigan** rejimda bajariladi (spec 5-bo'lim).

## Texnik ma'lumot
- Stek: Python 3.13 + pywin32 (Office COM) + pywebview (WebView2 UI). Sabablari: docs/ARCHITECTURE.md.
- Muhit: `.\scripts\setup.ps1` (`.venv` D: diskda). Ishga tushirish: `.\scripts\run.ps1`.
- Kod: `src/nexvara/` (core, skills/<nom>, app). Testlar: `tests/unit` (Office'siz), `tests/office` (haqiqiy Office).
- Lint/format: `ruff` (pyproject.toml). Har commitdan oldin `ruff check` va `ruff format --check` toza bo'lishi kerak.
- Office 2016 (32-bit) o'rnatilgan, Python 64-bit: COM out-of-process ishlaydi.
- **Word/PowerPoint COM: faqat pozitsion argumentlar.** Nomli argumentlar (`Range=...`, `Replace=...`) jimgina e'tiborsiz qoldiriladi. Uslub va layoutlar faqat raqamli konstanta orqali beriladi (ruscha Office'da nomlar boshqacha). Word paragraf obyektlarini keyinroq ishlatish uchun saqlamang, matn bo'yicha toping.
- PowerPoint bitta nusxada ishlaydi: foydalanuvchining taqdimotlariga tegmang (`OfficeSession` faqat o'z hujjatlarini yopadi).
- Formulalarni `Range.Formula` (inglizcha) orqali yozing, `FormulaLocal` orqali emas. Office ruscha bo'lishi ham mumkin.
- Raqam formatlari: faqat `ops.set_number_format` orqali (Excel 2016 + uz-Latn mintaqasida `NumberFormat` tarjima qilinmaydi, `NumberFormatLocal` + Excel ajratgichlari kerak). Sanalar: faqat `ops.write_rows`/`to_excel_value` orqali (pywin32 naive datetime ni 5 soatga siljitadi).
- Telegram session va API ma'lumotlari faqat `D:\NEXVARA\telegram` da; Git'ga hech qachon qo'shilmaydi.
- Telefon ulanishi: sertifikat `D:\NEXVARA\remote`, qurilma tokenlari faqat SHA-256 xesh holida `app.db` da. Sukut bo'yicha o'chiq. Android ilova faqat `/api/v1` (docs/api/openapi.yaml) bilan ishlaydi; marshrutlar ro'yxati test bilan hujjatga bog'langan.
- Google login: client JSON faqat `D:\NEXVARA\google_client.json`, refresh token Credential Manager'da (`NEXVARA/google/`). Reliz imzo kaliti faqat `D:\NEXVARA\release\signing_key.pem` (Git'ga hech qachon). Build: `.\scripts\build.ps1` (docs/RELEASE.md).
- UI sinovlari: `tests/ui_scripts/*.py` haqiqiy oyna ochadi (`tests/office/test_ui_pages.py` orqali, `-Office` bilan). Smoke har bir sahifani ochadi va JS xatolarini tekshiradi.
- `api.py` katta bo'lmasligi uchun har bo'lim o'z mixin faylida: `app/api_memory.py`, `api_files.py`, `api_workflows.py`, `api_bi.py`, `api_devices.py`.
- Darsliklar: haqiqiy darslik PDF'lari Git'ga **hech qachon** qo'shilmaydi (mualliflik huquqi). Testlar `tests/textbook_fixture.py` dagi sintetik matn va PDF bilan ishlaydi. Foydalanuvchi ma'lumotlari `D:\NEXVARA` da.
- Office testlarida `Windows fatal exception: code 0x80010108` chiqishi zararsiz: Excel yopilgandan keyin COM proxy bo'shatilganda pywin32 ichida ushlanadigan xato. Natija = pytest PASS/FAIL.
