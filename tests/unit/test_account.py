"""Google login: the whole OAuth/OIDC flow against a fake Google on localhost.

The fake checks what real Google checks (PKCE verifier, redirect URI, client) and signs a
real RS256 ID token, so the code path is the production one; only the URLs differ.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

CLIENT = {"client_id": "123-abc.apps.googleusercontent.com", "client_secret": "GOCSPX-test"}


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeGoogle:
    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.codes: dict[str, dict] = {}
        self.revoked: list[str] = []
        self.refresh_ok = True
        self.sub = "1001"
        self.verified = True
        self.offline = False
        self.tamper = ""
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, data, code=200):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                if self.path == "/certs":
                    n = fake.key.public_key().public_numbers()
                    self._json({"keys": [{"kty": "RSA", "kid": "k1", "alg": "RS256",
                                          "n": b64(n.n.to_bytes(256, "big")),
                                          "e": b64(n.e.to_bytes(3, "big"))}]})  # fmt: skip
                else:
                    self._json({}, 404)

            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("Content-Length") or 0)
                form = {
                    k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode()).items()
                }
                if self.path == "/revoke":
                    fake.revoked.append(form.get("token", ""))
                    self._json({})
                    return
                if form.get("grant_type") == "refresh_token":
                    if not fake.refresh_ok:
                        self._json({"error": "invalid_grant"}, 400)
                    else:
                        now = int(time.time())
                        self._json(
                            {
                                "access_token": "at-2",
                                "expires_in": 3599,
                                "id_token": fake.sign(
                                    {
                                        "iss": "https://accounts.google.com",
                                        "aud": CLIENT["client_id"],
                                        "sub": fake.sub,
                                        "iat": now,
                                        "exp": now + 3600,
                                    }
                                ),
                            }
                        )
                    return
                req = fake.codes.pop(form.get("code", ""), None)
                challenge = b64(hashlib.sha256(form.get("code_verifier", "").encode()).digest())
                if (req is None or challenge != req["code_challenge"]
                        or form.get("redirect_uri") != req["redirect_uri"]
                        or form.get("client_secret") != CLIENT["client_secret"]):  # fmt: skip
                    self._json({"error": "invalid_grant"}, 400)
                    return
                claims = {"iss": "https://accounts.google.com", "aud": req["client_id"],
                          "sub": fake.sub, "email": "ali@gmail.com",
                          "email_verified": fake.verified, "name": "Ali Valiyev",
                          "nonce": req["nonce"],
                          "iat": int(time.time()), "exp": int(time.time()) + 3600}  # fmt: skip
                if fake.tamper == "aud":
                    claims["aud"] = "boshqa.apps.googleusercontent.com"
                self._json({"access_token": "at-1", "refresh_token": "rt-1",
                            "id_token": fake.sign(claims), "expires_in": 3599,
                            "scope": req["scope"]})  # fmt: skip

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def sign(self, claims: dict) -> str:
        head = b64(json.dumps({"alg": "RS256", "kid": "k1", "typ": "JWT"}).encode())
        body = b64(json.dumps(claims).encode())
        sig = self.key.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
        if self.tamper == "sig":
            sig = bytes([sig[0] ^ 1]) + sig[1:]
        return f"{head}.{body}.{b64(sig)}"

    def browser(self, deny=False, bad_state=False):
        """Plays the user's browser: signs in and follows the redirect."""

        def open_url(url):
            q = {
                k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()
            }
            assert q["code_challenge_method"] == "S256" and q["scope"].startswith(
                "openid email profile"
            )
            self.last_query = q
            assert q["redirect_uri"].startswith("http://127.0.0.1:")
            code = "c-" + q["state"][:6]
            self.codes[code] = q
            params = (
                {"error": "access_denied"}
                if deny
                else {"code": code, "state": "x" if bad_state else q["state"]}
            )

            def go():
                urllib.request.urlopen(q["redirect_uri"] + "?" + urllib.parse.urlencode(params),
                                       timeout=10).read()  # fmt: skip

            threading.Thread(target=go, daemon=True).start()

        return open_url


@pytest.fixture
def google(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path))
    fake = FakeGoogle()
    from nexvara.account import Endpoints, GoogleAccount
    from nexvara.ai.keys import MemoryKeyStore

    ep = Endpoints(auth=fake.base + "/auth", token=fake.base + "/token",
                   revoke=fake.base + "/revoke", jwks=fake.base + "/certs")  # fmt: skip
    keys = MemoryKeyStore()

    def make(**kw):
        return GoogleAccount(CLIENT, endpoints=ep, keys=keys, profile_path=tmp_path / "acc.json",
                             open_browser=fake.browser(**kw))  # fmt: skip

    yield fake, make, keys
    fake.httpd.shutdown()


def test_login_refresh_logout(google):
    fake, make, keys = google
    acc = make()
    prof = acc.login(timeout=10)
    assert prof["email"] == "ali@gmail.com" and prof["name"] == "Ali Valiyev"
    assert acc.confirm_owner(True)["owner"] is True
    st = acc.status()
    assert st["signed_in"] and st["profile"]["sub"] == "1001"
    assert keys.load("refresh_token") == "rt-1"
    assert "rt-1" not in acc.profile_path.read_text()  # secrets only in Credential Manager
    assert acc.refresh()["access_token"] == "at-2"
    out = acc.logout()
    assert out["revoked"] and fake.revoked == ["rt-1"] and not out["signed_in"]
    assert keys.load("refresh_token") is None and not acc.profile_path.exists()


def test_expired_session_signs_out(google):
    fake, make, keys = google
    acc = make()
    acc.login(timeout=10)
    acc.confirm_owner(True)
    fake.refresh_ok = False
    from nexvara.account import AuthError

    with pytest.raises(AuthError, match="tugagan"):
        acc.refresh()
    assert not acc.status()["signed_in"]


@pytest.mark.parametrize("case,match", [
    ({"deny": True}, "bekor"),
    ({"bad_state": True}, "state"),
])  # fmt: skip
def test_login_rejections(google, case, match):
    fake, make, keys = google
    from nexvara.account import AuthError

    with pytest.raises(AuthError, match=match):
        make(**case).login(timeout=10)
    assert keys.load("refresh_token") is None


@pytest.mark.parametrize("tamper,match", [("sig", "imzo"), ("aud", "boshqa ilova")])
def test_bad_id_token_is_rejected(google, tamper, match):
    fake, make, keys = google
    fake.tamper = tamper
    from nexvara.account import AuthError

    with pytest.raises(AuthError, match=match):
        make().login(timeout=10)
    assert keys.load("refresh_token") is None


def test_async_login_for_ui(google):
    fake, make, keys = google
    acc = make()
    assert acc.login_async()["login"]["state"] == "waiting"
    for _ in range(100):
        if acc.status()["login"]["state"] != "waiting":
            break
        time.sleep(0.1)
    assert acc.status()["login"] == {"state": "confirm_owner", "email": "ali@gmail.com"}
    assert acc.status()["pending_owner"]["email"] == "ali@gmail.com"
    assert not acc.status()["signed_in"]  # nothing stored before the user confirms
    acc.confirm_owner(True)
    assert acc.status()["login"] == {"state": "done", "email": "ali@gmail.com"}


def test_not_configured_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path))
    from nexvara.account import GoogleAccount, load_client
    from nexvara.ai.keys import MemoryKeyStore
    from nexvara.app.api import Api

    acc = GoogleAccount(keys=MemoryKeyStore())
    st = acc.status()
    assert st["configured"] is False and "google_client.json" in st["blocked"]
    api = Api(overrides={"google_account": acc})
    assert api.account_login()["ok"] is False
    (tmp_path / "google_client.json").write_text(json.dumps({"installed": CLIENT}))
    assert load_client() == CLIENT and acc.status()["configured"] is True
    (tmp_path / "google_client.json").write_text('{"installed": {"client_id": "x"}}')
    assert load_client() is None


def test_drive_scope_for_sync(google):
    fake, make, keys = google
    from nexvara.account import DRIVE_SCOPE

    acc = make()
    prof = acc.login(timeout=10, drive=True)
    acc.confirm_owner(True)
    assert DRIVE_SCOPE in fake.last_query["scope"].split()
    assert fake.last_query["include_granted_scopes"] == "true"
    assert DRIVE_SCOPE in prof["scopes"]


def test_import_client_json(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.account import AuthError, GoogleAccount, import_client
    from nexvara.ai.keys import MemoryKeyStore

    web = tmp_path / "web.json"
    web.write_text(json.dumps({"web": CLIENT}))
    with pytest.raises(AuthError, match="Desktop app"):
        import_client(web)
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    with pytest.raises(AuthError, match="client_id"):
        import_client(bad)
    good = tmp_path / "client_secret_123.json"
    good.write_text(json.dumps({"installed": {**CLIENT, "project_id": "nexvara-1"}}))
    assert import_client(good)["project_id"] == "nexvara-1"
    import_client(good)  # again: the previous file is kept as .bak
    assert (tmp_path / "data" / "google_client.json.bak").is_file()
    st = GoogleAccount(keys=MemoryKeyStore()).status()
    assert st["configured"] and not st["signed_in"]  # imported, but nobody logged in
    assert "…" in st["client_id"] and st["client_id"].endswith(".apps.googleusercontent.com")


# ---------------- owner-only (fake Google) ----------------


def test_first_login_needs_owner_confirmation(google):
    fake, make, keys = google
    acc = make()
    acc.login(timeout=10)
    assert keys.load("refresh_token") is None and not acc.profile_path.exists()
    out = acc.confirm_owner(False)  # "Yo‘q, bu mening hisobim emas"
    assert out["owner"] is False and not out["owner_set"] and "rt-1" in fake.revoked
    assert keys.load("refresh_token") is None
    acc.login(timeout=10)
    out = acc.confirm_owner(True)
    assert out["signed_in"] and out["owner_set"] and keys.load("owner_sub") == "1001"
    assert acc.confirm_owner(True)["ok"] is False  # nothing pending any more


def test_other_account_is_refused_and_its_tokens_revoked(google):
    fake, make, keys = google
    from nexvara.account import AuthError

    acc = make()
    acc.login(timeout=10)
    acc.confirm_owner(True)
    acc.logout()
    fake.revoked.clear()
    fake.sub = "2002"  # someone else's Google account
    with pytest.raises(AuthError, match="faqat egasining"):
        acc.login(timeout=10)
    assert fake.revoked == ["rt-1"] and keys.load("refresh_token") is None
    assert not acc.status()["signed_in"] and keys.load("owner_sub") == "1001"
    fake.sub = "1001"
    acc.login(timeout=10)  # the owner again: no confirmation needed
    assert acc.status()["signed_in"]


def test_unverified_email_is_refused(google):
    fake, make, keys = google
    from nexvara.account import AuthError

    fake.verified = False
    with pytest.raises(AuthError, match="tasdiqlanmagan"):
        make().login(timeout=10)
    assert keys.load("refresh_token") is None and keys.load("owner_sub") is None


def test_session_resume_offline_and_expired(google):
    fake, make, keys = google
    acc = make()
    acc.login(timeout=10)
    acc.confirm_owner(True)
    again = make()  # the app restarted
    assert again.resume()["session"] == "active" and again.status()["signed_in"]
    from nexvara.account import Endpoints

    offline = make()
    offline.ep = Endpoints(auth="", token="http://127.0.0.1:9/token", revoke="", jwks="")
    st = offline.resume()  # no network: still signed in, checked again next time
    assert st["signed_in"] and st["session"] == "offline"
    fake.refresh_ok = False  # the grant was revoked in the Google account settings
    st = make().resume()
    assert not st["signed_in"] and st["owner_set"]  # signed out; the owner is remembered


def test_refreshed_token_of_another_account_signs_out(google):
    fake, make, keys = google
    from nexvara.account import AuthError

    acc = make()
    acc.login(timeout=10)
    acc.confirm_owner(True)
    fake.sub = "3003"
    with pytest.raises(AuthError, match="boshqa Google"):
        acc.refresh()
    assert not acc.status()["signed_in"]


def test_forget_owner_only_when_signed_out(google):
    fake, make, keys = google
    acc = make()
    acc.login(timeout=10)
    acc.confirm_owner(True)
    assert acc.forget_owner()["ok"] is False
    acc.logout()
    assert acc.forget_owner()["owner_set"] is False


def test_api_methods(google, monkeypatch):
    fake, make, keys = google
    from nexvara.app.api import Api

    api = Api(overrides={"google_account": make()})
    api._google().login(timeout=10)
    assert api.account_status()["pending_owner"]
    assert api.account_confirm_owner(True)["signed_in"]
    assert api.account_resume()["session"] == "active"
