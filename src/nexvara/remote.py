"""Devices: control NEXVARA from a phone on the same Wi-Fi.

The phone opens https://<PC>:<port>/ in its browser (a QR code on the Devices page),
pairs with a one-time 6-digit code and gets a device token. Security:
- HTTPS with a certificate made on this PC (the phone shows a one-time warning);
- one-time pairing code valid 10 minutes, locked after 5 wrong attempts;
- tokens are stored only as SHA-256 hashes; a device can be revoked at any time;
- tokens are rotated weekly (the old one works until the new one is used) and expire
  after 30 days without rotation; requests carry an id so a retried command never runs twice;
- requests are rate-limited per address;
- off by default; nothing is reachable from the internet (local network only).

The native Android app uses the versioned API in `remote_v1.py` (/api/v1/...); the
browser page keeps the original /api/... routes.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import json
import secrets
import socket
import sqlite3
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from nexvara import config

DEFAULT_PORT = 8765
CODE_TTL = 600
MAX_BAD_CODES = 5
TOKEN_ROTATE_DAYS = 7
TOKEN_MAX_DAYS = 30  # a token not rotated for this long stops working (re-pair)
MAX_UPLOAD = 50 * 1024 * 1024
UI_FILE = Path(__file__).parent / "app" / "ui" / "mobile.html"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created REAL NOT NULL,
    token_created REAL NOT NULL,
    last_seen REAL,
    last_ip TEXT NOT NULL DEFAULT ''
);
"""
# Columns added after the first release (old app.db files get them on open).
_MIGRATIONS = {
    "prev_hash": "TEXT",  # the previous token, valid until the new one is first used
    "platform": "TEXT NOT NULL DEFAULT 'browser'",
    "app_version": "TEXT NOT NULL DEFAULT ''",
    "install_id": "TEXT NOT NULL DEFAULT ''",
    "google_email": "TEXT NOT NULL DEFAULT ''",  # set when the phone proved it is the owner
}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def lan_ip() -> str:
    """This PC's address in the local network (no packet is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())


class DeviceStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.data_dir() / "app.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(_SCHEMA)
            have = {r[1] for r in db.execute("PRAGMA table_info(devices)")}
            for col, decl in _MIGRATIONS.items():
                if col not in have:
                    try:
                        db.execute(f"ALTER TABLE devices ADD COLUMN {col} {decl}")
                    except sqlite3.OperationalError as e:  # another thread added it first
                        if "duplicate column" not in str(e):
                            raise

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    def add(self, name: str, platform: str = "browser", app_version: str = "",
            install_id: str = "") -> tuple[int, str]:  # fmt: skip
        token = secrets.token_urlsafe(32)
        now = time.time()
        name = (name or "Telefon").strip()[:60] or "Telefon"
        with self._lock, self._db() as db:
            if install_id:  # the same phone pairing again replaces its old entry
                db.execute("DELETE FROM devices WHERE install_id = ?", (install_id[:64],))
            cur = db.execute(
                "INSERT INTO devices (name, token_hash, created, token_created, platform, "
                "app_version, install_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, _hash(token), now, now, platform[:20], app_version[:20], install_id[:64]),
            )
            return int(cur.lastrowid), token

    def check(self, token: str, ip: str = "") -> dict[str, Any] | None:
        """The device owning `token`, or None. An expired token gives {"expired": True}."""
        if not token:
            return None
        h = _hash(token)
        with self._lock, self._db() as db:
            r = db.execute(
                "SELECT id, name, token_created, token_hash = ?, platform FROM devices "
                "WHERE token_hash = ? OR prev_hash = ?",
                (h, h, h),
            ).fetchone()
            if r is None:
                return None
            if time.time() - r[2] > TOKEN_MAX_DAYS * 86400:
                return {"id": r[0], "name": r[1], "token_created": r[2], "expired": True}
            if r[3]:  # the new token is in use: the previous one stops working
                db.execute("UPDATE devices SET prev_hash = NULL WHERE id = ?", (r[0],))
            db.execute("UPDATE devices SET last_seen = ?, last_ip = ? WHERE id = ?",
                       (time.time(), ip, r[0]))  # fmt: skip
        return {"id": r[0], "name": r[1], "token_created": r[2], "platform": r[4]}

    def rotate(self, device_id: int) -> str:
        """A new token; the current one keeps working until the new one is first used
        (so a reply lost on the way does not lock the phone out)."""
        token = secrets.token_urlsafe(32)
        with self._lock, self._db() as db:
            db.execute(
                "UPDATE devices SET prev_hash = token_hash, token_hash = ?, token_created = ? "
                "WHERE id = ?",
                (_hash(token), time.time(), device_id),
            )
        return token

    def set_google(self, device_id: int, email: str) -> None:
        with self._lock, self._db() as db:
            db.execute("UPDATE devices SET google_email = ? WHERE id = ?", (email[:120], device_id))

    def google_email(self, device_id: int) -> str:
        with self._db() as db:
            r = db.execute("SELECT google_email FROM devices WHERE id = ?", (device_id,)).fetchone()
        return r[0] if r else ""

    def revoke(self, device_id: int) -> None:
        with self._lock, self._db() as db:
            db.execute("DELETE FROM devices WHERE id = ?", (device_id,))

    def all(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute(
                "SELECT id, name, created, last_seen, last_ip, platform, app_version "
                "FROM devices ORDER BY id"
            ).fetchall()
        return [{"id": r[0], "name": r[1], "created": r[2], "last_seen": r[3], "last_ip": r[4],
                 "platform": r[5], "app_version": r[6]} for r in rows]  # fmt: skip


def server_id() -> str:
    """A random id of this PC, so the phone can tell Work PC from Home PC."""
    p = config.data_dir() / "remote" / "server_id.txt"
    try:
        sid = p.read_text(encoding="ascii").strip()
        if sid:
            return sid
    except OSError:
        pass
    p.parent.mkdir(parents=True, exist_ok=True)
    sid = secrets.token_hex(8)
    p.write_text(sid, encoding="ascii")
    return sid


def cert_fingerprint(cert_path: Path) -> str:
    """SHA-256 of the certificate (DER), hex. The QR code carries it so the Android app
    pins this exact certificate instead of trusting any self-signed one."""
    der = ssl.PEM_cert_to_DER_cert(cert_path.read_text(encoding="ascii"))
    return hashlib.sha256(der).hexdigest()


class RateLimiter:
    """Sliding window per key (client address)."""

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            allowed = len(hits) < self.limit
            if allowed:
                hits.append(now)
            self._hits[key] = hits
            return allowed


def ensure_certificate(folder: Path, ip: str) -> tuple[Path, Path]:
    """A self-signed certificate for this PC (made once, renewed when the IP changes)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    folder.mkdir(parents=True, exist_ok=True)
    cert_p, key_p, ip_p = folder / "cert.pem", folder / "key.pem", folder / "ip.txt"
    if cert_p.is_file() and key_p.is_file() and ip_p.is_file() and ip_p.read_text() == ip:
        return cert_p, key_p
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "NEXVARA " + socket.gethostname())])
    now = dt.datetime.now(dt.UTC)
    alt = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    try:
        alt.append(x509.IPAddress(ipaddress.ip_address(ip)))
    except ValueError:
        pass
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .sign(key, hashes.SHA256())
    )
    key_p.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                        serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))  # fmt: skip
    cert_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ip_p.write_text(ip)
    return cert_p, key_p


class RemoteServer:
    """HTTPS server for paired phones; `api` is the app's Api (chat, tasks...)."""

    def __init__(self, api: Any, store: DeviceStore | None = None, port: int = DEFAULT_PORT,
                 use_tls: bool = True, host: str = "0.0.0.0") -> None:  # fmt: skip
        self.api = api
        self.store = store or DeviceStore()
        self.port = port
        self.use_tls = use_tls
        self.host = host
        self.httpd: ThreadingHTTPServer | None = None
        self.code = ""
        self.code_expires = 0.0
        self.bad_codes = 0
        self._seen: dict[str, tuple[float, dict]] = {}  # request id -> reply (idempotency)
        self._lock = threading.Lock()
        self.fingerprint = ""
        self.limiter = RateLimiter(240)  # requests per minute per address
        self.pair_limiter = RateLimiter(10)

    # ----- lifecycle -----
    @property
    def running(self) -> bool:
        return self.httpd is not None

    def start(self) -> None:
        if self.httpd is not None:
            return
        handler = type("Handler", (_Handler,), {"server_ref": self})
        httpd = ThreadingHTTPServer((self.host, self.port), handler)
        httpd.daemon_threads = True
        if self.use_tls:
            cert, key = ensure_certificate(config.data_dir() / "remote", lan_ip())
            self.fingerprint = cert_fingerprint(cert)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(cert, key)
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        self.port = httpd.server_address[1]
        self.httpd = httpd
        threading.Thread(target=httpd.serve_forever, name="remote", daemon=True).start()
        self.new_code()

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.code = ""

    def url(self) -> str:
        return f"{'https' if self.use_tls else 'http'}://{lan_ip()}:{self.port}/"

    def pair_link(self) -> str:
        """What the QR code holds: the browser opens the URL (and reads p=), the Android
        app reads all fields: p = code, fp = certificate SHA-256, sid = this PC's id."""
        link = f"{self.url()}#p={self.code}&sid={server_id()}"
        return link + (f"&fp={self.fingerprint}" if self.fingerprint else "")

    def new_code(self) -> str:
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.code_expires = time.time() + CODE_TTL
        self.bad_codes = 0
        return self.code

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {"running": self.running, "devices": self.store.all()}
        if self.running:
            left = int(self.code_expires - time.time())
            code_ok = bool(self.code) and left > 0 and self.bad_codes < MAX_BAD_CODES
            out.update({
                "url": self.url(),
                "code": self.code if code_ok else "",
                "code_left": max(0, left),
                "locked": self.bad_codes >= MAX_BAD_CODES,
                "fingerprint": self.fingerprint,
            })  # fmt: skip
            if code_ok:
                import segno

                out["qr_svg"] = segno.make(self.pair_link(), error="m").svg_inline(
                    scale=5, dark="#121933", light="#ffffff"
                )
        return out

    # ----- requests -----
    def pair(self, code: str, name: str, **device: str) -> dict[str, Any]:
        """`error_code` is the protocol code (protocol.ERRORS) for the v1 API."""
        with self._lock:
            if self.bad_codes >= MAX_BAD_CODES:
                return {"error": "Ko‘p noto‘g‘ri urinish. Kompyuterda yangi kod oling.",
                        "error_code": "PAIRING_LOCKED"}  # fmt: skip
            if not self.code or time.time() > self.code_expires:
                return {"error": "Kod eskirgan. Kompyuterdagi Devices bo‘limida yangi kod oling.",
                        "error_code": "PAIRING_CODE_EXPIRED"}  # fmt: skip
            if not secrets.compare_digest(str(code).strip().encode(), self.code.encode()):
                self.bad_codes += 1
                return {"error": "Kod noto‘g‘ri", "error_code": "PAIRING_CODE_INVALID"}
            self.code = ""  # one-time
        device_id, token = self.store.add(name, **device)
        return {"token": token, "device_id": device_id}

    def remember(self, request_id: str, reply: dict | None = None) -> dict | None:
        """Idempotency: a retried request (same id) gets the first reply, not a second run."""
        now = time.time()
        with self._lock:
            for k in [k for k, (t, _r) in self._seen.items() if now - t > 600]:
                del self._seen[k]
            if reply is None:
                hit = self._seen.get(request_id)
                return hit[1] if hit else None
            self._seen[request_id] = (now, reply)
            return reply


def _snap(t: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "title", "status", "error", "created_at", "finished_at")
    out = {k: t.get(k) for k in keep}
    out["steps"] = [{"name": s["name"], "status": s["status"], "detail": s.get("detail", "")}
                    for s in t.get("steps") or []]  # fmt: skip
    res = t.get("result") or {}
    out["files"] = [res[k] for k in ("path", "pdf") if isinstance(res.get(k), str) and res.get(k)]
    out["report"] = res.get("report") or []
    return out


class _Handler(BaseHTTPRequestHandler):
    server_ref: RemoteServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet console
        pass

    # ----- helpers -----
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")  # fmt: skip

    def _body(self, limit: int = 1 << 20) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("juda katta")
        return self.rfile.read(n) if n else b""

    def _device(self) -> dict[str, Any] | None:
        auth = self.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else ""
        dev = self.server_ref.store.check(token, self.client_address[0])
        return None if dev is None or dev.get("expired") else dev

    def _limited(self) -> bool:
        if self.server_ref.limiter.allow(self.client_address[0]):
            return False
        self._send(429, b'{"error": "rate limited"}', "application/json", {"Retry-After": "30"})
        return True

    def _v1(self, method: str) -> bool:
        if not self.path.startswith("/api/v1/"):
            return False
        from nexvara.remote_v1 import handle

        handle(self, method)
        return True

    # ----- routes -----
    def do_GET(self) -> None:  # noqa: N802
        if self._v1("GET"):
            return
        if self._limited():
            return
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            csp = {"Content-Security-Policy": "default-src 'self' 'unsafe-inline' data: blob:"}
            self._send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8", csp)
            return
        dev = self._device()
        if dev is None:
            self._json({"error": "unauthorized"}, 401)
            return
        api = self.server_ref.api
        if u.path == "/api/hello":
            age = time.time() - dev["token_created"]
            out = {"device": dev["name"], "pc": socket.gethostname()}
            if age > TOKEN_ROTATE_DAYS * 86400:
                out["new_token"] = self.server_ref.store.rotate(dev["id"])
            self._json(out)
        elif u.path == "/api/tasks":
            self._json([_snap(t) for t in api.list_tasks()[:20]])
        elif u.path == "/api/file":
            path = (parse_qs(u.query).get("path") or [""])[0]
            allowed = {f for t in api.list_tasks()[:200] for f in _snap(t)["files"]}
            p = Path(path)
            if path not in allowed or not p.is_file():
                self._json({"error": "fayl topilmadi"}, 404)
                return
            name = p.name.encode("ascii", "replace").decode()
            self._send(200, p.read_bytes(), "application/octet-stream",
                       {"Content-Disposition": f'attachment; filename="{name}"'})  # fmt: skip
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self._v1("POST"):
            return
        if self._limited():
            return
        u = urlparse(self.path)
        srv = self.server_ref
        try:
            if u.path == "/api/pair":
                if not srv.pair_limiter.allow(self.client_address[0]):
                    self._json({"error": "Juda ko‘p urinish. Biroz kuting."}, 429)
                    return
                data = json.loads(self._body() or b"{}")
                out = srv.pair(str(data.get("code", "")), str(data.get("name", "")))
                out.pop("error_code", None)
                self._json(out, 200 if "token" in out else 403)
                return
            dev = self._device()
            if dev is None:
                self._json({"error": "unauthorized"}, 401)
                return
            api = srv.api
            rid = self.headers.get("X-Request-Id", "")
            if rid:
                seen = srv.remember(f"{dev['id']}:{rid}")
                if seen is not None:
                    self._json(seen)
                    return
            if u.path == "/api/chat":
                data = json.loads(self._body() or b"{}")
                out = api.chat(str(data.get("text", ""))[:4000])
                out = {k: v for k, v in out.items() if k in ("reply", "confirm", "task", "open_bi")}
                if out.get("task"):
                    out["task"] = _snap(out["task"])
            elif u.path == "/api/confirm":
                data = json.loads(self._body() or b"{}")
                out = api.confirm_ai(str(data.get("token", "")), bool(data.get("yes", True)))
                out = {k: v for k, v in out.items() if k in ("reply", "confirm", "task")}
                if out.get("task"):
                    out["task"] = _snap(out["task"])
            elif u.path.startswith("/api/cancel/"):
                out = {"ok": api.cancel_task(u.path.rsplit("/", 1)[-1])}
            elif u.path == "/api/upload":
                from urllib.parse import unquote

                name = Path(unquote(self.headers.get("X-Filename", "fayl"))).name
                name = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or "fayl"
                body = self._body(MAX_UPLOAD)
                folder = config.data_dir() / "Telefondan"
                folder.mkdir(parents=True, exist_ok=True)
                from nexvara.fileagent import free_name

                target = free_name(folder / name)
                target.write_bytes(body)
                api.set_context_file(str(target))
                out = {"path": str(target), "name": target.name,
                       "reply": f"«{target.name}» kompyuterga saqlandi ({target.parent}). Endi "
                       "u bilan ishlash buyrug‘ini yozing, masalan «shu faylni formatla va "
                       "PDF qilib saqla»."}  # fmt: skip
            else:
                self._json({"error": "not found"}, 404)
                return
            if rid:
                srv.remember(f"{dev['id']}:{rid}", out)
            self._json(out)
        except (ValueError, KeyError) as e:
            self._json({"error": str(e)}, 400)
