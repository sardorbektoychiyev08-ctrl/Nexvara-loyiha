# NEXVARA Android V1

Kotlin + Jetpack Compose ilovasi. `minSdk=29` (Android 10), `targetSdk=36` (Android 16).

## Ishga tushirish

Android SDK va JDK 17 kerak. `android/local.properties` faylida `sdk.dir` ni belgilang, so‘ng Windows'da `.\gradlew.bat assembleDebug` ishlating. Debug APK: `app/build/outputs/apk/debug/app-debug.apk`. Release signing uchun `NEXVARA_RELEASE_STORE_FILE`, `NEXVARA_RELEASE_STORE_PASSWORD`, `NEXVARA_RELEASE_KEY_ALIAS`, `NEXVARA_RELEASE_KEY_PASSWORD` muhit qiymatlari kerak; kalit loyiha ichiga qo‘yilmaydi.

Windows NEXVARA → Devices bo‘limida serverni yoqing va QR kodini skanerlang. Telefon va kompyuter bitta Wi-Fi tarmog‘ida bo‘lishi kerak. Sertifikat QR ichidagi SHA-256 izi bilan tekshiriladi; odatdagi TLS hostname tekshiruvi ham saqlangan. Token Android Keystore bilan shifrlanadi.

## Windows API chegarasi

Android faqat `src/nexvara/remote_v1.py` dagi `/api/v1` ni chaqiradi. JSON javoblari `{"v":1,"ok":true,"data":{...}}` ko‘rinishida. Ishlatiladigan yo‘llar: `info`, `pair`, `session`, `chat`, `confirm`, `tasks`, `tasks/watch`, `tasks/{id}/cancel`, `files` va `session/logout`. POST so‘rovlarda `X-Request-Id` yuboriladi. Fayl yuborishda `X-Filename` va `X-Content-SHA256` bor.

Windows tomondan kerak bo‘ladigan keyingi endpointlar: `pause/resume`, chat tarixini o‘qish, Memory/Teach, Workflows, BI dashboard JSON, ulangan kompyuterlar ro‘yxati va Google account linkage. To‘liq API hujjatlari: [`docs/api/MOBILE_API.md`](../docs/api/MOBILE_API.md) va [`docs/api/openapi.yaml`](../docs/api/openapi.yaml). Google OAuth uchun Google Cloud Android client ID va SHA sertifikat izi kerak.

## Ma’lum cheklovlar

- Bir nechta PC sessiyasi shifrlangan holda saqlanadi; Devices sahifasida tanlanadi.
- Chatning oxirgi 200 xabari har bir PC uchun Android Keystore bilan shifrlanib saqlanadi va ilova qayta ochilganda ko‘rsatiladi.
- Chatdagi tasdiq `POST /api/v1/confirm` orqali beriladi.
- Vazifa holati ilova ekranda bo‘lganida `tasks/watch` bilan yangilanadi. Fon bildirishnomalari keyingi bosqichda.
- `session` tavsiya qilsa token avtomatik almashtiriladi.
- Kompyuter vaqtincha javob bermasa chat buyrug‘i shifrlangan navbatda qoladi va ekrandagi aloqa tiklanganda o‘sha `X-Request-Id` bilan qayta yuboriladi. Windows serveri idempotency javobini 10 daqiqa saqlaydi; undan uzoq uzilishdan keyingi noma’lum natijani foydalanuvchi vazifalar tarixida tekshirishi kerak.
- Kamera rasmi Android `TakePicture` orqali olinadi. Android 16 da kamera oynasini ochish PASS; suratga olish va yuborish NOT TESTED. Oddiy fayl yuborish demo server bilan PASS.
- Release signing va Google login haqiqiy konfiguratsiyasiz BLOCKED.
