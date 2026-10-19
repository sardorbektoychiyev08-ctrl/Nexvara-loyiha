"""First start on a new PC (mixed into app.api.Api): a short guide — Office found or not,
the phone (switch on, Tailscale), start with Windows, AI key, Google — each step can be skipped.

Shown once: settings.json "onboarding" -> {"done": true} afterwards. A PC that already used
NEXVARA before this guide existed (app.db has finished tasks, chat or a paired phone) is
treated as done, so nobody who already works with NEXVARA is interrupted.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

OFFICE = {"excel": "Excel.Application", "word": "Word.Application",
          "powerpoint": "PowerPoint.Application"}  # fmt: skip


def office_installed() -> dict[str, bool]:
    try:
        import winreg
    except ImportError:
        return dict.fromkeys(OFFICE, False)
    out = {}
    for name, progid in OFFICE.items():
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\CLSID"))
            out[name] = True
        except OSError:
            out[name] = False
    return out


def used_before() -> bool:
    """Tasks, chat or a paired phone in app.db: NEXVARA already worked on this PC."""
    from nexvara import config

    db = config.data_dir() / "app.db"
    if not db.is_file():
        return False
    try:
        with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)) as con:
            for table in ("history", "chat_log", "devices"):
                try:
                    if con.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                        return True
                except sqlite3.OperationalError:
                    continue
    except sqlite3.Error:
        return False
    return False


class OnboardingApi:
    _overrides: dict
    _history: Any

    def onboarding_status(self) -> dict[str, Any]:
        from nexvara.appdata import Settings

        s = Settings()
        if self._history is None and "onboarding_force" not in self._overrides:
            return {"show": False}  # tests and self-tests never see it
        if s.load()["onboarding"].get("done"):
            return {"show": False}
        seen = self._overrides.get("used_before") or used_before
        if seen():  # an existing user: never interrupt
            s.update({"onboarding": {"done": True}})
            return {"show": False}
        office = (self._overrides.get("office_installed") or office_installed)()
        return {"show": True, "office": office}

    def onboarding_done(self) -> dict[str, Any]:
        self.save_settings({"onboarding": {"done": True}})
        return {"show": False}
