"""Phone API v1: «Chizma» on the phone. The phone draws (finger strokes become clean lines,
circles, rectangles) and sends the same JSON the PC editor uses (app/api_cad.py); the PC saves
a real AutoCAD DXF plus PDF/PNG in the Chizmalar folder and can open it in its own editor.
Merged into remote_v1.ROUTES and documented in docs/api/openapi.yaml."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from nexvara import config
from nexvara import remote_v1_sections as sec
from nexvara.protocol import ApiError

ROUTES: list[tuple[str, str, bool]] = [
    ("GET", "/api/v1/cad", True),
    ("POST", "/api/v1/cad", True),
    ("GET", "/api/v1/cad/drawing", True),
    ("POST", "/api/v1/cad/open", True),
    ("POST", "/api/v1/cad/ai", True),
    ("GET", "/api/v1/cad/templates", True),
    ("POST", "/api/v1/cad/templates", True),
]
HANDLED = {p for _m, p, _a in ROUTES}
PHONE_MAX_ENTITIES = 5000  # a phone screen does not need more; the PC keeps the full file


def _folder(api: Any) -> Path:
    folder = getattr(api, "_output_dir", None) or (config.data_dir() / "Chizmalar")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _inside(api: Any, raw: str) -> Path:
    """Only drawings in the Chizmalar folder can be read or opened from the phone."""
    folder = _folder(api).resolve()
    p = Path(raw or "")
    p = (folder / p.name) if not p.is_absolute() else p
    p = p.resolve()
    if p.parent != folder or p.suffix.lower() != ".dxf" or not p.is_file():
        raise ApiError("NOT_FOUND", "Chizma topilmadi")
    return p


def _safe_name(name: str) -> str:
    base = re.sub(r"[^\w‘’' -]", "", str(name or "")).strip()[:50] or "Telefon chizmasi"
    return base.replace(" ", "_")


def route(
    h: Any,
    srv: Any,
    route: str,
    args: dict[str, str],
    q: dict[str, list[str]],
    dev: dict[str, Any],
    body: Any,
) -> dict[str, Any] | None:
    from nexvara import cad
    from nexvara.app.api_cad import doc_to_json

    api = srv.api
    if route == "/api/v1/cad" and h.command == "GET":
        files = sorted(_folder(api).glob("*.dxf"), key=lambda p: p.stat().st_mtime, reverse=True)
        return {"drawings": [{"name": p.name, "path": str(p), "modified": p.stat().st_mtime,
                              "size": p.stat().st_size} for p in files[:30]]}  # fmt: skip
    if route == "/api/v1/cad/drawing":
        p = _inside(api, (q.get("path") or [""])[0])
        try:
            data = doc_to_json(cad.read(p))
        except Exception as e:  # a broken file is a clear message, not a crash
            raise ApiError("BAD_REQUEST", f"Chizmani o‘qib bo‘lmadi: {e}") from e
        cut = len(data["entities"]) > PHONE_MAX_ENTITIES
        data["entities"] = data["entities"][:PHONE_MAX_ENTITIES]
        return {"name": p.name, "path": str(p), "drawing": data, "truncated": cut}
    if route == "/api/v1/cad/ai":  # «AI bilan tuzatish» for the phone sketch
        b = body()
        out = api.cad_ai_fix(b.get("drawing") or {}, str(b.get("note") or "")[:500],
                             bool(b.get("approved")))  # fmt: skip
        if not out.get("ok") and not out.get("confirm"):
            raise ApiError("BAD_REQUEST", out.get("error") or "Tuzatib bo‘lmadi")
        return out
    if route == "/api/v1/cad/templates" and h.command == "GET":
        return {"templates": api.cad_templates()}
    if route == "/api/v1/cad/templates":
        b = body()
        out = api.cad_template(str(b.get("name") or ""), str(b.get("size") or ""))
        if not out.get("ok"):
            raise ApiError("BAD_REQUEST", out.get("error") or "Shablon topilmadi")
        return out
    if route == "/api/v1/cad/open":
        p = _inside(api, str(body().get("path") or ""))
        api.ui_push({"kind": "cad_open", "path": str(p)})
        return {"opened": p.name}
    if route == "/api/v1/cad":
        b = body()
        drawing = b.get("drawing")
        if not isinstance(drawing, dict) or not drawing.get("entities"):
            raise ApiError("BAD_REQUEST", "Chizma bo‘sh")
        folder = _folder(api)
        stem = f"{_safe_name(b.get('name'))}_{time.strftime('%Y%m%d-%H%M%S')}"
        target = folder / f"{stem}.dxf"
        saved = api.cad_save(drawing, str(target))
        if not saved.get("ok"):
            raise ApiError("BAD_REQUEST", saved.get("error") or "Saqlab bo‘lmadi")
        out = {"dxf": saved["path"], "entities": saved["entities"]}
        for kind in ("pdf", "png"):
            r = api.cad_export(drawing, kind, str(folder / f"{stem}.{kind}"))
            if r.get("ok"):
                out[kind] = r["path"]
        for k in ("dxf", "pdf", "png"):
            if out.get(k):
                sec._grant(srv, dev, out[k], "shared", sec.SHARED_TTL)
        if b.get("open_on_pc", True):
            api.ui_push({"kind": "cad_open", "path": saved["path"]})
        return out
    return None
