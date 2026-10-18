# Office hujjatlari: rasmiy qoidalar

NEXVARA Excel, Word va PowerPoint bilan ishlaganda quyidagi rasmiy manbalarga tayanadi.
Qoidalar kodda: [src/nexvara/knowledge/office_guide.py](../src/nexvara/knowledge/office_guide.py).

## Qayerda ishlatiladi

1. **AI’ga ko‘rsatma.** So‘rov hujjat, ariza, jadval yoki taqdimot haqida bo‘lsa (`for_prompt`),
   tegishli qoidalar AI’ning tizim ko‘rsatmasiga qo‘shiladi. AI javobi doim o‘zbekcha lotinda
   (kirill bo‘lsa NEXVARA o‘zi lotinga o‘giradi; foydalanuvchi ruscha so‘rasa — ruscha).
2. **«Tekshir» buyrug‘i** (faylni o‘zgartirmaydi, faqat tavsiya beradi):
   - Excel — «Hisobot.xlsx ni tekshir»: standart varaq nomlari, bo‘sh varaqlar, birlashtirilgan
     kataklar, sarlavhasiz va takror ustunlar, jadval ichidagi va jadvalni ikkiga bo‘lgan bo‘sh
     qatorlar, matn sifatida yozilgan raqamlar, xato formulalar, jami qatori yo‘qligi.
   - Word — «Xat.docx ni tekshir»: sarlavha uslubisiz «sarlavhalar», ketma-ket bo‘sh qatorlar,
     ikkita bo‘sh joy, aralash shriftlar, 12 pt dan kichik matn, sahifa raqami yo‘qligi,
     nostandart sana shakli, birlashtirilgan katakli jadvallar, izohsiz rasmlar, imlo.
   - PowerPoint — «Taqdimot.pptx ni och va slaydlarni tekshir»: sarlavhasiz va bir xil
     sarlavhali slaydlar, 18 pt dan kichik matn (jadval ichida ham), 6 tadan ortiq band, izohsiz
     rasmlar, sig‘magan matn, ustma-ust obyektlar.

## Manbalar (2026-10-18 da tekshirilgan)

| Manba | Nima olindi |
|---|---|
| [Microsoft: Excel hujjatlarini hamma uchun qulay qilish](https://support.microsoft.com/en-us/office/make-your-excel-documents-accessible-to-people-with-disabilities-6cc05fc5-1314-48b5-8eb3-683e49b3e593) | sarlavha qatori, merge yo‘q, bo‘sh qator/ustun yo‘q, varaq nomlari, A1 da sarlavha, diagramma sarlavhalari |
| [Microsoft: Word hujjatlari](https://support.microsoft.com/en-us/office/make-your-word-documents-accessible-to-people-with-disabilities-d9bf3683-87ac-47ea-b91a-78dcacb3c66d) | o‘rnatilgan sarlavha uslublari, darajalarni o‘tkazib yubormaslik, oddiy jadvallar, alt matn, kolontitulga muhim ma’lumot qo‘ymaslik |
| [Microsoft: PowerPoint taqdimotlari](https://support.microsoft.com/en-us/office/make-your-powerpoint-presentations-accessible-to-people-with-disabilities-6f7772b2-2f33-4bd2-8ca7-dae3b2b3ef25) | har slaydda o‘z sarlavhasi, kamida 18 pt, kontrast, alt matn, o‘rnatilgan maketlar |
| [VM 1999-yil 29-martdagi 140-son qarori (lex.uz)](https://lex.uz/acts/-863120) | sana shakli (16-band), adresat (15), imzo (17), tasdiqlash (20), ilova (14), ijrochi (24), hujjat turi va sarlavha (8–9) |
| «Davlat tilida ish yuritish» qo‘llanmasi | A4, Times New Roman 14, 1–1,5 qator, chetlar 3 / 1,5 / 2 / 2 sm (amaliy tavsiya; qarorda millimetrlar yo‘q) |

Eslatma: 140-son qarorning lex.uz dagi matnida qog‘oz chetlari va shrift o‘lchami berilmagan;
ular amaliyotdagi qo‘llanmadan olingan va «tavsiya» deb ko‘rsatiladi.
