# PROGRESS — ish jurnali

Claude Code va Codex shu faylni ishni boshlashda o'qiydi va yakunida **yuqoriga** yangi yozuv qo'shadi (qoidalar: [AGENTS.md](AGENTS.md)).

---

## 2026-10-17 — Codex — Android vaqtincha to‘xtatildi

- Foydalanuvchi ko‘rsatmasiga ko‘ra Windows NEXVARA PERSONAL to‘liq tugamaguncha Android ishlab chiqilishi to‘xtaydi. Qolgan ishlar `docs/ANDROID_HANDOFF.md` ga yozildi. Claude Windows ishchi papkasi va fayllariga tegilmadi.
- Oxirgi Android build va 8/8 unit test **PASS**; yangi APK telefonda **NOT TESTED** (ADB ruxsati rad etildi). Haqiqiy Windows Agent E2E **NOT TESTED**; pause/resume hamda chat/Memory sync **BLOCKED** (API yo‘q).
- `codex/android-mobile` tarmog‘ida mahalliy commit va PRIVATE GitHub push so‘raldi; natija quyidagi yakuniy ish holatida aniqlanadi.

## 2026-10-17 — Codex — Android V1 fayl va kamera tekshiruvlari

- Ish faqat `codex/android-mobile` worktree'da. Kamera URI qayta yaratilganda saqlanadi; upload javobi va download fayli SHA-256 bilan tekshiriladi; vazifa watcherining takrorlanishi tuzatildi. Pause/resume, chat tarixi va Memory API talablari `docs/ANDROID_WINDOWS_API_GAPS.md` ga yozildi.
- **PASS:** Android debug APK build, 8/8 unit test; Windows ruff check va format. Oldingi APK bilan Android 16 pairing, chat, chat tarixi, oddiy fayl upload va kamera oynasini ochish PASS holatida.
- **BLOCKED/NOT TESTED:** yangi APK’ni telefonga o‘rnatish ADB avtomatik ruxsatida rad etildi; Windows NEXVARA oynasini avtomatik boshqarish ham rad etildi. Shu sabab haqiqiy Agent pairing, Office vazifalari/progress/cancel, kamera suratini yuborish va natija faylini olish tasdiqlanmadi. `scripts/test.ps1` uchun worktree'da `.venv` yo‘q; boshqa venv bilan pytest ham sandboxda rad etildi. Windows chat/Memory sync va pause/resume uchun API yo‘q.
- **Push BLOCKED:** diff maxfiy ma’lumot naqshlariga tekshirildi, APK va lokal sozlamalar ignore qilingan. GitHub tarmoq ulanishi sandboxda ishlamadi, eskalatsiya avtomatik rad etildi. PRIVATE holat masofadan tasdiqlanmadi; lokal commit saqlanadi.
- Keyingi qadam: qurilma/UI ruxsati mavjud bo‘lganda haqiqiy Agent bilan E2E; Office kodi o‘zgartirilmadi.

## 2026-10-17 — Codex — Android chat tarixi va fayl sinovi

- `codex/android-mobile` worktree'da har bir PC uchun so‘nggi 200 chat xabari shifrlangan xotiraga yoziladigan qilindi. Ilova qayta ochilganda tarix tiklanadi.
- **PASS:** Android APK build, 3/3 QR unit test; Android 16 telefonda ilova majburan to‘xtatilib qayta ochilgach chat tarixi ko‘rindi; 41 baytli sun’iy fayl demo Windows API'ga yuborildi; kamera oynasi ochildi va ilovaga qaytildi.
- **FAIL/BLOCKED:** `scripts/test.ps1` bu worktree'da `.venv` bo‘lmagani uchun ishlamadi. **NOT TESTED:** suratga olish/yuborish, faylni olish, haqiqiy Windows agenti vazifalari, fon bildirishnomalari. Office testlari ruxsatsiz ishga tushirilmadi.
- Keyingi qadam: Windows agenti bilan vazifalar va faylni olish sinovi; qolgan mobil bo‘limlar va fon ishlashi.

## 2026-10-17 — Codex — Android V1 telefon sinovi

- Ish faqat alohida `.worktrees/android` worktree va `codex/android-mobile` tarmog‘ida bajarildi. `main` dagi telefon API v1 shu tarmoqqa merge qilindi; Claude ishchi papkasi va tarmog‘i almashtirilmadi.
- Android chat tasdig‘i, vazifalar long-poll, ko‘p PC, shifrlangan offline navbat, kamera va release signing sozlamalari qo‘shildi. Klaviatura chat maydonini berkitishi haqiqiy telefonda topilib tuzatildi.
- **PASS:** Android APK build, 3/3 QR unit test, Android 16 telefonga o‘rnatish va ishga tushirish, QR pairing, demo Windows API bilan chat so‘rovi va javobi, klaviatura tuzatishining qurilmadagi sinovi.
- **FAIL/BLOCKED:** `scripts/test.ps1` Android worktree'da `.venv` yo‘qligi sababli ishga tushmadi. **NOT TESTED:** kamera, fayl almashinuvi, haqiqiy Windows agenti vazifalari, Office testlari, fon bildirishnomalari. Google Android OAuth va pause/resume uchun tashqi sozlama/API kerak.
- Keyingi qadam: haqiqiy Windows agenti bilan vazifa, kamera va fayl almashinuvini sinash; fon sinxronizatsiyasi va bildirishnomalar.

## 2026-10-17 (13) — Claude Code — Windows Agent integratsiyalari: telefon API v1, Google login, installer/updater, bo'limlar auditi

**Foydalanuvchi talabi:** 179 PASS testni saqlab, Android uchun xavfsiz API, Google OAuth/OIDC, installer/updater tekshiruvi, 12 bo'lim ↔ Core Agent holati, Codex uchun Android hujjatlari, PROGRESS va private GitHub'ga push. Pullik AI chaqirilmadi.

**Qilindi** (tarmoq `claude/integratsiyalar`):
- **Telefon API v1** (`remote_v1.py`, `protocol.py`, [docs/api/](docs/api/)): 13 marshrut, `{"v":1,"ok":...}` javob + 11 ta barqaror xato kodi, QR'da sertifikat SHA-256 (`fp`) va kompyuter ID (`sid`) — Android sertifikatni pin qiladi; tokenni yumshoq almashtirish (eski token yangisi ishlatilguncha ishlaydi), 30 kunlik muddat, chiqish, bir xil o'rnatish qayta bog'lansa eski yozuv almashadi; long-poll `tasks/watch`; fayl yuklash/olishda SHA-256; har manzilga tezlik cheklovi (240/daq, bog'lash 10/daq); eski `app.db` avtomatik migratsiya. Brauzer sahifasi eski `/api/...` bilan ishlashda davom etadi. `openapi.yaml` marshrutlari test bilan serverga bog'langan. `python -m nexvara.devserver` — Android uchun demo server.
- **Google login (Windows)** (`account.py`, Sozlamalar → Google hisobi): tizim brauzeri + `127.0.0.1` callback, PKCE S256, state, nonce, ID token RS256 imzosi (JWKS), iss/aud/exp tekshiruvi, refresh token Credential Manager'da, refresh, `invalid_grant` → avtomatik chiqish, logout → Google'da revoke. Client JSON yo'q bo'lsa karta **BLOCKED** deb aniq yozadi.
- **Installer** (`installer/`, `scripts/build.ps1`): PyInstaller (NEXVARA.exe, 128 MB papka) + Inno Setup 6 (47 MB `NEXVARA-Setup-0.1.0.exe`): admin'siz, Start Menu, ixtiyoriy yorliq, uninstaller, `/NOLAUNCH`. Yorliq yaratish o'rnatilgan exe uchun tuzatildi. PyInstaller (.venv) va Inno Setup (winget, user scope) o'rnatildi.
- **Updater** (`updater.py`, Sozlamalar → Versiya va yangilanish): papka yoki https kanal; Ed25519 imzoli `latest.json` (maxfiy kalit faqat `D:\NEXVARA\release\signing_key.pem`, ochig'i kodda), hajm + SHA-256, `pending.json` → keyingi ishga tushishda "yangilandi" yoki "muvaffaqiyatsiz", oxirgi 2 installer saqlanadi, rollback; `http://` rad etiladi.
- **12 bo'lim auditi** ([docs/SECTIONS_STATUS.md](docs/SECTIONS_STATUS.md)): chatdan bajarilmaydigan bo'limlarga buyruqlar qo'shildi (`app/api_sections.py`): workflowni nomi bilan ishga tushirish/ro'yxat, oxirgi vazifalar, «nimalarni eslab qolgansan?», «xotiradan ... top», telefon ulanishini yoqish/o'chirish/holat, yorug'/qorong'i mavzu. Natija: 7 REAL IMPLEMENTED, 4 PARTIAL (Files, BI, Workflows, Settings), Home N/A.
- **Codex uchun**: [docs/ANDROID_HANDOFF.md](docs/ANDROID_HANDOFF.md) (stek, tuzilma, 15 qabul mezoni, pinning, offline navbat, BLOCKED ro'yxat), [docs/api/MOBILE_API.md](docs/api/MOBILE_API.md), [docs/GOOGLE_LOGIN.md](docs/GOOGLE_LOGIN.md), [docs/RELEASE.md](docs/RELEASE.md). AGENTS.md: `android/` → Codex (`codex/android-mobile`).
- Mavjud test o'zgardi (1 ta): `test_revoke_and_rotate` — eski token endi yangisi ishlatilguncha ishlaydi (yo'qolgan javob telefonni bloklamasligi uchun), keyin rad etiladi.

**Testlar:**
| Test | Natija |
|---|---|
| ruff + format | PASS |
| unit: 214 ta (oldingi 179 + telefon API v1 10, Google 8, updater 6, bo'limlar chat 11) | PASS |
| Oyna smoke (12 sahifa, JS xatosiz) | PASS |
| UI haqiqiy oynada: Google kartasi BLOCKED, yangilanish xatosi, chatdan mavzu/tarix/workflow (`tests/ui_scripts/settings_integrations.py`) | PASS |
| Installer: build → jim o'rnatish → o'rnatilgan `NEXVARA.exe --smoke` → o'chirish; `D:\NEXVARA\app.db` tegilmadi; paketda maxfiy fayl yo'q | PASS |
| Haqiqiy reliz kaliti bilan imzolash → tekshirish → SHA-256 → jim qayta o'rnatish → `after_start` = updated | PASS |
| Office testlari (`-Office`) | NOT TESTED — Office kodi o'zgarmadi, ruxsatsiz Office ochilmadi |
| Haqiqiy Google login | BLOCKED — Google Cloud Desktop OAuth client kerak |
| Haqiqiy telefon bilan v1 | NOT TESTED — telefon kerak; native ilova BLOCKED (JDK/SDK) → Codex |
| Updater https kanali | NOT TESTED; Authenticode imzo BLOCKED |

**Keyingi qadam:** Codex — `codex/android-mobile` da APK (ANDROID_HANDOFF.md). Foydalanuvchi — `google_client.json` va AI kaliti (ixtiyoriy). Claude — Files/BI/Workflows/Settings qolgan amallarini chatga ulash, sync.

---

## 2026-10-16 (12) — Claude Code — Qolgan barcha bo'limlar: Memory, Teach, Files, Workflows, NEXVARA BI, Devices

**Foydalanuvchi talabi:** "qolgan barcha bo'limlarni mukammal darajada qo'sh". Endi 12 bo'limning hech biri bo'sh emas (smoke buni tekshiradi).

**Qilindi:**
- **Memory** (`memory/store.py`): eslatmalar (qo'shish/tahrir/o'chirish), suhbatlar tarixi (ilova qayta ochilganda chat davom etadi), oxirgi fayllar, o'zbekcha qo'shimchalarni tushunadigan qidiruv ("maktabimizda" → "maktab"), JSON zaxira va tiklash (takrorlamasdan). AI'ga faqat mos eslatmalar yuboriladi.
- **Teach NEXVARA** (`memory/teach.py`): chatda "Har doim Excel raqamlarini markazga joyla", "testlar doim 2 variant bo'lsin", "Mana shu Word shablonini ishlat: D:\...\x.dotx" → nima qilishi ko'rsatiladi, "Ha"dan keyin saqlanadi. Qoidalar keyingi buyruqlarga (saqlash/eksportdan oldin, takrorlanmasdan), testlarga va yangi Word hujjatlarga qo'llanadi. Versiyalar, yoqish/o'chirish. Tuzatildi: "raqamlarini" so'zi "sahifa raqamlari" deb tushunilardi.
- **Fayllar** (`fileagent.py`): qidiruv, ma'lumot + SHA-256, nusxa/ko'chirish (hech qachon ustiga yozmaydi), nomlash va ommaviy nomlash, ZIP (papkadan tashqariga chiqadigan xavfli arxiv rad etiladi), zaxira/versiyalar/tiklash, papkani turlarga ajratib tartiblash, Savatga o'chirish, Word/Excel/PowerPoint → PDF ommaviy, amallar jurnali. Chatda "hisobot fayllarini top".
- **Workflows** (`workflows.py`): qadamlar (buyruq / tasdiq / kutish), qo'lda, papkaga yangi fayl tushganda (har fayl bir marta, `_NEXVARA` chiqishlar e'tiborsiz) yoki har kuni soat X da; qayta urinish, xatoda to'xtash yoki davom etish, pauza/davom, to'xtatish, tarix, 3 ta shablon. Workflow pullik AI'ni o'zi chaqirmaydi.
- **NEXVARA BI** (`bi/`, `ui/bi.js`): XLSX/CSV/JSON/XML/TXT/papka; ustun turlari, tozalash, bo'sh qiymatlar, formula ustun (xavfsiz, `eval`siz), boshqa fayl bilan birlashtirish; avtomatik dashboard (daromad+xarajat bo'lsa sof foyda, rentabellik, oylik o'sish); KPI, ustunli, chiziqli, doiraviy, nuqtali, jadval; filtrlar, sana oralig'i, bosib drill-down, sahifalar, vidjet qo'shish/tahrirlash; saqlash; PNG/PDF/Excel/CSV eksport. Chatda "Savdo.xlsx dan dashboard yarat".
- **Devices** (`remote.py`, `ui/mobile.html`): telefon brauzeridan boshqarish. QR + bir martalik 6 xonali kod (10 daqiqa, 5 xatodan keyin blok), HTTPS (kompyuterning o'z sertifikati), tokenlar faqat xesh holida va haftalik almashadi, qurilmani uzish, takroriy so'rov ikki marta bajarilmaydi, kompyuter javob bermasa buyruqlar navbatda kutadi, fayl/rasm yuborish, natijani telefonga yuklab olish. Sukut bo'yicha o'chiq.
- Smoke endi har bir sahifani ochib, JS xatolari yo'qligini tekshiradi; `tests/ui_scripts/` haqiqiy oynada har bo'limni bosib chiqadi.
- Yangi kutubxonalar: `openpyxl` (BI), `segno` (QR).

**Testlar** (`.\scripts\test.ps1 -Office`):
| Test | Natija |
|---|---|
| ruff + format | PASS |
| unit (179 ta; +memory, teach, fayllar, workflow, BI, telefon serveri HTTPS bilan) | PASS |
| Office: 227/228 birinchi ishga tushirishda; yiqilgan bitta — band kompyuterda oyna 20 soniyada yuklanmagan (skript kutish vaqti), 90 soniyaga oshirilgach UI sinovlari 5/5 | PASS |
| Haqiqiy Office: ommaviy PDF (Word+Excel), papka kuzatuvchi workflow (Excel), AI test Word'da (soxta AI) | PASS |
| UI (haqiqiy oyna): Memory/Teach, Fayllar, Workflows, BI (eksportlar bilan), Devices (ikki oyna: kompyuter + telefon) | PASS |
| Haqiqiy telefon bilan ulanish | NOT TESTED — foydalanuvchi telefoni kerak |
| Native Android ilova, Google login | TODO (Android SDK / Google Cloud loyihasi kerak) |

---

## 2026-10-16 (11) — Claude Code — Oyna ekranga sig'adi

**Foydalanuvchi:** "ko'rinmayabdi oxiri" (aylantirish tuzatilgandan keyin ham).

**Sabab:** foydalanuvchi ekrani 1920×1080, 125% kattalashtirish → ishlatiladigan maydon 1536×816 (mantiqiy piksel). Oyna qat'iy 1320×820 ochilardi, pastki qismi vazifalar paneli ostida qolardi. Ilova ichidagi aylantirish to'g'ri ishlardi (barcha sahifalar 3 o'lchamda o'lchandi).

**Qilindi:** `app/main.py`: `work_area()` (SPI_GETWORKAREA, DPI hisobga olinadi) va `window_geometry()`: oyna ekranga sig'adigan o'lchamda va markazda ochiladi; minimal o'lcham 900×560.

**Testlar:** unit 135 PASS (+3 oyna o'lchami); haqiqiy oynada: oyna pastki cheti 1005 px ≤ ish maydoni 1020 px (fizik) — PASS; smoke PASS.

---

## 2026-10-16 (10) — Claude Code — M7: AI ulanishi (kalit kiritish joyi, xarajat, limit)

**Foydalanuvchi talabi:** NEXVARA'ni to'liq tugatish; API kalit kerak bo'lganda aytish. Codex `codex/model-router` da ish qilmagani uchun M7 ni Claude oldi.

**Qilindi** (`src/nexvara/ai/`):
- 4 provayder: Anthropic (rasmiy SDK; Opus/Sonnet 5.5 da server tomonidagi zaxira model `fallbacks: "default"`), OpenAI, Gemini, DeepSeek (bitta HTTPS mijoz, 429/5xx da qayta urinish).
- Darajalar: arzon / o'rtacha / kuchli. Buyruqni tushunish → arzon, savol-javob va test → o'rtacha. Kalit tekshirilganda (bepul model ro'yxati so'rovi) hisobdagi haqiqiy model nomlari tanlanadi.
- Kalitlar Windows Credential Manager'da; UI'ga faqat niqoblangan ko'rinish (`sk-a…1234`) chiqadi.
- Xarajat: har chaqiruv `app.db` → `ai_usage`. Kunlik ($1) va oylik ($10) limit; $0.05 dan qimmat so'rov chatda "Ha, davom et / Yo'q" tugmalari bilan so'raladi. Anthropic narxlari rasmiy; boshqalari taxminiy, `settings.json` → `ai.prices` da o'zgartiriladi.
- Chat: AI'siz tushunilmagan matnni AI sinalgan buyruq tiliga qayta yozadi va odatdagi ijrochi bajaradi; bilim savollariga darslikdan (manba va bet bilan) javob beradi.
- AI test: "AI bilan 7-sinf fizika kuch 10 ta test" yoki formadagi "AI bilan tuzish" belgisi. Savollar mavzu matnidan, variantlarda tartib va javob o'rni aralashtiriladi, rasmli savollar AI'siz qoladi.
- Sozlamalar → AI: har provayder uchun kalit kiritish, "Kalit olish ↗" havolasi, limitlar, sarf jadvali.
- Tuzatildi: "AI" so'zi test mavzusiga qo'shilib ketardi; `Task.wait()` tarix yozilishini kutmasdi (ba'zan yiqiladigan test).

**Testlar:**
| Test | Natija |
|---|---|
| ruff + unit testlar (132 ta; +AI router, byudjet, tasdiq, provayder formatlari, Credential Manager) | PASS |
| Office: kutubxona testlari 8/8, shu jumladan AI test Word'da (soxta provayder, pulsiz) | PASS |
| Smoke: 12 menyu + Sozlamalarda 4 provayder | PASS |
| Haqiqiy kalit bilan AI chaqiruvi | Sinalmagan — foydalanuvchi kalit kiritishi kerak |

---

## 2026-10-16 (9) — Claude Code — Ilova asoslari: aylantirish, tarix, sozlamalar, belgi

**Foydalanuvchi talabi:** "ilovani pastga sursam oxiri ko'rinmayabdi"; ilovadagi kamchiliklarni tuzatish.

**Qilindi:**
- Aylantirish: oyna butunligicha aylanmaydi, chap menyu, markaziy sahifa va vazifa paneli har biri o'zi aylanadi; sahifa oxiri doim ko'rinadi (haqiqiy oynada tekshirildi). Darsliklar jadvali o'z ichida aylanadi. Tor oynada vazifa paneli yashiriladi va yopish tugmasi bilan chiqadi.
- `appdata.py`: vazifalar tarixi (`D:\NEXVARA\app.db`, oxirgi 500 ta) va sozlamalar (`settings.json`) qayta ishga tushirishda saqlanadi.
- Sozlamalar sahifasi: mavzu (qorong'i/yorug'), savollar soni va variantlar (sukut), Office oynasi ochiq qolsinmi, ma'lumotlar papkasini ochish, ish stolida yorliq, tarixni tozalash.
- `app/shortcut.py`: NEXVARA belgisi (.ico, dasturda chiziladi) va ish stolidagi yorliq (konsolsiz `pythonw`).

**Testlar:**
| Test | Natija |
|---|---|
| ruff + format + unit testlar (119 ta; +sozlamalar, tarix) | PASS |
| Office: kutubxona va buyruqlar testlari (17 ta, haqiqiy Excel/Word/PowerPoint) | PASS |
| Smoke (12 menyu bandi) | PASS |

---

## 2026-10-16 (8) — Claude Code — Testlarda rasmli va chizmali savollar

**Foydalanuvchi talabi:** test tuzilganda rasm va chizmali savollar ham bo'lsin ("Rasmda nima ko'rsatilgan?").

**Qilindi** (`knowledge/figures.py`, `quiz.py`, `testdoc.py`):
- Darslikdagi rasm izohlari ("61-rasm. Ikki qayiqning bir-biriga tortilishi") PyMuPDF bilan topiladi. Ikki qatorga o'tgan izoh birlashtiriladi, matndagi havolalar ("61-rasmda ...") izoh deb olinmaydi.
- Izohga tegishli rasm topiladi: eng yaqin rasm, unga tegib turgan bo'laklar (strelka, yozuvlar) qo'shiladi; vektor chizmalar uchun chiziqlar to'plami olinadi. Rasm 2× sifatda qirqib olinadi.
- **Javob oshkor qilinmaydi:** rasm ichiga tushgan izoh so'zlari oq rang bilan yopiladi.
- Himoya: sahifa sarlavhasi bezaklari, banner rasmlar, bo'sh yoki matnli qirqimlar rad etiladi (noto'g'ri rasmdan ko'ra savol bo'lmagani yaxshi).
- Savol: "Rasmda nima tasvirlangan?" (sxema/grafik/jadval/xarita bo'lsa "Chizmada..."). Variantlar: to'g'ri izoh + shu darslikdagi boshqa rasm izohlari (yetmasa, darslik tushunchalari). Rasmli savollar testning ~25% i, har variantda boshqacha.
- Word: rasm savol ostida (eni 8 sm, balandligi 7 sm gacha). Savol, rasm va variantlar bir sahifada qoladi (KeepWithNext). Javoblar kalitida harf va bet.

**Topilgan va tuzatilgan:** sahifa bo'ylab ko'rinmas suv belgisi ("http:eduportal.uz") butun rasmni oq qilib yuborardi; matndagi "68-rasm" havolasi izoh deb olinardi; sarlavha bezagi rasm deb olinardi; savol matni va rasm turli sahifaga bo'linardi.

**Haqiqiy darsliklarda:** 6 ta kitobdan 72 ta izoh, 57 tasida rasm to'g'ri qirqildi (7-fizika 12/13, 8-kimyo 7/7, 9-kimyo 8/9, 10-biologiya 19/20, 7-biologiya 11/23). OCR qilingan (skaner) kitoblarda rasmli savol yo'q, chunki izoh matni yo'q. 7-sinf fizika "Nyuton qonunlari" testi: 12 savoldan 3 tasi rasmli, hammasi rasmi bilan bir sahifada.

**Testlar** (`.\scripts\test.ps1 -Office`):
| Test | Natija |
|---|---|
| ruff + unit testlar (112 ta; +rasm izohlari, javob yashirilishi, chalg'ituvchilar) | PASS |
| Office testlari: 152/153 birinchi ishga tushirishda; yiqilgan bitta UI self-test eskirgan kutilgan son (5→6 tekshiruv) sababli, tuzatilgandan keyin kutubxona testlari 7/7 | PASS |
| Word'da rasmli test (sintetik darslik rasmlar bilan): rasm hujjatda, PDF'da rasmlar soni = rasmli savollar soni, vaqtinchalik fayllar o'chirilgan | PASS |
| Haqiqiy darsliklarda rasm qirqish (6 kitob) | 57/72 (79%), qolganlari xavfsiz o'tkazib yuborildi |

---

## 2026-10-16 (7) — Claude Code — Darsliklarni avtomatik yuklash, OCR, Telegram yuklovchi

**Foydalanuvchi talabi:** "kitoblarni o'zing yuklab ol". Tanlov: **ikkalasi**, ya'ni hozir eski rasmiy nashr, yangilari esa Telegram orqali.

**Manbalar tekshiruvi:**
- `dr.rtm.uz` (RTM rasmiy sayti): DNS'da yo'q (Google/Cloudflare DNS ham topmaydi). `kitob.uz`: 502.
- `infoedu.uz` "2026-yilgi rasmiy nashr" deb e'lon qilgan `fizika_7_uzb.pdf` eski eduportal fayli bilan **SHA-256 bo'yicha bir xil** (2017-08-31 da yaratilgan). Bunday saytlar ishlatilmaydi.
- Yangi darsliklar faqat RTM'ning rasmiy Telegram kanalida (`t.me/rtm_metodik_xizmat`) Telegram hujjati sifatida bor (masalan `Algebra_7-sinf_2-CH_uzb.pdf`).

**Qilindi:**
- `sources/eduportal.py`: portal sahifalari (id ≠ sinf; sinf fayl yo'lidan olinadi) → **205 ta o'zbekcha darslik (1–11-sinf)**. Yuklash to'xtab qolsa davom ettiriladi, PDF tekshiriladi. **203 tasi yuklandi (3,3 GB)**; 2 tasi serverning o'zida yo'q (404): `algebra_8_afidum`, `geometriya_10`.
- `sources/telegram_rtm.py`: foydalanuvchi o'z Telegram hisobi bilan bir marta kiradi (my.telegram.org dan bepul API ID/hash + telefon kodi). Kanaldan faqat o'zbek maktablari uchun PDF'lar olinadi (qardosh, rus va boshqa tillar, dastur va reja fayllari o'tkazib yuboriladi), `rtm/<sinf>-sinf/` ga joylanadi. Session faqat `D:\NEXVARA\telegram` da saqlanadi.
- Kutubxona: manba ustuvorligi **rtm > foydalanuvchi > eduportal**. Bir fanning chorak/qismlari birga qidiriladi. Yil matndan topilmasa PDF yaratilgan sanadan olinadi (sxema v4).
- `knowledge/ocr.py`: **Windows'ning o'zidagi OCR** (en-US o'zbek lotin uchun, ru kirill uchun), sahifalar PyMuPDF bilan rasmga aylantiriladi. API ham, qo'shimcha dastur ham kerak emas, sahifasiga ~0,2 s.
- `cryptography`: AES bilan shifrlangan 5 ta rasmiy PDF endi ochiladi. Yangi fanlar qo'shildi: Odobnoma, Nutq o'stirish, Milliy istiqlol g'oyasi, Tadbirkorlik va boshqalar.
- Mavzu topish tuzatildi: qisman sarlavha mosligi ("amir" ~ "Amirligida") endi qabul qilinmaydi. O'zbekcha qo'shimchalar uchun o'zak 4 harfgacha qisqartiriladi. OCR shovqini ("01") testga tushmaydi.

**Kutubxona natijasi** (`D:\NEXVARA\Darsliklar`, 203 PDF): **194 tasi tayyor** (52 tasi OCR orqali), 5 tasi kirill (rus tili darsliklari), 3 tasi matnsiz (1-sinf yozuv/matematika daftari, nemis tili 1), 0 xato, 0 noma'lum fan. To'liq indekslash OCR bilan ~80 daqiqa.

**Haqiqiy darsliklarda sinov:** 7-sinf fizika "Nyuton qonunlari" → 19-§ (65–70); "Nyutonning ikkinchi qonuni" → 21-§; 8-sinf fizika (OCR) "Om qonuni" → 57–58-betlar; 9-sinf tarix "Toshkentning bosib olinishi" → 7-§; "tarixdan jadidlar" → 26-§; 10-sinf tarix "Amir Temur" → "topilmadi" (to'g'ri, bu sinfda yo'q).

**Ma'lum cheklovlar:** OCR qilingan kitoblarda § sarlavhalar har doim tanilmaydi (mavzu matn bo'yicha topiladi). Formulalarda OCR xatolari bo'ladi. Eski nashr hozirgi o'quv dasturidan farq qilishi mumkin; yangi darsliklar Telegram orqali qo'shilgach ular ustun turadi.

Test tuzish ham tuzatildi: endi mavzuning to'liq §-bo'limi olinadi va savol yetmasa keyingi betlar qo'shiladi. Natija: 7-sinf fizika "Nyuton qonunlari" 3/15 dan **15/15** ga; 9-sinf tarix 15/15; 8-sinf fizika (OCR) 10/10; 6-sinf biologiya "fotosintez" (OCR, § sarlavhasi topilmagan) 4/10, bu ochiq aytiladi.

**Testlar** (`.\scripts\test.ps1 -Office`, foydalanuvchi ruxsati bilan):
| Test | Natija |
|---|---|
| ruff + unit testlar (111 ta: manbalar 12, OCR 2, nashr ustuvorligi, qisman sarlavha regressiyasi) | PASS |
| Office testlari (40 ta) | PASS (to'liq regressiya: 151/151; tuzatishdan keyin kutubxona va buyruq testlari 16/16) |
| Oyna smoke | PASS |
| Haqiqiy kutubxonada chat orqali: test (2 variant), mavzu (OCR kitob), taqdimot | PASS (5/5, 4/4, 3/3 tekshiruv) |
| Telegram orqali haqiqiy kirish va yuklash | NOT TESTED: foydalanuvchining Telegram hisobi kerak (soxta mijoz bilan PASS) |

---

## 2026-10-16 (6) — Claude Code — Office buyruqlari (AI'siz), chat, vaqt chegarasi

**Foydalanuvchi talabi:** darsliklar kelguncha qolgan ishlarni qilish; hammasi **API kalitsiz** ishlashi; Office buyruq berilganda mukammal bajarishi.

**Qilindi** (`src/nexvara/agent/`):
- `parse.py`: o'zbekcha buyruq → reja. Gap bo'laklarga bo'linadi ("," / "va" / "keyin"; "1,5" bo'linmaydi). Fayl nomi, ilova (Excel/Word/PowerPoint) va har bir amal aniqlanadi; tushunilmagan qism alohida aytiladi. Qisqa yordamchi so'zlar ("da", "bu", "ga") faqat butun so'z sifatida olinadi, shuning uchun "Daromad", "Buxoro" buzilmaydi.
- `excel_exec.py`: ochish, tozalash, dublikat, saralash (ustun nomi yoki harfi; o'sish/kamayish), filtr (matn qiymati jadvaldagi haqiqiy qiymatga moslanadi: "Toshkentni" → "Toshkent"; raqam: "500000 dan katta"), formatlash, jami (takror so'ralsa bitta qator qoladi), diagramma (takrorlanuvchi toifalar SUMIFS bilan jamlanadi, "JAMI" kirmaydi), pivot, qotirish, PDF, CSV. Har amal tekshiriladi, oxirida fayl qayta ochiladi.
- `word_exec.py`: almashtirish (topilmasa ochiq aytadi), shrift, qator oralig'i, xatboshi, A4/chetlar, sahifa raqamlari, mundarija, imlo, "rasmiy formatla" (Times New Roman 14, 1,5, 1,25 sm, A4), PDF.
- `ppt_exec.py`: darslik mavzusidan dars taqdimoti (mazmun, asosiy tushunchalar, sanalar, darslikning o'z savollari, uyga vazifa, ma'ruzachi izohlari, o'tishlar, animatsiya, joylashuv tekshiruvi), mavjud .pptx → PDF.
- `files.py`: faylni nomi bo'yicha topish (Ish stoli, Hujjatlar, Yuklanmalar, D:\ ...). **Asl fayl hech qachon o'zgarmaydi**: natija `<nom>_NEXVARA.xlsx/.docx` ga yoziladi; "ustiga saqla" deyilsa avval `.bak` nusxa olinadi.
- Chat: test → taqdimot → mavzu → Office buyrug'i tartibida tushunadi. 📎 bilan fayl tanlanadi, "shu fayl" esda qoladi. Vazifa tugaganda chatga hisobot chiqadi (nima qilindi, fayl, tekshiruv).
- `core/task.py`: **vaqt chegarasi** (10 daqiqa). Osilib qolgan Office vazifasi "Vaqt tugadi" deb yakunlanadi va UI bloklanmaydi (avvalgi PowerPoint osilishiga qarshi). Foydalanuvchi xatolari texnik prefikssiz ko'rsatiladi.
- Gap ajratishda bosh harflar ("M. Chernyayev") gapni bo'lmaydi.

**Topilgan va tuzatilgan:** "JAMI" qatori saralash/diagramma/pivotga ma'lumot sifatida tushardi; ", keyin" bog'lovchisi bo'lak boshida qolardi; fayl yo'lidagi so'zlar ("...\Testlar\...") buyruqni "test tuz" deb adashtirardi (endi fayl ko'rsatilsa, bu Office buyrug'i hisoblanadi).

**Testlar** (`.\scripts\test.ps1 -Office`, foydalanuvchi ruxsati bilan):
| Test | Natija |
|---|---|
| ruff check + format | PASS |
| Unit testlar (94 ta; +parser 18, vaqt chegarasi, fayl yo'li regressiyasi) | PASS |
| Office testlari (40 ta; +Excel ko'p qadamli buyruq, filtrlar, noto'g'ri ustun, ustiga saqlash + .bak, Word buyrug'i 7/7, yo'q matn, mavzudan taqdimot + PPTX→PDF, chat konteksti, UI'da chatga buyruq yozish) | PASS |
| Oyna smoke | PASS |
| Asl fayl o'zgarmasligi (SHA-256 bilan tekshirildi) | PASS |
| Haqiqiy foydalanuvchi fayllari bilan | NOT TESTED: foydalanuvchi o'z fayllarida sinab ko'radi |
| Ruscha/inglizcha buyruqlar | NOT TESTED: hozircha faqat o'zbekcha lotin |

**Keyingi qadam:** foydalanuvchi o'z fayllari va darsliklarida sinaganidan keyin parserni kengaytirish; ruscha buyruqlar; Excel'da formula yozish, shartli formatlash va bir nechta faylni birlashtirish buyruqlari.

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
