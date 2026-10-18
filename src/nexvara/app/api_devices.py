"""Devices page of the UI bridge (mixed into app.api.Api)."""

from __future__ import annotations

import platform
import socket
from typing import Any


class DevicesApi:
    _overrides: dict
    _history: Any
    _remote = None

    def _server(self):
        if self._remote is None:
            from nexvara.remote import DeviceStore, RemoteServer

            store = self._overrides.get("device_store")
            if store is None:
                if self._history is None:
                    return None
                store = DeviceStore()
            port = self._overrides.get("remote_port")
            if port is None:
                from nexvara.appdata import Settings

                port = int(Settings().load()["remote"]["port"]) if self._history else 0
            tls = self._overrides.get("remote_tls", True)
            self._remote = RemoteServer(self, store, port=port, use_tls=tls)
        return self._remote

    def devices_status(self) -> dict[str, Any]:
        srv = self._server()
        info = {"pc": socket.gethostname(), "os": f"{platform.system()} {platform.release()}"}
        if srv is None:
            return {**info, "available": False, "running": False, "devices": []}
        return {**info, "available": True, **srv.status()}

    # ----- what a paired phone may do (Devices page switches) -----
    def devices_options(self) -> dict[str, Any]:
        from nexvara import pcpower

        r = self.get_settings().get("remote", {})
        try:
            auto = pcpower.autostart_enabled()
        except Exception:
            auto = False
        return {
            "screen_view": bool(r.get("screen_view", True)),
            "control": bool(r.get("control", False)),
            "autostart": auto,
        }

    def devices_set_option(self, name: str, value: bool) -> dict[str, Any]:
        if name in ("screen_view", "control"):
            self.save_settings({"remote": {name: bool(value)}})
        elif name == "autostart":
            from nexvara import pcpower

            pcpower.set_autostart(bool(value))
        else:
            raise ValueError(name)
        return self.devices_options()

    def devices_start(self) -> dict[str, Any]:
        srv = self._server()
        if srv is None:
            return {"ok": False, "error": "Bu rejimda mavjud emas"}
        try:
            srv.start()
        except OSError as e:
            return {"ok": False, "error": f"Port {srv.port} band yoki ruxsat yo‘q: {e}"}
        self._remember_remote(True)
        return {"ok": True, **self.devices_status()}

    def devices_stop(self) -> dict[str, Any]:
        srv = self._server()
        if srv is not None:
            srv.stop()
        self._remember_remote(False)
        return self.devices_status()

    def devices_new_code(self) -> dict[str, Any]:
        srv = self._server()
        if srv is not None and srv.running:
            srv.new_code()
        return self.devices_status()

    def devices_revoke(self, device_id: int) -> dict[str, Any]:
        srv = self._server()
        if srv is not None:
            srv.store.revoke(int(device_id))
        return self.devices_status()

    def _remember_remote(self, enabled: bool) -> None:
        if self._history is None:
            return
        from nexvara.appdata import Settings

        Settings().update({"remote": {"enabled": enabled}})

    def start_remote_if_enabled(self) -> None:
        if self._history is None:
            return
        from nexvara.appdata import Settings

        if Settings().load()["remote"]["enabled"]:
            try:
                srv = self._server()
                if srv is not None:
                    srv.start()
            except OSError:
                pass  # the Devices page shows it as stopped; the user can retry
