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

## Android (prepared, not implemented — Codex's area)

Use the **same Google Cloud project** so the phone and the PC see the same account:

- an **Android** OAuth client: package `uz.nexvara.mobile` (Codex's applicationId) + SHA-1 of the release keystore
  (and the debug keystore while developing);
- a **Web application** OAuth client: its client ID is the `serverClientId` that Android
  Credential Manager (`GetGoogleIdOption` / Sign in with Google) puts in the ID token's `aud`.
  No secret of it goes into the app.
- Owner check on the phone: compare the ID token's `sub` with the PC owner. Google's `sub` is
  the same for one Google account across all clients, so the phone can confirm it is the same
  person. A PC endpoint for this (verify the phone's ID token against the Web client ID) is
  not built yet; until then the phone pairs by QR as today.
- No `google-services.json` is needed for Sign in with Google alone (only for Firebase).
