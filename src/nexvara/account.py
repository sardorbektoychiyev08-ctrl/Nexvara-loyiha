"""Google login for the Windows app: OAuth 2.0 for installed apps + OpenID Connect.

Flow (RFC 8252 + RFC 7636): a one-shot HTTP listener on 127.0.0.1 (random port) is the
redirect URI; the system browser opens Google's sign-in page with a PKCE S256 challenge,
`state` and `nonce`; the code comes back to the listener, is exchanged for tokens, and the
ID token's signature (Google JWKS, RS256), issuer, audience, expiry and nonce are verified.

Where things live:
- client configuration: D:\\NEXVARA\\google_client.json, the "Desktop app" OAuth client file
  downloaded from Google Cloud Console (never in Git). Missing -> status "blocked";
- the refresh token: Windows Credential Manager, NEXVARA/google/refresh_token;
- the profile (email, name, picture; nothing secret): D:\\NEXVARA\\account.json.
- owner-only: the first account that signs in must be confirmed by the user in the app; its
  stable Google `sub` is then stored (Credential Manager, NEXVARA/google/owner_sub) and any
  other account is refused (its tokens are revoked at once, nothing is saved). The email is
  never used for this: it can change, `sub` cannot.
Login is optional: everything else in NEXVARA works without it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.ai.keys import KeyStore

SCOPES = "openid email profile"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.appdata"  # sync files, hidden app folder
CLIENT_FILE = "google_client.json"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")
LOGIN_TIMEOUT = 300.0


@dataclass
class Endpoints:
    auth: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token: str = "https://oauth2.googleapis.com/token"
    revoke: str = "https://oauth2.googleapis.com/revoke"
    jwks: str = "https://www.googleapis.com/oauth2/v3/certs"


class AuthError(Exception):
    """Shown to the user as is (Uzbek)."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def pkce_pair() -> tuple[str, str]:
    """(verifier, S256 challenge)."""
    verifier = _b64url(secrets.token_bytes(48))  # 64 chars, within 43..128
    return verifier, _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def check_client_json(raw: Any) -> dict[str, str]:
    """The Google Cloud client file must be a "Desktop app" client (loopback redirect)."""
    if not isinstance(raw, dict):
        raise AuthError("Bu Google client JSON fayli emas")
    if "web" in raw and "installed" not in raw:
        raise AuthError("Bu «Web application» client. Google Cloud → Clients → Create client → "
                        "turi «Desktop app» bo‘lsin va o‘sha JSON faylni tanlang.")  # fmt: skip
    c = raw.get("installed") or {}
    cid = str(c.get("client_id", ""))
    if not cid.endswith(".apps.googleusercontent.com"):
        raise AuthError(
            "JSON ichida client_id topilmadi (Google Cloud’dan yuklangan faylni tanlang)"
        )
    return {"client_id": cid, "client_secret": str(c.get("client_secret", "")),
            "project_id": str(c.get("project_id", ""))}  # fmt: skip


def import_client(src: Path, dest: Path | None = None) -> dict[str, str]:
    """Validate the downloaded JSON and copy it to D:\\NEXVARA (the old one is kept as .bak)."""
    try:
        raw = json.loads(Path(src).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise AuthError(f"Faylni o‘qib bo‘lmadi: {e}") from e
    info = check_client_json(raw)
    dest = dest or (config.data_dir() / CLIENT_FILE)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.replace(dest.with_suffix(".json.bak"))
    dest.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return info


def load_client(path: Path | None = None) -> dict[str, str] | None:
    """client_id/client_secret from the Google Cloud "Desktop app" JSON, or None."""
    p = path or (config.data_dir() / CLIENT_FILE)
    try:
        c = check_client_json(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, ValueError, AuthError):
        return None
    # For installed apps Google's "client secret" is not confidential (RFC 8252 §8.5), but
    # we still keep the file outside the repo.
    return {"client_id": c["client_id"], "client_secret": c["client_secret"]}


def verify_id_token(id_token: str, jwks: dict[str, Any], client_id: str, nonce: str,
                    now: float | None = None) -> dict[str, Any]:  # fmt: skip
    """Check an RS256 ID token against the JWKS; returns its claims."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    try:
        head_b, body_b, sig_b = id_token.split(".")
        header = json.loads(_unb64url(head_b))
        claims = json.loads(_unb64url(body_b))
    except ValueError as e:
        raise AuthError("Google javobi buzilgan (ID token)") from e
    if header.get("alg") != "RS256":
        raise AuthError("ID token algoritmi kutilgan emas")
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid")), None)
    if key is None or key.get("kty") != "RSA":
        raise AuthError("ID token kaliti topilmadi")
    pub = rsa.RSAPublicNumbers(
        int.from_bytes(_unb64url(key["e"]), "big"), int.from_bytes(_unb64url(key["n"]), "big")
    ).public_key()
    try:
        pub.verify(_unb64url(sig_b), f"{head_b}.{body_b}".encode("ascii"),
                   padding.PKCS1v15(), hashes.SHA256())  # fmt: skip
    except InvalidSignature as e:
        raise AuthError("ID token imzosi noto‘g‘ri") from e
    now = time.time() if now is None else now
    aud = claims.get("aud")
    if claims.get("iss") not in ISSUERS:
        raise AuthError("ID token boshqa tashkilotdan")
    if aud != client_id and not (isinstance(aud, list) and client_id in aud):
        raise AuthError("ID token boshqa ilova uchun berilgan")
    if float(claims.get("exp", 0)) < now - 60:
        raise AuthError("ID token muddati o‘tgan")
    if nonce and not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise AuthError("ID token nonce mos emas")
    return claims


class _Callback(BaseHTTPRequestHandler):
    result: dict[str, str]
    done: threading.Event

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if not ("code" in q or "error" in q):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.result.update({k: v[0] for k, v in q.items()})
        ok = "code" in q
        text = ("Kirish muvaffaqiyatli. Bu oynani yopib, NEXVARA'ga qayting." if ok
                else "Kirish bekor qilindi. NEXVARA'ga qayting.")  # fmt: skip
        body = (f"<!doctype html><meta charset='utf-8'><title>NEXVARA</title>"
                f"<body style='font-family:sans-serif;padding:40px'><h2>NEXVARA</h2>"
                f"<p>{text}</p></body>").encode()  # fmt: skip
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.done.set()


class GoogleAccount:
    def __init__(self, client: dict[str, str] | None = None, *, endpoints: Endpoints | None = None,
                 keys: KeyStore | None = None, profile_path: Path | None = None,
                 open_browser: Callable[[str], Any] | None = None) -> None:  # fmt: skip
        self._client = client
        self.ep = endpoints or Endpoints()
        self.keys = keys or KeyStore("NEXVARA/google/")
        self.profile_path = profile_path or (config.data_dir() / "account.json")
        self.open_browser = open_browser or webbrowser.open
        self._lock = threading.Lock()
        self._login: dict[str, Any] = {"state": "idle"}
        self._id_expires = 0.0
        self._pending: dict[str, Any] | None = None  # first login, waiting for "this is me"
        self.session = "none"  # none | active | offline (refresh failed for lack of network)

    @property
    def client(self) -> dict[str, str] | None:
        return self._client if self._client is not None else load_client()

    # ----- state -----
    def profile(self) -> dict[str, Any] | None:
        try:
            p = json.loads(self.profile_path.read_text(encoding="utf-8"))
            return p if isinstance(p, dict) and p.get("sub") else None
        except (OSError, ValueError):
            return None

    def status(self) -> dict[str, Any]:
        prof = self.profile()
        signed_in = bool(prof) and bool(self.keys.load("refresh_token"))
        out: dict[str, Any] = {
            "configured": self.client is not None,
            "signed_in": signed_in,
            "profile": prof if signed_in else None,
            "login": dict(self._login),
            "client_file": str(config.data_dir() / CLIENT_FILE),
            "owner_set": bool(self.keys.load("owner_sub")),
            "session": self.session if signed_in else "none",
        }
        if self._pending is not None:
            p = self._pending["profile"]
            out["pending_owner"] = {"email": p["email"], "name": p["name"]}
        if out["configured"]:
            cid = self.client["client_id"]
            out["client_id"] = cid[:8] + "…" + cid[cid.find(".apps") :]
        if not out["configured"]:
            out["blocked"] = (
                "Google Cloud loyihasi kerak: OAuth client (Desktop app) yarating va JSON "
                f"faylini {out['client_file']} ga qo‘ying. Ko‘rsatma: docs/GOOGLE_LOGIN.md"
            )
        return out

    # ----- HTTP helpers -----
    def _post(self, url: str, form: dict[str, str]) -> dict[str, Any]:
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(form).encode(), method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read() or b"{}")
            except ValueError:
                err = {}
            err.setdefault("error", f"http_{e.code}")
            return err
        except (urllib.error.URLError, TimeoutError) as e:
            raise AuthError(f"Google bilan aloqa yo‘q: {e}") from e

    def _jwks(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(self.ep.jwks, timeout=20) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise AuthError(f"Google kalitlarini olib bo‘lmadi: {e}") from e

    # ----- login -----
    def login(self, timeout: float = LOGIN_TIMEOUT, drive: bool = False) -> dict[str, Any]:
        """Blocking: opens the browser, waits for the redirect, verifies, saves.
        `drive` also asks for the hidden app folder in Drive (used only for sync)."""
        client = self.client
        if client is None:
            raise AuthError(self.status()["blocked"])
        verifier, challenge = pkce_pair()
        state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        done = threading.Event()
        result: dict[str, str] = {}
        handler = type("Cb", (_Callback,), {"result": result, "done": done})
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        redirect = f"http://127.0.0.1:{httpd.server_address[1]}/"
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            url = self.ep.auth + "?" + urllib.parse.urlencode({
                "client_id": client["client_id"], "redirect_uri": redirect,
                "response_type": "code", "scope": SCOPES + (" " + DRIVE_SCOPE if drive else ""),
                "include_granted_scopes": "true", "state": state, "nonce": nonce,
                "code_challenge": challenge, "code_challenge_method": "S256",
                "access_type": "offline", "prompt": "consent select_account",
            })  # fmt: skip
            self._login = {"state": "waiting"}
            self.open_browser(url)
            if not done.wait(timeout):
                raise AuthError("Kirish vaqti tugadi (brauzerda Google'ga kirilmadi)")
        finally:
            httpd.shutdown()
            httpd.server_close()
        if "error" in result:
            raise AuthError("Google'ga kirish bekor qilindi" if result["error"] == "access_denied"
                            else f"Google xatosi: {result['error']}")  # fmt: skip
        if not secrets.compare_digest(result.get("state", ""), state):
            raise AuthError("Xavfsizlik tekshiruvi o‘tmadi (state mos emas)")
        tok = self._post(self.ep.token, {
            "code": result["code"], "client_id": client["client_id"],
            "client_secret": client["client_secret"], "redirect_uri": redirect,
            "grant_type": "authorization_code", "code_verifier": verifier,
        })  # fmt: skip
        if "id_token" not in tok:
            raise AuthError(f"Token olinmadi: {tok.get('error_description') or tok.get('error')}")
        claims = verify_id_token(tok["id_token"], self._jwks(), client["client_id"], nonce)
        if not claims.get("email_verified"):
            self._revoke(tok)
            raise AuthError("Bu Google hisobining emaili tasdiqlanmagan — kirish rad etildi.")
        owner = self.keys.load("owner_sub")
        if owner and not secrets.compare_digest(str(claims["sub"]), owner):
            self._revoke(tok)  # a stranger's tokens are not kept anywhere
            raise AuthError("Bu NEXVARA faqat egasining Google hisobi bilan ishlaydi. Boshqa "
                            "hisob bilan kirish rad etildi.")  # fmt: skip
        if not tok.get("refresh_token") and not (owner and self.keys.load("refresh_token")):
            self._revoke(tok)
            raise AuthError("Google refresh token bermadi; qayta urinib ko‘ring")
        self._id_expires = float(claims.get("exp", 0))
        prof = {
            "sub": claims["sub"],
            "email": claims.get("email", ""),
            "email_verified": bool(claims.get("email_verified")),
            "name": claims.get("name", ""),
            "picture": claims.get("picture", ""),
            "scopes": str(tok.get("scope") or SCOPES).split(),
            "signed_in_at": time.time(),
        }
        if not owner:
            # First login on this PC: nothing is stored until the user confirms in the app
            # that this is their own account (confirm_owner).
            self._pending = {"tok": tok, "profile": prof}
            return {**prof, "pending_owner": True}
        self._store(tok, prof)
        return prof

    def _store(self, tok: dict[str, Any], prof: dict[str, Any]) -> None:
        if tok.get("refresh_token"):
            self.keys.save("refresh_token", tok["refresh_token"])
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(json.dumps(prof, ensure_ascii=False, indent=2), "utf-8")
        self.session = "active"

    def _revoke(self, tok: dict[str, Any]) -> None:
        token = tok.get("refresh_token") or tok.get("access_token")
        if token:
            try:
                self._post(self.ep.revoke, {"token": token})
            except AuthError:
                pass  # offline: the tokens were never stored anyway

    def confirm_owner(self, yes: bool) -> dict[str, Any]:
        """The user's answer to "is this your account?" after the first login."""
        pending, self._pending = self._pending, None
        if pending is None:
            return {"ok": False, "error": "Tasdiqlanadigan kirish yo‘q", **self.status()}
        if not yes:
            self._revoke(pending["tok"])
            self._login = {"state": "idle"}
            return {"ok": True, "owner": False, **self.status()}
        self.keys.save("owner_sub", pending["profile"]["sub"])
        self._store(pending["tok"], pending["profile"])
        self._login = {"state": "done", "email": pending["profile"]["email"]}
        return {"ok": True, "owner": True, **self.status()}

    def forget_owner(self) -> dict[str, Any]:
        """Only while signed out (the UI asks first): the next login chooses a new owner."""
        if self.status()["signed_in"]:
            return {"ok": False, "error": "Avval Google hisobidan chiqing", **self.status()}
        self.keys.delete("owner_sub")
        return {"ok": True, **self.status()}

    def resume(self) -> dict[str, Any]:
        """At app start: check the saved session without opening a browser."""
        if not (self.profile() and self.keys.load("refresh_token")):
            self.session = "none"
            return self.status()
        try:
            self.refresh()
            self.session = "active"
        except AuthError as e:
            # A revoked/expired grant already signed us out inside refresh(); no network keeps
            # the session (it is checked again next time).
            self.session = "none" if not self.keys.load("refresh_token") else "offline"
            self._login = {"state": "error", "error": str(e)} if self.session == "none" else {
                "state": "idle"}  # fmt: skip
        return self.status()

    def login_async(self, drive: bool = False) -> dict[str, Any]:
        """For the UI: runs login() in the background; the page polls status()."""
        with self._lock:
            if self._login.get("state") == "waiting":
                return self.status()
            self._login = {"state": "waiting"}

        def run() -> None:
            try:
                prof = self.login(drive=drive)
                if prof.get("pending_owner"):
                    self._login = {"state": "confirm_owner", "email": prof["email"]}
                else:
                    self._login = {"state": "done", "email": prof["email"]}
            except AuthError as e:
                self._login = {"state": "error", "error": str(e)}
            except Exception as e:  # noqa: BLE001 - shown to the user, app keeps running
                self._login = {"state": "error", "error": f"{type(e).__name__}: {e}"}

        threading.Thread(target=run, name="google-login", daemon=True).start()
        return self.status()

    # ----- session -----
    def refresh(self) -> dict[str, Any]:
        """New access/ID token from the refresh token. A revoked or expired grant signs out."""
        client, rt = self.client, self.keys.load("refresh_token")
        if client is None or not rt:
            raise AuthError("Google hisobiga kirilmagan")
        tok = self._post(self.ep.token, {
            "client_id": client["client_id"], "client_secret": client["client_secret"],
            "refresh_token": rt, "grant_type": "refresh_token",
        })  # fmt: skip
        if tok.get("error") == "invalid_grant":
            self._forget()
            raise AuthError("Google sessiyasi tugagan. Qaytadan kiring.")
        if "access_token" not in tok:
            raise AuthError(f"Token yangilanmadi: {tok.get('error')}")
        owner = self.keys.load("owner_sub")
        if tok.get("id_token") and owner:
            claims = verify_id_token(tok["id_token"], self._jwks(), client["client_id"], "")
            if not secrets.compare_digest(str(claims.get("sub")), owner):
                self._forget()
                raise AuthError("Sessiya boshqa Google hisobiga tegishli — chiqildi.")
        self._id_expires = time.time() + float(tok.get("expires_in", 3600))
        return {"access_token": tok["access_token"], "expires_at": self._id_expires}

    def logout(self) -> dict[str, Any]:
        self.session = "none"
        """Revokes the grant at Google (best effort) and forgets everything locally."""
        rt = self.keys.load("refresh_token")
        revoked = False
        if rt:
            try:
                revoked = "error" not in self._post(self.ep.revoke, {"token": rt})
            except AuthError:
                revoked = False  # offline: still sign out locally
        self._forget()
        self._login = {"state": "idle"}
        return {"ok": True, "revoked": revoked, **self.status()}

    def _forget(self) -> None:
        self.keys.delete("refresh_token")
        try:
            self.profile_path.unlink()
        except OSError:
            pass
