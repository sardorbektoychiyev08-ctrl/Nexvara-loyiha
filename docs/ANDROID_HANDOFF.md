# Android app — handoff (Claude → Codex)

## 2026-10-17 (kech) — Claude: Android V1 qayta dizayn va to‘liq bo‘limlar

**Egasi o‘zgardi:** foydalanuvchi Android’ni Claude’ga topshirdi. Tarmoq: `claude/android-v1`
(worktree `D:\Nexvara loyiha\.worktrees\android`, `codex/android-mobile` + `main` ustiga).
Codex limit bo‘lsa shu tarmoqdan davom etadi (PROGRESS.md dagi oxirgi yozuv).

**Build:** `.\scripts\android_build.ps1` (JDK/SDK/Gradle `.tools` da, Git’da emas) →
`android/app/build/outputs/apk/debug/app-debug.apk`, nusxasi `D:\NEXVARA\android\`.

**Kod tuzilishi** (`android/app/src/main/java/uz/nexvara/mobile/`):
- `AppModel.kt` — butun holat va barcha `/api/v1` chaqiruvlari (ViewModel, coroutines);
- `Model.kt` — server JSON → Kotlin (`Parse`), o‘zbekcha format (`Fmt`);
- `WindowsApi.kt` (TLS pin), `SecureSession.kt` (Keystore AES-GCM), `TransferChecks.kt`;
- `ui/Theme.kt` (brend ranglari, qorong‘i/yorug‘), `ui/Components.kt`,
  `ui/MainScreens.kt` (qulf, ulanish, Bosh sahifa, Suhbat, Vazifalar, Bo‘limlar),
  `ui/SectionScreens.kt` (Office+Chizma, Darsliklar, Fayllar, BI, Workflow, Teach, Xotira,
  AI xarajat, Kompyuterlar+Google, Sozlamalar);
- `MainActivity.kt` — QR, fayl/rasm/PDF/kamera, ovoz (SpeechRecognizer + TTS),
  bildirishnoma, BiometricPrompt qulf, Credential Manager (Google).

**1.1.0 (2026-10-17 kechasi):** kompyuter ekrani (jonli, faqat ko‘rish), PC fayl qidirish /
ochish / telefonga olish, «Tayyor buyruqlar» (o‘qituvchi, ofis, hujjat, chizma), Tailscale
orqali boshqa tarmoq (manzillar `session` dan, pin bo‘yicha ishonch), chizmani tuzatish + DXF,
«Ulashish → NEXVARA», WorkManager bilan fon xabarlari (`Notifier.kt`), skrinshot taqiqi.
Telefonda (Xiaomi, Android 16) adb bilan E2E qilindi — skriptlar scratchpad’da edi; qayta
qilish uchun: `adb reverse tcp:8766 tcp:8766`, vaqtinchalik `NEXVARA_DATA` bilan Agent,
havolani `127.0.0.1` ga almashtirib qo‘lda joylash, uiautomator dump + `input tap`.

**Qolgan ish (keyingi agent uchun):** 1) haqiqiy telefon + haqiqiy Windows Agent E2E
(foydalanuvchi bilan); 2) release imzo kaliti `D:\NEXVARA\android\release.jks` (foydalanuvchi
tasdig‘i bilan yaratiladi) va `-Release` build; 3) Google: foydalanuvchi Google Cloud’da
Android + Web client yaratadi ([GOOGLE_LOGIN.md](GOOGLE_LOGIN.md) § Android), Web client ID
`settings.json → google.android_web_client_id`; 4) fon bildirishnomalari uchun WorkManager
(hozir ilova jarayoni tirik paytda ishlaydi).

## 2026-10-17 — Codex: vaqtinchalik to‘xtash (tarix)

Foydalanuvchi ko‘rsatmasi: Windows NEXVARA PERSONAL to‘liq tugamaguncha Android ishlab chiqilishi davom ettirilmaydi. Claude Windows versiyasini yakunlaydi; Codex uning ishchi papkasi va fayllariga tegmaydi. Android kodi faqat `D:\Nexvara loyiha\.worktrees\android` va `codex/android-mobile` tarmog‘ida.

Hozirgi holat: Kotlin/Compose ilova, QR pairing, TLS pin, token saqlash, Home/Chat/Tasks/Devices, foreground task watcher, cancel, fayl yuborish/olish kodi, kamera va shifrlangan chat tarixi. Debug APK build va 8/8 Android unit test **PASS**. Oldingi APK bilan Android 16 telefonda pairing, chat, chat tarixi, oddiy fayl yuborish va kamera oynasini ochish **PASS**. Oxirgi kodli APK qurilmada sinovdan o‘tmagan: ADB avtomatik ruxsati rad etildi. Windows oynasini avtomatik boshqarish ham rad etildi. `scripts/test.ps1` uchun alohida worktree'da `.venv` yo‘q.

Windows versiyasi yakunlanib, foydalanuvchi Android ishini qayta boshlashni aytgach qolgan vazifalar:

1. Oxirgi APK’ni Android 16 telefonga o‘rnatish; kamera bilan rasm olib Windows Agent’ga yuborish va SHA-256 natijasini tekshirish.
2. Windows NEXVARA Devices QR kodi bilan **haqiqiy** Agent’ga pairing; demo server natijasini haqiqiy Agent natijasi deb belgilamaslik.
3. Telefondan deterministik Excel, Word, PowerPoint vazifalarini yuborish; task ID, progress/qadamlar, cancel va tayyor faylni telefonga yuklab olishni E2E tekshirish. Office oynalari ochilishi kerak; haqiqiy foydalanuvchi hujjatlariga tegmaslik.
4. Chat tarixi va Memory sinxronlashuvini Windows API paydo bo‘lgach amalga oshirish. Pause/resume ham Windows `TaskRunner` va `/api/v1` endpointlari tayyor bo‘lgach qo‘shiladi. Aniq server talabi: [ANDROID_WINDOWS_API_GAPS.md](ANDROID_WINDOWS_API_GAPS.md).
5. Android 16 real sinovini yakunlash: kamera, mikrofon, fayl download, reconnect/offline queue, cancel, bir nechta PC va UI. Fon bildirishnomalari, biometrik qulf, Google OAuth va qolgan mobil bo‘limlar hali tugallanmagan. Google uchun Android OAuth client ID va signing SHA kerak.
6. Build, unit/UI/API contract testlari, `scripts/test.ps1`, xavfsizlik tekshiruvi; PASS/PARTIAL/NOT TESTED/BLOCKED holatlarini yangilash. Pushdan oldin PRIVATE GitHub va maxfiy ma’lumot yo‘qligini qayta tasdiqlash.

Oxirgi build fayli: `android/app/build/outputs/apk/debug/app-debug.apk` (Git’ga kiritilmaydi), SHA-256 `8c02e7d8a346d43e6a3b9f46e273f464a3ca2b6894ead7d58646afdb4ea81f9c`. Ish jurnali: [ANDROID_PROGRESS.md](ANDROID_PROGRESS.md).

Goal: a native Android app (MASTER_SPEC §18) that controls the NEXVARA Windows Agent over the
local network. The Windows side is done and tested; this document is everything needed to
build the APK against it. Owner now: **Claude**, branch `claude/android-v1`, folder `android/`.

Read first: [api/MOBILE_API.md](api/MOBILE_API.md) (protocol) and [api/openapi.yaml](api/openapi.yaml)
(contract). Do not change the Windows API without a matching change in `remote_v1.py`,
`openapi.yaml` and its test (Claude owns those files; coordinate in PROGRESS.md).

## 1. Toolchain (not installed on this PC yet)

- JDK 17 (Temurin), Android SDK (cmdline-tools, platform 36, build-tools), Gradle wrapper.
  Install on D: (for example `D:\Android\sdk`), set `ANDROID_HOME`. Do not commit
  `local.properties`, keystores or `*.apk` (already in `.gitignore`).
- Kotlin 2.x, Jetpack Compose (Material 3), minSdk 29 (Android 10), targetSdk 36. Main test
  device: the user's Android 16 phone.

## 2. Suggested structure

```
android/
  settings.gradle.kts, build.gradle.kts, gradle/libs.versions.toml, gradlew
  app/src/main/java/uz/nexvara/mobile/   (Codex uses applicationId uz.nexvara.mobile)
    data/api/        NexvaraApi (Retrofit or Ktor), DTOs generated from openapi.yaml or hand-written
    data/net/        PinnedTls (OkHttp X509TrustManager that checks SHA-256 of the leaf cert)
    data/store/      PcStore (DataStore + Keystore AES-GCM), OutboxQueue (Room)
    work/            SyncWorker, OutboxWorker (WorkManager)
    ui/              Home, Chat, Tasks, TaskDetail, Devices (pair/QR), Memory, Settings
  app/src/test/...   unit tests (MockWebServer)
  app/src/androidTest/... instrumented tests
```

## 3. Must-have behaviour (acceptance criteria)

| # | Feature | Acceptance |
|---|---|---|
| A1 | Pair by QR | Camera (CameraX + ML Kit barcode) reads the link, app calls `info` then `pair`, stores token + `fp`. Wrong/expired code shows the server message |
| A2 | Certificate pinning | A server with a different certificate is rejected (test with MockWebServer + two certs) |
| A3 | Several PCs | "Work PC / Home PC": list stored PCs by `server_id`, switch, rename locally, remove |
| A4 | Chat | Send text, show `reply`; if `task` present, open live progress; if `confirm` present show "Ha, davom et / Yo‘q" and call `/confirm` |
| A5 | Live progress | Foreground long-poll `tasks/watch`; steps with status icons; Cancel button → `/cancel` |
| A6 | Results | Download `files` with `GET /files?path=`, verify `X-Content-SHA256`, open with an Intent / share |
| A7 | Upload | Pick a file or take a photo, `POST /files` with `X-Filename` and `X-Content-SHA256`; then the chat can say "shu faylni PDF qil" |
| A8 | Offline / retry | PC off → message queued with its `X-Request-Id`, clear status text, WorkManager retries with backoff, never sends twice |
| A9 | Token lifecycle | `session` on start; rotate when `rotate_recommended`; `AUTH_REQUIRED`/`TOKEN_EXPIRED` → re-pair screen; Logout calls `/session/logout` |
| A10 | Secure storage | Token and `fp` encrypted with an Android Keystore key; no token in logs; `allowBackup=false` for those files |
| A11 | Biometric unlock | Optional setting: BiometricPrompt before the app opens |
| A12 | Voice input | Android `SpeechRecognizer` (uz-UZ if available, else ru-RU) → text → same chat call (no paid API) |
| A13 | Notifications | Local notification when a task started from the phone finishes (WorkManager periodic check while in background) |
| A14 | Design | Dark/Light, NEXVARA brand colors: accent `#6366F1`, accent-2 `#06B6D4`, dark background `#0B1020`; Uzbek UI text |
| A15 | Release | `assembleRelease` signed with a keystore kept outside Git (`D:\NEXVARA\android\release.jks`); versionCode increments; upgrade keeps data |

## 4. Network security config

The PC is on a private address with a self-signed certificate; trust comes only from the pin.

- Do not use `cleartextTrafficPermitted`. Everything is HTTPS.
- Implement pinning in OkHttp with a custom `X509TrustManager` for the stored host: accept iff
  `sha256(chain[0].encoded) == fp` (lowercase hex). Hostname verification: accept the stored
  host only (the certificate SAN contains the PC's LAN IP).
- `res/xml/network_security_config.xml`: no user CAs.

## 5. Testing without the real PC

```
.venv\Scripts\python.exe -m nexvara.devserver --port 8765
```

Real v1 server, fake agent, temp folder; prints the QR link with `fp`. From the emulator the PC
is `10.0.2.2` (the link shows the LAN IP; both work because only the pin is checked).
Unit tests: OkHttp MockWebServer with recorded envelopes from MOBILE_API.md.

## 6. Blocked / out of scope for v1

| Item | Status | Why / what is needed |
|---|---|---|
| Google login on Android | BLOCKED | Same Google Cloud project as Windows: an **Android** client (package `uz.nexvara.mobile` + SHA-1) and a **Web** client ID as `serverClientId` for Credential Manager. Only the PC owner (same Google `sub`) should be accepted. Details: [GOOGLE_LOGIN.md](GOOGLE_LOGIN.md) §Android. The app must work fully without it |
| Push notifications (FCM) | BLOCKED | Needs a Firebase project and an internet relay; v1 uses long-poll + WorkManager |
| Access outside home Wi-Fi | BLOCKED | Needs a relay/VPN (e.g. Tailscale) chosen by the user; the protocol does not change |
| Memory / Teach / settings sync | Windows side READY | `GET/POST /api/v1/sync` (MOBILE_API.md §10). Optional for the app v1 |

## 7. Rules (same as AGENTS.md)

- Never call paid AI APIs from the phone; the PC decides and asks via `confirm`.
- No secrets in Git (keystore, `google-services.json`, tokens).
- Do not mark anything PASS without running it; write results to PROGRESS.md.
