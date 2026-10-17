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
        return {"ok": True, **acc.login_async()}

    def account_logout(self) -> dict[str, Any]:
        return self._google().logout()
