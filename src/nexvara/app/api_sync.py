"""Sync card in Settings, "sinxronla" in chat and the phone's /api/v1/sync (mixed into Api)."""

from __future__ import annotations

import time
from typing import Any


class SyncApi:
    _overrides: dict
    _history: Any

    def _sync_engine(self):
        if "sync_engine" in self._overrides:
            return self._overrides["sync_engine"]
        mem = self._mem()
        if mem is None:
            return None
        from nexvara.appdata import Settings
        from nexvara.sync import SyncEngine, device_id

        return SyncEngine(mem, Settings(), device_id(), mem.path)

    def _sync_keys(self):
        if "sync_keys" in self._overrides:
            return self._overrides["sync_keys"]
        from nexvara.ai.keys import KeyStore

        return KeyStore("NEXVARA/sync/")

    def sync_status(self) -> dict[str, Any]:
        s = self.get_settings()["sync"]
        return {**s, "has_passphrase": bool(self._sync_keys().load("passphrase")),
                "available": self._sync_engine() is not None,
                "drive_ready": self._drive_ready()}  # fmt: skip

    def sync_set_passphrase(self, passphrase: str) -> dict[str, Any]:
        if len(passphrase or "") < 8:
            return {"ok": False, "error": "Parol kamida 8 belgi bo‘lsin"}
        self._sync_keys().save("passphrase", passphrase)
        return {"ok": True, **self.sync_status()}

    def _drive_ready(self) -> bool:
        try:
            st = self._google().status()
        except Exception:
            return False
        prof = st.get("profile") or {}
        return bool(st.get("signed_in")) and "drive.appdata" in " ".join(prof.get("scopes") or [])

    def _transports(self) -> list[tuple[str, Any]]:
        from nexvara.sync import DriveTransport, FolderTransport, SyncError

        s = self.get_settings()["sync"]
        pw = self._sync_keys().load("passphrase") or ""
        out: list[tuple[str, Any]] = []
        if s.get("folder"):
            out.append(("papka", FolderTransport(s["folder"], pw)))
        if s.get("google_drive"):
            if not self._drive_ready():
                raise SyncError("Google Drive sinxroni uchun Google hisobiga «sinxronlash "
                                "ruxsati» bilan kiring (Sozlamalar → Google hisobi).")  # fmt: skip
            out.append(
                ("Google Drive", DriveTransport(self._google().refresh()["access_token"], pw))
            )
        if not out:
            raise SyncError("Sinxronlash joyi tanlanmagan: Sozlamalar → Sinxronlash → papka "
                            "(masalan OneDrive yoki Google Drive papkasi).")  # fmt: skip
        return out

    def sync_now(self) -> dict[str, Any]:
        from nexvara.account import AuthError
        from nexvara.sync import SyncError

        eng = self._sync_engine()
        if eng is None:
            return {"ok": False, "error": "Sinxronlash bu rejimda o‘chirilgan"}
        try:
            parts = []
            for label, tr in self._transports():
                r = eng.sync(tr)
                who = f", qurilmalar: {', '.join(r['devices'])}" if r["devices"] else ""
                parts.append(f"{label}: {r['received']} ta o‘zgarish olindi{who}")
        except (SyncError, AuthError, OSError) as e:
            return {"ok": False, "error": str(e)}
        self.save_settings({"sync": {"last": time.time()}})
        return {"ok": True, "summary": "Sinxronlandi ✓ " + "; ".join(parts), **self.sync_status()}

    # ----- the phone (paired over TLS; the records are not encrypted again) -----
    def sync_export(self) -> dict[str, Any]:
        eng = self._sync_engine()
        if eng is None:
            return {"device": "", "records": []}
        eng.scan()
        return {"device": eng.device, "records": eng.records()}

    def sync_import(self, device: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        eng = self._sync_engine()
        if eng is None:
            return {"applied": 0, "device": "", "records": []}
        eng.scan()
        applied = eng.merge(records)
        eng.scan()
        return {"applied": applied, "device": eng.device, "records": eng.records()}
