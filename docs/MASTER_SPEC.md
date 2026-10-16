# NEXVARA PERSONAL — MASTER SPECIFICATION
**Versiya:** 1.0 — qayta qurish uchun asosiy texnik topshiriq  
**Platformalar:** Windows 11, Android  
**Loyiha joylashuvi:** `D:\Nexvara loyiha`  
**Maqsad:** Oldingi NEXVARA AI Office Agent imkoniyatlarini qayta qurish, Microsoft Power BI va NEXVARA ADMIN'siz.

## 0. SENING ROLING VA ASOSIY QOIDALAR

Sen NEXVARA loyihasining Lead Software Architect, Senior Full-Stack Developer, Windows Automation Engineer, Android Developer, AI Agent Engineer, UI/UX Designer, Security Engineer va QA Engineer vazifalarini bajarasan.

Foydalanuvchi dasturchi emas. Unga ortiqcha texnik murakkablik yuklama. Loyiha kodlarini, fayllarni, testlarni, build jarayonlarini va hisobotlarni imkon qadar o‘zing boshqar.

NEXVARA oddiy chatbot, Office fayl generatori yoki Microsoft Office nusxasi emas. U Microsoft Office va Windows dasturlarida foydalanuvchi topshiriqlarini real bajaradigan AI Agent hisoblanadi.

**Majburiy prinsiplar:**

- Faqat reja yozib to‘xtab qolma. Ishlaydigan kod yarat.
- Har bir bosqichni avtomatik test qil.
- Sinovdan o‘tmagan funksiyani PASS deb ko‘rsatma.
- Ishlayotgan kodni asossiz buzma.
- Xavfli, qaytarib bo‘lmaydigan amallardan oldin tasdiq ol.
- API kalitlari, tokenlar va maxfiy ma’lumotlarni Git'ga joylama.
- Keraksiz API chaqiruvlari va token xarajatlarini kamaytir.
- Eski loyiha kodlari mavjud deb faraz qilma.
- Oldingi versiya raqamlari tarixiy ma’lumot, yangi kodning tayyorlik dalili emas.
- Har bir funksiyani haqiqiy ishlashi bo‘yicha bahola.

## 1. LOYIHANING YAKUNIY MAQSADI

NEXVARA Windows kompyuterda ishlaydigan, foydalanuvchi bilan tabiiy tilda muloqot qiladigan va topshiriqlarni amalda bajaradigan shaxsiy AI yordamchi bo‘ladi.

Foydalanuvchi quyidagicha buyruq bera olishi kerak:

"Excel'ni och, shu fayldagi ma’lumotlarni tozala, hisob-kitob qil, chiroyli jadval yarat, diagramma qo‘sh va saqla."

Agent vazifani tushunadi, kerakli dasturni ochadi, ishni bosqichlarga ajratadi, bajaradi, tekshiradi va natijani ko‘rsatadi.

Windows va Android bitta tizimning ikki qismi bo‘ladi. Telefon orqali yuborilgan topshiriq Windows kompyuterda bajariladi.

Loyiha shaxsiy foydalanishga mo‘ljallangan. Sotuv, abonent tariflari, mijozlarni boshqarish va NEXVARA ADMIN talab qilinmaydi.

## 2. PLATFORMALAR VA MOSLIK

### Windows
- Windows 11 x64 — asosiy platforma.
- Windows 10 x64 — imkon qadar qo‘llab-quvvatlash.
- Office 2016 — birinchi real moslik maqsadi.
- Office 2019, LTSC 2021, Microsoft 365 — keyingi moslik testlari.
- Office 2010/2013 — texnik imkoniyat tekshiriladi, kafolat berilmaydi.
- Office ruscha yoki inglizcha interfeysda bo‘lsa ham ishlashi.
- Microsoft Office qonuniy o‘rnatilgan va aktivlashtirilgan bo‘lishi kerak.

### Android
- Android 16 — mavjud telefon uchun asosiy test.
- Android 10 va undan yuqori versiyalar — maqsadli qo‘llab-quvvatlash, test natijasiga qarab.
- APK o‘rnatish.
- Internet orqali Windows Agent bilan aloqa.
- Kamera, mikrofon, fayl tanlash va bildirishnomalar.
- Biometrik himoya, agar qurilma qo‘llasa.

### Internet va AI
- Lokal katta AI modelini majburiy o‘rnatma.
- AI modellar API orqali ishlaydi.
- Office avtomatlashtirishning deterministik qismlari lokal bajarilishi mumkin.
- Internet bo‘lmasa, AI funksiyalari cheklanishi va bu foydalanuvchiga aniq ko‘rsatilishi kerak.

## 3. WINDOWS ILOVASI DIZAYNI

NEXVARA mustaqil, professional Windows ilovasi bo‘ladi.

### Vizual uslub
- Brend: NEXVARA.
- Zamonaviy, minimal, premium texnologik dizayn.
- Dark va Light rejimlar.
- Tavsiya etilgan dark fon: #0B1020.
- Asosiy aksent: #6366F1.
- Ikkinchi aksent: #06B6D4.
- Muvaffaqiyat: #22C55E.
- Xato: #EF4444.
- Ogohlantirish: #F59E0B.
- Yumaloq kartalar, silliq animatsiyalar.
- Windows ekran o‘lchamlariga moslashuv.
- O‘qilishi aniq matn, klaviatura bilan boshqarish va accessibility.

Ranglar dizaynning dastlabki taklifi; keyinchalik foydalanuvchi tasdiqlaydi.

### Asosiy oynaning tuzilishi

**Chap navigatsiya:**
- Home
- AI Chat
- Office Agent
- Files
- NEXVARA BI
- Workflows
- Teach NEXVARA
- Memory
- Tasks / History
- Devices
- Settings

**Markaziy maydon:**
- AI bilan suhbat.
- Fayl va rasm biriktirish.
- Ovozli buyruq.
- Vazifani rejalashtirish.
- Ish jarayonining jonli holati.
- Natijalar va xatolar.

**O‘ng panel:**
- Hozir bajarilayotgan vazifa.
- Qaysi dastur ishlayotgani.
- Model va provayder.
- Bajarilgan qadamlar.
- API token va taxminiy xarajat.
- Pause, Resume, Cancel.
- Zarur tasdiqlash oynalari.

### Qo‘shimcha dizayn talablari
- Birinchi ishga tushirish ustasi.
- Tillarni tanlash.
- Google login yoki xavfsiz lokal shaxsiy rejim.
- API provayderlarini sozlash.
- Office mosligini tekshirish.
- Qurilmalarni bog‘lash.
- Oson tushuniladigan xato xabarlari.
- Progress indikatorlari.
- Vazifalar tarixi.
- Natija fayllariga tezkor kirish.
- O‘rnatilgan versiyani ko‘rsatish.
- Yangilanish mavjudligi haqidagi bildirishnoma.

## 4. CORE AI AGENT

Bu butun tizimning markaziy qismi.

### Agent ishlash sikli
1. Buyruqni qabul qilish.
2. Foydalanuvchi niyatini aniqlash.
3. Kontekst va avvalgi suhbatni tekshirish.
4. Kerakli fayllar va dasturlarni aniqlash.
5. Vazifani kichik bosqichlarga ajratish.
6. Mos Skill va AI modelni tanlash.
7. Xavfsizlik tekshiruvini bajarish.
8. Zarur bo‘lsa tasdiq so‘rash.
9. Amallarni bajarish.
10. Natijani tekshirish.
11. Xatoni tiklash yoki qayta urinish.
12. Yakuniy hisobot va fayllarni ko‘rsatish.

### Ko‘p bosqichli muloqot
Agent oldingi suhbatni tushunsin.

Masalan:
- "Shu Excel faylini tartibla."
- "Endi diagramma qo‘sh."
- "Natijani Word'ga o‘tkaz."
- "Oldingi faylni och."
- "Shu ishni har hafta takrorlash uchun workflow yarat."

Agent avvalgi fayl va topshiriq kontekstini saqlashi kerak.

### Agent imkoniyatlari
- Tool calling.
- Structured plans.
- Multi-step execution.
- Replanning.
- Error recovery.
- Checkpoint va resume.
- Task cancellation.
- Idempotency.
- Task history.
- Context management.
- Output validation.
- Confirmation gates.

Biror vazifa muvaffaqiyatsiz tugasa, agent buni yashirmaydi.

## 5. LIVE OFFICE VISIBLE EXECUTION

**Bu NEXVARA'ning eng muhim talabidir.**

Office topshiriqlarida standart rejim — LIVE VISIBLE EXECUTION.

- Kerakli Office dasturi ochiladi.
- Oyna tiklanadi va oldingi planga chiqariladi.
- Zarur bo‘lsa maksimal kattalashtiriladi.
- Foydalanuvchi ish jarayonini ko‘radi.
- Agent haqiqiy Office hujjati bilan ishlaydi.
- Jarayon holati NEXVARA oynasida ham ko‘rsatiladi.
- Ish yakunida natija tekshiriladi.

Faqat foydalanuvchi "fonda bajar" desa background rejimga o‘tish mumkin.

### Texnik yondashuv
Birinchi navbatda Office COM Automation / Interop, Windows UI Automation va zarur joylarda keyboard/mouse control ishlat.

Ekran koordinatalariga qattiq bog‘langan avtomatlashtirishga suyanma. DPI, til, oyna o‘lchami va Office versiyasidagi farqlarni hisobga ol.

Ko‘rinadigan bajarish degani barcha amallar albatta sichqoncha bilan bajarilishi shart degani emas. COM orqali bajarilgan amallar ham Office oynasida aks etishi va foydalanuvchi natijani kuzata olishi kerak.

## 6. EXCEL SKILL

### Asosiy amallar
- Excel'ni ochish.
- Mavjud faylni yuklash.
- Yangi workbook yaratish.
- Sheet yaratish, nomlash, ko‘chirish.
- Ma’lumot kiritish va o‘zgartirish.
- Qator va ustun qo‘shish/o‘chirish.
- Sort va Filter.
- Find/Replace.
- Duplicate removal.
- Data validation.
- Conditional formatting.
- Number formats.
- Date formats.
- Table styles.
- Merge/unmerge.
- Freeze panes.
- Print settings.
- Import/export.

### Murakkab amallar
- SUM, IF, COUNTIF, SUMIFS, XLOOKUP va mos formulalar.
- Office versiyasiga mos formula fallback.
- PivotTable.
- Diagrammalar.
- Ma’lumotlarni tozalash.
- Bir nechta Excel faylini birlashtirish.
- Ma’lumotlarni solishtirish.
- Statistik tahlil.
- Hisobotlar.
- Katta jadvallar bilan ishlash.
- Xatoli formulalarni aniqlash.
- Natijani CSV, XLSX, PDF formatida chiqarish.

### Majburiy formatlash
- Raqamli kataklar gorizontal markazda.
- Imkon qadar vertikal markazda.
- Ustun kengliklari mazmunga mos.
- Sarlavhalar aniq ajratilgan.
- Bir xil jadvalda bir xil format.
- O‘qilishi qulay professional ko‘rinish.
- Formula natijalarini tekshirish.

### Birinchi real test
Excel ochilsin, yangi workbook yaratilisin, 10 qatorli jadval kiritilsin, hisob-kitob qilinsin, formatlansin, saqlansin va qayta ochib tekshirilsin.

## 7. WORD SKILL

- Word'ni ochish.
- DOCX hujjat yaratish va tahrirlash.
- Mavjud hujjatni ochish.
- Matn yozish, qayta yozish va tarjima.
- Sarlavha va uslublar.
- Sahifa o‘lchami, chetlar, orientatsiya.
- Header/Footer.
- Sahifa raqamlari.
- Mundarija.
- Jadvallar.
- Rasmlar.
- Diagrammalar.
- Izohlar.
- Find/Replace.
- Imlo va grammatika tekshiruvi.
- Rasmiy xatlar.
- Arizalar.
- Ma’lumotnomalar.
- Shartnomalar uchun shablonlar.
- Uzun hujjatlar.
- DOCX/PDF eksport.
- Shablonlarni qayta ishlatish.
- Mavjud formatni imkon qadar saqlash.
- Hujjatni qayta ochib tekshirish.

## 8. POWERPOINT SKILL

- PowerPoint'ni ochish.
- Taqdimot yaratish.
- Mavjud PPTX'ni tahrirlash.
- Slayd tuzilmasi.
- Professional mavzular.
- Shrift va rang tizimi.
- Diagramma va jadval.
- Rasmlar va ikonlar.
- SmartArt yoki muqobil shakllar.
- Animatsiya va transition.
- Speaker notes.
- Slaydlarni qayta tartiblash.
- Brend shablonlari.
- Vizual izchillik.
- PPTX/PDF eksport.
- Matn sig‘ishi va obyektlar ustma-ust tushmasligini tekshirish.

AI orqali rasm yaratish alohida ixtiyoriy funksiya bo‘lsin. Foydalanuvchi tasdiqlamaguncha pullik rasm API ishlatilmasin.

## 9. NEXVARA BI SKILL

**NEXVARA BI qoladi. Microsoft Power BI olib tashlanadi.**

Bu NEXVARA ichidagi mustaqil biznes-tahlil va interaktiv dashboard tizimi.

### Ma’lumot manbalari
- XLSX
- CSV
- JSON
- XML
- TXT
- Papkadagi bir nechta fayl
- Keyinchalik ma’lumotlar bazasi ulanishlari

### ETL
- Import.
- Ma’lumotlarni tozalash.
- Ustun turlarini aniqlash.
- Null qiymatlarni qayta ishlash.
- Duplicate removal.
- Join/Merge.
- Group/Aggregation.
- Calculated columns.
- KPI hisoblash.
- Filtrlash.
- Transformatsiya bosqichlarini saqlash.

### Dashboard
- KPI cards.
- Bar chart.
- Line chart.
- Pie/Donut chart.
- Scatter chart.
- Tables.
- Filter va slicer.
- Sana bo‘yicha filtrlash.
- Drill-down.
- Interaktiv tooltip.
- Bir nechta sahifali dashboard.
- Responsive layout.
- Dashboard shablonlari.
- PNG/PDF/CSV/XLSX eksport.
- Dashboard konfiguratsiyasini saqlash.

### Misol
Foydalanuvchi "Shu Excel fayldan daromad, xarajat, sof foyda va oylik o‘sish dashboardi yarat" desa, NEXVARA BI mustaqil dashboard yaratishi kerak.

Dashboard NEXVARA ichida ochiladi. Alohida Power BI Desktop talab qilinmaydi.

## 10. COMPUTER CONTROL SKILL

- Windows dasturlarini ishga tushirish.
- Oynalarni topish.
- Minimize/Maximize/Restore.
- Foreground boshqaruvi.
- Klaviatura va sichqoncha.
- Clipboard.
- Fayl tanlash dialoglari.
- UI Automation elementlari.
- Screenshot.
- Ekran holatini tahlil qilish.
- Xato dialoglarini aniqlash.
- Foydalanuvchi bilan birgalikda boshqarish.

### Xavfsizlik
- O‘chirish, overwrite va boshqa xavfli amallarda tasdiq.
- Yashirin destruktiv amallar bo‘lmasin.
- O‘zboshimchalik bilan parol kiritmasin.
- Muhim amallar logga yozilsin.
- Bekor qilish va to‘xtatish imkoniyati bo‘lsin.

## 11. FILE AGENT

- Fayllarni qidirish.
- Papkalarni ochish.
- Fayllarni o‘qish.
- Nomlash va tartiblash.
- Nusxalash va ko‘chirish.
- Format konvertatsiyasi.
- Bir nechta faylni qayta ishlash.
- ZIP arxivlarni yaratish va ochish.
- Fayl metadata.
- Hash tekshirish.
- Backup.
- Versioning.
- Restore.
- Xavfsiz overwrite.
- Faylni o‘chirishdan oldin tasdiq.

## 12. VISION VA OCR

- Rasmni tushunish.
- Screenshot tahlili.
- Skanerlangan hujjat.
- Jadvalni rasmdan aniqlash.
- OCR orqali matn olish.
- PDF sahifalarini ko‘rish.
- Diagramma va chizmalarni tahlil qilish.
- Noaniq qismlarni foydalanuvchiga ko‘rsatish.
- Olingan ma’lumotlarni Word yoki Excel'ga o‘tkazish.

### Technical Drawing Skill
- Texnik chizmalar.
- Qiyshaygan skanlarni to‘g‘rilash.
- Belgilar va yozuvlarni aniqlash.
- O‘lchamlar va ulanishlar.
- Texnologik sxemalar.
- Qayta chizish uchun strukturali tavsif.
- Noaniq belgilarni taxmin qilib yashirmaslik.

## 13. WEB RESEARCH SKILL

- Internetdan ma’lumot izlash.
- Manbalarni solishtirish.
- Yangilik va rasmiy ma’lumotlarni topish.
- Ma’lumotlarning sanasini tekshirish.
- Havolalar bilan hisobot.
- Topilgan ma’lumotlarni Office hujjatiga kiritish.
- Foydalanuvchi tasdiqlamaguncha veb-saytlarda xavfli amallar bajarmaslik.

### Uzbekistan Business Skill
- O‘zbekiston biznes hujjatlari bilan ishlash.
- STIR kabi identifikatorlarni tekshirish uchun qonuniy ochiq manbalar yoki ruxsatli API.
- Korxona ma’lumotlarini tahlil qilish.
- Mahalliy hujjat shakllari.
- Elektron hujjat almashinuvi integratsiyalariga tayyor arxitektura.
- Hujjat yuborish, imzolash va moliyaviy amallar uchun tasdiq.

## 14. MEMORY VA TEACH NEXVARA

### Memory
- Suhbatlar tarixi.
- Vazifalar tarixi.
- Oldingi fayllar bilan bog‘liqlik.
- Foydalanuvchi afzalliklari.
- Uzoq muddatli loyiha konteksti.
- Semantik qidiruv.
- Xotirani tahrirlash.
- Xotirani o‘chirish.
- Backup va restore.

### Teach NEXVARA
Foydalanuvchi bir marta o‘rgatgan qoida keyinchalik qayta ishlatilishi kerak.

Misol:
"Har doim Excel raqamlarini markazga joyla."
"Mana shu Word shablonini ishlat."
"Shu turdagi hisobotni shu tartibda tayyorla."

### Texnik talablar
- Local SQLite yoki mos ma’lumotlar bazasi.
- Knowledge versioning.
- User confirmation.
- Structured knowledge.
- Retrieval.
- Keraksiz kontekstni modelga qayta yubormaslik.
- Xotirani eksport/import qilish.
- Mobil va Windows o‘rtasida ruxsatli sinxronlash.

## 15. AI MODEL ROUTER

NEXVARA bitta AI provayderiga qaram bo‘lmasin.

### Provayder adapterlari
- OpenAI.
- Google Gemini.
- Anthropic Claude.
- DeepSeek.
- Keyinchalik boshqa provayderlar.

Model nomlari konfiguratsiyadan olinadi. Eskirgan yoki mavjud bo‘lmagan model identifikatorlarini qattiq kodlama.

### Router darajalari
**CHEAP:** Oddiy savollar, klassifikatsiya, sodda matn ishlari.

**BALANCED:** O‘rtacha murakkablikdagi hujjatlar va rejalashtirish.

**POWERFUL:** Murakkab Excel, uzun hujjatlar, ko‘p bosqichli agent vazifalari.

**SPECIALIST:** Vision, OCR, image generation, speech va maxsus vazifalar.

### Model tanlash mezonlari
- Vazifa murakkabligi.
- Model imkoniyati.
- Narx.
- Token hajmi.
- Javob tezligi.
- Ishonchlilik.
- Provayder mavjudligi.
- Fallback imkoniyati.

### Xarajat nazorati
- Har bir API chaqiruvini hisoblash.
- Input/output tokenlar.
- Taxminiy USD xarajat.
- Kunlik/oylik limit.
- Foydalanuvchi belgilagan budget.
- Limitdan oshishdan oldin ogohlantirish.
- Cache.
- Qisqa kontekst.
- Takroriy chaqiruvlarni kamaytirish.
- Arzon modeldan kuchli modelga faqat zarur bo‘lsa o‘tish.

**Muhim:** Foydalanuvchining ChatGPT yoki Claude obunasi uchinchi tomon API xarajatlarini avtomatik qoplamaydi. API billing alohida bo‘lishi mumkin.

## 16. WORKFLOW AUTOMATION

- Ko‘p bosqichli ishlarni saqlash.
- Qayta ishlatiladigan workflow.
- Fayl kelganda ishga tushirish.
- Jadval asosidagi ishlar.
- Ketma-ket va shartli amallar.
- Retry.
- Pause/Resume.
- Task history.
- Approval steps.
- Idempotency.
- Xatodan tiklash.
- Workflow template.

V1 uchun minimal workflow engine, keyingi bosqichda murakkab avtomatlashtirish.

## 17. OVOZLI BOSHQARUV

- Mikrofon orqali buyruq.
- Uzbek, Russian, English speech-to-text.
- Matnni ovozda qaytarish.
- Mikrofon ruxsati.
- Recording indikatori.
- Push-to-talk.
- Shovqinli muhitda xatolarni kamaytirish.
- Ixtiyoriy realtime voice.
- Voice API xarajatlarini hisoblash.

Ovozli buyruqlar uchun avval matnli buyruqlar bilan bir xil Agent pipeline ishlatilsin.

## 18. ANDROID MOBILE V1

Android ilova Windows Agent'ni masofadan boshqaradi.

### Dizayn
- Windows bilan bir xil brend.
- Dark/Light.
- Home dashboard.
- AI Chat.
- Voice input.
- File upload.
- Camera.
- Task history.
- Devices.
- Memory.
- Notifications.
- Settings.

### Funksiyalar
- Google login.
- Biometric unlock.
- Windows qurilmasini bog‘lash.
- Work PC / Home PC tanlash.
- Matnli buyruq.
- Ovozli buyruq.
- Rasm yuborish.
- Fayl yuborish.
- Windows vazifasini boshlash.
- Task progress.
- Natijani olish.
- Task cancellation.
- Offline/retry.
- Push notification.
- Xotira va sozlamalar sinxronlash.

### Masofaviy aloqa
Mobile → xavfsiz aloqa qatlami → Windows Agent.

Shaxsiy foydalanish uchun arzon, xavfsiz ulanish usulini tanla. To‘liq tijoriy server infratuzilmasi shart emas.

Pairing, device authorization, TLS, token rotation, reconnect, queue, retry va idempotency bo‘lishi kerak.

Windows o‘chiq yoki internet uzilgan bo‘lsa, foydalanuvchiga aniq xabar ber.

## 19. GOOGLE LOGIN VA ACCOUNT SYNC

- Google OAuth/OIDC.
- Windows va Android uchun alohida client konfiguratsiyalari.
- PKCE va xavfsiz callback.
- Tokenlarni Windows Credential Manager / Android Keystore kabi himoyalangan saqlash.
- Logout.
- Session expiry.
- Device revoke.
- Profile sync.
- Language sync.
- Teach knowledge sync.
- Task history sync.
- Device status.
- No secret in Git.

Google loginni birinchi lokal Office test uchun majburiy bloklovchi qilma. Keyingi bosqichda real end-to-end sinovdan o‘tkaz.

## 20. XAVFSIZLIK VA MAXFIYLIK

- Least privilege.
- Secure credential storage.
- `.gitignore`.
- `.env.example`, lekin haqiqiy kalitsiz.
- Loglarda tokenlarni yashirish.
- Sensitive data redaction.
- Input validation.
- Path traversal protection.
- Safe file operations.
- Confirmation for destructive actions.
- Backup before risky edits.
- Audit log.
- HTTPS/TLS.
- Secure device pairing.
- Rate limiting.
- Dependency audit.
- Update integrity verification.
- Signed releases when available.
- No unauthorized remote access.
- No hidden execution.
- No unnecessary data collection.

Shaxsiy hujjatlar va fayllar AI provayderiga yuborilishidan oldin foydalanuvchi sozlagan maxfiylik qoidalariga amal qil.

## 21. TEXNOLOGIK ARXITEKTURA

Claude Code avval muhitni tekshirsin, keyin asoslangan texnologiya tanlasin.

Tavsiya etilgan yo‘nalish:

### Windows
- TypeScript / Node.js orchestration.
- Electron yoki Tauri desktop shell.
- Office COM Automation uchun Python pywin32 yoki .NET interop.
- Windows UI Automation.
- SQLite local storage.

### BI
- TypeScript frontend.
- React.
- ECharts yoki Recharts.
- DuckDB / Pandas / Polars kabi data processing.
- Mustaqil interaktiv dashboard engine.

### Android
- Kotlin.
- Jetpack Compose.
- Android Keystore.
- WorkManager.
- Camera/Files/Audio APIs.

### Shared
- Typed API contracts.
- Structured tool schemas.
- Versioned messages.
- Common error codes.
- Task state machine.

Texnologiyalarni majburan aralashtirma. Yakuniy stackni muhit, Office integratsiyasi, installer hajmi, xotira sarfi va qo‘llab-quvvatlash xarajatiga qarab tanla.

## 22. LOYIHA TUZILMASI

`D:\Nexvara loyiha`

Tavsiya etilgan papkalar:

- `apps/windows`
- `apps/mobile`
- `services/agent`
- `services/office-bridge`
- `services/bi`
- `packages/core`
- `packages/model-router`
- `packages/memory`
- `packages/workflow`
- `packages/shared`
- `skills/excel`
- `skills/word`
- `skills/powerpoint`
- `skills/file`
- `skills/vision`
- `skills/web`
- `skills/computer`
- `skills/technical-drawing`
- `skills/uzbekistan-business`
- `docs`
- `tests`
- `scripts`
- `installer`

Monorepo yoki mos alternativani tanlash mumkin. Papkalar haqiqiy ishlatiladigan kod asosida yaratiladi.

## 23. INSTALLER VA UPDATE

### Windows
- `.exe` installer.
- Ish stoli yorlig‘i.
- Start Menu.
- Uninstaller.
- Version display.
- User data preservation.
- Update notification.
- Update integrity verification.
- Rollback.
- Failed update recovery.
- Config migration.
- Oldingi sozlamalarni saqlash.

### Android
- APK build.
- Release signing.
- Versioning.
- Update compatibility.
- Data preservation.
- Install/upgrade tests.

Shaxsiy foydalanish uchun lokal yoki private release kanalini qo‘llash mumkin.

## 24. ISHLASH TEZLIGI

- Kuchli GPU majburiy bo‘lmasin.
- Katta lokal LLM talab qilinmasin.
- Lazy loading.
- Background services minimal bo‘lsin.
- Memory leak tekshiruvi.
- Startup optimizatsiyasi.
- UI bloklanmasin.
- Long-running task progress.
- Katta fayllarni chunk processing.
- Cache management.
- Disk joyini nazorat qilish.
- Build/cache imkon qadar D: diskida.

## 25. TESTLAR VA SIFAT

### Test turlari
- Unit.
- Integration.
- E2E.
- Office real UI tests.
- Security.
- Performance.
- Installer.
- Update.
- Rollback.
- Android device.
- Windows-Mobile pairing.
- Network interruption.
- API failure.
- Data preservation.
- Accessibility.
- Multilingual.
- Recovery.

### Office testlari
- Excel ochish va yozish.
- Word yaratish va tahrirlash.
- PowerPoint yaratish.
- Barchasini saqlash.
- Qayta ochib tekshirish.
- Foydalanuvchi ko‘z oldida bajarish.
- Xato holatida xavfsiz to‘xtash.

### QA status
- PASS — amalda tekshirilgan.
- FAIL — test muvaffaqiyatsiz.
- BLOCKED — muhit yoki ruxsat yetishmaydi.
- NOT TESTED — hali sinov qilinmagan.

Hech qanday test natijasini o‘ylab topma.

## 26. ISHLAB CHIQISH BOSQICHLARI

### M0 — Environment
Git, Node, Python, Android toolchain, Office mosligi, xavfsizlik va loyiha strukturasi.

### M1 — Windows Shell
NEXVARA desktop oynasi, chat UI, settings, task status.

### M2 — Core Agent
Task planning, tool execution, structured results, error handling.

### M3 — Excel Live Automation
Haqiqiy Excel testlari va formatlash.

### M4 — Word va PowerPoint
Office Skills va real UI testlari.

### M5 — File, Vision, Web, Computer Control
Ko‘p turdagi amaliy vazifalar.

### M6 — Memory, Teach, Workflow
Xotira va qayta ishlatiladigan jarayonlar.

### M7 — Model Router
Ko‘p provayder, xarajat nazorati va fallback.

### M8 — NEXVARA BI
ETL, dashboard, interaktiv grafiklar.

### M9 — Google Login va Sync
Account, pairing uchun asos, secure credential.

### M10 — Windows Release
Installer, update, rollback, performance va final QA.

### M11 — Android Mobile
Kotlin ilovasi, kamera, ovoz, fayllar, login.

### M12 — Windows-Mobile E2E
Telefon buyruqlarining haqiqiy Windows Office'da bajarilishi.

### M13 — Final Personal Release
Release build, qo‘llanma, backup/restore, yakuniy sinovlar.

Bosqichlar ichidagi ishlarni texnik bog‘liqliklarga qarab qayta tartiblash mumkin. Windows asosiy funksiyalari barqaror bo‘lmasdan Android'ga shoshilma.

## 27. QABUL QILISH MEZONLARI

NEXVARA PERSONAL V1 tayyor hisoblanishi uchun:

- Windows ilovasi o‘rnatiladi va ochiladi.
- Excel, Word, PowerPoint haqiqiy dastur ichida boshqariladi.
- Default Office execution ko‘rinadigan rejimda ishlaydi.
- NEXVARA BI interaktiv dashboard yaratadi.
- Memory va Teach ishlaydi.
- Model Router xarajatlarni hisoblaydi.
- File, Vision, Web va Workflow amalda tekshiriladi.
- O‘zbek, rus, ingliz buyruqlari sinovdan o‘tadi.
- Android Windows Agent'ga xavfsiz ulanadi.
- Telefon buyruqlari Windows'da bajariladi.
- Update va rollback ishlaydi.
- Shaxsiy ma’lumotlar va API kalitlari himoyalanadi.
- ADMIN va Microsoft Power BI kodga kiritilmaydi.
- Muhim testlarda ochiq FAIL/BLOCKED holatlar yakuniy hisobotda ko‘rsatiladi.

## 28. CLAUDE CODE UCHUN ISH REJIMI

Har bir bosqichda:

1. Mavjud kodni tekshir.
2. Kerakli arxitekturani aniqlashtir.
3. Fayllarni yarat yoki o‘zgartir.
4. Kodni formatla.
5. Static analysis.
6. Testlarni bajar.
7. Natijani tekshir.
8. Xatolarni tuzat.
9. O‘zgartirishlarni hujjatlashtir.
10. PASS / FAIL / BLOCKED hisobotini chiqar.

Hisobotda:
- Yaratilgan fayllar.
- O‘zgartirilgan fayllar.
- Ishlayotgan funksiyalar.
- Bajarilgan testlar.
- Test natijalari.
- Qolgan muammolar.
- Keyingi vazifalar.

Git commitlarni mantiqiy bosqichlarda yarat. GitHub'ga push qilishdan oldin maxfiy ma’lumotlarni tekshir va foydalanuvchi tasdig‘ini ol.

## 29. HOZIRGI BIRINCHI AMALIY TOPSHIRIQ

Hozirgi papka: `D:\Nexvara loyiha`.

Avval `.gitignore` mavjudligini tekshir. Uni buzma.

So‘ng:
1. Environment audit bajar.
2. `docs/MASTER_SPEC.md` fayliga ushbu texnik topshiriqni joylashtir.
3. `docs/ARCHITECTURE.md` yarat.
4. `docs/ROADMAP.md` yarat.
5. Windows ilovasi uchun texnologik stack tanla.
6. Minimal Windows desktop shell yarat.
7. Office 2016 COM automation mosligini tekshir.
8. Excel'ni ko‘rinadigan oynada ochish uchun bridge yarat.
9. Jadval yaratish va saqlash uchun test kodi yoz.
10. Mavjud muhitda testlarni bajar.
11. Xatolarni tuzat.
12. Yakuniy hisobot chiqar.

Haqiqiy Excel sinovini faqat Office o‘rnatilgan va foydalanuvchi ishga tushirishga ruxsat bergan holatda bajar.

API kalitlari hozircha talab qilinmasin. Pullik API ishlatilmasin.

**Boshlang‘ich maqsad: foydalanuvchi ko‘z oldida Excel'da jadval yaratadigan, testdan o‘tgan NEXVARA Windows Agent asosini ishlab chiqish.**

## 30. LOYIHANING YAKUNIY QOIDASI

NEXVARA shunchaki matn yozadigan AI emas.

U foydalanuvchi bilan muloqot qiladigan, topshiriqni rejalashtiradigan, kompyuter va Office dasturlarida ishni amalda bajaradigan, natijani tekshiradigan, xotirada saqlaydigan va Windows hamda Android orqali boshqariladigan AI Agent bo‘lishi shart.

Asosiy tamoyil:

**"Foydalanuvchi buyruq beradi — NEXVARA ishni bajaradi — foydalanuvchi natijani ko‘radi."**
