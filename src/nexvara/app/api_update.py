"""Version and updates card in Settings (mixed into app.api.Api)."""

from __future__ import annotations

import threading
from typing import Any

from nexvara import __version__


class UpdateApi:
    _overrides: dict
    _history: Any
    _update_state: dict[str, Any] = {}
    _last_start: dict[str, Any] = {}

    def _updater(self):
        if "updater" in self._overrides:
            return self._overrides["updater"]
        from nexvara.appdata import Settings
        from nexvara.updater import Updater

        channel = Settings().load()["update"]["channel"]  # reading only
        return Updater(channel)

    def update_after_start(self) -> dict[str, Any]:
        """Called once when the desktop app opens: result of an update started last time."""
        self._last_start = self._updater().after_start()
        return self._last_start

    def update_auto(self) -> dict[str, Any]:
        """At start (Home banner): check the channel once if "auto_check" is on. Only reads
        the signed manifest — nothing is downloaded or installed without the user's click."""
        from nexvara.appdata import Settings
        from nexvara.updater import UpdateError

        cfg = self._overrides.get("update_settings") or Settings().load()["update"]
        if not cfg.get("auto_check") or not str(cfg.get("channel") or "").strip():
            return {"available": False, "checked": False, "last_start": self._last_start}
        try:
            r = self._updater().check()
        except UpdateError as e:
            return {"available": False, "checked": False, "error": str(e),
                    "last_start": self._last_start}  # fmt: skip
        r.pop("manifest")
        self._update_state = {"check": r}
        return {**r, "checked": True, "last_start": self._last_start}

    def update_status(self) -> dict[str, Any]:
        upd = self._updater()
        return {"current": __version__, "channel": upd.channel,
                "kept": upd.installed_versions(), "last_start": self._last_start,
                **self._update_state}  # fmt: skip

    def update_check(self) -> dict[str, Any]:
        from nexvara.updater import UpdateError

        try:
            r = self._updater().check()
        except UpdateError as e:
            self._update_state = {"error": str(e)}
            return {"ok": False, "error": str(e), **self.update_status()}
        r.pop("manifest")
        self._update_state = {"check": r}
        return {"ok": True, **self.update_status()}

    def update_install(self) -> dict[str, Any]:
        """Download + verify, then start the installer; the window closes after a moment."""
        from nexvara.updater import UpdateError

        upd = self._updater()
        try:
            r = upd.check()
            if not r["available"]:
                return {"ok": False, "error": "Yangi versiya yo‘q", **self.update_status()}
            exe = upd.download(r["manifest"])
            upd.install(exe, r["version"], **self._run_kw())
        except UpdateError as e:
            return {"ok": False, "error": str(e), **self.update_status()}
        if "update_run" not in self._overrides:
            threading.Timer(1.5, self._quit_for_update).start()
        return {"ok": True, "installing": r["version"], **self.update_status()}

    def update_rollback(self, version: str) -> dict[str, Any]:
        from nexvara.updater import UpdateError

        try:
            self._updater().rollback(str(version), **self._run_kw())
        except UpdateError as e:
            return {"ok": False, "error": str(e)}
        if "update_run" not in self._overrides:
            threading.Timer(1.5, self._quit_for_update).start()
        return {"ok": True}

    def _run_kw(self) -> dict[str, Any]:
        """Tests replace the process start (no installer is really run)."""
        return {"run": self._overrides["update_run"]} if "update_run" in self._overrides else {}

    def _quit_for_update(self) -> None:
        import webview

        self._quitting = True  # the window closes for real, not into the background
        for w in list(webview.windows):
            w.destroy()
