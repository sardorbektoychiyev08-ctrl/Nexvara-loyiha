"""Sync of settings, memory facts and Teach rules between the user's devices.

Model: every synced item has a stable `uid`, the time of its last change (`updated`) and the
device that made it. Deletions are kept as tombstones. Merging is last-writer-wins per item
(ties broken by device id), so two devices that each changed something different both keep
their change, and the same item changed on both ends converges to the newer edit.

What is synced: facts, rules (text, app, on/off) and the harmless settings in SYNC_SETTINGS.
Never synced: API keys, tokens, `ai.enabled` (a device must not switch on paid AI for
another), machine-specific paths (update channel, sync folder, phone port).

Transports (the data model is the same for all):
- FolderTransport: a folder both PCs see (OneDrive/Google Drive desktop folder, network
  share, USB). Each device writes its own `<device>.nxsync`, encrypted with the user's sync
  passphrase (scrypt → AES-256-GCM). Without the passphrase the files are unreadable.
- the phone: GET/POST /api/v1/sync over the paired TLS connection (remote_v1.py).
- DriveTransport: Google Drive appDataFolder (needs Google login with the drive.appdata
  scope); same encrypted files.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara.appdata import DEFAULT_SETTINGS as DEFAULTS

SYNC_SETTINGS = (
    "theme", "test_count", "test_variants", "keep_office_open",
    "ai.daily_budget_usd", "ai.monthly_budget_usd", "ai.confirm_over_usd",
    "ai.send_textbook_text",
)  # fmt: skip
FORMAT = 1
MAGIC = b"NXS1"
_AAD = b"NEXVARA-SYNC-1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_items (
    kind TEXT NOT NULL,
    uid TEXT NOT NULL,
    local_id TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL DEFAULT '{}',
    updated REAL NOT NULL,
    device TEXT NOT NULL,
    deleted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (kind, uid)
);
"""


class SyncError(Exception):
    """Shown to the user (Uzbek)."""


def _hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _get(d: dict[str, Any], key: str) -> Any:
    for part in key.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d


def _nested(key: str, value: Any) -> dict[str, Any]:
    out: dict[str, Any] = {key.split(".")[-1]: value}
    for part in reversed(key.split(".")[:-1]):
        out = {part: out}
    return out


# ---------------- encryption ----------------


def _key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)


def seal(obj: Any, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt, nonce = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(passphrase, salt)).encrypt(nonce, json.dumps(obj).encode("utf-8"), _AAD)
    return MAGIC + salt + nonce + ct


def unseal(blob: bytes, passphrase: str) -> Any:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not blob.startswith(MAGIC) or len(blob) < 4 + 16 + 12 + 16:
        raise SyncError("Sinxron fayli buzilgan")
    salt, nonce, ct = blob[4:20], blob[20:32], blob[32:]
    try:
        return json.loads(AESGCM(_key(passphrase, salt)).decrypt(nonce, ct, _AAD))
    except InvalidTag as e:
        raise SyncError("Sinxron paroli boshqa qurilmadagidan farq qiladi") from e


# ---------------- the engine ----------------


class SyncEngine:
    def __init__(self, mem: Any, settings: Any, device: str, path: Path | None = None) -> None:
        self.mem = mem
        self.settings = settings
        self.device = device
        self.path = path or mem.path
        self._lock = threading.Lock()
        with self._db() as db:
            db.executescript(_SCHEMA)

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    # what exists locally right now: kind -> local_id -> data
    def _local(self) -> dict[str, dict[str, dict[str, Any]]]:
        s = self.settings.load()
        return {
            "fact": {str(f["id"]): {"text": f["text"]} for f in self.mem.facts()},
            "rule": {
                str(r.id): {"app": r.app, "text": r.text, "enabled": bool(r.enabled)}
                for r in self.mem.rules()
            },  # fmt: skip
            "setting": {k: {"value": _get(s, k)} for k in SYNC_SETTINGS},
        }

    def scan(self) -> int:
        """Record local changes since the last scan (new, edited, deleted items)."""
        now, changed = time.time(), 0
        local = self._local()
        with self._lock, self._db() as db:
            rows = db.execute(
                "SELECT kind, uid, local_id, hash, deleted FROM sync_items"
            ).fetchall()
            seen: set[tuple[str, str]] = set()
            for kind, uid, local_id, h, deleted in rows:
                item = local.get(kind, {}).get(local_id)
                if item is not None:
                    seen.add((kind, local_id))
                    if _hash(item) != h or deleted:
                        db.execute(
                            "UPDATE sync_items SET hash=?, data=?, updated=?, device=?, "
                            "deleted=0 WHERE kind=? AND uid=?",
                            (_hash(item), json.dumps(item), now, self.device, kind, uid),
                        )
                        changed += 1
                elif not deleted and kind != "setting":
                    db.execute(
                        "UPDATE sync_items SET deleted=1, data='{}', hash='', updated=?, "
                        "device=? WHERE kind=? AND uid=?",
                        (now, self.device, kind, uid),
                    )
                    changed += 1
            for kind, items in local.items():
                for local_id, item in items.items():
                    if (kind, local_id) in seen:
                        continue
                    uid = local_id if kind == "setting" else uuid.uuid4().hex
                    # A setting still at its default must not override another device's choice.
                    at_default = kind == "setting" and item["value"] == _get(DEFAULTS, local_id)
                    db.execute("INSERT OR REPLACE INTO sync_items (kind, uid, local_id, hash, "
                               "data, updated, device) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (kind, uid, local_id, _hash(item), json.dumps(item),
                                0.0 if at_default else now, self.device))  # fmt: skip
                    changed += kind != "setting"
        return changed

    def records(self) -> list[dict[str, Any]]:
        with self._db() as db:
            rows = db.execute("SELECT kind, uid, data, updated, device, deleted FROM sync_items "
                              "ORDER BY kind, uid").fetchall()  # fmt: skip
        return [{"kind": k, "uid": u, "data": json.loads(d), "updated": t, "device": dv,
                 "deleted": bool(x)} for k, u, d, t, dv, x in rows]  # fmt: skip

    def merge(self, remote: list[dict[str, Any]]) -> int:
        """Apply remote records that are newer than ours. Returns how many were applied."""
        applied = 0
        for r in remote:
            try:
                kind, uid = str(r["kind"]), str(r["uid"])
                upd, dev = float(r["updated"]), str(r.get("device", ""))
                data = r.get("data") or {}
                deleted = bool(r.get("deleted"))
            except (KeyError, TypeError, ValueError):
                continue
            if kind not in ("fact", "rule", "setting") or not isinstance(data, dict):
                continue
            if kind == "setting" and uid not in SYNC_SETTINGS:
                continue  # never let a remote change anything outside the safe list
            with self._db() as db:
                row = db.execute("SELECT local_id, updated, device FROM sync_items WHERE kind=? "
                                 "AND uid=?", (kind, uid)).fetchone()  # fmt: skip
            if row is not None and (upd, dev) <= (row[1], row[2]):
                continue
            local_id = self._apply(kind, uid, row[0] if row else "", data, deleted)
            with self._lock, self._db() as db:
                db.execute("INSERT OR REPLACE INTO sync_items (kind, uid, local_id, hash, data, "
                           "updated, device, deleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (kind, uid, local_id, "" if deleted else _hash(self._local_item(
                               kind, local_id) or data), json.dumps({} if deleted else data),
                            upd, dev, int(deleted)))  # fmt: skip
            applied += 1
        return applied

    def _local_item(self, kind: str, local_id: str) -> dict[str, Any] | None:
        return self._local().get(kind, {}).get(local_id)

    def _apply(self, kind: str, uid: str, local_id: str, data: dict, deleted: bool) -> str:
        from nexvara.knowledge.textnorm import fold

        if kind == "setting":
            if not deleted:
                try:
                    self.settings.update(_nested(uid, data.get("value")))
                except (TypeError, ValueError):
                    pass  # an invalid value from another device is ignored
            return uid
        exists = local_id and self._local_item(kind, local_id) is not None
        if deleted:
            if exists:
                (self.mem.delete_fact if kind == "fact" else self.mem.delete_rule)(int(local_id))
            return local_id
        text = str(data.get("text", "")).strip()
        if not text:
            return local_id
        if kind == "fact":
            if exists:
                self.mem.update_fact(int(local_id), text)
                return local_id
            same = next((f for f in self.mem.facts() if fold(f["text"]) == fold(text)), None)
            return str(same["id"] if same else self.mem.add_fact(text))
        app = str(data.get("app", ""))
        enabled = bool(data.get("enabled", True))
        if exists:
            self.mem.update_rule(int(local_id), text=text, enabled=enabled)
            return local_id
        same = next((r for r in self.mem.rules(app) if fold(r.text) == fold(text)), None)
        rule = same or self.mem.add_rule(app, text)
        if rule.enabled != enabled:
            self.mem.update_rule(rule.id, enabled=enabled)
        return str(rule.id)

    def sync(self, transport: Any) -> dict[str, Any]:
        self.scan()
        received = 0
        devices = []
        for device, recs in transport.pull(self.device):
            received += self.merge(recs)
            devices.append(device)
        self.scan()
        transport.push(self.device, self.records())
        return {"received": received, "devices": devices, "sent": len(self.records())}


# ---------------- transports ----------------


def bundle(device: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {"format": FORMAT, "device": device, "ts": time.time(), "records": records}


class FolderTransport:
    def __init__(self, folder: str | Path, passphrase: str) -> None:
        self.dir = Path(folder) / "NEXVARA-sync"
        if not Path(folder).is_dir():
            raise SyncError(f"Sinxron papkasi topilmadi: {folder}")
        if len(passphrase or "") < 8:
            raise SyncError("Sinxron paroli kamida 8 belgi bo‘lsin (Sozlamalar → Sinxronlash)")
        self.passphrase = passphrase

    def pull(self, me: str):
        for p in sorted(self.dir.glob("*.nxsync")) if self.dir.is_dir() else []:
            if p.stem == me:
                continue
            b = unseal(p.read_bytes(), self.passphrase)
            if isinstance(b, dict) and b.get("format") == FORMAT:
                yield str(b.get("device") or p.stem), list(b.get("records") or [])

    def push(self, me: str, records: list[dict[str, Any]]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f"{me}.tmp"
        tmp.write_bytes(seal(bundle(me, records), self.passphrase))
        tmp.replace(self.dir / f"{me}.nxsync")


class DriveTransport:
    """Google Drive appDataFolder (hidden app storage in the user's own Drive)."""

    API = "https://www.googleapis.com/drive/v3"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3"

    def __init__(self, access_token: str, passphrase: str, api: str = "", upload: str = "",
                 opener: Any = None) -> None:  # fmt: skip
        import urllib.request

        if len(passphrase or "") < 8:
            raise SyncError("Sinxron paroli kamida 8 belgi bo‘lsin (Sozlamalar → Sinxronlash)")
        self.token = access_token
        self.passphrase = passphrase
        self.api = api or self.API
        self.upload = upload or self.UPLOAD
        self.open = opener or urllib.request.urlopen

    def _req(self, method: str, url: str, body: bytes | None = None, ctype: str = "") -> bytes:
        import urllib.error
        import urllib.request

        h = {"Authorization": f"Bearer {self.token}"}
        if ctype:
            h["Content-Type"] = ctype
        try:
            with self.open(urllib.request.Request(url, data=body, headers=h, method=method),
                           timeout=30) as r:  # fmt: skip
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SyncError("Google Drive ruxsati yo‘q: Google’ga qaytadan kiring "
                                "(sinxronlash ruxsati bilan)") from e  # fmt: skip
            raise SyncError(f"Google Drive xatosi: {e.code}") from e
        except OSError as e:
            raise SyncError(f"Google Drive bilan aloqa yo‘q: {e}") from e

    def _files(self) -> list[dict[str, Any]]:
        from urllib.parse import quote

        q = quote("name contains '.nxsync'")
        raw = self._req("GET", f"{self.api}/files?spaces=appDataFolder&q={q}&fields=files(id,name)")
        return list(json.loads(raw or b"{}").get("files") or [])

    def pull(self, me: str):
        for f in self._files():
            if f["name"] == f"{me}.nxsync":
                continue
            b = unseal(self._req("GET", f"{self.api}/files/{f['id']}?alt=media"), self.passphrase)
            if isinstance(b, dict) and b.get("format") == FORMAT:
                yield str(b.get("device") or f["name"]), list(b.get("records") or [])

    def push(self, me: str, records: list[dict[str, Any]]) -> None:
        blob = seal(bundle(me, records), self.passphrase)
        mine = next((f for f in self._files() if f["name"] == f"{me}.nxsync"), None)
        if mine:
            self._req("PATCH", f"{self.upload}/files/{mine['id']}?uploadType=media", blob,
                      "application/octet-stream")  # fmt: skip
            return
        boundary = uuid.uuid4().hex
        meta = json.dumps({"name": f"{me}.nxsync", "parents": ["appDataFolder"]}).encode()
        part = "\r\n--" + boundary + "\r\nContent-Type: "
        body = (part[2:] + "application/json; charset=UTF-8\r\n\r\n").encode() + meta
        body += (part + "application/octet-stream\r\n\r\n").encode() + blob
        body += f"\r\n--{boundary}--".encode()
        self._req("POST", f"{self.upload}/files?uploadType=multipart", body,
                  f"multipart/related; boundary={boundary}")  # fmt: skip


def device_id() -> str:
    from nexvara.remote import server_id

    return "pc-" + server_id()


def default_engine(mem: Any) -> SyncEngine:
    from nexvara.appdata import Settings

    return SyncEngine(mem, Settings(), device_id(), config.data_dir() / "app.db")
