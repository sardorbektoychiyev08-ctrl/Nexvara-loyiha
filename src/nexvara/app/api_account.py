"""Google account card in Settings (mixed into app.api.Api)."""

from __future__ import annotations

from typing import Any


class AccountApi:
    _overrides: dict
    _account = None

    def _google(self):
        if self._account is None:
            acc = self._overrides.get("google_account")
            if acc is None:
                from nexvara.account import GoogleAccount

                acc = GoogleAccount()
            self._account = acc
        return self._account

    def account_status(self) -> dict[str, Any]:
        return self._google().status()

    def account_login(self) -> dict[str, Any]:
        acc = self._google()
        if acc.client is None:
            return {"ok": False, "error": acc.status()["blocked"], **acc.status()}
        drive = bool(self.get_settings()["sync"].get("google_drive"))
        return {"ok": True, **acc.login_async(drive=drive)}

    def account_import_client(self, path: str = "") -> dict[str, Any]:
        """Settings → «Client JSON faylini tanlash»: validate and copy, never log in."""
        from pathlib import Path

        from nexvara.account import AuthError, import_client

        if not path:
            import webview

            if not webview.windows:
                return {"ok": False, "error": "Fayl tanlanmadi"}
            chosen = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG, file_types=("Google client JSON (*.json)",))  # fmt: skip
            if not chosen:
                return {"ok": False, "error": "Fayl tanlanmadi"}
            path = str(chosen[0])
        try:
            info = import_client(Path(path))
        except AuthError as e:
            return {"ok": False, "error": str(e), **self.account_status()}
        return {"ok": True, "project": info["project_id"], **self.account_status()}

    def account_logout(self) -> dict[str, Any]:
        return self._google().logout()
