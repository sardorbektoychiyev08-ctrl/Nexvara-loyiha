# AGENTS.md — NEXVARA uchun AI agentlar qo'llanmasi

Bu loyihada **Claude Code** va **OpenAI Codex** navbatma-navbat ishlaydi: birining limiti tugasa, ikkinchisi davom ettiradi. Bir-biringizning xotirangizni ko'rmaysiz, shuning uchun **yagona haqiqat manbai shu repozitoriy**.

## Ishni boshlashdan oldin (majburiy)
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
- `claude/<mavzu>`: Claude Code ishlaydigan tarmoqlar (hozir: `claude/excel-skill`).
- `codex/<mavzu>`: Codex ishlaydigan tarmoqlar (hozir: `codex/model-router`).
- Har agent **faqat o'z tarmog'ida** ishlaydi. Boshqa agentning tarmog'ini faqat limit tugab ish shu agentga o'tganda davom ettiradi, va bu PROGRESS.md da yoziladi.
- Merge qilishdan oldin: tarmoqqa `main` ni merge qiling, `.\scripts\test.ps1` (Office kodi o'zgargan bo'lsa `-Office` bilan) PASS bo'lsin, keyin `git checkout main && git merge --no-ff <tarmoq>`.
- Konfliktlarni kamaytirish uchun papka egaligi:
  - `src/nexvara/skills/excel/`, `tests/office/` → `claude/excel-skill`
  - `src/nexvara/models/` (yangi paket), `tests/unit/test_models*.py` → `codex/model-router`
  - Umumiy fayllar (`PROGRESS.md`, `ROADMAP.md`, `pyproject.toml`, `app/`) → kichik, alohida commitlarda o'zgartiring; konflikt bo'lsa ikkala tomonning yozuvlarini saqlang.

## Hozirgi vazifalar taqsimoti
- **Claude → `claude/excel-skill`**: Excel skill kengaytmasi (formulalar, formatlash, PivotTable, grafiklar, filtrlar, katta fayllar, dashboard).
- **Codex → `codex/model-router`**: M7 Model Router skeleti, `src/nexvara/models/`: provayder interfeysi, CHEAP/BALANCED/POWERFUL/SPECIALIST darajalari, model nomlari konfiguratsiyadan, token/xarajat hisobi, kunlik/oylik budget, fallback. **Faqat soxta (fake/offline) provayder bilan testlar; haqiqiy pullik API chaqirilmaydi.** Kalitlar faqat `.env` dan o'qiladi.

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
- Formulalarni `Range.Formula` (inglizcha) orqali yozing, `FormulaLocal` orqali emas. Office ruscha bo'lishi ham mumkin.
