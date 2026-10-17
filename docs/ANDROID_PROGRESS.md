# Android ish jurnali

## 2026-10-17 — Codex — Android V1 boshlanishi

- Alohida `codex/android-mobile` worktree yaratildi; Windows fayllari o‘zgartirilmadi.
- Kotlin/Compose loyiha, Home, Chat, Tasks, Devices, QR pairing, TLS sertifikat izini tekshirish, Android Keystore sessiyasi, fayl tanlash/yuborish va ovoz tanish intenti qo‘shildi.
- Windows `/api/v1` haqiqiy shartnomasi bilan ishlash boshlandi.
- JDK 17, Android SDK 36 va Gradle 8.13 D: diskidagi ish joyida o‘rnatildi.
- `:app:assembleDebug :app:testDebugUnitTest` — PASS (debug APK 57 299 091 bayt, 3/3 QR unit test). SHA-256: `51164f76b3382f0f2d2bf0bbbe9de68e431ad83925b9321fd742499e33a7d3b9`.
- Windows `scripts/test.ps1` — FAIL: hozirgi Claude Windows fayllarida ruff xatolari bor va mavjud `.venv` Python ishga tushmadi. Android bu fayllarni o‘zgartirmadi.
- Haqiqiy telefon, kamera, mikrofon, bildirishnoma, Windows–Android E2E — NOT TESTED.
- Google login — BLOCKED (Google Cloud Android client ID va signing SHA kerak). Pause/resume — BLOCKED (Windows API endpoint yo‘q).

Keyingi qadam: Android toolchain bilan APK yig‘ish; mobil UI va haqiqiy telefon/Windows E2E sinovi.
