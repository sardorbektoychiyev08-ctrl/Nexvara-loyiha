"""Morning summary lines: scheduled workflows, approvals, an old backup."""

from __future__ import annotations

import time
from types import SimpleNamespace

from nexvara import morning


class _Store:
    def __init__(self, wfs):
        self.wfs = wfs

    def all(self):
        return self.wfs


def test_summary_lines():
    now = time.mktime((2026, 10, 19, 7, 30, 0, 0, 0, -1))  # a Monday
    wfs = [
        SimpleNamespace(name="Kunlik PDF", enabled=True,
                        trigger={"type": "daily", "time": "17:00"}),
        SimpleNamespace(name="Juma hisobot", enabled=True,
                        trigger={"type": "weekly", "time": "17:00", "days": [4]}),
        SimpleNamespace(name="O‘chiq", enabled=False, trigger={"type": "daily", "time": "08:00"}),
    ]  # fmt: skip
    eng = SimpleNamespace(store=_Store(wfs),
                          active=lambda: [{"name": "Arxiv", "waiting_approval": True}])  # fmt: skip
    api = SimpleNamespace(
        list_tasks=lambda: [{"status": "succeeded", "title": "ok", "finished_at": now - 100}],
        _wf=lambda: eng,
        get_settings=lambda: {"backup": {"last": now - 10 * 86400}},
    )
    s = morning.summary(api, now)
    assert s["weekday"] == "Dushanba" and s["failed"] == 0 and s["scheduled"] == 1
    text = "\n".join(s["lines"])
    assert "17:00 Kunlik PDF" in text and "Juma hisobot" not in text and "O‘chiq" not in text
    assert "«Ha» kutmoqda: Arxiv" in text and "10 kun oldin" in text
