# Android APK build + unit tests with the local toolchain in .tools (JDK 17, Android SDK, Gradle).
# .tools is not in Git (see .gitignore); docs/ANDROID_HANDOFF.md says how to install it.
#   .\scripts\android_build.ps1            -> debug APK + unit tests
#   .\scripts\android_build.ps1 -Release   -> also a signed release APK (needs NEXVARA_RELEASE_* env)
param([switch]$Release)
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root ".tools"
# The toolchain may live in the Android worktree (.worktrees\android\.tools) instead.
if (-not (Test-Path (Join-Path $tools "jdk"))) {
    $alt = Join-Path $root ".worktrees\android\.tools"
    if (Test-Path (Join-Path $alt "jdk")) { $tools = $alt }
    else { Write-Host "ANDROID: .tools topilmadi (docs/ANDROID_HANDOFF.md)" -ForegroundColor Red; exit 1 }
}
# Release: the key lives only in D:\NEXVARA\release (never in Git), its password in Windows
# Credential Manager (NEXVARA/release/android). Explicit NEXVARA_RELEASE_* values still win.
if ($Release -and -not $env:NEXVARA_RELEASE_STORE_FILE) {
    $jks = "D:\NEXVARA\release\android-release.jks"
    $pw = & (Join-Path $root ".venv\Scripts\python.exe") -c "import sys; sys.path.insert(0, r'$root\src'); from nexvara.ai.keys import KeyStore; print(KeyStore('NEXVARA/release/').load('android') or '')"
    if (-not (Test-Path $jks) -or -not $pw) { Write-Host "ANDROID: release kaliti topilmadi ($jks)" -ForegroundColor Red; exit 1 }
    $env:NEXVARA_RELEASE_STORE_FILE = $jks; $env:NEXVARA_RELEASE_KEY_ALIAS = "nexvara"
    $env:NEXVARA_RELEASE_STORE_PASSWORD = $pw; $env:NEXVARA_RELEASE_KEY_PASSWORD = $pw
}
$env:JAVA_HOME = (Get-ChildItem (Join-Path $tools "jdk") -Directory | Select-Object -First 1).FullName
$env:GRADLE_USER_HOME = Join-Path $tools "gradle-home"
$env:ANDROID_USER_HOME = Join-Path $tools "android-home"
$env:ANDROID_HOME = Join-Path $tools "android-sdk"
Set-Location (Join-Path $root "android")
$tasks = @(":app:assembleDebug", ":app:testDebugUnitTest")
if ($Release) { $tasks += ":app:assembleRelease" }
& .\gradlew.bat --no-daemon --console=plain @tasks
if ($LASTEXITCODE -ne 0) { Write-Host "ANDROID: FAIL" -ForegroundColor Red; exit 1 }
$apk = Join-Path $root "android\app\build\outputs\apk\debug\app-debug.apk"
$hash = (Get-FileHash $apk -Algorithm SHA256).Hash.ToLower()
Write-Host "APK: $apk"
Write-Host "SHA-256: $hash"
Write-Host "ANDROID: PASS" -ForegroundColor Green
