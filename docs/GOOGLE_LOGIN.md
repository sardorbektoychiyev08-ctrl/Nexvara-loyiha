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
4. Download JSON and save it as `D:\NEXVARA\google_client.json` (never into the project folder).
5. Settings → Google hisobi → "Google bilan kirish".

For Android (Codex, later): Clients → **Android** → package `uz.nexvara.app` + SHA-1 of the
release keystore. No file goes into Git.

## Not done yet

- Profile / language / Teach / history sync between devices: needs a storage place (for
  example Google Drive `appDataFolder` with the `drive.appdata` scope). TODO.
- Linking the Google account to paired phones: phones pair by QR today; Google is not needed.
