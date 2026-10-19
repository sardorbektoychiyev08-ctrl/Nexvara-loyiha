"""Sync of settings, memory and Teach rules: two "devices" in temp folders, a shared folder,
the phone endpoint and a fake Google Drive. Nothing leaves this PC."""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nexvara.appdata import Settings
from nexvara.memory.store import MemoryStore
from nexvara.sync import DriveTransport, FolderTransport, SyncEngine, SyncError, seal, unseal

PW = "maxfiy-parol-123"


@pytest.fixture
def two(tmp_path):
    def device(name):
        mem = MemoryStore(tmp_path / name / "app.db")
        return SyncEngine(mem, Settings(tmp_path / name / "settings.json"), f"pc-{name}")

    shared = tmp_path / "OneDrive"
    shared.mkdir()
    return device("a"), device("b"), shared


def test_facts_rules_settings_flow_both_ways(two):
    a, b, shared = two
    a.mem.add_fact("maktabim 21-maktab")
    a.mem.add_rule("excel", "raqamlarni markazga joyla")
    a.settings.update({"test_count": 30, "theme": "light"})
    b.mem.add_fact("fanim fizika")
    a.sync(FolderTransport(shared, PW))
    r = b.sync(FolderTransport(shared, PW))
    assert r["received"] >= 3 and r["devices"] == ["pc-a"]
    a.sync(FolderTransport(shared, PW))
    for eng in (a, b):
        assert {f["text"] for f in eng.mem.facts()} == {"maktabim 21-maktab", "fanim fizika"}
        assert [x.text for x in eng.mem.rules("excel")] == ["raqamlarni markazga joyla"]
    assert b.settings.load()["test_count"] == 30 and b.settings.load()["theme"] == "light"
    raw = next(shared.glob("NEXVARA-sync/*.nxsync")).read_bytes()
    assert b"21-maktab" not in raw  # encrypted at rest


def test_last_edit_wins_and_deletes_propagate(two):
    a, b, shared = two
    fid = a.mem.add_fact("telefonim 90 123")
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    b_id = b.mem.facts()[0]["id"]
    a.mem.update_fact(fid, "telefonim 90 111")
    a.sync(FolderTransport(shared, PW))
    time.sleep(0.01)
    b.mem.update_fact(b_id, "telefonim 90 999")  # newer edit on the other device
    b.sync(FolderTransport(shared, PW))
    a.sync(FolderTransport(shared, PW))
    assert a.mem.facts()[0]["text"] == b.mem.facts()[0]["text"] == "telefonim 90 999"
    rule = b.mem.add_rule("word", "sahifa raqamini qo‘y")
    b.sync(FolderTransport(shared, PW))
    a.sync(FolderTransport(shared, PW))
    a.mem.update_rule(a.mem.rules("word")[0].id, enabled=False)
    a.mem.delete_fact(a.mem.facts()[0]["id"])
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    assert b.mem.facts() == [] and b.mem.rule(rule.id).enabled is False


def test_chat_history_only_when_turned_on(two):
    """The chat goes to the other PC only after both owners' PCs turned on sync.chat; «unut»
    deletes there too; messages that only grew old are not deleted anywhere."""
    a, b, shared = two
    a.mem.log_chat("user", "Baholar.xlsx ni PDF qil")
    a.mem.log_chat("nexvara", "Tayyor: Baholar.pdf")
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    assert b.mem.chat() == []  # off by default
    raw = next(shared.glob("NEXVARA-sync/pc-a.nxsync")).read_bytes()
    assert b"Baholar" not in unseal(raw, PW).__repr__().encode()  # chat not even sent
    for eng in (a, b):
        eng.settings.update({"sync": {"chat": True}})
    b.mem.log_chat("user", "salom")
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    a.sync(FolderTransport(shared, PW))
    want = ["Baholar.xlsx ni PDF qil", "Tayyor: Baholar.pdf", "salom"]
    assert [m["text"] for m in a.mem.chat()] == want  # in time order on both PCs
    assert [m["text"] for m in b.mem.chat()] == want
    assert b.mem.recent_turns()[0]["text"] == "Baholar.xlsx ni PDF qil"
    a.sync(FolderTransport(shared, PW))  # nothing doubles on repeated syncs
    b.sync(FolderTransport(shared, PW))
    assert len(b.mem.chat()) == 3
    # «… ni unut» on one PC removes the message on the other one too
    assert a.mem.forget_chat("Baholar xlsx") == 1
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    assert [m["text"] for m in b.mem.chat()] == ["Tayyor: Baholar.pdf", "salom"]
    # Turning chat sync off on a PC stops sending, and deletes nothing elsewhere.
    a.settings.update({"sync": {"chat": False}})
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    assert len(b.mem.chat()) == 2 and len(a.mem.chat()) == 2


def test_safety_rules(two, tmp_path):
    a, b, shared = two
    a.settings.update({"ai": {"enabled": True, "daily_budget_usd": 3.0}})
    a.sync(FolderTransport(shared, PW))
    b.sync(FolderTransport(shared, PW))
    assert b.settings.load()["ai"]["daily_budget_usd"] == 3.0
    assert b.settings.load()["ai"]["enabled"] is False  # never switched on remotely
    # A forged record for a setting outside the safe list is ignored.
    b.merge([{"kind": "setting", "uid": "update.channel", "data": {"value": "https://evil"},
              "updated": time.time() + 99, "device": "x", "deleted": False}])  # fmt: skip
    assert b.settings.load()["update"]["channel"] == ""
    with pytest.raises(SyncError, match="parol"):
        b.sync(FolderTransport(shared, "boshqa-parol-1"))
    with pytest.raises(SyncError, match="8 belgi"):
        FolderTransport(shared, "qisqa")
    assert unseal(seal({"x": 1}, PW), PW) == {"x": 1}


def test_api_sync_now_and_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.ai.keys import MemoryKeyStore
    from nexvara.app.api import Api

    shared = tmp_path / "Shared"
    shared.mkdir()
    mem = MemoryStore(tmp_path / "app.db")
    keys = MemoryKeyStore()
    api = Api(overrides={"memory": mem, "sync_keys": keys})
    assert "joyi tanlanmagan" in api.chat("sinxronla")["reply"]
    api.chat(f"sinxronlash papkasi {shared}")
    assert "8 belgi" in api.chat("sinxronla")["reply"]
    assert api.sync_set_passphrase(PW)["has_passphrase"] and keys.load("passphrase") == PW
    mem.add_fact("eslatma bir")
    r = api.chat("hozir sinxronla")
    assert r["reply"].startswith("Sinxronlandi"), r
    assert list((shared / "NEXVARA-sync").glob("*.nxsync"))
    assert api.get_settings()["sync"]["last"] > 0


def test_phone_sync_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from tests.unit.test_remote_v1 import call, j, pair

    from nexvara.app.api import Api
    from nexvara.core.task import TaskRunner
    from nexvara.remote import DeviceStore

    mem = MemoryStore(tmp_path / "app.db")
    mem.add_fact("kompyuterdagi eslatma")
    store = DeviceStore(tmp_path / "d.db")
    api = Api(TaskRunner(), overrides={"memory": mem, "device_store": store, "remote_port": 0})
    assert api.devices_start()["ok"]
    srv = api._server()
    srv.host_url = f"https://127.0.0.1:{srv.port}"
    try:
        token = pair(srv)
        got = j(call(srv, "GET", "/api/v1/sync", token=token))["data"]
        assert any(r["data"].get("text") == "kompyuterdagi eslatma" for r in got["records"])
        rec = {"kind": "fact", "uid": "phone-1-abc", "data": {"text": "telefondan eslatma"},
               "updated": time.time(), "device": "phone-1", "deleted": False}  # fmt: skip
        out = j(call(srv, "POST", "/api/v1/sync", {"records": [rec]}, token,
                     {"Content-Type": "application/json"}))["data"]  # fmt: skip
        assert out["applied"] == 1 and "telefondan eslatma" in {f["text"] for f in mem.facts()}
        assert call(srv, "POST", "/api/v1/sync", {"records": "x"}, token)[0] == 400
    finally:
        api.devices_stop()


class FakeDrive:
    def __init__(self):
        self.files: dict[str, dict] = {}
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"{}", ctype="application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth(self):
                if self.headers.get("Authorization") != "Bearer at-drive":
                    self._send(401)
                    return False
                return True

            def do_GET(self):  # noqa: N802
                if not self._auth():
                    return
                u = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(u.query)
                if u.path == "/drive/v3/files":
                    assert q["spaces"] == ["appDataFolder"]
                    items = [{"id": k, "name": v["name"]} for k, v in fake.files.items()]
                    self._send(200, json.dumps({"files": items}).encode())
                else:
                    fid = u.path.rsplit("/", 1)[-1]
                    self._send(200, fake.files[fid]["data"], "application/octet-stream")

            def _body(self):
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_POST(self):  # noqa: N802
                if not self._auth():
                    return
                body = self._body()
                boundary = self.headers["Content-Type"].split("boundary=")[1].encode()
                parts = body.split(b"--" + boundary)
                meta = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].strip())
                assert meta["parents"] == ["appDataFolder"]
                data = parts[2].split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0]
                fid = f"id{len(fake.files) + 1}"
                fake.files[fid] = {"name": meta["name"], "data": data}
                self._send(200, json.dumps({"id": fid}).encode())

            def do_PATCH(self):  # noqa: N802
                if not self._auth():
                    return
                fid = urllib.parse.urlparse(self.path).path.rsplit("/", 1)[-1]
                fake.files[fid]["data"] = self._body()
                self._send(200)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


def test_google_drive_transport(two):
    a, b, _ = two
    drive = FakeDrive()
    try:

        def tr(token="at-drive"):
            return DriveTransport(token, PW, api=drive.base + "/drive/v3",
                                  upload=drive.base + "/upload/drive/v3")  # fmt: skip

        a.mem.add_fact("drive orqali eslatma")
        a.sync(tr())
        a.sync(tr())  # second time updates the same file (PATCH), no duplicate
        assert len(drive.files) == 1
        b.sync(tr())
        assert b.mem.facts()[0]["text"] == "drive orqali eslatma" and len(drive.files) == 2
        with pytest.raises(SyncError, match="ruxsati"):
            b.sync(tr("eskirgan"))
    finally:
        drive.httpd.shutdown()
