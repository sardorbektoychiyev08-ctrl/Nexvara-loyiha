"""Windows <-> phone protocol v1: the shared contract (see docs/api/MOBILE_API.md).

Every /api/v1 reply is an envelope:
    {"v": 1, "ok": true,  "data": {...}}
    {"v": 1, "ok": false, "error": {"code": "AUTH_REQUIRED", "message": "...", "retry": false}}
`code` is stable (the Android app switches on it); `message` is Uzbek text for the user.
"""

from __future__ import annotations

from typing import Any

PROTOCOL = 1
MIN_CLIENT_PROTOCOL = 1

# code -> (HTTP status, retry makes sense, default Uzbek message)
ERRORS: dict[str, tuple[int, bool, str]] = {
    "BAD_REQUEST": (400, False, "So‘rov noto‘g‘ri"),
    "AUTH_REQUIRED": (401, False, "Qurilma ulanmagan. Qaytadan bog‘lang."),
    "TOKEN_EXPIRED": (401, False, "Ulanish muddati tugagan. Kompyuter bilan qaytadan bog‘lang."),
    "PAIRING_CODE_INVALID": (403, False, "Kod noto‘g‘ri"),
    "PAIRING_CODE_EXPIRED": (403, False, "Kod eskirgan. Kompyuterda yangi kod oling."),
    "PAIRING_LOCKED": (403, False, "Ko‘p noto‘g‘ri urinish. Kompyuterda yangi kod oling."),
    "NOT_FOUND": (404, False, "Topilmadi"),
    "PAYLOAD_TOO_LARGE": (413, False, "Fayl juda katta (50 MB gacha)"),
    "UNSUPPORTED_PROTOCOL": (426, False, "Ilova versiyasi mos emas. Ilovani yangilang."),
    "RATE_LIMITED": (429, True, "Juda ko‘p so‘rov. Biroz kuting."),
    "INTERNAL": (500, True, "Kompyuterda xato yuz berdi"),
}

TASK_STATES = ("pending", "running", "succeeded", "failed", "cancelled")
FINAL_STATES = ("succeeded", "failed", "cancelled")


class ApiError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        if code not in ERRORS:
            raise ValueError(code)
        super().__init__(message or ERRORS[code][2])
        self.code = code
        self.status = ERRORS[code][0]

    def body(self) -> dict[str, Any]:
        return {
            "v": PROTOCOL,
            "ok": False,
            "error": {"code": self.code, "message": str(self), "retry": ERRORS[self.code][1]},
        }


def ok(data: Any) -> dict[str, Any]:
    return {"v": PROTOCOL, "ok": True, "data": data}


def task_dto(t: dict[str, Any]) -> dict[str, Any]:
    """A task as the phone sees it (no internal fields, only files NEXVARA produced)."""
    res = t.get("result") or {}
    return {
        "id": t.get("id"),
        "title": t.get("title", ""),
        "status": t.get("status", "pending"),
        "error": t.get("error", ""),
        "created_at": t.get("created_at"),
        "finished_at": t.get("finished_at"),
        "steps": [
            {"name": s["name"], "status": s["status"], "detail": s.get("detail", "")}
            for s in t.get("steps") or []
        ],
        "files": [res[k] for k in ("path", "pdf") if isinstance(res.get(k), str) and res.get(k)],
        "report": res.get("report") or [],
    }
