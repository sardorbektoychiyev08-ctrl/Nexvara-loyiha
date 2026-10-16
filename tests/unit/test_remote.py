"""Phone access server: real HTTPS on localhost with a throwaway data folder."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request

import pytest


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.remote import DeviceStore

    out = tmp_path / "natija.pdf"
    out.write_bytes(b"%PDF-1.4 natija")
    runner = TaskRunner()
    api = Api(runner, overrides={
        "device_store": DeviceStore(tmp_path / "app.db"), "remote_port": 0,
        "excel_demo": lambda t: {"path": str(out)},
    })  # fmt: skip
    r = api.devices_start()
    assert r["ok"], r
    srv = api._server()
    srv.host_url = f"https://127.0.0.1:{srv.port}"
    yield api, srv, out
    api.devices_stop()


CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE  # the PC's own certificate (the phone accepts it once)


def req(srv, path, data=None, token=None, headers=None, raw=None):
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    if data is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(srv.host_url + path, data=body, headers=h,
                               method="POST" if body is not None else "GET")  # fmt: skip
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def pair(srv):
    code = srv.status()["code"]
    st, body = req(srv, "/api/pair", {"code": code, "name": "Sinov telefoni"})
    assert st == 200, body
    return json.loads(body)["token"]


def test_page_and_auth(env):
    api, srv, _ = env
    st, body = req(srv, "/")
    assert st == 200 and b"NEXVARA" in body
    assert req(srv, "/api/tasks")[0] == 401
    assert req(srv, "/api/tasks", token="yolgon")[0] == 401
    status = api.devices_status()
    assert status["running"] and len(status["code"]) == 6 and "<svg" in status["qr_svg"]
    assert status["url"].startswith("https://")


def test_pairing_is_one_time_and_locks(env):
    api, srv, _ = env
    code = srv.status()["code"]
    assert req(srv, "/api/pair", {"code": "000000" if code != "000000" else "111111"})[0] == 403
    token = pair(srv)
    assert req(srv, "/api/pair", {"code": code})[0] == 403  # used once
    api.devices_new_code()
    for _ in range(5):
        req(srv, "/api/pair", {"code": "x"})
    assert srv.status()["locked"]
    st, body = req(srv, "/api/pair", {"code": srv.code})
    assert st == 403 and "Ko‘p" in json.loads(body)["error"]
    assert req(srv, "/api/hello", token=token)[0] == 200
    assert api.devices_status()["devices"][0]["name"] == "Sinov telefoni"


def test_chat_is_idempotent(env):
    api, srv, _ = env
    token = pair(srv)
    calls = []
    real = api.chat
    api.chat = lambda text: calls.append(text) or real(text)
    h = {"X-Request-Id": "abc123"}
    s1, b1 = req(srv, "/api/chat", {"text": "salom"}, token, h)
    s2, b2 = req(srv, "/api/chat", {"text": "salom"}, token, h)
    assert s1 == s2 == 200 and b1 == b2 and calls == ["salom"]


def test_tasks_files_upload(env):
    api, srv, out = env
    token = pair(srv)
    snap = api.run_excel_demo()
    assert api._runner.get(snap["id"]).wait(5)
    st, body = req(srv, "/api/tasks", token=token)
    tasks = json.loads(body)
    assert tasks[0]["files"] == [str(out)] and tasks[0]["status"] == "succeeded"
    from urllib.parse import quote

    st, body = req(srv, f"/api/file?path={quote(str(out))}", token=token)
    assert st == 200 and body == b"%PDF-1.4 natija"
    st, _ = req(srv, f"/api/file?path={quote(str(out.parent / 'boshqa.txt'))}", token=token)
    assert st == 404  # only files NEXVARA produced
    st, body = req(srv, "/api/upload", token=token, raw=b"salom",
                   headers={"X-Filename": quote("Hisobot yanvar.xlsx")})  # fmt: skip
    saved = json.loads(body)["path"]
    assert saved.endswith("Telefondan\\Hisobot yanvar.xlsx") or saved.endswith(
        "Telefondan/Hisobot yanvar.xlsx"
    )
    assert api.get_context_file() == saved


def test_revoke_and_rotate(env):
    api, srv, _ = env
    token = pair(srv)
    dev = api.devices_status()["devices"][0]
    with srv.store._db() as db:  # a token older than a week
        db.execute("UPDATE devices SET token_created = ?", (time.time() - 8 * 86400,))
    st, body = req(srv, "/api/hello", token=token)
    new = json.loads(body)["new_token"]
    assert req(srv, "/api/hello", token=token)[0] == 401  # the old one stops working
    assert req(srv, "/api/hello", token=new)[0] == 200
    api.devices_revoke(dev["id"])
    assert req(srv, "/api/hello", token=new)[0] == 401


def test_plain_tests_have_no_server():
    from nexvara.app.api import Api

    st = Api().devices_status()
    assert st["available"] is False and Api().devices_start()["ok"] is False
