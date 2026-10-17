# NEXVARA Android V1

Kotlin + Jetpack Compose ilovasi. `minSdk=29` (Android 10), `targetSdk=36` (Android 16).

## Ishga tushirish

Android SDK va JDK 17 kerak. `android/local.properties` faylida `sdk.dir` ni belgilang, so‘ng Windows'da `.\gradlew.bat assembleDebug` ishlating. Debug APK: `app/build/outputs/apk/debug/app-debug.apk`. Release build imzosi qurilma tashqarisidagi shaxsiy keystore bilan sozlanadi; loyiha ichiga kalit qo‘yilmaydi.

Windows NEXVARA → Devices bo‘limida serverni yoqing va QR kodini skanerlang. Telefon va kompyuter bitta Wi-Fi tarmog‘ida bo‘lishi kerak. Sertifikat QR ichidagi SHA-256 izi bilan tekshiriladi; odatdagi TLS hostname tekshiruvi ham saqlangan. Token Android Keystore bilan shifrlanadi.

## Windows API chegarasi

Android faqat `src/nexvara/remote_v1.py` dagi `/api/v1` ni chaqiradi. JSON javoblari `{"v":1,"ok":true,"data":{...}}` ko‘rinishida. Hozir ishlatiladigan yo‘llar: `info`, `pair`, `session`, `chat`, `tasks`, `tasks/{id}/cancel`, `files` (POST), `session/logout`. POST so‘rovlarda `X-Request-Id` yuboriladi. Fayl yuborishda `X-Filename` va `X-Content-SHA256` bor. Windows tarafidagi hujjatlarda tilga olingan `docs/api/MOBILE_API.md` va `docs/api/openapi.yaml` hozirgi repozitoriyada mavjud emas; haqiqiy kontrakt koddan tekshirildi.

Windows tomondan kerak bo‘ladigan keyingi endpointlar: `pause/resume`, chat tarixini o‘qish, Memory/Teach, Workflows, BI dashboard JSON, ulangan kompyuterlar ro‘yxati va Google account linkage. Bu funksiyalar ilovada muvaffaqiyatli ishlayotgandek ko‘rsatilmaydi. Google OAuth uchun Google Cloud Android client ID va SHA sertifikat izi kerak.

## Ma’lum cheklovlar

- Joriy versiyada bitta PC sessiyasi saqlanadi. Yangi PC bog‘lash eskisini almashtiradi.
- Chatdagi tasdiq Windows oynasida bajariladi. Mobil tasdiq UI hali ulanmagan.
- Vazifa holati qo‘lda yangilanadi. Push bildirishnomalar va fon sinxronizatsiyasi keyingi bosqichda.
- Release signing va Google login haqiqiy konfiguratsiyasiz BLOCKED.
