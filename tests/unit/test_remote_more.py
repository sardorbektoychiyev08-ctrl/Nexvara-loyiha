"""Phone extras: PC screen, PC file search/open/share, other networks (Tailscale), drawing
edits and DXF. Real HTTPS on localhost; fake screen, fake AI; nothing is opened on the PC."""

from __future__ import annotations

import json
from urllib.parse import quote

import pytest
from test_drawing import SPEC, Draftsman
from test_remote_v1 import call, j, pair

from nexvara.ai.keys import MemoryKeyStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara import fileagent
    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.remote import DeviceStore

    docs = tmp_path / "Hujjatlar"
    docs.mkdir()
    (docs / "Oylik hisobot.xlsx").write_bytes(b"xlsx-data")
    (docs / "hisobot.exe").write_bytes(b"MZ")
    (docs / "hisobot kalit.pem").write_text("-----BEGIN PRIVATE KEY-----")
    monkeypatch.setattr(fileagent, "default_roots", lambda: [docs])
    api = Api(TaskRunner(), overrides={"device_store": DeviceStore(tmp_path / "app.db"),
                                       "remote_port": 0,
                                       "screen_capture": lambda: b"\xff\xd8fake-jpeg"})  # fmt: skip
    opened = []
    api.open_file = lambda p: opened.append(p) or True
    assert api.devices_start()["ok"]
    srv = api._server()
    srv.host_url = f"https://127.0.0.1:{srv.port}"
    yield api, srv, pair(srv), docs, opened
    api.devices_stop()


def post(srv, path, data, token):
    return call(srv, "POST", path, data, token, {"Content-Type": "application/json"})


def test_screen_view_shows_on_pc_and_can_be_turned_off(env):
    api, srv, token, _docs, _ = env
    r = call(srv, "GET", "/api/v1/screen", token=token)
    assert r[0] == 200 and r[1] == b"\xff\xd8fake-jpeg" and r[2]["Content-Type"] == "image/jpeg"
    assert {"kind": "phone_screen"} in api.ui_events()
    assert call(srv, "GET", "/api/v1/screen")[0] == 401  # never without the device token
    api.save_settings({"remote": {"screen_view": False}})
    assert call(srv, "GET", "/api/v1/screen", token=token)[0] == 404


def test_file_search_share_open(env):
    api, srv, token, docs, opened = env
    found = j(call(srv, "GET", "/api/v1/files/search?q=hisobot", token=token))["data"]["files"]
    names = {f["name"] for f in found}
    assert "Oylik hisobot.xlsx" in names and "hisobot kalit.pem" not in names  # keys never listed
    xlsx = str(docs / "Oylik hisobot.xlsx")
    # Not shared yet: not downloadable.
    assert call(srv, "GET", f"/api/v1/files?path={quote(xlsx)}", token=token)[0] == 404
    assert j(post(srv, "/api/v1/files/share", {"path": xlsx}, token))["data"]["size"] == 9
    r = call(srv, "GET", f"/api/v1/files?path={quote(xlsx)}", token=token)
    assert r[0] == 200 and r[1] == b"xlsx-data"
    assert j(post(srv, "/api/v1/files/open", {"path": xlsx}, token))["data"]["opened"]
    assert opened == [xlsx]
    r = post(srv, "/api/v1/files/open", {"path": str(docs / "hisobot.exe")}, token)
    assert r[0] == 400 and opened == [xlsx]  # a program is never started from the phone
    # A path that was never found by a search is refused.
    other = str(docs.parent / "data" / "settings.json")
    assert post(srv, "/api/v1/files/share", {"path": other}, token)[0] == 404


def test_other_networks_and_stable_certificate(env, tmp_path):
    from nexvara.remote import allowed_client, ensure_certificate

    _api, srv, token, _docs, _ = env
    for ok in ("192.168.1.5", "10.1.2.3", "172.20.0.4", "100.101.1.2", "127.0.0.1", "fd7a::1"):
        assert allowed_client(ok), ok
    for bad in ("8.8.8.8", "::ffff:1.1.1.1", "2a00:1450::1", "nonsense"):
        assert not allowed_client(bad), bad
    info = j(call(srv, "GET", "/api/v1/info"))["data"]
    assert info["port"] == srv.port and isinstance(info["addresses"], list)
    sess = j(call(srv, "GET", "/api/v1/session", token=token))["data"]
    assert "addresses" in sess
    # The certificate (and so the phone's pin) survives a change of network.
    folder = tmp_path / "cert"
    c1, _k = ensure_certificate(folder, "192.168.1.5")
    first = c1.read_bytes()
    c2, _k = ensure_certificate(folder, "10.0.0.7")
    assert c2.read_bytes() == first


def test_drawing_edit_and_dxf(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara import drawing
    from nexvara.ai.router import AiRouter, Ledger
    from nexvara.app.api import Api
    from nexvara.appdata import Settings

    dxf = drawing.to_dxf(SPEC)
    assert (
        dxf.lstrip().startswith("0\nSECTION")
        and "CIRCLE" in dxf
        and "ARC" in dxf
        and dxf.rstrip().endswith("EOF")
    )
    lines = dxf.splitlines()  # code/value pairs only: a text cannot inject DXF codes
    assert len(lines) % 2 == 0 and all(c.strip().isdigit() for c in lines[0::2])
    pro = Draftsman()
    r = AiRouter(Settings(tmp_path / "s.json"), MemoryKeyStore({"openai": "sk-test-openai-123456"}),
                 Ledger(tmp_path / "l.db"), factory=lambda n, k: pro)  # fmt: skip
    r.settings.update({"ai": {"enabled": True}})
    api = Api(overrides={"ai_router": r}, output_dir=tmp_path / "out")
    assert not api.chat("Oxirgi chizmani o‘zgartir: teshik 10 mm").get("confirm")  # none yet
    first = api.confirm_ai(api.chat("Flanes chizmasini chizib ber")["confirm"], True)
    t = api._runner.get(first["task"]["id"])
    assert t.wait(30) and t.status == "succeeded" and t.result["dxf"].endswith(".dxf")
    ask = api.chat("Oxirgi chizmani o‘zgartir: markaziy teshik 10 mm bo‘lsin")
    assert ask.get("confirm") and "o‘zgartiraman" in ask["reply"]
    done = api.confirm_ai(ask["confirm"], True)
    t2 = api._runner.get(done["task"]["id"])
    assert t2.wait(30) and t2.status == "succeeded"
    sent = pro.calls[-1][0]["content"]
    assert "Current:" in sent and json.loads(sent.split("Current: ", 1)[1])["shapes"]
    from nexvara.protocol import task_dto

    assert any(f.endswith(".dxf") for f in task_dto(t2.snapshot())["files"])
