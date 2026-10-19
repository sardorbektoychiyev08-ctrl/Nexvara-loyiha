# NEXVARA — foydalanuvchi qo‘llanmasi

NEXVARA — kompyuteringizdagi yordamchi. U Excel, Word va PowerPoint’da ishlarni bajaradi,
darsliklardan test tuzadi, jadvallardan hisobot (BI) qiladi, chizma chizadi va telefoningizdan
boshqariladi. Buyruqni oddiy o‘zbek tilida yozasiz yoki aytasiz.

Bu qo‘llanma Windows 1.5.0 va Android 1.6.0 versiyalariga mos.

---

## 1. O‘rnatish va ishga tushirish

- O‘rnatuvchi: `NEXVARA-Setup-<versiya>.exe`. Administrator huquqi kerak emas.
- Ish stolidagi yoki Start menyusidagi **NEXVARA** belgisini bosing.
- Sizning ma’lumotlaringiz (sozlamalar, darsliklar, natijalar) `D:\NEXVARA` papkasida
  turadi. Dastur o‘chirilsa ham, yangilansa ham ular saqlanib qoladi.
- Har hafta ma’lumotlarning zaxira nusxasi avtomatik olinadi.

## 2. Chap menyu

| Bo‘lim | Nima uchun |
|---|---|
| Bosh sahifa | Tezkor amallar, AI xarajatlari |
| AI suhbat | Buyruq yozish yoki aytish — eng ko‘p ishlatiladigan joy |
| Office yordamchisi | Excel / Word / PowerPoint namunaviy ishlari |
| Darsliklar va testlar | Darslik yuklash, mavzu bo‘yicha test tuzish |
| Fayllar | Qidirish, nusxalash, ko‘chirish, nomlash, ZIP, PDF, zaxira |
| NEXVARA BI | Jadval yoki ma’lumotlar bazasidan hisobot paneli |
| Chizmalar | Chizish, AutoCAD (DXF), PDF, Word, albom |
| Ish jarayonlari | Takrorlanadigan ishlarni avtomatlashtirish |
| NEXVARA’ga o‘rgatish | «Excel’da doim shunday qil» kabi qoidalar |
| Xotira | NEXVARA siz haqingizda eslab qolgan narsalar |
| Vazifalar va tarix | Bajarilgan va bajarilayotgan ishlar |
| Qurilmalar | Telefonni ulash va ruxsatlar |
| Sozlamalar | AI, sinxronlash, yangilanish, mavzu |

## 3. AI suhbat: buyruq misollari

Office ishlari (Office ekranda ochiladi, nima qilinayotganini ko‘rib turasiz):
- «Baholar.xlsx ni och, jadvalni formatla, B ustun bo‘yicha saralab, PDF qilib saqla»
- «Hisobot.docx dagi sarlavhalarni rasmiy ko‘rinishga keltir»
- «Baholar.xlsx ni och, Baho ustuniga faqat 2 dan 5 gacha butun son kiritilsin» — noto‘g‘ri qiymat kiritilsa Excel ogohlantiradi
- «Vazifalar.xlsx ni och, Holat ustuniga tanlash ro‘yxati: Bajarildi, Jarayonda, Bekor»
- «Yanvar.xlsx va Fevral.xlsx ni bitta faylga varaq qilib yig‘»
- «7-sinf fizika Nyuton qonunlari bo‘yicha taqdimot tayyorla»

Darslik va testlar:
- «7-sinf fizika «Nyuton qonunlari» mavzusidan 20 ta test, 2 variant» (AI’siz, bepul)
- «AI bilan 5-sinf matematika «Kasrlar» bo‘yicha uyga vazifa va javoblarini tuz»

Fayllar:
- «hisobot fayllarini top», keyin «topilgan fayllarni ZIP qil»
- «Arxiv.zip ni och» (arxivdan chiqarish)

Chizma:
- «100x60 plastina, markazida 20 mm teshik chizib ber» (oddiy detallar AI’siz)
- «chizma.dxf ni PDF qil», «chizma.dxf ni Word qil»
- «chizma.dxf ni Hisobot.docx ga qo‘y» — chizma va o‘lchamlar jadvali Word hujjat oxiriga
  qo‘shiladi

Internetdan qidirish (AI kerak):
- «internetdan qidir: Toshkentda ertaga ob-havo»
- «so‘nggi yangiliklar: maktab ta’limi»
Javob manbalar (havolalar) bilan keladi. Gemini’ning oylik bepul qidiruvlari bo‘lsa darhol
bajariladi, pullik bo‘lsa avval narxini aytib, «Ha» deyishingizni kutadi.

Chat tugmalari: 🎤 gapirish · 🔊 javobni ovoz bilan eshitish · 🖼️ rasm yuborish ·
📷 kamera · ✨ rasm yaratish · 🎧 jonli suhbat · 🧠 AI modelini tanlash.

## 4. AI: kalit, bepul rejim va xarajat

- **Sozlamalar → AI**: OpenAI, Gemini, Claude yoki DeepSeek kalitini kiriting. Kalitlar
  Windows’ning himoyalangan xotirasida saqlanadi, faylga yozilmaydi.
- **Bepul rejim**: Gemini kaliti bo‘lsa, ko‘p ishlar Gemini’ning bepul darajasida bajariladi.
- **Pullik so‘rov**: NEXVARA avval taxminiy narxini aytadi va «Ha» deyishingizni kutadi.
- **Limitlar**: kunlik va oylik chegarani Sozlamalarda qo‘yasiz; chegaradan oshmaydi.
- **🧠 menyusi**: har bir yo‘nalish (matn, rasmni ko‘rish, rasm yaratish, ovoz → matn,
  matn → ovoz, jonli suhbat, internetdan qidirish) uchun **AUTO** (eng arzon/bepul o‘zi
  tanlanadi) yoki **qo‘lda** (siz tanlagan model, hech qachon almashtirilmaydi).
- **Maxfiylik**: ism-familiya, telefon, manzil, karta raqami kabi ma’lumotlar AI’ga
  yuborilishidan oldin yashiriladi va javobda kompyuteringizda qayta tiklanadi. Aniqlab
  bo‘lmasa, so‘rov umuman yuborilmaydi.

## 5. Fayllar

- Qidirish: nomi bo‘yicha, Hujjatlar, Ish stoli, Yuklanmalar va OneDrive’dan.
- Amallar: nusxalash, ko‘chirish, nomlash (ommaviy ham), ZIP qilish, ZIP’dan chiqarish,
  Word/Excel/PowerPoint → PDF, zaxira va eski versiyani tiklash, papkani tartiblash.
- Hech bir amal mavjud faylning ustidan yozmaydi: bir xil nom bo‘lsa yangi nom beriladi.
- O‘chirish faqat Savatga va faqat tasdiqdan keyin.

## 6. NEXVARA BI

- **Manba**: Excel, CSV, JSON, XML, TXT, butun papka yoki **ma’lumotlar bazasi**
  (SQLite `.db/.sqlite`, Access `.accdb/.mdb`).
- Bazadagi jadvallar Excel varaqlari kabi ro‘yxatda chiqadi. Kerak bo‘lsa, «Bazadan so‘rov»
  maydoniga bitta `SELECT …` so‘rovini yozib Enter bosing.
- Bazalar faqat o‘qiladi: NEXVARA ulardagi hech narsani o‘zgartirmaydi.
- Panel avtomatik tuziladi (KPI, ustunli, chiziqli, doiraviy grafiklar, jadval), keyin
  filtr, sahifa, formula ustun qo‘shish va eksport qilish mumkin.

## 7. Chizmalar

- Asboblar panelida chizish, tahrirlash, o‘lcham, shtrix, qatlam, ranglar.
- Saqlash: AutoCAD DXF (mm). Eksport: **PDF** (chop etish uchun), **PNG** (rasm),
  **Word** (chizma A4 varaqda va ostida o‘lchamlar jadvali: umumiy o‘lcham, obyektlar,
  aylanalar diametri, chiziqlar uzunligi, chizmadagi o‘lchamlar).
- **Albom**: bir nechta DXF chizmani tanlasangiz, hammasi bitta PDF’ga yig‘iladi (har biri
  alohida sahifa, mundarija bilan).
- Telefonda qo‘l bilan chizilgan chizma kompyuterda DXF, PDF, PNG va Word bo‘lib saqlanadi.

## 8. Telefon

**Ulash (bir marta):**
1. Kompyuterda **Qurilmalar → Telefondan boshqarish → Yoqish**.
2. Telefonda NEXVARA ilovasini oching va QR kodni skanerlang.
3. Telefon va kompyuter bitta Wi‑Fi’da yoki USB orqali ulangan bo‘lishi kerak. Boshqa
   tarmoqdan ishlash uchun Tailscale (bepul) kerak.

**Telefondan nimalar mumkin:**
- Buyruq yozish yoki aytish — kompyuter ekranida bajariladi; natijani telefonga olish.
- **Kompyuter ekrani**: jonli ko‘rish. Boshqarish uchun 🖱 belgisini bosing (barmoq izi so‘raladi):
  - ekrandagi joyga bosish — o‘sha joy bosiladi;
  - **Sensorli panel** — telefon noutbuk paneli kabi: barmoqni suring (kursor yuradi),
    bir bosish (chap tugma), ikki marta (ochish), uzoq bosish (o‘ng tugma), ikki barmoq bilan
    yuqoriga/pastga (aylantirish), «Ushlab sudrash».
  - Kompyuterda **Qurilmalar → «Telefon sichqoncha va klaviaturani boshqarishi mumkin»**
    yoqilgan bo‘lishi kerak.
- **Fayllar → Kompyuterdan qidirish**: fayl topish, kompyuterda ochish, telefonga olish,
  **nomlash**, **PDF qilish**; bir nechta faylni belgilab **ZIP qilish** yoki **ko‘chirish**
  (Hujjatlar / Ish stoli / Yuklanmalar, istasangiz ichida yangi papka); ZIP faylni
  **chiqarish**.
- Chizma, BI panellari, darsliklar, jurnal, javob varaqalari, ertalabki xulosa.
- Kalitlar, parollar va bazalar hech qachon telefonga berilmaydi.

## 9. Sinxronlash (bir nechta kompyuter)

- **Sozlamalar → Sinxronlash**: ikkala kompyuter ko‘radigan papka (masalan OneDrive) va
  sinxron paroli. Ixtiyoriy: Google Drive orqali.
- Sinxronlanadi: xotira, o‘rgatilgan qoidalar, xavfsiz sozlamalar. Belgi qo‘ysangiz —
  **suhbat tarixi ham** (oxirgi 30 kun). Hammasi parol bilan shifrlangan.
- Bir kompyuterda «… ni unut» desangiz, o‘sha xabar boshqasida ham o‘chadi.
- AI kalitlari va «AI yoqilgan» belgisi hech qachon sinxronlanmaydi.

## 10. Yangilash va zaxira

- **Sozlamalar → Versiya va yangilanish**: yangi versiya bo‘lsa «Yangilash» chiqadi.
  Yangilanish imzo bilan tekshiriladi; buzilgan fayl o‘rnatilmaydi.
- Yangi versiya ishlamasa, oldingisiga qaytish (rollback) mumkin.
- Zaxira: har hafta avtomatik (`D:\NEXVARA-zaxira`).

## 11. Muammo bo‘lsa

| Muammo | Nima qilish kerak |
|---|---|
| Telefon «Aloqa yo‘q» | Kompyuterda NEXVARA ochiqmi va «Telefondan boshqarish» yoqilganmi tekshiring; bir xil Wi‑Fi yoki USB |
| Telefon ulanmayapti, kompyuter yangi o‘rnatilgan | Qurilmalar → «Yangi kod», QR kodni qayta skanerlang |
| «Buning uchun AI kerak» | Sozlamalar → AI: kalitni kiriting va «AI yoqilgan» ni yoqing |
| «Limit tugadi» | Sozlamalar → AI: kunlik/oylik limitni oshiring yoki ertaga urinib ko‘ring |
| Office oynasi qotib qoldi | Vazifalar va tarix → «Bekor qilish»; kerak bo‘lsa Office’ni yopib qayta urining |
| Chizma PDF’da ko‘rinmaydi | Fayl DXF ekanini tekshiring (DWG’ni AutoCAD’da DXF qilib saqlang) |
