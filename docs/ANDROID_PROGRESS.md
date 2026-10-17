# Android ish jurnali

## 2026-10-17 — Codex — Android V1 integratsiya davom etdi

- `main` dagi telefon API v1 hujjatlari va demo serveri faqat `codex/android-mobile` worktree'iga merge qilindi; ROADMAP konflikti ikkala tomon yozuvlarini saqlab hal qilindi. Claude papkasi va tarmog‘i o‘zgartirilmadi.
- Chatdagi Windows AI tasdig‘i (`/confirm`), foreground vazifa long-poll (`/tasks/watch`), qadamlar ro‘yxati, bir nechta PC tanlash, tavsiya qilinganda token rotation qo‘shildi.
- Chat buyruqlari Windows javob bermasa Android Keystore bilan shifrlangan navbatda qoladi; qayta yuborishda avvalgi `X-Request-Id` ishlatiladi. Kamera orqali rasm olish va yuborish qo‘shildi. Release signing muhit qiymatlari bilan tayyorlandi; haqiqiy keystore kiritilmadi.
- Android `:app:assembleDebug :app:testDebugUnitTest` — PASS, 3/3 QR unit test. APK SHA-256: `0fb936e716d501bc6259e01d0cd4f4d87cf758c8e8c728a8ad8a3079384532bc`.
- Android 16 haqiqiy telefonga ADB orqali APK o‘rnatish va ishga tushirish — PASS. QR orqali demo Windows API bilan pairing va `salom` chat so‘roviga server javobining telefonda ko‘rinishi — PASS. Klaviatura xabar maydonini berkitishi topildi, `imePadding` bilan tuzatildi va telefonda qayta tekshirildi — PASS.
- Windows `scripts/test.ps1` — FAIL/BLOCKED: Android worktree'da `.venv` yo‘q. Windows kodi va Claude ishchi papkasi tegilmagan.
- Kamera, fayl almashinuvi, haqiqiy Windows ish stoli agenti bilan E2E va fon bildirishnomalari — NOT TESTED. Google OAuth — BLOCKED (Google Cloud Android client ID/SHA kerak); pause/resume — BLOCKED (API yo‘q).

Keyingi qadam: kamera va fayl almashinuvini, haqiqiy Windows agenti bilan vazifalarni E2E sinash; fon sinxronizatsiyasi va bildirishnomalar.

## 2026-10-17 — Codex — Android V1 boshlanishi

- Alohida `codex/android-mobile` worktree yaratildi; Windows fayllari o‘zgartirilmadi.
- Kotlin/Compose loyiha, Home, Chat, Tasks, Devices, QR pairing, TLS sertifikat izini tekshirish, Android Keystore sessiyasi, fayl tanlash/yuborish va ovoz tanish intenti qo‘shildi.
- Windows `/api/v1` haqiqiy shartnomasi bilan ishlash boshlandi.
- JDK 17, Android SDK 36 va Gradle 8.13 D: diskidagi ish joyida o‘rnatildi.
- `:app:assembleDebug :app:testDebugUnitTest` — PASS (debug APK 57 299 091 bayt, 3/3 QR unit test). Oxirgi APK SHA-256: `557d0921c1cb8584e4d3162acf182be6e2f5bdd0f4308b9467eb643abb37907d`.
- Kompyuter o‘chiq bo‘lsa Home ulanishni tasdiqlanmagan deb ko‘rsatadi; logout mahalliy sessiyani baribir tozalaydi. Qayta build va unit test PASS.
- Windows `scripts/test.ps1` — FAIL: hozirgi Claude Windows fayllarida ruff xatolari bor va mavjud `.venv` Python ishga tushmadi. Android bu fayllarni o‘zgartirmadi.
- Haqiqiy telefon, kamera, mikrofon, bildirishnoma, Windows–Android E2E — NOT TESTED.
- Google login — BLOCKED (Google Cloud Android client ID va signing SHA kerak). Pause/resume — BLOCKED (Windows API endpoint yo‘q).

Keyingi qadam: Android toolchain bilan APK yig‘ish; mobil UI va haqiqiy telefon/Windows E2E sinovi.
