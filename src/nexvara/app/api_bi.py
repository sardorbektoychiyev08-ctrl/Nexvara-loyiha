"""NEXVARA BI page of the UI bridge (mixed into app.api.Api)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


class BiApi:
    _bi_cache: tuple[str, Any] | None = None

    def _bi_table(self, cfg: dict[str, Any]):
        """The prepared table; reused while the source file and ETL steps are unchanged,
        so clicking a filter does not re-read a large Excel file."""
        from nexvara.bi.dash import prepare

        src = Path(cfg["source"])
        stamp = src.stat().st_mtime if src.exists() else 0
        key = json.dumps([str(src), stamp, cfg.get("sheet"), cfg.get("steps")], default=str)
        if self._bi_cache is None or self._bi_cache[0] != key:
            self._bi_cache = (key, prepare(cfg))
        return self._bi_cache[1]

    def _bi_err(self, e: Exception) -> dict[str, Any]:
        return {"ok": False, "error": str(e) or type(e).__name__}

    def bi_pick_source(self) -> str:
        import webview

        if not webview.windows:
            return ""
        chosen = webview.windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=(
                "Ma’lumot fayllari (*.xlsx;*.xlsm;*.csv;*.json;*.xml;*.txt;*.tsv)",
                "Barcha fayllar (*.*)",
            ),
        )
        return str(chosen[0]) if chosen else ""

    def bi_sheets(self, path: str) -> list[str]:
        from nexvara.bi.data import sheets

        try:
            return sheets(path)
        except Exception:
            return []

    def bi_auto(self, path: str, sheet: str | None = None) -> dict[str, Any]:
        from nexvara.bi.dash import auto_dashboard
        from nexvara.bi.data import load, typed

        try:
            t = typed(load(path, sheet or None))
            cfg = auto_dashboard(t, str(path), sheet=sheet or None)
            return {"ok": True, "config": cfg, "result": self._bi_compute(cfg, {})}
        except Exception as e:
            return self._bi_err(e)

    def _bi_compute(self, cfg: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        from nexvara.bi.dash import compute

        return compute(cfg, state, table=self._bi_table(cfg))

    def bi_compute(self, cfg: dict[str, Any], state: dict[str, Any] | None = None):
        try:
            return {"ok": True, "result": self._bi_compute(cfg, state or {})}
        except Exception as e:
            return self._bi_err(e)

    def bi_preview(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Columns with types and the first rows after the ETL steps (for the data editor)."""
        try:
            t = self._bi_table(cfg)
        except Exception as e:
            return self._bi_err(e)
        from nexvara.bi.data import describe_step

        rows = [[v.isoformat() if hasattr(v, "isoformat") else v for v in r] for r in t.rows[:20]]
        return {
            "ok": True,
            "columns": [{"name": c, "type": t.types.get(c, "text")} for c in t.columns],
            "rows": rows,
            "total": len(t.rows),
            "steps": [describe_step(s) for s in cfg.get("steps") or []],
            "notes": t.notes,
        }

    def bi_save(self, cfg: dict[str, Any]) -> dict[str, Any]:
        from nexvara.bi import dash

        try:
            return {"ok": True, "file": str(dash.save(cfg)), "list": dash.saved()}
        except Exception as e:
            return self._bi_err(e)

    def bi_list(self) -> list[dict[str, Any]]:
        from nexvara.bi import dash

        return dash.saved()

    def bi_open(self, file: str) -> dict[str, Any]:
        from nexvara.bi import dash

        try:
            cfg = dash.load_saved(file)
            return {"ok": True, "config": cfg, "result": self._bi_compute(cfg, {})}
        except Exception as e:
            return self._bi_err(e)

    def bi_delete(self, file: str) -> list[dict[str, Any]]:
        from nexvara.bi import dash

        p = Path(file)
        if dash.bi_dir().resolve() in p.resolve().parents and p.suffix == ".json":
            p.unlink(missing_ok=True)
        return dash.saved()

    def _bi_out(self, cfg: dict[str, Any], ext: str) -> Path:
        from nexvara.bi.dash import export_dir

        name = re.sub(r"[^\w‘’' -]", "", str(cfg.get("name") or "dashboard")).strip() or "dashboard"
        return export_dir() / f"{name.replace(' ', '_')}_{time.strftime('%Y%m%d-%H%M%S')}{ext}"

    def bi_export(self, cfg: dict[str, Any], state: dict[str, Any], fmt: str) -> dict[str, Any]:
        from nexvara.bi.dash import export_rows

        try:
            path = export_rows(cfg, state or {}, fmt, self._bi_out(cfg, f".{fmt}"))
            return {"ok": True, "path": str(path)}
        except Exception as e:
            return self._bi_err(e)

    def bi_export_png(self, cfg: dict[str, Any], data_url: str) -> dict[str, Any]:
        from nexvara.bi.dash import save_png

        try:
            return {"ok": True, "path": str(save_png(data_url, self._bi_out(cfg, ".png")))}
        except Exception as e:
            return self._bi_err(e)

    def bi_export_pdf(self, cfg: dict[str, Any], data_urls: list[str]) -> dict[str, Any]:
        from nexvara.bi.dash import pngs_to_pdf

        try:
            out = pngs_to_pdf(data_urls, self._bi_out(cfg, ".pdf"), str(cfg.get("name") or ""))
            return {"ok": True, "path": str(out)}
        except Exception as e:
            return self._bi_err(e)

    # ----- chat: "Savdo.xlsx dan dashboard yarat" -----
    def _chat_bi(self, text: str) -> dict[str, Any] | None:
        from nexvara.agent import files
        from nexvara.agent.parse import find_file
        from nexvara.knowledge.textnorm import fold

        f = fold(text)
        if not re.search(r"\b(dashboard\w*|dashbord\w*|bi\b|tahlil paneli|hisobot paneli|"
                         r"boshqaruv paneli|panel\w* yarat)", f):  # fmt: skip
            return None
        name = find_file(text)
        if not name:
            if re.search(r"\b(shu|ushbu|oxirgi) fayl", f) and getattr(self, "_context_file", None):
                name = self._context_file
            else:
                return {
                    "reply": "Qaysi fayldan dashboard qilay? Fayl nomini yozing (masalan "
                    "«Savdo.xlsx dan dashboard yarat») yoki NEXVARA BI bo‘limida tanlang."
                }
        try:
            near = Path(self._context_file).parent if getattr(self, "_context_file", None) else None
            src = files.resolve(name, near)
        except LookupError as e:
            return {"reply": str(e)}
        self._context_file = str(src)
        return {
            "reply": f"{src.name} dan dashboard tayyorlayapman — NEXVARA BI bo‘limi ochiladi. "
            "Daromad va xarajat ustunlari bo‘lsa sof foyda va oylik o‘sish ham hisoblanadi.",
            "open_bi": str(src),
        }
