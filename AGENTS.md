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
