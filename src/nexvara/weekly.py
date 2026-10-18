"""«Haftalik hisobot»: every Excel file in a folder that changed during the week, summed up in one
PDF — read with openpyxl and drawn with PyMuPDF, so it also runs on a Friday evening in the
background without opening Excel. A workflow template runs it every Friday at 17:00; the
finished task (with the PDF) shows up on the phone like any other task.
"""

from __future__ import annotations

import time
from html import escape
from pathlib import Path
from typing import Any

from nexvara.core.task import UserError

MAX_FILES = 60
MAX_ROWS = 20000


def _number(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    return None


def summarize(path: Path) -> dict[str, Any]:
    """Sheets, data rows and the totals of numeric columns of one workbook."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = []
        for ws in wb.worksheets:
            rows = [
                r
                for r in ws.iter_rows(values_only=True, max_row=MAX_ROWS + 1)
                if any(v not in (None, "") for v in r)
            ]
            if not rows:
                continue
            head = [
                str(h).strip() if h not in (None, "") else f"Ustun {i + 1}"
                for i, h in enumerate(rows[0])
            ]
            body = rows[1:]
            # a footer row ("JAMI") is not data
            if body and any(
                isinstance(v, str) and v.strip().lower() in ("jami", "itogo", "total")
                for v in body[-1]
            ):
                body = body[:-1]
            totals = {}
            for c, name in enumerate(head):
                vals = [_number(r[c]) for r in body if c < len(r)]
                nums = [v for v in vals if v is not None]
                if body and len(nums) >= max(1, len(body) * 0.8):
                    totals[name] = sum(nums)
            sheets.append({"name": ws.title, "rows": len(body), "totals": totals})
        return {"file": path.name, "modified": path.stat().st_mtime, "sheets": sheets}
    finally:
        wb.close()


def _fmt(v: float) -> str:
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", " ").replace(".", ",")


def build(folder: Path, out_dir: Path, days: int = 7) -> dict[str, Any]:
    folder = Path(folder)
    if not folder.is_dir():
        raise UserError(f"Papka topilmadi: {folder}")
    since = time.time() - days * 86400
    files = sorted(
        (p for p in folder.glob("*.xlsx") if not p.name.startswith("~$")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    week = [p for p in files if p.stat().st_mtime >= since][:MAX_FILES]
    if not week:
        raise UserError(f"«{folder.name}» papkasida oxirgi {days} kunda o‘zgargan Excel fayl yo‘q")
    summaries, errors = [], []
    for p in week:
        try:
            summaries.append(summarize(p))
        except Exception as e:  # a locked or broken file is listed, not fatal
            errors.append(f"{p.name}: {e.__class__.__name__}")
    grand: dict[str, float] = {}
    for s in summaries:
        for sh in s["sheets"]:
            for k, v in sh["totals"].items():
                grand[k] = grand.get(k, 0.0) + v
    period = f"{time.strftime('%d.%m.%Y', time.localtime(since))} – {time.strftime('%d.%m.%Y')}"
    html = [
        f"<h1>Haftalik hisobot</h1><p><b>Papka:</b> {escape(str(folder))}<br>"
        f"<b>Davr:</b> {period}<br><b>Fayllar:</b> {len(summaries)}</p>"
    ]
    if grand:
        html.append("<h2>Umumiy yig‘indilar</h2><table><tr><th>Ustun</th><th>Jami</th></tr>")
        html += [
            f"<tr><td>{escape(k)}</td><td align='right'>{_fmt(v)}</td></tr>"
            for k, v in sorted(grand.items())
        ]
        html.append("</table>")
    html.append(
        "<h2>Fayllar bo‘yicha</h2><table><tr><th>Fayl</th><th>Varaq</th>"
        "<th>Qatorlar</th><th>Yig‘indilar</th></tr>"
    )
    for s in summaries:
        for sh in s["sheets"] or [{"name": "—", "rows": 0, "totals": {}}]:
            tot = "; ".join(f"{escape(k)}: {_fmt(v)}" for k, v in list(sh["totals"].items())[:6])
            html.append(
                f"<tr><td>{escape(s['file'])}</td><td>{escape(sh['name'])}</td>"
                f"<td align='right'>{sh['rows']}</td><td>{tot or '—'}</td></tr>"
            )
    html.append("</table>")
    if errors:
        html.append("<p><b>O‘qib bo‘lmadi:</b> " + escape("; ".join(errors)) + "</p>")
    html.append(f"<p class='note'>NEXVARA {time.strftime('%d.%m.%Y %H:%M')} da tayyorladi.</p>")
    css = (
        "body{font-family:sans-serif;font-size:10pt} h1{font-size:18pt;color:#3730a3} "
        "h2{font-size:13pt;color:#3730a3;margin-top:14pt} table{border-collapse:collapse;"
        "width:100%} th{background:#e0e7ff;text-align:left} th,td{border:1px solid #c7d2fe;"
        "padding:3pt} .note{color:#6b7280;font-size:8pt}"
    )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"Haftalik_hisobot_{folder.name}_{time.strftime('%Y%m%d-%H%M')}.pdf"
    _html_to_pdf("".join(html), css, out)
    return {
        "path": str(out),
        "pdf": str(out),
        "files": len(summaries),
        "errors": errors,
        "totals": grand,
        "report": [f"Haftalik hisobot: {len(summaries)} ta fayl, {period}"],
    }


def _html_to_pdf(html: str, css: str, out: Path) -> None:
    import fitz

    story = fitz.Story(html=html, user_css=css)
    writer = fitz.DocumentWriter(str(out))
    page = fitz.paper_rect("a4")
    area = page + (40, 40, -40, -40)
    more = True
    while more:
        dev = writer.begin_page(page)
        more, _ = story.place(area)
        story.draw(dev)
        writer.end_page()
    writer.close()
