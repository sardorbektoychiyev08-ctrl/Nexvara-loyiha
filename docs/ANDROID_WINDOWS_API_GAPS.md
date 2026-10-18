# Android V1 uchun Windows API yetishmaydigan qismlar

Bu hujjat `codex/android-mobile` tarmog‘ida yozildi. Windows kodi va Claude ishchi papkasi o‘zgartirilmadi. Mavjud `/api/v1` marshrutlari: [api/MOBILE_API.md](api/MOBILE_API.md).

## Pause / resume — BLOCKED

Hozir `TaskRunner` faqat `pending`, `running`, `succeeded`, `failed`, `cancelled` holatlarini biladi; `POST /api/v1/tasks/{id}/cancel` mavjud. Mobil UI pause/resume tugmasini ko‘rsata olmaydi, chunki serverda pauza mexanizmi ham, endpoint ham yo‘q.

Windows tomonidagi talab:

1. `Task` ga `pause_requested` va `paused` holatlarini, thread-safe pause signalini qo‘shish. Office qadamlarida xavfsiz nazorat nuqtalari bo‘lsin; COM amali o‘rtasida kuch bilan to‘xtatilmasin.
2. `POST /api/v1/tasks/{id}/pause` va `/resume`: amaldagi bearer token, `X-Request-Id` idempotency, aniqlangan xato kodlari (`NOT_FOUND`, yakunlangan vazifa uchun `BAD_REQUEST`). Javobda haqiqiy vazifa snapshoti bo‘lsin. `pause` faqat signal qo‘ygan bo‘lsa, `paused` deb erta qaytarmasin.
3. `GET /tasks`, `GET /tasks/{id}` va `GET /tasks/watch` bir xil yangi holatlarni bersin; `etag` har o‘zgarishda yangilansin. Cancel pauza holatida ham ishlasin.
4. Windows unit va Office E2E sinovlari: running → pause_requested → paused → running → succeeded; pauzada cancel; COM qadam chegarasida pause; takroriy request ID.

Android bu shartnoma paydo bo‘lgach tugmalar va holatlarni qo‘shadi. Hozir bekor qilish mavjud.

## Chat tarixi sinxronlashuvi — BLOCKED

Telefon oxirgi 200 xabarni har bir PC uchun Keystore bilan shifrlab saqlaydi. Bu tarix faqat telefonda; Windows chat tarixi bilan sinxronlashgan deb hisoblanmaydi. `/api/v1` da chat xabarlarini o‘qish endpointi va barqaror xabar ID yo‘q.

Windows tomoniga `GET /api/v1/chat/history?cursor=&limit=` kerak: `id`, `created_at`, `role`, `text`, `task_id` va keyingi `cursor`; sahifalash, bekor qilingan/yangilangan xabarlar qoidasi, token tekshiruvi va boshqa qurilmalardagi suhbatni ko‘rish chegarasi aniq bo‘lsin. Android lokal navbatdagi `X-Request-Id` bilan server xabarlarini moslashtiradi va dublikat ko‘rsatmaydi.

## Memory sinxronlashuvi — BLOCKED

Windows Agent chat orqali xotira haqidagi savollarga javob bera oladi, ammo Android uchun Memory ro‘yxati/o‘zgarishlarini o‘qish API yo‘q. `GET /api/v1/memory?cursor=&limit=` yoki versiyali snapshot endpointi, yozuv ID, tahrir/o‘chirish vaqti, sahifalash va token tekshiruvi kerak. O‘chirilgan yozuvlar uchun tombstone yoki to‘liq snapshot bo‘lsin. Android faqat shundan keyin mahalliy Memory ekranini ishonchli sinxronlaydi.

## Haqiqiy Windows Office E2E sinovi

`POST /api/v1/chat` Windows Agent bilan bir pipeline’dan foydalanadi; Office topshiriqlari uchun alohida Android endpoint kerak emas. Excel, Word, PowerPoint buyruqlarini telefondan yuborish, `task.id` bo‘yicha `tasks/watch` ni kuzatish, `cancel` va natija faylini `GET /files?path=` bilan olish haqiqiy Windows Agent pairingidan keyin tekshiriladi. Pullik AI kaliti talab qilinmaydigan deterministik demo buyruqlar ishlatiladi.
