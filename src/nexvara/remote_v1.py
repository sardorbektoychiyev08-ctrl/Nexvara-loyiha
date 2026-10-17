"""Phone API v1 (/api/v1/...): the contract the native Android app is built against.

Documented in docs/api/MOBILE_API.md and docs/api/openapi.yaml; `ROUTES` is checked
against openapi.yaml by the unit tests, so the docs cannot silently drift.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from nexvara import __version__, config, remote_v1_sections
from nexvara.protocol import MIN_CLIENT_PROTOCOL, PROTOCOL, ApiError, ok, task_dto

# (method, path pattern, needs a device token)
ROUTES: list[tuple[str, str, bool]] = [
    ("GET", "/api/v1/info", False),
    ("POST", "/api/v1/pair", False),
    ("GET", "/api/v1/session", True),
    ("POST", "/api/v1/session/rotate", True),
    ("POST", "/api/v1/session/logout", True),
    ("POST", "/api/v1/chat", True),
    ("POST", "/api/v1/confirm", True),
    ("GET", "/api/v1/tasks", True),
    ("GET", "/api/v1/tasks/watch", True),
    ("GET", "/api/v1/tasks/{id}", True),
    ("POST", "/api/v1/tasks/{id}/cancel", True),
    ("POST", "/api/v1/files", True),
    ("GET", "/api/v1/files", True),
    ("GET", "/api/v1/sync", True),
    ("POST", "/api/v1/sync", True),
    *remote_v1_sections.ROUTES,  # Home, AI spend, Memory, Teach, Workflows, BI, textbooks...
]
log = logging.getLogger(__name__)
WATCH_MAX = 25.0  # seconds a long-poll may hang
_ID = re.compile(r"^[0-9a-f]{6,32}$")


def _match(method: str, path: str) -> tuple[str, bool, dict[str, str]] | None:
    for m, pattern, auth in ROUTES:
        if m != method:
            continue
        rx = "^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern) + "$"
        hit = re.match(rx, path)
        if hit:
            return pattern, auth, hit.groupdict()
    return None


def _etag(tasks: list[dict[str, Any]]) -> str:
    sig = [(t.get("id"), t.get("status"), len(t.get("steps") or []), t.get("finished_at"))
           for t in tasks]  # fmt: skip
    return hashlib.sha1(json.dumps(sig, default=str).encode()).hexdigest()[:16]


def _allowed_files(api: Any) -> set[str]:
    return {f for t in api.list_tasks()[:200] for f in task_dto(t)["files"]}


def handle(h: Any, method: str) -> None:
    """`h` is the remote._Handler serving this request."""
    srv = h.server_ref
    u = urlparse(h.path)
    q = parse_qs(u.query)
    try:
        from nexvara.remote import allowed_client

        if not allowed_client(h.client_address[0]):
            raise ApiError("AUTH_REQUIRED", "Faqat uy/ish tarmog‘i yoki Tailscale orqali")
        if not srv.limiter.allow(h.client_address[0]):
            raise ApiError("RATE_LIMITED")
        client = h.headers.get("X-Nexvara-Protocol", "")
        if client.isdigit() and int(client) < MIN_CLIENT_PROTOCOL:
            raise ApiError("UNSUPPORTED_PROTOCOL")
        found = _match(method, u.path)
        if found is None:
            raise ApiError("NOT_FOUND")
        route, needs_auth, args = found
        dev = None
        if needs_auth:
            auth = h.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else ""
            dev = srv.store.check(token, h.client_address[0])
            if dev is None:
                limiter = getattr(srv, "bad_auth", None)
                if limiter is not None and not limiter.allow(h.client_address[0]):
                    raise ApiError("RATE_LIMITED")  # someone is guessing tokens
                raise ApiError("AUTH_REQUIRED")
            if dev.get("expired"):
                raise ApiError("TOKEN_EXPIRED")
        rid = h.headers.get("X-Request-Id", "")[:64] if method == "POST" else ""
        if rid and dev is not None:
            seen = srv.remember(f"v1:{dev['id']}:{rid}")
            if seen is not None:
                h._json(ok(seen))
                return
        data = _route(h, srv, route, args, q, dev)
        if data is None:  # a file was sent
            return
        if rid and dev is not None:
            srv.remember(f"v1:{dev['id']}:{rid}", data)
        h._json(ok(data))
    except ApiError as e:
        extra = {"Retry-After": "30"} if e.code == "RATE_LIMITED" else None
        body = json.dumps(e.body(), ensure_ascii=False).encode("utf-8")
        h._send(e.status, body, "application/json; charset=utf-8", extra)
    except (ValueError, KeyError, TypeError) as e:
        err = ApiError("BAD_REQUEST", f"So‘rov noto‘g‘ri: {e}")
        h._send(err.status, json.dumps(err.body(), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8")  # fmt: skip
    except Exception:  # never drop the connection: the phone gets a retryable INTERNAL
        log.exception("phone API %s %s failed", method, h.path.split("?")[0])
        err = ApiError("INTERNAL")
        h._send(err.status, json.dumps(err.body(), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8")  # fmt: skip


def _json_body(h: Any) -> dict[str, Any]:
    raw = h._body()
    data = json.loads(raw) if raw else {}
    if not isinstance(data, dict):
        raise ValueError("JSON obyekt kerak")
    return data


def _addresses() -> list[dict[str, str]]:
    from nexvara.remote import addresses

    try:
        return addresses()
    except Exception:
        return []


def _session(srv: Any, dev: dict[str, Any]) -> dict[str, Any]:
    from nexvara.remote import TOKEN_MAX_DAYS, TOKEN_ROTATE_DAYS, server_id

    age = time.time() - dev["token_created"]
    return {
        "device_id": dev["id"],
        "device_name": dev["name"],
        "pc_name": socket.gethostname(),
        "server_id": server_id(),
        "token_expires_at": dev["token_created"] + TOKEN_MAX_DAYS * 86400,
        "rotate_recommended": age > TOKEN_ROTATE_DAYS * 86400,
        "port": srv.port,
        "addresses": _addresses(),  # the phone keeps them to reconnect from another network
    }


def _route(h: Any, srv: Any, route: str, args: dict[str, str], q: dict[str, list[str]],
           dev: dict[str, Any] | None) -> dict[str, Any] | None:  # fmt: skip
    from nexvara.remote import MAX_UPLOAD, TOKEN_MAX_DAYS, server_id

    api = srv.api
    if route in remote_v1_sections.HANDLED:
        assert dev is not None
        return remote_v1_sections.route(h, srv, route, args, q, dev, lambda: _json_body(h))
    if route == "/api/v1/info":
        return {
            "protocol": PROTOCOL,
            "min_client_protocol": MIN_CLIENT_PROTOCOL,
            "app": "NEXVARA Personal",
            "app_version": __version__,
            "pc_name": socket.gethostname(),
            "server_id": server_id(),
            "pairing_open": bool(srv.code) and time.time() < srv.code_expires,
            "max_upload_bytes": MAX_UPLOAD,
            "port": srv.port,
            "addresses": _addresses(),
        }
    if route == "/api/v1/pair":
        if not srv.pair_limiter.allow(h.client_address[0]):
            raise ApiError("RATE_LIMITED")
        body = _json_body(h)
        out = srv.pair(
            str(body.get("code", "")),
            str(body.get("device_name", "")),
            platform=str(body.get("platform", "android")),
            app_version=str(body.get("app_version", "")),
            install_id=str(body.get("install_id", "")),
        )
        if "token" not in out:
            raise ApiError(out["error_code"], out["error"])
        return {
            "token": out["token"],
            "device_id": out["device_id"],
            "server_id": server_id(),
            "pc_name": socket.gethostname(),
            "token_expires_at": time.time() + TOKEN_MAX_DAYS * 86400,
        }
    assert dev is not None
    if route == "/api/v1/session":
        return _session(srv, dev)
    if route == "/api/v1/session/rotate":
        token = srv.store.rotate(dev["id"])
        return {"token": token, "token_expires_at": time.time() + TOKEN_MAX_DAYS * 86400}
    if route == "/api/v1/session/logout":
        srv.store.revoke(dev["id"])
        return {"logged_out": True}
    if route == "/api/v1/chat":
        text = str(_json_body(h).get("text", "")).strip()[:4000]
        if not text:
            raise ApiError("BAD_REQUEST", "Matn bo‘sh")
        out = api.chat(text)
        # The PC window shows the phone's message and follows its task / opens the dashboard.
        api.ui_push({"kind": "phone_chat", "text": text, "reply": out})
        return _chat_reply(out)
    if route == "/api/v1/confirm":
        body = _json_body(h)
        out = api.confirm_ai(str(body.get("token", "")), bool(body.get("yes")))
        api.ui_push({"kind": "phone_chat", "text": "Ha" if body.get("yes") else "Yo‘q",
                     "reply": out})  # fmt: skip
        return _chat_reply(out)
    if route == "/api/v1/tasks":
        limit = max(1, min(int((q.get("limit") or ["20"])[0]), 100))
        tasks = api.list_tasks()[:limit]
        return {"tasks": [task_dto(t) for t in tasks], "etag": _etag(tasks[:20])}
    if route == "/api/v1/tasks/watch":
        # Long-poll: returns when any of the last 20 tasks changes, or after `wait` seconds.
        etag = (q.get("etag") or [""])[0]
        wait = max(0.0, min(float((q.get("wait") or ["25"])[0]), WATCH_MAX))
        deadline = time.monotonic() + wait
        while True:
            tasks = api.list_tasks()[:20]
            now_tag = _etag(tasks)
            if now_tag != etag or time.monotonic() >= deadline:
                return {"changed": now_tag != etag, "etag": now_tag,
                        "tasks": [task_dto(t) for t in tasks]}  # fmt: skip
            time.sleep(0.5)
    if route == "/api/v1/tasks/{id}":
        task_id = args["id"]
        snap = api.get_task(task_id) if _ID.match(task_id) else None
        if snap is None:
            snap = next((t for t in api.list_tasks() if t.get("id") == task_id), None)
        if snap is None:
            raise ApiError("NOT_FOUND", "Vazifa topilmadi")
        return task_dto(snap)
    if route == "/api/v1/tasks/{id}/cancel":
        if not _ID.match(args["id"]):
            raise ApiError("NOT_FOUND", "Vazifa topilmadi")
        return {"cancelled": bool(api.cancel_task(args["id"]))}
    if route == "/api/v1/files" and h.command == "POST":
        return _upload(h, api, MAX_UPLOAD)
    if route == "/api/v1/files":
        path = (q.get("path") or [""])[0]
        p = Path(path)
        shared = dev is not None and remote_v1_sections.granted(srv, dev, path)
        if (path not in _allowed_files(api) and not shared) or not p.is_file():
            raise ApiError("NOT_FOUND", "Fayl topilmadi")
        data = p.read_bytes()
        name = p.name.encode("ascii", "replace").decode()
        h._send(200, data, "application/octet-stream", {
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-SHA256": hashlib.sha256(data).hexdigest(),
        })  # fmt: skip
        return None
    if route == "/api/v1/sync" and h.command == "GET":
        return api.sync_export()
    if route == "/api/v1/sync":
        raw = h._body(8 << 20)
        body = json.loads(raw) if raw else {}
        recs = body.get("records") if isinstance(body, dict) else None
        if not isinstance(recs, list):
            raise ApiError("BAD_REQUEST", "records ro‘yxati kerak")
        return api.sync_import(f"phone-{dev['id']}", recs)
    raise ApiError("NOT_FOUND")


def _chat_reply(out: dict[str, Any]) -> dict[str, Any]:
    reply: dict[str, Any] = {"reply": out.get("reply", ""), "confirm": None, "task": None}
    if out.get("confirm"):
        reply["confirm"] = {"token": out["confirm"], "text": out.get("reply", "")}
    if out.get("task"):
        reply["task"] = task_dto(out["task"])
    if out.get("open_bi"):
        reply["open_bi"] = True  # the dashboard opens on the PC screen
    return reply


def _upload(h: Any, api: Any, limit: int) -> dict[str, Any]:
    from nexvara.fileagent import free_name

    n = int(h.headers.get("Content-Length") or 0)
    if n > limit:
        raise ApiError("PAYLOAD_TOO_LARGE")
    name = Path(unquote(h.headers.get("X-Filename", "fayl"))).name
    name = "".join(c for c in name if c not in '<>:"/\\|?*' and ord(c) >= 32).strip() or "fayl"
    from nexvara.remote import blocked_upload

    if blocked_upload(name):
        raise ApiError("BAD_REQUEST", "Bu turdagi fayl (dastur, skript yoki yorliq) qabul "
                       "qilinmaydi. Hujjat, PDF, rasm yoki arxiv yuboring.")  # fmt: skip
    body = h._body(limit)
    want = h.headers.get("X-Content-SHA256", "").lower()
    digest = hashlib.sha256(body).hexdigest()
    if want and want != digest:
        raise ApiError("BAD_REQUEST", "Fayl yo‘lda buzilgan (SHA-256 mos emas). Qayta yuboring.")
    folder = config.data_dir() / "Telefondan"
    folder.mkdir(parents=True, exist_ok=True)
    target = free_name(folder / name)
    target.write_bytes(body)
    api.set_context_file(str(target))
    api.ui_push({"kind": "phone_file", "name": target.name, "path": str(target)})
    return {"path": str(target), "name": target.name, "size": len(body), "sha256": digest}
