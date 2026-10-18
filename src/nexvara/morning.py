"""The morning summary the phone shows at 07:30 (GET /api/v1/morning).

The phone adds today's lessons from its own timetable; the PC tells what is waiting there:
tasks that failed since yesterday, workflows waiting for «Ha», what runs today on a schedule,
and the age of the last backup. Only short Uzbek lines and counts — no file contents.
"""

from __future__ import annotations

import time
from typing import Any

WEEKDAYS = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")


def summary(api: Any, now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    lt = time.localtime(now)
    lines: list[str] = []

    tasks = api.list_tasks()
    failed = [t for t in tasks if t.get("status") == "failed"
              and (t.get("finished_at") or t.get("created_at") or 0) > now - 86400]  # fmt: skip
    running = [t for t in tasks if t.get("status") in ("running", "pending", "paused")]
    if failed:
        names = ", ".join(str(t.get("title", ""))[:40] for t in failed[:3])
        lines.append(f"⚠ Kecha {len(failed)} ta ish bajarilmadi: {names}")
    if running:
        lines.append(f"⏳ Hozir {len(running)} ta ish bajarilmoqda")

    waiting: list[str] = []
    today: list[str] = []
    eng = api._wf() if hasattr(api, "_wf") else None
    if eng is not None:
        waiting = [a["name"] for a in eng.active() if a.get("waiting_approval")]
        for wf in eng.store.all():
            tr = wf.trigger or {}
            if not wf.enabled or tr.get("type") not in ("daily", "weekly"):
                continue
            if tr.get("type") == "weekly" and lt.tm_wday not in (tr.get("days") or []):
                continue
            today.append(f"{tr.get('time', '')} {wf.name}")
    if waiting:
        lines.append(f"✋ «Ha» kutmoqda: {', '.join(waiting[:3])}")
    if today:
        lines.append("📅 Bugun avtomatik: " + "; ".join(sorted(today)[:4]))

    backup_days = None
    try:
        last = float((api.get_settings().get("backup") or {}).get("last") or 0)
        if last:
            backup_days = int((now - last) // 86400)
            if backup_days >= 8:
                lines.append(f"💾 Oxirgi zaxira {backup_days} kun oldin — «zaxira qil» deb yozing")
    except Exception:  # noqa: BLE001 - the summary never fails because of settings
        pass
    return {
        "date": time.strftime("%Y-%m-%d", lt),
        "weekday": WEEKDAYS[lt.tm_wday],
        "lines": lines,
        "failed": len(failed),
        "running": len(running),
        "waiting": len(waiting),
        "scheduled": len(today),
        "backup_days": backup_days,
    }
