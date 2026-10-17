"""Phone API v1 (the Android contract): real HTTPS on localhost, throwaway data folder."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.remote import DeviceStore

    out = tmp_path / "natija.pdf"
    out.write_bytes(b"%PDF-1.4 natija")
    api = Api(TaskRunner(), overrides={
        "device_store": DeviceStore(tmp_path / "app.db"), "remote_port": 0,
        "excel_demo": lambda t: {"path": str(out)},
    })  # fmt: skip
    assert api.devices_start()["ok"]
    srv = api._server()
    srv.host_url = f"https://127.0.0.1:{srv.port}"
    yield api, srv, out
    api.devices_stop()


def pinned_context(srv) -> ssl.SSLContext:
    """What the Android app does: trust only the certificate whose SHA-256 was in the QR."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def call(srv, method, path, data=None, token=None, headers=None, raw=None):
    h = {"X-Nexvara-Protocol": "1", **(headers or {})}
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    if method == "POST" and body is None:
        body = b""
    r = urllib.request.Request(srv.host_url + path, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, context=pinned_context(srv), timeout=40) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def j(resp):
    return json.loads(resp[1])


def pair(srv, install_id="inst-1"):
    code = srv.status()["code"]
    r = call(srv, "POST", "/api/v1/pair", {"code": code, "device_name": "Pixel",
             "platform": "android", "app_version": "1.0.0", "install_id": install_id})  # fmt: skip
    assert r[0] == 200, r[1]
    return j(r)["data"]["token"]


def test_info_and_envelope(env):
    api, srv, _ = env
    st, body, _ = call(srv, "GET", "/api/v1/info")
    data = json.loads(body)
    assert st == 200 and data["v"] == 1 and data["ok"] is True
    assert data["data"]["protocol"] == 1 and data["data"]["pairing_open"] is True
    st, body, _ = call(srv, "GET", "/api/v1/tasks")
    err = json.loads(body)
    assert st == 401 and err["ok"] is False and err["error"]["code"] == "AUTH_REQUIRED"
    assert call(srv, "GET", "/api/v1/yoq", token="x")[0] == 404
    old = call(srv, "GET", "/api/v1/info", headers={"X-Nexvara-Protocol": "0"})
    assert old[0] == 426 and j(old)["error"]["code"] == "UNSUPPORTED_PROTOCOL"


def test_qr_carries_certificate_fingerprint(env):
    api, srv, _ = env
    link = srv.pair_link()
    fp = re.search(r"fp=([0-9a-f]{64})", link).group(1)
    assert re.search(r"#p=\d{6}&sid=[0-9a-f]{16}", link)
    # The fingerprint is the certificate the server really presents.
    with socket.create_connection(("127.0.0.1", srv.port), timeout=5) as raw:
        with pinned_context(srv).wrap_socket(raw) as tls:
            der = tls.getpeercert(binary_form=True)
    assert hashlib.sha256(der).hexdigest() == fp


def test_pair_errors_have_codes(env):
    api, srv, _ = env
    code = srv.status()["code"]
    bad = "000000" if code != "000000" else "111111"
    r = call(srv, "POST", "/api/v1/pair", {"code": bad})
    assert r[0] == 403 and j(r)["error"]["code"] == "PAIRING_CODE_INVALID"
    pair(srv)
    r = call(srv, "POST", "/api/v1/pair", {"code": code})
    assert j(r)["error"]["code"] == "PAIRING_CODE_EXPIRED"  # one-time
    srv.new_code()
    for _ in range(5):
        call(srv, "POST", "/api/v1/pair", {"code": "x"})
    r = call(srv, "POST", "/api/v1/pair", {"code": srv.code})
    assert j(r)["error"]["code"] in ("PAIRING_LOCKED", "RATE_LIMITED")


def test_same_install_replaces_old_entry(env):
    api, srv, _ = env
    t1 = pair(srv, "inst-A")
    srv.new_code()
    t2 = pair(srv, "inst-A")
    devices = api.devices_status()["devices"]
    assert len(devices) == 1 and devices[0]["platform"] == "android"
    assert call(srv, "GET", "/api/v1/session", token=t1)[0] == 401
    assert call(srv, "GET", "/api/v1/session", token=t2)[0] == 200


def test_session_rotate_logout_expiry(env):
    api, srv, _ = env
    token = pair(srv)
    s = j(call(srv, "GET", "/api/v1/session", token=token))["data"]
    assert s["device_name"] == "Pixel" and s["rotate_recommended"] is False
    new = j(call(srv, "POST", "/api/v1/session/rotate", token=token))["data"]["token"]
    assert call(srv, "GET", "/api/v1/session", token=token)[0] == 200  # grace period
    assert call(srv, "GET", "/api/v1/session", token=new)[0] == 200
    assert call(srv, "GET", "/api/v1/session", token=token)[0] == 401
    with srv.store._db() as db:
        db.execute("UPDATE devices SET token_created = ?", (time.time() - 31 * 86400,))
    r = call(srv, "GET", "/api/v1/session", token=new)
    assert r[0] == 401 and j(r)["error"]["code"] == "TOKEN_EXPIRED"
    with srv.store._db() as db:
        db.execute("UPDATE devices SET token_created = ?", (time.time(),))
    assert j(call(srv, "POST", "/api/v1/session/logout", token=new))["data"]["logged_out"]
    assert call(srv, "GET", "/api/v1/session", token=new)[0] == 401
    assert api.devices_status()["devices"] == []


def test_chat_idempotent_and_task_flow(env):
    api, srv, out = env
    token = pair(srv)
    calls = []
    real = api.chat
    api.chat = lambda text: calls.append(text) or real(text)
    h = {"X-Request-Id": "r-1", "Content-Type": "application/json"}
    a = call(srv, "POST", "/api/v1/chat", {"text": "salom"}, token, h)
    b = call(srv, "POST", "/api/v1/chat", {"text": "salom"}, token, h)
    assert a[0] == b[0] == 200 and a[1] == b[1] and calls == ["salom"]
    reply = j(a)["data"]
    assert set(reply) >= {"reply", "confirm", "task"} and reply["reply"]
    assert call(srv, "POST", "/api/v1/chat", {"text": " "}, token)[0] == 400

    etag = j(call(srv, "GET", "/api/v1/tasks", token=token))["data"]["etag"]
    result = {}

    def watch():
        result["r"] = j(call(srv, "GET", f"/api/v1/tasks/watch?etag={etag}&wait=20", token=token))

    th = threading.Thread(target=watch)
    th.start()
    time.sleep(0.6)
    snap = api.run_excel_demo()
    th.join(25)
    assert result["r"]["data"]["changed"] is True
    assert api._runner.get(snap["id"]).wait(5)
    t = j(call(srv, "GET", f"/api/v1/tasks/{snap['id']}", token=token))["data"]
    assert t["status"] == "succeeded" and t["files"] == [str(out)]
    assert call(srv, "GET", "/api/v1/tasks/ffffffffffff", token=token)[0] == 404
    c = j(call(srv, "POST", f"/api/v1/tasks/{snap['id']}/cancel", token=token))["data"]
    assert c["cancelled"] is False  # already finished

    r = call(srv, "GET", f"/api/v1/files?path={quote(str(out))}", token=token)
    assert r[0] == 200 and r[1] == b"%PDF-1.4 natija"
    assert r[2]["X-Content-SHA256"] == hashlib.sha256(r[1]).hexdigest()
    other = quote(str(out.parent / "boshqa.txt"))
    assert call(srv, "GET", f"/api/v1/files?path={other}", token=token)[0] == 404


def test_upload_checks_integrity(env):
    api, srv, _ = env
    token = pair(srv)
    body = b"rasm"
    h = {"X-Filename": quote("../../Rasm 1.jpg"), "X-Content-SHA256": "00" * 32}
    r = call(srv, "POST", "/api/v1/files", token=token, raw=body, headers=h)
    assert r[0] == 400 and "SHA-256" in j(r)["error"]["message"]
    h["X-Content-SHA256"] = hashlib.sha256(body).hexdigest()
    r = call(srv, "POST", "/api/v1/files", token=token, raw=body, headers=h)
    f = j(r)["data"]
    assert r[0] == 200 and f["name"] == "Rasm 1.jpg" and f["size"] == 4
    assert Path(f["path"]).parent.name == "Telefondan"  # no path traversal
    assert api.get_context_file() == f["path"]


def test_rate_limit(env):
    api, srv, _ = env
    from nexvara.remote import RateLimiter

    srv.limiter = RateLimiter(3)
    codes = [call(srv, "GET", "/api/v1/info")[0] for _ in range(5)]
    assert codes[:3] == [200] * 3 and codes[3] == 429
    r = call(srv, "GET", "/api/v1/info")
    assert j(r)["error"]["code"] == "RATE_LIMITED" and r[2]["Retry-After"] == "30"


def test_old_database_is_migrated(tmp_path):
    import sqlite3

    db = tmp_path / "old.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                  "token_hash TEXT NOT NULL UNIQUE, created REAL NOT NULL, token_created REAL "
                  "NOT NULL, last_seen REAL, last_ip TEXT NOT NULL DEFAULT '')")  # fmt: skip
        c.execute("INSERT INTO devices (name, token_hash, created, token_created) "
                  "VALUES ('Eski', 'h', 1, ?)", (time.time(),))  # fmt: skip
    from nexvara.remote import DeviceStore

    store = DeviceStore(db)
    assert store.all()[0]["platform"] == "browser"


def test_openapi_matches_routes():
    """docs/api/openapi.yaml documents exactly the routes the server serves."""
    from nexvara.protocol import ERRORS
    from nexvara.remote_v1 import ROUTES

    text = (ROOT / "docs" / "api" / "openapi.yaml").read_text(encoding="utf-8")
    documented = set()
    path = None
    for line in text.splitlines():
        m = re.match(r"^  (/api/v1/\S+):\s*$", line)
        if m:
            path = m.group(1)
            continue
        m = re.match(r"^    (get|post):\s*$", line)
        if m and path:
            documented.add((m.group(1).upper(), path))
    assert documented == {(m, p) for m, p, _a in ROUTES}
    for code in ERRORS:
        assert code in text, code
