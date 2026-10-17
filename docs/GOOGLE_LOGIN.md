# Google login (optional)

NEXVARA works fully without Google. Login is implemented for Windows
([src/nexvara/account.py](../src/nexvara/account.py)) and tested against a fake Google server
that checks PKCE and signs real RS256 ID tokens. A real login needs the user's own Google
Cloud project — until it exists the Settings card shows **BLOCKED**.

## How it works (Windows)

1. Settings → "Google bilan kirish" opens the system browser (not an embedded window).
2. Google redirects to a one-time listener on `http://127.0.0.1:<random port>/` (RFC 8252).
3. PKCE S256 + `state` + `nonce`; the code is exchanged for tokens.
4. The ID token's RS256 signature (Google JWKS), issuer, audience, expiry and nonce are checked.
5. The refresh token goes to Windows Credential Manager (`NEXVARA/google/refresh_token`);
   the profile (name, email, picture) to `D:\NEXVARA\account.json`.
6. "Chiqish" revokes the grant at Google and deletes both. An expired/revoked grant
   (`invalid_grant`) signs out automatically.

Scopes: `openid email profile` only. Nothing is uploaded anywhere.

## One-time setup (user, ~10 minutes) — unblocks the real test

1. https://console.cloud.google.com → create project "NEXVARA".
2. "Google Auth Platform" → Branding: app name NEXVARA, your email. Audience: External,
   status **Testing**, add your Gmail as a test user.
3. Clients → Create client → type **Desktop app** → name "NEXVARA Windows".
4. Download the JSON. In NEXVARA: Settings → Google hisobi → **«Client JSON faylini tanlash»**.
   The file is checked (must be a *Desktop app* client, not *Web application*) and copied to
   `D:\NEXVARA\google_client.json` (an older one is kept as `.bak`). Nothing is sent anywhere.
5. Only you sign in: Settings → Google hisobi → "Google bilan kirish" opens your browser.
   NEXVARA never signs in on its own and never sees the password.
6. For sync through Google Drive also: APIs & Services → enable **Google Drive API**, and in
   Data access add the scope `.../auth/drive.appdata`. Turn on Settings → Sinxronlash →
   "Google Drive orqali ham" *before* signing in, so the consent screen asks for it.

For Android (Codex, later): Clients → **Android** → package `uz.nexvara.app` + SHA-1 of the
release keystore. No file goes into Git.

## Not done yet

- Sync is implemented (src/nexvara/sync.py, docs/AGENT.md): shared folder and phone work
  without Google; the Drive transport is tested against a fake Drive only — real Drive is
  BLOCKED until the steps above are done by the user. Task history is not synced.
- Linking the Google account to paired phones: phones pair by QR today; Google is not needed.
