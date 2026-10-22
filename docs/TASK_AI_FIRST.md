# TOPSHIRIQ: «Avval AI» — NEXVARA Claude chati kabi tushunib ishlasin

Kimga: **Codex** (Windows). Yozdi: Claude, 2026-10-22. Tugagach **Claude tekshiradi**.
Egasining so‘zi: «pul ketsa ham mayli, lekin sen (Claude chat) kabi ishlasin; jadval tuzishda ham
xatolar qilyapti».

## 0. Boshlashdan oldin
- [AGENTS.md](../AGENTS.md), [PROGRESS.md](../PROGRESS.md) (45), (46) yozuvlari, [docs/AI.md](AI.md),
  [docs/AGENT.md](AGENT.md), [docs/PRIVACY.md](PRIVACY.md).
- Tarmoq: `claude/qolgan-ishlar` dan `codex/ai-first` oching, faqat shu yerda ishlang.
  `main` ga merge, push va reliz — **faqat egasi tasdig‘i bilan**.

## 1. Muammo (dalil bilan)
`Api.chat` → `Api._chat_inner` ([src/nexvara/app/api.py](../src/nexvara/app/api.py)) xabarni AI’dan
**oldin** ~12 ta qoida asosidagi ishlovchidan o‘tkazadi: `_chat_sections`, `_chat_teach`,
`_chat_read`, `_chat_drawing`, `_chat_officeai`, `_chat_media`, `_chat_weekly`, `_chat_agent`
(`agent/nlu.py`, `split_chain`), `_chat_bi`, `_chat_find_files`, `_chat_command` (`agent/parse.py`),
dars ishlanmasi, test, taqdimot, mavzu… AI rejalashtiruvchisi (`_chat_ai` → `ai/features.plan`)
faqat **hech kim tutmasa** chaqiriladi. Qoidalar so‘z qidiradi, ma’noni emas — natijada xato
tutib oladi. 2026-10-22 jonli suhbat (`D:\NEXVARA\app.db`, `chat_log`):

| Egasi yozdi | NEXVARA nima qildi | To‘g‘risi |
|---|---|---|
| «noutbukimdagi exselni och» | AI `office.write` tanladi, javob yozdi | Excel’ni ochish (`app.open`, (45) da qo‘shildi) |
| «qara men hali senga yoz demadim tozala yozganlaringni» | «Qaysi Office fayli…?» | Rad etishni tushunish; hozirgina yaratilgan fayl/yozuvni bekor qilishni taklif qilish (o‘chirish — tasdiq bilan) |
| (telefondan rasm) «jadvalni chiroyliroq qilib tuz» | «Rasmda jadval topilmadi (ustunlar ajralmadi)» — oflayn OCR | AI ko‘rish bilan jadvalni o‘qib, chiroyli Excel jadval |
| «bugungi sanadagini exselga jadval qilib tushib ber», «exsel qil» | yana o‘sha oflayn xato | rasmdagi bugungi sana qatorlarini Excel’ga |
| «hozir qilgan ishingni ko‘ryabsanmi», «exsel oynasi ochilmadiyu» | «So‘rov yuborilmadi: «Telefondan»…» | (46) da maxfiylik xatosi tuzatildi; endi suhbatni tushunib javob berish, faylni ekranda ochish |
| «qara jadvalda xatoliklar bor ko‘rgin» | rasmni yana AI’ga yubordi, natija Excel bilan solishtirilmadi | rasm ↔ yaratilgan Excel’ni solishtirib, farqlarni ko‘rsatish va tuzatishni taklif qilish |

## 2. Talablar

### 2.1 Yo‘naltirish: AI birinchi
1. AI tayyor bo‘lsa (`_ai_ready()`, limit tugamagan), **har bir xabar avval rejalashtiruvchiga**
   boradi. Undan oldin faqat quyidagilar qoladi (AI’siz, darhol):
   - API kalitga o‘xshash matn (`looks_like_secret`) — hozirgidek;
   - kutilayotgan tasdiqqa «Ha/Yo‘q» javobi;
   - «buni unut» (`_chat_forget`).
2. Hozirgi qoida ishlovchilari o‘chirilmaydi: ular **asbob (tool)** bo‘lib qoladi va AI ularni
   tanlaydi. Rejalashtiruvchi ko‘ra olmaydigan imkoniyatlar uchun `agent/tools.py` ga asbob
   qo‘shing (hozir faqat `_chat_inner` ichida bo‘lganlar): rasm → Excel/Word (AI ko‘rish bilan),
   rasmni o‘qish, chizma, test tuzish, dars ishlanmasi, taqdimot, mavzu, haftalik hisobot,
   OfficeAI (tarjima va h.k.), media (rasm yaratish), o‘rgatish (teach). Mavjud `plan.intent`
   (`test/topic/presentation/command`) yo‘li ishlayversin.
3. AI o‘chiq, internet yo‘q, provayder band yoki limit tugagan bo‘lsa — **hozirgi zanjir
   o‘zgarmasdan** ishlaydi (zaxira). Bunda javob oxirida bir qator: «AI hozir ishlamayapti, oddiy
   rejimda bajardim».
4. Sozlama: `settings.json` → `ai.ai_first` (standart `true`), Sozlamalar → AI’da o‘zbekcha belgi
   («Avval AI: har xabarni AI tushunadi»). Telefondan kelgan chat (`/api/v1/chat`) ham shu yo‘ldan.
5. Rejalashtiruvchiga yuboriladi: suhbat tarixi (`_recall`), kontekst (`_ctx.snapshot()`:
   oxirgi fayl, oxirgi natija, ochiq rasm), qoidalar, faktlar. «uni», «o‘sha jadval», «hozir
   qilgan ishing» — kontekstdagi oxirgi faylga bog‘lanadi.
6. Rad etish va tuzatish: «yo‘q», «unday demadim», «to‘xta», «bekor qil», «tozala yozganlaringni»
   — AI tushunadi; oxirgi amal natijasini bekor qilishni **taklif qiladi**; fayl o‘chirish/ustidan
   yozish — faqat «Ha» bilan (AGENTS.md qat’iy qoida).
7. Noaniq bo‘lsa — **bitta** aniq savol (HUMAN_STYLE), taxmin bilan noto‘g‘ri ish qilmaslik.

### 2.2 Jadval sifati (rasm → Excel)
1. AI yoqiq bo‘lsa rasmdagi jadval **standart holatda AI ko‘rish** bilan o‘qiladi (oflayn OCR
   faqat zaxira). «AI bilan» deb yozish shart emas.
2. Natija: sarlavha qatori (qalin, fon, muzlatilgan), ramka, ustun kengligi moslangan, raqamlar
   raqam sifatida (`ops.set_number_format`), sanalar `ops.write_rows` orqali, birlashgan
   kataklar saqlanadi, bo‘sh/keraksiz qatorlar yo‘q. Formulalar faqat `Range.Formula` (AGENTS.md).
3. Excel **ekranda ochiladi** (spec 5-bo‘lim; egasi «exsel oynasi ochilmadi» dedi). Telefondan
   bo‘lsa — kompyuterda ochiladi va telefonga fayl yo‘li/yuklab olish beriladi.
4. «chiroyliroq qil» — oxirgi Excel faylga bezak; «bugungi sanadagini» — faqat mos qatorlar.
5. «jadvalda xatolar bor» — AI rasm va yaratilgan jadvalni solishtiradi, farqlar ro‘yxatini
   ko‘rsatadi va tuzatishni taklif qiladi (tuzatish — tasdiq bilan, yangi versiya fayl).

### 2.3 Model va xarajat
- Egasi pullik ishlatishga rozi. Rejalashtiruvchi va jadval/ko‘rish uchun **kuchli** daraja
  (Flash-Lite emas); bepul Gemini birinchi, band/limit bo‘lsa pullik zaxira (PROGRESS (43)).
- Har chaqiruv `ai_usage` ga yoziladi; kunlik/oylik limit va `confirm_over_usd` qoidasi
  o‘zgarmaydi. Tasdiqsiz pullik chaqiruv yo‘q — faqat mavjud qoidalar bo‘yicha.
- Maxfiylik: hamma narsa `ai/privacy.py` orqali (o‘zgartirmang, chetlab o‘tmang).

## 3. Testlar (majburiy)
- `tests/unit/test_ai_first.py`: **soxta provayder** bilan (haqiqiy pullik chaqiruv yo‘q).
  1-bo‘limdagi 6 ta ibora + quyidagilar uchun rejalashtiruvchi **birinchi** chaqirilishi va
  kutilgan asbob tanlanishi: «Excel’ni och», «Hisobot.xlsx ni och, B ustun bo‘yicha sarala»,
  «7-sinf fizika 20 ta test», «salom». AI o‘chiq bo‘lsa — eski natija o‘zgarmagani
  (mavjud testlar PASS bo‘lib qolishi kerak).
- Provayder 503/limit → zaxira zanjir, «oddiy rejim» qatori.
- Rasm → Excel: AI javobidan qurilgan qatorlar (sarlavha, raqam, sana) — Office’siz birlik testi;
  haqiqiy Excel — `tests/office/` da, faqat egasi ruxsati bilan (`-Office`).
- `.\scripts\test.ps1` to‘liq PASS (ruff check + format). Natijani to‘qimang: FAIL/NOT TESTED
  bo‘lsa shunday yozing.

## 4. Yakunlash
1. PROGRESS.md yuqorisiga yozuv (47): nima qilindi, test natijalari, haqiqiy AI bilan sinov —
   NOT TESTED (egasi bilan qilinadi).
2. docs/AI.md va docs/AGENT.md ga «Avval AI» yo‘li qisqacha.
3. Mantiqiy commitlar `codex/ai-first` da. Push/reliz yo‘q.
4. HANDOFF_CODEX.md tepasiga: «AI-first tayyor, Claude tekshirsin» + nimalar qolgani.
