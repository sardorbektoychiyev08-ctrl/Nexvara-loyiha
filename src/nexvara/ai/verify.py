"""«Bajar → tekshir → tuzat»: after NEXVARA made a document for an AI-understood request, the
AI reads what was actually written and says whether it matches the request. If not, the
chat repairs it with a corrected plan (a new file; nothing of the user's is overwritten).

Only files NEXVARA itself just created are read (Word, Excel, PowerPoint, PDF), as text and
through the privacy guard like every request.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from nexvara.ai.privacy import public

MAX_CHARS = 6000

CHECK_SYSTEM = """Sen NEXVARA’ning sifat nazoratchisisan. Senga foydalanuvchining so‘rovi va \
NEXVARA hozirgina tayyorlagan faylning matni beriladi. Fayl so‘rovga to‘liq mos keladimi, \
tekshir:
- so‘ralgan narsa bormi, soni to‘g‘rimi (savollar, variantlar, slaydlar, qatorlar);
- mazmun to‘g‘rimi: fakt, hisob va javob kalitlarida xato yo‘qmi;
- o‘zbek tilida imlo, kelishik va uslub xatolari;
- rasmiy hujjatda shakl: kimga (-ga), kimdan (-dan), sarlavha, aniq iltimos, sana, imzo;
- takror, chala gap, mavzudan chetga chiqish.
[Qavs ichidagi] to‘ldiriladigan joylar xato emas. ⟦...⟧ belgilari — yashirilgan shaxsiy \
ma’lumot, xato emas. Mayda did masalasini xato dema.
Faqat JSON qaytar: {"ok": true yoki false, "problems": ["aniq kamchilik", ...], \
"fixed_request": "kamchiliklar tuzatilgan holda shu ishni qayta bajarish uchun aniq \
ko‘rsatma (ok bo‘lsa bo‘sh)"}"""


def _xml_text(data: bytes) -> str:
    text = data.decode("utf-8", "replace")
    # Slide animations hold «style.visibility» etc.: not text the reader sees.
    text = re.sub(r"<p:timing>.*?</p:timing>", "", text, flags=re.S)
    text = re.sub(r"</w:p>|</a:p>", "\n", text)  # paragraph ends (Word, PowerPoint)
    text = re.sub(r"<w:tab/>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
        text = text.replace(a, b)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def document_text(path: str | Path) -> str:
    """The visible text of a file NEXVARA made; "" for kinds it cannot read."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".docx":
            with zipfile.ZipFile(p) as z:
                return _xml_text(z.read("word/document.xml"))[:MAX_CHARS]
        if ext == ".pptx":
            with zipfile.ZipFile(p) as z:
                names = sorted(
                    (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                    key=lambda n: int(re.findall(r"\d+", n)[-1]),
                )
                return "\n\n".join(
                    f"[{i}-slayd]\n{_xml_text(z.read(n))}" for i, n in enumerate(names, 1)
                )[:MAX_CHARS]
        if ext in (".xlsx", ".xlsm"):
            import openpyxl

            wb = openpyxl.load_workbook(p, read_only=True, data_only=False)
            try:
                lines = []
                for ws in wb.worksheets[:3]:
                    lines.append(f"[varaq: {ws.title}]")
                    for row in ws.iter_rows(max_row=80, values_only=True):
                        if any(v not in (None, "") for v in row):
                            lines.append(" | ".join("" if v is None else str(v) for v in row))
                return "\n".join(lines)[:MAX_CHARS]
            finally:
                wb.close()
        if ext == ".pdf":
            import pymupdf

            with pymupdf.open(p) as pdf:
                return "\n".join(page.get_text() for page in pdf)[:MAX_CHARS]
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return ""
    return ""


def outputs(result: dict[str, Any]) -> list[str]:
    """Readable files a finished task produced (its own outputs only)."""
    found: list[str] = []
    for key in ("path", "pdf"):
        v = result.get(key)
        if isinstance(v, str):
            found.append(v)
    found += [f for f in result.get("files") or [] if isinstance(f, str)]
    seen, out = set(), []
    for f in found:
        p = Path(f)
        if f not in seen and p.suffix.lower() in (".docx", ".pptx", ".xlsx", ".xlsm", ".pdf"):
            seen.add(f)
            out.append(f)
    # a DOCX and its PDF hold the same text: read one
    stems = {Path(f).with_suffix("") for f in out if not f.lower().endswith(".pdf")}
    return [f for f in out if not (f.lower().endswith(".pdf") and Path(f).with_suffix("") in stems)]


def check(router: Any, request: str, files: list[str]) -> dict[str, Any] | None:
    """{"ok", "problems", "fixed_request"}; None when nothing could be read or checked."""
    from nexvara.ai.router import NeedsConfirmation
    from nexvara.core.task import UserError

    parts = []
    for f in files[:3]:
        text = document_text(f)
        if text.strip():
            parts.append(f"=== {Path(f).name} ===\n{text}")
    if not parts:
        return None
    msgs = [{"role": "user", "content": f"So‘rov: {request}\n\nTayyorlangan fayl:\n\n"
             + "\n\n".join(parts)}]  # fmt: skip
    try:
        r = router.complete("verify", public(CHECK_SYSTEM), msgs, max_tokens=1500,
                            expected_out=400, effort="medium")  # fmt: skip
    except (NeedsConfirmation, UserError):
        return None  # a check never asks for money or blocks the work
    a, b = r.text.find("{"), r.text.rfind("}")
    try:
        data = json.loads(r.text[a : b + 1]) if 0 <= a < b else None
    except ValueError:
        return None
    if not isinstance(data, dict) or "ok" not in data:
        return None
    problems = [str(x).strip() for x in data.get("problems") or [] if str(x).strip()]
    return {"ok": bool(data["ok"]) and not problems, "problems": problems[:8],
            "fixed_request": str(data.get("fixed_request") or "").strip()}  # fmt: skip
