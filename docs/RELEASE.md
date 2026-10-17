# Windows release: build, install, update, rollback

## Build

```
.\scripts\build.ps1
```

1. Draws `build\nexvara.ico`, writes version info from `nexvara.__version__`.
2. PyInstaller ([installer/nexvara.spec](../installer/nexvara.spec)) → `dist\NEXVARA\NEXVARA.exe` (one folder, ~130 MB, no console).
3. Inno Setup 6 ([installer/nexvara.iss](../installer/nexvara.iss)) → `dist\installer\NEXVARA-Setup-<ver>.exe` (~47 MB).

Tools: `pip install pyinstaller` in `.venv`, `winget install JRSoftware.InnoSetup --scope user`.
`dist\` and `build\` are git-ignored.

## Installer

- Per-user, no admin: `%LOCALAPPDATA%\Programs\NEXVARA`. Start Menu group with uninstaller,
  optional desktop icon.
- User data is never touched: `D:\NEXVARA` (settings, app.db, textbooks), Credential Manager keys.
  Upgrade = install over the old version (old program files are replaced as a whole).
- Silent: `NEXVARA-Setup-x.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART [/NOLAUNCH] [/DIR=...]`.
- Uninstall: Start Menu → "NEXVARA’ni o‘chirish" or `unins000.exe /VERYSILENT`.
- The wizard is in Uzbek (`[Messages]` in the .iss; Inno Setup ships no Uzbek file).
- The installer leaves a copy of itself in `%LOCALAPPDATA%\NEXVARA\installers\<ver>\`, so a
  version installed by hand is also a rollback target.
- Before installing over an existing copy, back up the data:
  `python scripts\backup_userdata.py backup` (→ `D:\NEXVARA-zaxira\<time>\`, SHA-256 per file,
  SQLite through its backup API, desktop shortcut; Credential Manager secrets are never
  exported — only their names are listed). `verify <folder>` re-checks, `restore <folder> --to
  <dir>` restores (into a non-empty folder only with `--i-approve`, old files are moved aside).
- Check an installed copy: `NEXVARA.exe --selftest-installed <temp dir>` → 12 pages, Google
  session, sync folder decrypts, AI settings, Excel/Word/PowerPoint demos and BI into the temp
  dir, `report.json` (yes/no and counts only).

## Updates (private channel)

- Channel: a folder (e.g. `D:\NEXVARA\releases`, a network share, a USB stick) or an `https://`
  URL. Set in Settings → Versiya va yangilanish. Plain `http://` is refused.
- Publish (release PC only):

  ```
  .\scripts\build.ps1 -Publish D:\NEXVARA\releases -Notes "Nima yangi"
  ```

  writes `latest.json`, `latest.json.sig` (Ed25519) and the installer.
- The signing key is `D:\NEXVARA\release\signing_key.pem` — **outside Git, back it up**. Losing
  it means a new key and a new public key in `updater.py` (old installs would not accept the
  new releases). Its public half is `RELEASE_PUBLIC_KEY` in [src/nexvara/updater.py](../src/nexvara/updater.py).
- The app: checks the signature → downloads → checks size + SHA-256 → writes
  `updates\pending.json` → starts the installer silently and closes; the installer starts the
  new version.
- At start, if "auto_check" is on and a channel is set, the signed manifest is read once and
  a banner offers «Yangilash» (nothing is downloaded before the click).
- Next start: version matches → "Yangilandi" message, the installer is kept for rollback (last 2).
  Version does not match → "yangilash tugamadi", rollback offered to the previous kept version.
- Settings are migrated by merging with defaults (`appdata.DEFAULT_SETTINGS`); unknown keys
  are kept, missing keys get defaults. Device table columns are added by `DeviceStore`.

## Not done

- **Internet updates: no HTTPS server yet.** The code accepts an `https://` channel, but it has
  not been tested against a real server. Today's channel is a local folder
  (`D:\NEXVARA\releases`) — that is a local update, not an internet one.

- Code signing of the .exe (Authenticode) needs a certificate — **BLOCKED** (SmartScreen
  shows "unknown publisher" on first run).
- GitHub Releases as a channel: the repository is private, so downloads need a token; use a
  folder or another https host instead.
