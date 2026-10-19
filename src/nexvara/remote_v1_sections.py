"""Phone API v1: the sections of the Windows app (Home, AI spend, Memory, Teach, Workflows,
BI, Textbooks, Office, Google) for the Android app.

Everything here is a thin wrapper over the same `Api` methods the PC window uses, so the phone
and the PC are one system: one database, one AI ledger (spend is never counted twice), one
privacy guard (every AI request still goes through `AiRouter.complete`). Routes are listed in
`ROUTES` (merged into remote_v1.ROUTES and checked against docs/api/openapi.yaml).
"""

from __future__ import annotations

import hashlib
import socket
import time
from pathlib import Path
from typing import Any

from nexvara import __version__, config
from nexvara.protocol import ApiError, task_dto

ROUTES: list[tuple[str, str, bool]] = [
    ("GET", "/api/v1/overview", True),
    ("GET", "/api/v1/chat/history", True),
    ("POST", "/api/v1/tasks/{id}/pause", True),
    ("POST", "/api/v1/tasks/{id}/resume", True),
    ("GET", "/api/v1/ai", True),
    ("POST", "/api/v1/ai/{provider}/balance", True),
    ("GET", "/api/v1/ai/capabilities", True),
    ("POST", "/api/v1/ai/capabilities", True),
    ("POST", "/api/v1/ai/speak", True),
    ("GET", "/api/v1/memory", True),
    ("POST", "/api/v1/memory", True),
    ("GET", "/api/v1/memory/search", True),
    ("POST", "/api/v1/memory/{id}", True),
    ("POST", "/api/v1/memory/{id}/delete", True),
    ("GET", "/api/v1/teach", True),
    ("POST", "/api/v1/teach", True),
    ("POST", "/api/v1/teach/{id}", True),
    ("POST", "/api/v1/teach/{id}/delete", True),
    ("GET", "/api/v1/workflows", True),
    ("POST", "/api/v1/workflows", True),
    ("POST", "/api/v1/workflows/{id}/run", True),
    ("POST", "/api/v1/workflows/{id}/delete", True),
    ("POST", "/api/v1/workflows/runs/{id}/{action}", True),
    ("GET", "/api/v1/bi", True),
    ("POST", "/api/v1/bi/open", True),
    ("GET", "/api/v1/library", True),
    ("POST", "/api/v1/library/test", True),
    ("POST", "/api/v1/office/{kind}", True),
    ("GET", "/api/v1/account", True),
    ("POST", "/api/v1/account/link", True),
    ("GET", "/api/v1/screen", True),
    ("GET", "/api/v1/files/search", True),
    ("POST", "/api/v1/files/share", True),
    ("POST", "/api/v1/files/open", True),
    ("POST", "/api/v1/files/zip", True),
    ("POST", "/api/v1/files/unzip", True),
]
HANDLED = {p for _m, p, _a in ROUTES}

_PROVIDER_KEYS = ("label", "billing_url", "usage_url", "key_url", "has_key", "balance_api",
                  "balance", "spent_today", "spent_month", "daily_limit", "monthly_limit",
                  "task_limit", "free_tier", "subscription_note")  # fmt: skip


def _int(v: str) -> int:
    if not v.isdigit():
        raise ApiError("NOT_FOUND")
    return int(v)


def _ok_or_bad(out: dict[str, Any]) -> dict[str, Any]:
    """Api methods return {"ok": False, "error": ...} for a user mistake."""
    if isinstance(out, dict) and out.get("ok") is False:
        raise ApiError("BAD_REQUEST", str(out.get("error") or "Bajarib bo‘lmadi"))
    return out


# ---------------- AI spend (Home panel) ----------------
def _ai_provider(p: dict[str, Any]) -> dict[str, Any]:
    out = {k: p.get(k) for k in _PROVIDER_KEYS}  # never the key itself, not even masked
    for span, lim_key in (("today", "daily_limit"), ("month", "monthly_limit")):
        lim = p.get(lim_key)
        spent = p.get(f"spent_{span}") or 0.0
        out[f"left_{span}"] = round(max(0.0, float(lim) - spent), 4) if lim is not None else None
    return out


def ai_panel(api: Any, full: bool = False) -> dict[str, Any]:
    """Spend and limits of OpenAI, Gemini, Claude and DeepSeek from the PC's single ledger
    (app.db → ai_usage): requests from the phone run on the PC, so nothing is counted twice."""
    try:
        d = api.ai_dashboard() if full else api.ai_status()
    except Exception as e:  # no AI module state yet: still show the panel
        return {"error": f"AI holatini o‘qib bo‘lmadi: {e}", "providers": {}}
    out = {k: d.get(k) for k in ("enabled", "provider", "ready", "spent_today", "spent_month",
                                 "daily_budget_usd", "monthly_budget_usd", "warnings",
                                 "blocked", "fallback")}  # fmt: skip
    order = ("openai", "gemini", "anthropic", "deepseek")
    provs = d.get("providers") or {}
    out["providers"] = {n: _ai_provider(provs[n]) for n in order if n in provs}
    out["estimated"] = True  # NEXVARA's own estimate from token counts, not the provider's bill
    if full:
        out["series"] = d.get("series") or []
        out["history"] = d.get("history") or []
    return out


# ---------------- BI (compact widgets for a phone screen) ----------------
def _compact_widget(w: dict[str, Any]) -> dict[str, Any]:
    out = {k: w.get(k) for k in ("id", "type", "title", "unit", "value", "growth",
                                 "growth_label") if w.get(k) is not None}  # fmt: skip
    kind = w.get("type")
    if kind in ("bar", "pie"):
        out["labels"] = [str(x) for x in (w.get("labels") or [])[:12]]
        out["values"] = (w.get("values") or [])[:12]
    elif kind == "line":
        labels = [str(x) for x in w.get("labels") or []]
        keep = slice(max(0, len(labels) - 60), None)
        out["labels"] = labels[keep]
        out["series"] = [{"name": s.get("name"), "values": (s.get("values") or [])[keep]}
                         for s in (w.get("series") or [])[:3]]  # fmt: skip
    elif kind == "table":
        out["columns"] = [str(c) for c in (w.get("columns") or [])]
        out["rows"] = [[c if isinstance(c, int | float) or c is None else str(c) for c in r]
                       for r in (w.get("rows") or [])[:20]]  # fmt: skip
        out["total_rows"] = w.get("total_rows")
    elif kind == "scatter":
        out["points"] = len(w.get("points") or [])
    return out


def _bi_open(api: Any, body: dict[str, Any]) -> dict[str, Any]:
    file = str(body.get("file", ""))
    known = {d["file"] for d in api.bi_list()}
    if file not in known:
        raise ApiError("NOT_FOUND", "Dashboard topilmadi")
    state = body.get("state") if isinstance(body.get("state"), dict) else {}
    opened = _ok_or_bad(api.bi_open(file))
    res = opened["result"]
    if state:
        res = _ok_or_bad(api.bi_compute(opened["config"], state))["result"]
    if body.get("show_on_pc", True):  # the PC window switches to NEXVARA BI and opens it
        api.ui_push({"kind": "bi_open", "file": file, "state": state})
    return {
        "name": opened["config"].get("name"),
        "file": file,
        "page": res.get("page"),
        "pages": res.get("pages"),
        "widgets": [_compact_widget(w) for w in res.get("widgets") or []],
        "slicers": {k: v[:50] for k, v in (res.get("slicers") or {}).items()},
        "rows": res.get("rows"),
        "total_rows": res.get("total_rows"),
        "problems": res.get("problems") or [],
        "shown_on_pc": bool(body.get("show_on_pc", True)),
    }


# ---------------- small helpers ----------------
def _count(fn: Any) -> int | None:
    try:
        return len(fn())
    except Exception:
        return None


def _account(api: Any, dev: dict[str, Any], store: Any) -> dict[str, Any]:
    try:
        st = api.account_status()
    except Exception:
        st = {}
    prof = st.get("profile") or {}
    web_id = str(api.get_settings().get("google", {}).get("android_web_client_id") or "")
    return {
        "pc": {
            "configured": bool(st.get("configured")),
            "signed_in": bool(st.get("signed_in")),
            "owner_set": bool(st.get("owner_set")),
            "email": prof.get("email", ""),
            "name": prof.get("name", ""),
        },  # fmt: skip
        # The Web client ID is public (it is the audience of the phone's ID token).
        "phone": {
            "web_client_id": web_id,
            "ready": bool(web_id) and bool(st.get("owner_set")),
            "linked_email": store.google_email(dev["id"]),
        },  # fmt: skip
    }


def _sync(api: Any) -> dict[str, Any]:
    try:
        s = api.sync_status()
    except Exception:
        return {"available": False}
    folder = str(s.get("folder") or "")
    return {
        "available": bool(s.get("available")),
        "enabled": bool(s.get("enabled")),
        "folder_name": Path(folder).name if folder else "",  # not the full path
        "google_drive": bool(s.get("google_drive")),
        "has_passphrase": bool(s.get("has_passphrase")),
        "last": s.get("last") or 0,
    }


def _phone_file(path: str) -> str:
    """A workflow may run on a file the phone uploaded (and only on such a file)."""
    if not path:
        return ""
    p = Path(path).resolve()
    folder = (config.data_dir() / "Telefondan").resolve()
    if folder not in p.parents or not p.is_file():
        raise ApiError("BAD_REQUEST", "Faqat telefondan yuborilgan fayl tanlanadi")
    return str(p)


# ---------------- PC files for the phone (search, open on the PC, send to it) ----------------
FOUND_TTL = 600.0  # a search result may be opened/shared for 10 minutes
SHARED_TTL = 1800.0  # a shared file may be downloaded for 30 minutes
# Never handed to a phone, even if found: keys, tokens, databases, NEXVARA's own secrets.
_SECRET_NAMES = {"google_client.json", "account.json", "settings.json", "app.db", "nexvara.db",
                 ".env", "id_rsa", "id_ed25519", "known_hosts", "cert.pem", "key.pem"}  # fmt: skip
_SECRET_EXT = (".pem", ".key", ".jks", ".keystore", ".p12", ".pfx", ".kdbx", ".ppk", ".sqlite",
               ".session", ".db")  # fmt: skip


def _secret(p: Path) -> bool:
    name = p.name.lower()
    if name in _SECRET_NAMES or name.endswith(_SECRET_EXT):
        return True
    data = config.data_dir().resolve()
    for sub in ("remote", "telegram", "release", "updates", "android"):
        if (data / sub) in p.parents or p == data / sub:
            return True
    return False


def _grants(srv: Any) -> dict:
    if not hasattr(srv, "phone_files"):
        srv.phone_files = {}
    return srv.phone_files


def _grant(srv: Any, dev: dict[str, Any], path: str, kind: str, ttl: float) -> None:
    g = _grants(srv)
    now = time.time()
    for k in [k for k, exp in g.items() if exp < now]:
        del g[k]
    g[(dev["id"], kind, path)] = now + ttl


def granted(srv: Any, dev: dict[str, Any], path: str, kind: str = "shared") -> bool:
    exp = _grants(srv).get((dev["id"], kind, path))
    return exp is not None and exp > time.time()


def _found_file(srv: Any, dev: dict[str, Any], path: str) -> Path:
    if not (granted(srv, dev, path, "found") or granted(srv, dev, path, "shared")):
        raise ApiError("NOT_FOUND", "Avval faylni qidiruvdan toping")
    p = Path(path)
    if not p.is_file() or _secret(p.resolve()):
        raise ApiError("NOT_FOUND", "Fayl topilmadi")
    return p


def _screen(h: Any, api: Any) -> None:
    if not api.get_settings().get("remote", {}).get("screen_view", True):
        raise ApiError("NOT_FOUND", "Ekranni ko‘rish kompyuterda o‘chirilgan")
    cap = getattr(api, "_overrides", {}).get("screen_capture")
    if cap is None:
        from nexvara.screen import capture_jpeg as cap
    try:
        data = cap()
    except Exception as e:
        raise ApiError("INTERNAL", f"Ekranni olib bo‘lmadi: {e}") from e
    last = getattr(api, "_screen_seen", 0.0)
    if time.time() - last > 30:  # the PC shows that it is being watched
        api._screen_seen = time.time()
        api.ui_push({"kind": "phone_screen"})
    h._send(200, data, "image/jpeg", {"X-Content-SHA256": hashlib.sha256(data).hexdigest()})


# ---------------- router ----------------
def route(h: Any, srv: Any, route: str, args: dict[str, str], q: dict[str, list[str]],
          dev: dict[str, Any], body: Any) -> dict[str, Any]:  # fmt: skip
    """`body()` reads the JSON body (only for POST)."""
    from nexvara.remote import server_id

    api = srv.api
    if route == "/api/v1/overview":
        tasks = api.list_tasks()
        return {
            "pc_name": socket.gethostname(),
            "server_id": server_id(),
            "app_version": __version__,
            "time": time.time(),
            "tasks": [task_dto(t) for t in tasks[:5]],
            "running": sum(
                1 for t in tasks[:50] if t.get("status") in ("pending", "running", "paused")
            ),  # fmt: skip
            "counts": {
                "memory": _count(api.memory_facts),
                "teach": _count(api.teach_rules),
                "workflows": _count(api.wf_list),
                "dashboards": _count(api.bi_list),
            },
            "ai": ai_panel(api),
            "sync": _sync(api),
            "account": _account(api, dev, srv.store),
        }
    if route == "/api/v1/chat/history":
        limit = max(1, min(int((q.get("limit") or ["100"])[0]), 200))
        after = int((q.get("after") or ["0"])[0])
        items = [m for m in api.memory_chat(limit) if m["id"] > after]
        return {"messages": items}
    if route in ("/api/v1/tasks/{id}/pause", "/api/v1/tasks/{id}/resume"):
        task_id = args["id"]
        fn = api.pause_task if route.endswith("pause") else api.resume_task
        done = bool(fn(task_id))
        snap = api.get_task(task_id)
        if snap is None:
            raise ApiError("NOT_FOUND", "Vazifa topilmadi")
        if not done and snap.get("status") in ("succeeded", "failed", "cancelled"):
            raise ApiError("BAD_REQUEST", "Vazifa allaqachon tugagan")
        return {"ok": done, "task": task_dto(snap)}
    if route == "/api/v1/ai":
        return ai_panel(api, full=True)
    if route == "/api/v1/ai/{provider}/balance":
        from nexvara.ai import models

        if args["provider"] not in models.PROVIDERS:
            raise ApiError("NOT_FOUND", "Noma’lum provayder")
        return api.ai_balance(args["provider"])  # official balance API only; no model call
    # ----- 🧠 directions (AUTO/MANUAL) and 🔊 speech, shared with the PC's settings -----
    if route == "/api/v1/ai/capabilities" and h.command == "GET":
        return api.ai_capabilities()
    if route == "/api/v1/ai/capabilities":
        b = body()
        out = api.ai_set_capability(
            str(b.get("cap", "")),
            str(b.get("mode", "")),
            str(b.get("provider", "")),
            str(b.get("model", "")),
        )
        if not out.get("ok"):
            raise ApiError("BAD_REQUEST", out.get("error") or "Saqlanmadi")
        return out
    if route == "/api/v1/ai/speak":
        import base64
        import time as _time

        b = body()
        text = str(b.get("text", "")).strip()[:3000]
        if not text:
            raise ApiError("BAD_REQUEST", "Matn bo‘sh")
        out = api.ai_speak(text, bool(b.get("approved")), bool(b.get("live")))
        if out.get("needs_approval"):  # a paid voice: the phone shows the price and asks «Ha»
            return {"needs_approval": True, "text": out.get("error", "")}
        if not out.get("ok"):
            raise ApiError("BAD_REQUEST", out.get("error") or "Ovoz tayyorlanmadi")
        folder = config.data_dir() / "Ovoz"
        folder.mkdir(parents=True, exist_ok=True)
        wav = folder / f"javob-{_time.strftime('%Y%m%d-%H%M%S')}.wav"
        wav.write_bytes(base64.b64decode(out["audio"]))
        _grant(srv, dev, str(wav), "shared", SHARED_TTL)
        return {"path": str(wav), "provider": out["provider"], "model": out["model"],
                "cost": out["cost"]}  # fmt: skip
    # ----- Memory -----
    if route == "/api/v1/memory" and h.command == "GET":
        return {"facts": api.memory_facts()}
    if route == "/api/v1/memory":
        _ok_or_bad(api.memory_add_fact(str(body().get("text", ""))))
        return {"facts": api.memory_facts()}
    if route == "/api/v1/memory/search":
        return {"results": api.memory_search((q.get("q") or [""])[0])}
    if route == "/api/v1/memory/{id}":
        _ok_or_bad(api.memory_update_fact(_int(args["id"]), str(body().get("text", ""))))
        return {"facts": api.memory_facts()}
    if route == "/api/v1/memory/{id}/delete":
        api.memory_delete_fact(_int(args["id"]))
        return {"facts": api.memory_facts()}
    # ----- Teach NEXVARA -----
    if route == "/api/v1/teach" and h.command == "GET":
        from nexvara.memory.store import APP_LABELS

        return {"rules": api.teach_rules(), "apps": APP_LABELS}
    if route == "/api/v1/teach":
        b = body()
        app, text = str(b.get("app", "")), str(b.get("text", ""))
        if b.get("preview"):
            return api.teach_preview(app, text)
        return _ok_or_bad(api.teach_add(app, text))
    if route == "/api/v1/teach/{id}":
        b = body()
        text = b.get("text")
        enabled = b.get("enabled")
        try:
            out = api.teach_update(_int(args["id"]), None if text is None else str(text),
                                   None if enabled is None else bool(enabled))  # fmt: skip
        except LookupError as e:
            raise ApiError("NOT_FOUND", "Qoida topilmadi") from e
        return _ok_or_bad(out)
    if route == "/api/v1/teach/{id}/delete":
        return {"ok": True, "rules": api.teach_delete(_int(args["id"]))}
    # ----- Workflows -----
    if route == "/api/v1/workflows" and h.command == "GET":
        return {"workflows": api.wf_list(), "templates": api.wf_templates(),
                "active": api.wf_active(), "runs": api.wf_runs()[:20]}  # fmt: skip
    if route == "/api/v1/workflows":
        return _ok_or_bad(api.wf_save(body()))
    if route == "/api/v1/workflows/{id}/run":
        file = _phone_file(str(body().get("file", "")))
        return _ok_or_bad(api.wf_run(_int(args["id"]), file))
    if route == "/api/v1/workflows/{id}/delete":
        return {"ok": True, "workflows": api.wf_delete(_int(args["id"]))}
    if route == "/api/v1/workflows/runs/{id}/{action}":
        fn = {"approve": api.wf_approve, "pause": api.wf_pause, "resume": api.wf_resume}.get(
            args["action"]
        )
        if fn is None:
            raise ApiError("NOT_FOUND")
        return {"ok": bool(fn(_int(args["id"]))), "active": api.wf_active()}
    # ----- NEXVARA BI -----
    if route == "/api/v1/bi":
        return {"dashboards": [{"file": d["file"], "name": d["name"], "saved": d["saved"],
                                "source_name": Path(str(d.get("source") or "")).name}
                               for d in api.bi_list()]}  # fmt: skip
    if route == "/api/v1/bi/open":
        return _bi_open(api, body())
    # ----- Textbooks and tests -----
    if route == "/api/v1/library":
        info = api.library_info()
        return {"books": info.get("books") or [], "catalog": info.get("catalog") or {},
                "problems": len(info.get("problems") or [])}  # fmt: skip
    if route == "/api/v1/library/test":
        out = api.make_test(body())
        if out.get("confirm"):
            return {"confirm": {"token": out["confirm"], "text": "Bu pullik AI so‘rovi. "
                                "Davom etilsinmi?"}, "task": None}  # fmt: skip
        if out.get("error"):
            raise ApiError("BAD_REQUEST", out["error"])
        api.ui_push({"kind": "task", "task": out})
        return {"confirm": None, "task": task_dto(out)}
    # ----- Office (opens on the PC screen) -----
    if route == "/api/v1/office/{kind}":
        from nexvara.app.api import OFFICE_TASKS

        if args["kind"] not in OFFICE_TASKS:
            raise ApiError("NOT_FOUND", "Noma’lum Office amali")
        snap = api._start(args["kind"])
        api.ui_push({"kind": "task", "task": snap})
        return {"task": task_dto(snap)}
    # ----- PC screen and files -----
    if route == "/api/v1/screen":
        _screen(h, api)
        return None
    if route == "/api/v1/files/search":
        query = (q.get("q") or [""])[0]
        ext = (q.get("ext") or [""])[0]
        out = api.files_search(query, "", ext)
        if not out.get("ok"):
            raise ApiError("BAD_REQUEST", out.get("error") or "Qidirib bo‘lmadi")
        files = []
        for f in out["files"][:60]:
            p = Path(f["path"])
            if _secret(p.resolve()):
                continue
            _grant(srv, dev, f["path"], "found", FOUND_TTL)
            files.append({k: f[k] for k in ("path", "name", "folder", "ext", "size", "modified")})
        return {"files": files}
    if route == "/api/v1/files/share":
        p = _found_file(srv, dev, str(body().get("path", "")))
        from nexvara.remote import MAX_UPLOAD

        if p.stat().st_size > MAX_UPLOAD:
            raise ApiError("PAYLOAD_TOO_LARGE")
        _grant(srv, dev, str(p), "shared", SHARED_TTL)
        return {"path": str(p), "name": p.name, "size": p.stat().st_size}
    if route == "/api/v1/files/open":
        from nexvara.remote import blocked_upload

        p = _found_file(srv, dev, str(body().get("path", "")))
        if blocked_upload(p.name):  # never start a program from the phone
            raise ApiError(
                "BAD_REQUEST", "Dastur va skriptlarni telefondan ishga tushirib bo‘lmaydi"
            )
        api.ui_push({"kind": "phone_file", "name": p.name, "path": str(p)})
        return {"opened": bool(api.open_file(str(p)))}
    if route == "/api/v1/files/zip":
        from nexvara import fileagent
        from nexvara.remote import MAX_UPLOAD

        paths = body().get("paths") or []
        if not isinstance(paths, list) or not 1 <= len(paths) <= 50:
            raise ApiError("BAD_REQUEST", "1–50 ta fayl tanlang")
        items = [str(_found_file(srv, dev, str(x))) for x in dict.fromkeys(map(str, paths))]
        try:
            out = Path(fileagent.make_zip(items))
        except (OSError, ValueError) as e:
            raise ApiError("BAD_REQUEST", f"ZIP qilib bo‘lmadi: {e}") from e
        size = out.stat().st_size
        _grant(srv, dev, str(out), "found", FOUND_TTL)
        if size <= MAX_UPLOAD:  # the phone may take the archive right away
            _grant(srv, dev, str(out), "shared", SHARED_TTL)
        api.ui_push({"kind": "phone_file", "name": out.name, "path": str(out)})
        return {"path": str(out), "name": out.name, "size": size, "files": len(items),
                "downloadable": size <= MAX_UPLOAD}  # fmt: skip
    if route == "/api/v1/files/unzip":
        import zipfile

        from nexvara import fileagent

        p = _found_file(srv, dev, str(body().get("path", "")))
        if p.suffix.lower() != ".zip":
            raise ApiError("BAD_REQUEST", "Faqat .zip faylni ochish mumkin")
        try:
            folder = Path(fileagent.unzip(str(p)))
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            raise ApiError("BAD_REQUEST", f"Arxivdan chiqarib bo‘lmadi: {e}") from e
        count = sum(1 for f in folder.rglob("*") if f.is_file())
        return {"folder": str(folder), "name": folder.name, "files": count}
    # ----- Google -----
    if route == "/api/v1/account":
        return _account(api, dev, srv.store)
    if route == "/api/v1/account/link":
        from nexvara.account import AuthError

        web_id = str(api.get_settings().get("google", {}).get("android_web_client_id") or "")
        try:
            who = api._google().verify_phone(str(body().get("id_token", "")), web_id)
        except AuthError as e:
            raise ApiError("BAD_REQUEST", str(e)) from e
        srv.store.set_google(dev["id"], who["email"])
        return {"linked": True, **who}
    raise ApiError("NOT_FOUND")
