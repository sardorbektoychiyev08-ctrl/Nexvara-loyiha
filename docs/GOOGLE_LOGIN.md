# Google login (optional, owner-only)

NEXVARA works fully without Google. The Windows login is implemented in
[src/nexvara/account.py](../src/nexvara/account.py) and tested against a fake Google server that
checks PKCE and signs real RS256 ID tokens. A **real** login needs the owner's own Google
Cloud OAuth client; NEXVARA never creates one and never signs in on its own.

## State on this PC (checked 2026-10-17)

No Google OAuth configuration exists anywhere on this PC: no client JSON (Desktop / Web),
no `google-services.json` (Android), no NEXVARA Google entries in Credential Manager, nothing
in `D:\NEXVARA`. The only client IDs found are the fake ones in the unit tests. So the real
login is **BLOCKED** until the owner creates the client (steps below, ~10 minutes).

## How it works (Windows)

1. Settings → "Google bilan kirish" opens the system browser (not an embedded window).
2. Google redirects to a one-time listener on `http://127.0.0.1:<random port>/` (RFC 8252).
3. Authorization Code + PKCE S256 + `state` + `nonce`; the code is exchanged for tokens.
4. The ID token's RS256 signature (Google JWKS), issuer, audience, expiry and nonce are
   checked; the email must be verified.
5. **Owner-only.** First login on this PC: nothing is stored yet; the app asks
   "Ha, bu mening hisobim" / "Yo‘q". After "Ha", the account's stable Google subject id
   (`sub`) is stored in Credential Manager (`NEXVARA/google/owner_sub`). Any other account
   that signs in later is refused and its tokens are revoked at once. The email is not used
   for this (it can change; `sub` never does). "Egani almashtirish" works only while signed
   out and asks first.
6. Refresh token → Credential Manager (`NEXVARA/google/refresh_token`); profile (name, email,
   picture, granted scopes; nothing secret) → `D:\NEXVARA\account.json`.
7. Session restore: when the app opens it refreshes the session in the background, no browser.
   A revoked/expired grant signs out (the owner is remembered); no internet keeps the
   session ("offline") and checks again next time. A refreshed ID token of another account
   signs out.
8. "Chiqish" revokes the grant at Google and deletes the token and profile.

Scopes: `openid email profile`; plus `https://www.googleapis.com/auth/drive.appdata` only when
Drive sync is switched on (see below). Nothing else.

## One-time setup by the owner — this unblocks the real login

1. https://console.cloud.google.com → top bar → create project "NEXVARA" (or pick an existing
   project of yours; any project works, the client type is what matters).
2. **Google Auth Platform → Branding**: app name NEXVARA, your support email.
   **Audience**: External, publishing status *Testing*, add **your own Gmail** under Test users
   (only test users can sign in while in Testing — a second layer of owner-only).
3. **Clients → Create client → Application type: Desktop app** → name "NEXVARA Windows" →
   Create → **Download JSON**. (Do not send this file to anyone or paste it in chat.)
4. NEXVARA → Sozlamalar → Google hisobi → **«Client JSON faylini tanlash»** → pick the
   downloaded file. It is checked (must be *Desktop app*) and copied to
   `D:\NEXVARA\google_client.json`, never into the project folder or Git.
5. Click **«Google bilan kirish»**, choose your account in the browser, allow, then in NEXVARA
   press **«Ha, bu mening hisobim»**.
6. Optional, for Drive sync: **APIs & Services → Library → Google Drive API → Enable**; in
   **Data access → Add scopes** add only `.../auth/drive.appdata`; in NEXVARA turn on
   Sozlamalar → Sinxronlash → "Google Drive orqali ham", then sign in again.

Note: with publishing status *Testing*, Google expires refresh tokens after 7 days when
scopes beyond name/email are granted (Drive). NEXVARA then simply asks you to sign in again.

## Drive sync: the minimal permission

| Scope | Gives access to | Used |
|---|---|---|
| `drive.appdata` | only a hidden folder that belongs to this app in your Drive; your own files are invisible to NEXVARA | **yes** |
| `drive.file` | files NEXVARA creates or you open with it | no (not needed) |
| `drive.readonly` / `drive` | all your Drive files | **never** |

NEXVARA writes one encrypted file per device (`<device>.nxsync`, AES-256-GCM with your sync
passphrase), so even Google sees only ciphertext.

## Android (implemented; needs the owner's Google Cloud clients)

The phone signs in with Android **Credential Manager** ("Sign in with Google"). The PC checks
the phone's ID token: Google's RS256 signature, issuer, expiry, audience = our **Web client
ID**, verified email, and `sub` = the PC owner. Only the email is stored on the paired
device's row (`app.db`). No password, no secret, no `google-services.json`.

Owner's one-time steps (Google Cloud Console → the **same project** as the Windows client →
APIs & Services → Credentials → Create credentials → OAuth client ID):

1. **Android** client: package name `uz.nexvara.mobile`, SHA-1 of the signing certificate.
   - debug APK (this PC's debug key): `5F:D9:63:6F:A9:BD:5F:A0:0A:4C:A5:CD:D4:C6:18:E1:74:68:BE:11`
   - release APK: the SHA-1 of `D:\NEXVARA\android\release.jks` (made when the release key is
     created; `keytool -list -v -keystore release.jks`). Add both.
2. **Web application** client: no redirect URI needed. Copy its **Client ID** (ends with
   `.apps.googleusercontent.com`; it is public, not a secret).
3. Put the Web Client ID into `D:\NEXVARA\settings.json` → `"google": {"android_web_client_id":
   "…"}` (NEXVARA reads it; the phone gets it from the PC).
4. On the PC: Settings → Google → sign in and answer «Ha, bu mening hisobim» (sets the owner).
5. On the phone: Kompyuterlar → Google hisobi → «Google bilan bog‘lash».

Until then the phone works fully with QR pairing; the Google card says what is missing.

