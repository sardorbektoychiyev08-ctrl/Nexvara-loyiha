"""Phone API v1 sections (the Android app's Home, AI spend, Memory, Teach, Workflows, BI,
textbooks, Office, Google, pause/resume): real HTTPS on localhost, throwaway data folder,
fake AI provider. Nothing here reaches a paid API, Google or the user's real data."""

from __future__ import annotations

import base64
import json
import threading
import time

import pytest
from test_privacy import PERSON, SECRETS, Capture
from test_remote_v1 import call, j, pair

from nexvara.ai.keys import MemoryKeyStore


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.ai.router import AiRouter, Ledger
    from nexvara.app.api import Api
    from nexvara.appdata import Settings
    from nexvara.core.task import TaskRunner
    from nexvara.memory.store import MemoryStore
    from nexvara.remote import DeviceStore
    from nexvara.workflows import WorkflowStore

    cap = Capture("Javob tayyor")
    router = AiRouter(Settings(tmp_path / "s.json"),
                      MemoryKeyStore({"openai": "sk-test-openai-123456"}),
                      Ledger(tmp_path / "l.db"), factory=lambda n, k: cap)  # fmt: skip
    api = Api(TaskRunner(), overrides={
        "device_store": DeviceStore(tmp_path / "app.db"), "remote_port": 0,
        "memory": MemoryStore(tmp_path / "mem.db"), "ai_router": router,
        "workflow_store": WorkflowStore(tmp_path / "wf.db"),
        "sync_keys": MemoryKeyStore({}),
        "excel_demo": lambda t: {"path": str(tmp_path / "demo.xlsx")},
    })  # fmt: skip
    assert api.devices_start()["ok"]
    srv = api._server()
    srv.host_url = f"https://127.0.0.1:{srv.port}"
    token = pair(srv)
    yield api, srv, token, cap, tmp_path
    api.devices_stop()


def post(srv, path, data, token):
    return call(srv, "POST", path, data, token, {"Content-Type": "application/json"})


# ---------------- pause / resume (TaskRunner) ----------------
def _stepper(gate: threading.Event, n=3):
    def fn(task):
        for i in range(n):
            with task.step(f"Qadam {i + 1}"):
                gate.wait(5)
        return {}

    return fn


def test_pause_stops_at_step_boundary_and_resumes():
    from nexvara.core.task import Status, TaskRunner

    gate = threading.Event()
    t = TaskRunner().start("T", _stepper(gate))
    time.sleep(0.2)
    assert t.pause() and t.pause_requested
    assert t.status == Status.RUNNING  # still inside step 1: no Office call is interrupted
    gate.set()
    for _ in range(50):
        if t.status == Status.PAUSED:
            break
        time.sleep(0.05)
    assert t.status == Status.PAUSED and len(t.steps) == 1
    assert t.snapshot()["pause_requested"] is True
    assert t.resume()
    assert t.wait(5) and t.status == Status.SUCCEEDED and len(t.steps) == 3
    assert t.paused_seconds > 0 and not t.resume() and not t.pause()


def test_cancel_while_paused_and_paused_time_is_not_a_timeout():
    from nexvara.core.task import Status, TaskRunner

    def slow(task):
        for i in range(100):
            with task.step(f"Qadam {i}"):
                time.sleep(0.05)
        return {}

    runner = TaskRunner(timeout=0.6)
    t = runner.start("T", slow)
    t.pause()
    time.sleep(1.2)  # longer than the timeout, but paused
    assert t.status == Status.PAUSED
    t.cancel()
    assert t.wait(5) and t.status == Status.CANCELLED


# ---------------- through HTTPS ----------------
def test_pause_resume_routes(env):
    api, srv, token, _cap, _ = env
    gate = threading.Event()
    snap = api._runner.start("Uzun", _stepper(gate)).snapshot()
    r = j(post(srv, f"/api/v1/tasks/{snap['id']}/pause", {}, token))["data"]
    assert r["ok"] and r["task"]["pause_requested"] is True
    gate.set()
    task = api._runner.get(snap["id"])
    for _ in range(50):
        if task.status == "paused":
            break
        time.sleep(0.05)
    got = j(call(srv, "GET", f"/api/v1/tasks/{snap['id']}", token=token))["data"]
    assert got["status"] == "paused"
    r = j(post(srv, f"/api/v1/tasks/{snap['id']}/resume", {}, token))["data"]
    assert r["ok"] and task.wait(5) and task.status == "succeeded"
    r = post(srv, f"/api/v1/tasks/{snap['id']}/pause", {}, token)
    assert r[0] == 400  # already finished
    assert post(srv, "/api/v1/tasks/ffffffffffff/pause", {}, token)[0] == 404


def test_overview_and_ai_panel_never_leak_keys(env):
    api, srv, token, _cap, _ = env
    r = call(srv, "GET", "/api/v1/overview", token=token)
    assert r[0] == 200
    data = j(r)["data"]
    assert {"pc_name", "app_version", "tasks", "counts", "ai", "sync", "account"} <= set(data)
    assert list(data["ai"]["providers"]) == ["openai", "gemini", "anthropic", "deepseek"]
    oa = data["ai"]["providers"]["openai"]
    assert oa["has_key"] is True and oa["billing_url"].startswith("https://")
    assert oa["left_today"] is not None and data["ai"]["estimated"] is True
    raw = r[1].decode()
    assert "sk-test" not in raw and "key_masked" not in raw
    full = j(call(srv, "GET", "/api/v1/ai", token=token))["data"]
    assert "series" in full and "history" in full and "sk-test" not in json.dumps(full)
    b = j(post(srv, "/api/v1/ai/openai/balance", {}, token))["data"]
    assert b == {"supported": False}  # no official balance API: never a made-up number
    assert post(srv, "/api/v1/ai/nope/balance", {}, token)[0] == 404


def test_phone_ai_chat_is_masked_and_counted_once(env):
    """The phone's AI request runs on the PC: the privacy guard masks it, one ledger row."""
    api, srv, token, cap, _ = env
    api._router().settings.update({"ai": {"enabled": True, "provider": "openai"}})
    api._ai_ready = lambda: True
    before = len(api._router().ledger.recent())
    r = post(srv, "/api/v1/chat", {"text": "AI bilan xat yoz: " + PERSON}, token)
    assert r[0] == 200
    sent = "\n".join(cap.seen)
    assert cap.seen, "the AI path was not used"
    for s in SECRETS:
        assert s not in sent, s
    # one ledger row per AI call (an unusable plan may be retried once on a stronger tier)
    assert len(api._router().ledger.recent()) - before == len(cap.seen) <= 2


def test_phone_chat_reaches_pc_window_and_history(env):
    api, srv, token, _cap, _ = env
    post(srv, "/api/v1/chat", {"text": "salom"}, token)
    ev = api.ui_events()
    assert ev and ev[0]["kind"] == "phone_chat" and ev[0]["text"] == "salom"
    assert api.ui_events() == []  # delivered once
    h = j(call(srv, "GET", "/api/v1/chat/history?limit=10", token=token))["data"]["messages"]
    assert [m["role"] for m in h[-2:]] == ["user", "nexvara"] and h[-2]["text"] == "salom"
    last = h[-1]["id"]
    assert j(call(srv, "GET", f"/api/v1/chat/history?after={last}", token=token))["data"] == {
        "messages": []
    }


def test_memory_and_teach(env):
    api, srv, token, _cap, _ = env
    facts = j(post(srv, "/api/v1/memory", {"text": "Maktab: 21-maktab"}, token))["data"]["facts"]
    fid = facts[0]["id"]
    facts = j(post(srv, f"/api/v1/memory/{fid}", {"text": "Maktab: 22-maktab"}, token))["data"]
    assert facts["facts"][0]["text"] == "Maktab: 22-maktab"
    found = j(call(srv, "GET", "/api/v1/memory/search?q=maktab", token=token))["data"]
    assert found["results"]
    assert post(srv, "/api/v1/memory", {"text": ""}, token)[0] == 400
    assert j(post(srv, f"/api/v1/memory/{fid}/delete", {}, token))["data"]["facts"] == []
    assert post(srv, "/api/v1/memory/abc/delete", {}, token)[0] == 404

    t = j(call(srv, "GET", "/api/v1/teach", token=token))["data"]
    assert t["rules"] == [] and t["apps"]["excel"] == "Excel"
    pv = j(post(srv, "/api/v1/teach", {"app": "excel", "text": "sarlavha qalin",
                                        "preview": True}, token))["data"]  # fmt: skip
    assert "ok" in pv
    if pv["ok"]:
        rules = j(post(srv, "/api/v1/teach", {"app": "excel", "text": "sarlavha qalin"},
                       token))["data"]["rules"]  # fmt: skip
        rid = rules[0]["id"]
        off = j(post(srv, f"/api/v1/teach/{rid}", {"enabled": False}, token))["data"]
        assert off["rules"][0]["enabled"] is False
        assert j(post(srv, f"/api/v1/teach/{rid}/delete", {}, token))["data"]["rules"] == []
    assert post(srv, "/api/v1/teach", {"app": "x", "text": "y"}, token)[0] == 400
    assert post(srv, "/api/v1/teach/999", {"enabled": True}, token)[0] == 404


def test_workflows(env, tmp_path):
    api, srv, token, _cap, _ = env
    data = j(call(srv, "GET", "/api/v1/workflows", token=token))["data"]
    assert data["templates"] and data["workflows"] == []
    tpl = dict(next(t for t in data["templates"] if t["trigger"]["type"] == "manual"))
    tpl.pop("id", None)
    saved = j(post(srv, "/api/v1/workflows", tpl, token))["data"]
    assert saved["ok"] and saved["workflows"]
    wid = saved["id"]
    outside = tmp_path / "boshqa.xlsx"
    outside.write_bytes(b"x")
    r = post(srv, f"/api/v1/workflows/{wid}/run", {"file": str(outside)}, token)
    assert r[0] == 400  # only a file the phone uploaded
    assert post(srv, "/api/v1/workflows/runs/1/explode", {}, token)[0] == 404
    out = j(post(srv, f"/api/v1/workflows/{wid}/delete", {}, token))["data"]
    assert out["workflows"] == []


def test_bi_open_shows_on_pc_and_compact_widgets(env, tmp_path):
    api, srv, token, _cap, _ = env
    src = tmp_path / "savdo.csv"
    src.write_text("Sana,Hudud,Summa\n2026-01-05,Toshkent,100\n2026-02-07,Samarqand,250\n"
                   "2026-02-09,Toshkent,50\n", encoding="utf-8")  # fmt: skip
    auto = api.bi_auto(str(src))
    assert auto["ok"], auto
    saved = api.bi_save({**auto["config"], "name": "Savdo"})
    assert saved["ok"]
    lst = j(call(srv, "GET", "/api/v1/bi", token=token))["data"]["dashboards"]
    assert lst[0]["name"] == "Savdo" and lst[0]["source_name"] == "savdo.csv"
    api.ui_events()
    d = j(post(srv, "/api/v1/bi/open", {"file": lst[0]["file"]}, token))["data"]
    assert d["name"] == "Savdo" and d["widgets"] and d["shown_on_pc"]
    assert any(w["type"] == "kpi" and "value" in w for w in d["widgets"])
    assert api.ui_events()[0] == {"kind": "bi_open", "file": lst[0]["file"], "state": {}}
    bad = post(srv, "/api/v1/bi/open", {"file": str(src)}, token)
    assert bad[0] == 404  # only saved NEXVARA BI dashboards


def test_library_test_and_office(env, tmp_path):
    api, srv, token, _cap, _ = env
    out = tmp_path / "test.docx"
    api._overrides["make_test"] = lambda t: {"path": str(out)}
    lib = j(call(srv, "GET", "/api/v1/library", token=token))["data"]
    assert lib["books"] == [] and "catalog" in lib
    r = j(post(srv, "/api/v1/library/test", {"grade": 5, "subject": "Tarix", "count": 10},
               token))["data"]  # fmt: skip
    assert r["task"]["id"] and r["confirm"] is None
    assert post(srv, "/api/v1/library/test", {"count": "x"}, token)[0] == 400
    api.ui_events()
    o = j(post(srv, "/api/v1/office/excel_demo", {}, token))["data"]
    assert o["task"]["title"].startswith("Excel")
    assert api.ui_events()[0]["kind"] == "task"
    assert post(srv, "/api/v1/office/format_c", {}, token)[0] == 404


# ---------------- Google on the phone ----------------
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _id_token(key, claims):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    head = _b64(json.dumps({"alg": "RS256", "kid": "k1"}).encode())
    body = _b64(json.dumps(claims).encode())
    sig = key.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{body}.{_b64(sig)}"


def test_google_link_only_for_pc_owner(env, tmp_path):
    from cryptography.hazmat.primitives.asymmetric import rsa

    from nexvara.account import GoogleAccount

    api, srv, token, _cap, _ = env
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = key.public_key().public_numbers()
    jwks = {"keys": [{"kty": "RSA", "kid": "k1", "n": _b64(n.n.to_bytes(256, "big")),
                      "e": _b64(n.e.to_bytes(3, "big"))}]}  # fmt: skip
    acc = GoogleAccount(client={"client_id": "d.apps.googleusercontent.com", "client_secret": "s"},
                        keys=MemoryKeyStore({}), profile_path=tmp_path / "acc.json")  # fmt: skip
    acc._jwks = lambda: jwks
    api._account = acc
    web = "web-123.apps.googleusercontent.com"

    def tok(sub, aud=web):
        return _id_token(key, {"iss": "https://accounts.google.com", "aud": aud, "sub": sub,
                               "email": "ega@gmail.com", "email_verified": True,
                               "exp": time.time() + 600})  # fmt: skip

    st = j(call(srv, "GET", "/api/v1/account", token=token))["data"]
    assert st["phone"] == {"web_client_id": "", "ready": False, "linked_email": ""}
    r = post(srv, "/api/v1/account/link", {"id_token": tok("1001")}, token)
    assert r[0] == 400 and "Web client" in j(r)["error"]["message"]
    api.save_settings({"google": {"android_web_client_id": web}})
    r = post(srv, "/api/v1/account/link", {"id_token": tok("1001")}, token)
    assert r[0] == 400 and "kompyuterda" in j(r)["error"]["message"]  # no owner yet
    acc.keys.save("owner_sub", "1001")
    assert post(srv, "/api/v1/account/link", {"id_token": tok("2002")}, token)[0] == 400
    assert (
        post(srv, "/api/v1/account/link", {"id_token": tok("1001", aud="other")}, token)[0] == 400
    )
    ok = j(post(srv, "/api/v1/account/link", {"id_token": tok("1001")}, token))["data"]
    assert ok == {"linked": True, "email": "ega@gmail.com", "name": ""}
    st = j(call(srv, "GET", "/api/v1/account", token=token))["data"]
    assert st["phone"]["linked_email"] == "ega@gmail.com" and st["phone"]["ready"] is True
