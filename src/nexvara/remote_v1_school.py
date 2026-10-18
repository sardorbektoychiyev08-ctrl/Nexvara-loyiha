"""Phone API v1: teacher and office tools (answer sheets, class journal, document templates,
photo → text), file preview, remote control and autostart. Merged into remote_v1.ROUTES and
documented in docs/api/openapi.yaml like the other sections."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara import remote_v1_sections as sec
from nexvara.core.task import UserError
from nexvara.protocol import ApiError, task_dto

ROUTES: list[tuple[str, str, bool]] = [
    ("GET", "/api/v1/omr", True),
    ("POST", "/api/v1/omr", True),
    ("POST", "/api/v1/omr/{id}/keys", True),
    ("POST", "/api/v1/omr/{id}/grade", True),
    ("GET", "/api/v1/journal", True),
    ("POST", "/api/v1/journal", True),
    ("GET", "/api/v1/journal/{id}", True),
    ("POST", "/api/v1/journal/{id}/students", True),
    ("POST", "/api/v1/journal/{id}/delete", True),
    ("POST", "/api/v1/journal/{id}/export", True),
    ("POST", "/api/v1/journal/grade", True),
    ("POST", "/api/v1/journal/grade/{id}/delete", True),
    ("GET", "/api/v1/doctemplates", True),
    ("POST", "/api/v1/doctemplates/{id}", True),
    ("POST", "/api/v1/ocr", True),
    ("POST", "/api/v1/ocr/convert", True),
    ("GET", "/api/v1/morning", True),
    ("GET", "/api/v1/files/preview", True),
    ("POST", "/api/v1/control", True),
    ("GET", "/api/v1/autostart", True),
    ("POST", "/api/v1/autostart", True),
]
HANDLED = {p for _m, p, _a in ROUTES}
_PREVIEW_OFFICE = (".docx", ".doc", ".rtf", ".xlsx", ".xls", ".pptx", ".ppt")


def _journal(api: Any):
    j = api._overrides.get("journal") if hasattr(api, "_overrides") else None
    if j is None:
        if getattr(api, "_journal", None) is None:
            from nexvara.journal import Journal

            api._journal = Journal()
        j = api._journal
    return j


def _int(v: str) -> int:
    if not v.isdigit():
        raise ApiError("NOT_FOUND")
    return int(v)


def _share(srv: Any, dev: dict[str, Any], path: str | Path) -> str:
    sec._grant(srv, dev, str(path), "shared", sec.SHARED_TTL)
    return str(path)


def _user(fn):
    """UserError/LookupError from the tools become clear phone errors."""
    try:
        return fn()
    except UserError as e:
        raise ApiError("BAD_REQUEST", str(e)) from e
    except LookupError as e:
        raise ApiError("NOT_FOUND", str(e) or "Topilmadi") from e


def _last_test_keys(api: Any) -> tuple[int, int, dict[str, str]] | None:
    for t in api.list_tasks()[:50]:
        res = t.get("result") or {}
        if t.get("status") == "succeeded" and res.get("answers"):
            keys = {str(i + 1): k for i, k in enumerate(res["answers"])}
            return len(res["answers"][0]), len(res["answers"]), keys
    return None


def _omr_view(s: dict[str, Any]) -> dict[str, Any]:
    return {k: s[k] for k in ("id", "title", "questions", "variants", "keys", "pdf", "created")} | {
        "results": s["results"][:30]
    }


def route(
    h: Any,
    srv: Any,
    route: str,
    args: dict[str, str],
    q: dict[str, list[str]],
    dev: dict[str, Any],
    body: Any,
) -> dict[str, Any] | None:
    from nexvara import omr

    api = srv.api
    # ----- answer sheets -----
    if route == "/api/v1/omr" and h.command == "GET":
        last = _last_test_keys(api)
        return {
            "sets": [_omr_view(s) for s in omr.load_sets()],
            "last_test": {"questions": last[0], "variants": last[1]} if last else None,
        }
    if route == "/api/v1/omr":
        b = body()
        keys = b.get("keys") if isinstance(b.get("keys"), dict) else {}
        n, v = int(b.get("questions") or 0), int(b.get("variants") or 1)
        if b.get("from_last_test"):
            last = _last_test_keys(api)
            if last is None:
                raise ApiError("BAD_REQUEST", "Oxirgi tuzilgan testda javoblar kaliti yo‘q")
            n, v, keys = last
        s = _user(
            lambda: omr.create_set(
                str(b.get("title") or "Test"), n, v, keys, int(b.get("copies") or 1)
            )
        )
        _share(srv, dev, s["pdf"])
        if b.get("open_on_pc", True):  # ready to print on the PC
            api.ui_push({"kind": "phone_file", "name": Path(s["pdf"]).name, "path": s["pdf"]})
            api.open_file(s["pdf"])
        return _omr_view(s)
    if route == "/api/v1/omr/{id}/keys":
        keys = body().get("keys")
        if not isinstance(keys, dict):
            raise ApiError("BAD_REQUEST", "keys: {variant: «ABCD…»}")
        return _omr_view(_user(lambda: omr.set_keys(args["id"], keys)))
    if route == "/api/v1/omr/{id}/grade":
        b = body()
        photo = Path(sec._phone_file(str(b.get("path", ""))))
        res = _user(lambda: omr.grade(args["id"], photo, str(b.get("student") or "")))
        _share(srv, dev, res["excel"])
        return res
    # ----- class journal -----
    j = None
    if route.startswith("/api/v1/journal"):
        j = _journal(api)
    if route == "/api/v1/journal" and h.command == "GET":
        return {"classes": j.classes()}
    if route == "/api/v1/journal":
        cid = _user(lambda: j.add_class(str(body().get("name", ""))))
        return {"id": cid, "classes": j.classes()}
    if route == "/api/v1/journal/grade":
        b = body()
        gid = _user(
            lambda: j.add_grade(
                int(b.get("student_id") or 0),
                int(b.get("grade") or 0),
                str(b.get("subject") or ""),
                str(b.get("day") or ""),
                str(b.get("note") or ""),
            )
        )
        return {"id": gid}
    if route == "/api/v1/journal/grade/{id}/delete":
        j.delete_grade(_int(args["id"]))
        return {"ok": True}
    if route == "/api/v1/journal/{id}":
        subject = (q.get("subject") or [""])[0]
        return _user(lambda: j.class_view(_int(args["id"]), subject))
    if route == "/api/v1/journal/{id}/students":
        added = _user(lambda: j.add_students(_int(args["id"]), str(body().get("names", ""))))
        return {"added": added, **j.class_view(_int(args["id"]))}
    if route == "/api/v1/journal/{id}/delete":
        j.delete_class(_int(args["id"]))
        return {"classes": j.classes()}
    if route == "/api/v1/journal/{id}/export":
        b = body()
        out = _user(lambda: j.export(_int(args["id"])))
        _share(srv, dev, out)
        if b.get("open_on_pc", True):
            api.open_file(str(out))
        return {"path": str(out), "name": out.name}
    # ----- document templates -----
    if route == "/api/v1/doctemplates":
        from nexvara.doctemplates import catalog

        return {"templates": catalog()}
    if route == "/api/v1/doctemplates/{id}":
        from nexvara import doctemplates
        from nexvara.fileagent import free_name

        b = body()
        fields = b.get("fields") if isinstance(b.get("fields"), dict) else {}
        blocks = _user(lambda: doctemplates.render(args["id"], fields))
        name = doctemplates.TEMPLATES[args["id"]]["title"].split(" (")[0]
        out = free_name(doctemplates.out_dir() / f"{name} {time.strftime('%Y%m%d-%H%M%S')}.docx")
        fake = api._overrides.get("doctemplate") if hasattr(api, "_overrides") else None

        def fn(task: Any) -> dict[str, Any]:
            if fake is not None:
                return fake(task, args["id"], blocks, out)
            return doctemplates.write(
                task,
                args["id"],
                blocks,
                out,
                visible=not b.get("background"),
                keep_open=api._keep_open(),
            )

        snap = api._runner.start(doctemplates.TEMPLATES[args["id"]]["title"], fn).snapshot()
        api.ui_push({"kind": "task", "task": snap})
        return {"task": task_dto(snap)}
    # ----- photo → text -----
    if route == "/api/v1/ocr":
        b = body()
        photo = Path(sec._phone_file(str(b.get("path", ""))))
        ocr = api._overrides.get("ocr") if hasattr(api, "_overrides") else None
        if ocr is None:
            from nexvara.knowledge.ocr import ocr_image as ocr
        try:
            text = ocr(photo, str(b.get("lang") or ""))
        except Exception as e:
            raise ApiError("BAD_REQUEST", f"Matnni o‘qib bo‘lmadi: {e}") from e
        txt = photo.with_suffix(".txt")
        txt.write_text(text, encoding="utf-8")
        api.set_context_file(str(txt))
        _share(srv, dev, txt)
        return {"text": text, "path": str(txt), "chars": len(text)}
    if route == "/api/v1/morning":
        from nexvara import morning

        return morning.summary(api)
    if route == "/api/v1/ocr/convert":
        return _ocr_convert(api, srv, dev, body())
    # ----- preview (PDF in the app) -----
    if route == "/api/v1/files/preview":
        from nexvara.remote_v1 import _allowed_files

        path = (q.get("path") or [""])[0]
        p = Path(path)
        if (path not in _allowed_files(api) and not sec.granted(srv, dev, path)) or not p.is_file():
            raise ApiError("NOT_FOUND", "Fayl topilmadi")
        ext = p.suffix.lower()
        if ext == ".pdf":
            data, ctype = p.read_bytes(), "application/pdf"
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".txt", ".csv", ".svg"):
            data = p.read_bytes()
            ctype = {
                ".png": "image/png",
                ".txt": "text/plain; charset=utf-8",
                ".csv": "text/plain; charset=utf-8",
                ".svg": "image/svg+xml",
            }.get(ext, "image/jpeg")
        elif ext in _PREVIEW_OFFICE:
            data, ctype = _office_pdf(api, p), "application/pdf"
        else:
            raise ApiError(
                "BAD_REQUEST", "Bu turdagi faylni ko‘rib bo‘lmaydi — telefonga yuklab oling"
            )
        import hashlib

        h._send(200, data, ctype, {"X-Content-SHA256": hashlib.sha256(data).hexdigest()})
        return None
    # ----- remote control (off unless the owner turned it on in the PC window) -----
    if route == "/api/v1/control":
        if not api.get_settings().get("remote", {}).get("control", False):
            raise ApiError(
                "BAD_REQUEST",
                "Kompyuterni boshqarish o‘chiq: kompyuterda Qurilmalar → "
                "«Telefon sichqoncha va klaviaturani boshqarishi mumkin» ni yoqing.",
            )
        b = body()
        doer = api._overrides.get("control") if hasattr(api, "_overrides") else None
        if doer is None:
            from nexvara.control import act as doer
        last = getattr(api, "_control_seen", 0.0)
        if time.time() - last > 30:
            api._control_seen = time.time()
            api.ui_push({"kind": "phone_control"})
        try:
            doer(
                str(b.get("action", "")),
                b.get("x"),
                b.get("y"),
                int(b.get("dy") or 0),
                str(b.get("text") or ""),
                str(b.get("key") or ""),
            )
        except ValueError as e:
            raise ApiError("BAD_REQUEST", str(e)) from e
        return {"ok": True}
    # ----- start with Windows -----
    if route == "/api/v1/autostart":
        from nexvara import pcpower

        if h.command == "POST":
            on = bool(body().get("on"))
            setter = api._overrides.get("autostart") if hasattr(api, "_overrides") else None
            return {"on": (setter or pcpower.set_autostart)(on)}
        getter = api._overrides.get("autostart_get") if hasattr(api, "_overrides") else None
        return {"on": (getter or pcpower.autostart_enabled)()}
    raise ApiError("NOT_FOUND")


def _ocr_convert(api: Any, srv: Any, dev: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """The photo's text (as the phone shows/edited it) → Excel table or Word document."""
    from nexvara import photodoc

    to = str(b.get("to") or "")
    if to not in ("excel", "word"):
        raise ApiError("BAD_REQUEST", "to: excel yoki word")
    photo = Path(sec._phone_file(str(b.get("path", ""))))
    text = str(b.get("text") or "")
    if not text.strip():
        txt = photo.with_suffix(".txt")
        if photo.suffix.lower() == ".txt":
            text = photo.read_text(encoding="utf-8", errors="replace")
        elif txt.is_file():
            text = txt.read_text(encoding="utf-8", errors="replace")
        else:
            ocr = api._overrides.get("ocr") if hasattr(api, "_overrides") else None
            if ocr is None:
                from nexvara.knowledge.ocr import ocr_image as ocr
            text = ocr(photo, str(b.get("lang") or ""))
    if len(text) > 200_000:
        raise ApiError("BAD_REQUEST", "Matn juda uzun")
    if to == "excel":
        res = _user(lambda: photodoc.convert(text, photo, "excel"))
        _share(srv, dev, res["path"])
        api.set_context_file(res["path"])
        return res
    fake = api._overrides.get("photo_word") if hasattr(api, "_overrides") else None

    def fn(task: Any) -> dict[str, Any]:
        with task.step("Word hujjat") as s:
            res = (
                fake(text, photo)
                if fake
                else photodoc.convert(
                    text, photo, "word", visible=not b.get("background"), keep_open=api._keep_open()
                )
            )
            s.detail = Path(res["path"]).name
        return res

    snap = api._runner.start("Rasm → Word", fn).snapshot()
    api.ui_push({"kind": "task", "task": snap})
    return {"task": task_dto(snap)}


def _office_pdf(api: Any, p: Path) -> bytes:
    """A PDF copy of an Office file for viewing (made in a temp folder; the file is untouched)."""
    conv = api._overrides.get("office_pdf") if hasattr(api, "_overrides") else None
    if conv is not None:
        return conv(p)
    from nexvara.fileagent import convert_to_pdf

    tmp = Path(tempfile.mkdtemp(prefix="nexvara-preview-", dir=config.data_dir()))
    try:
        copy = tmp / p.name
        shutil.copy2(p, copy)
        task = api._runner.start(
            f"Ko‘rish uchun PDF: {p.name}", lambda t: convert_to_pdf(t, [str(copy)])
        )
        if not task.wait(120) or task.status != "succeeded":
            raise ApiError("INTERNAL", "PDF tayyorlab bo‘lmadi")
        made = (task.result or {}).get("files") or []
        pdf = Path(made[0]) if made else copy.with_suffix(".pdf")
        return pdf.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
