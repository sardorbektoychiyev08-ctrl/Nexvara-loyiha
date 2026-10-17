# Android ish jurnali

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
