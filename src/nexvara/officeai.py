"""AI for Word and PowerPoint files: translate or rewrite a whole document / presentation.

«Xat.docx ni ingliz tiliga tarjima qil», «Hisobot.docx ni rasmiy uslubda qayta yoz»,
«Taqdimot.pptx ni rus tiliga o‘gir». The original is copied to «<name>_EN.docx» (or
«_qayta.docx») and only the copy is changed, paragraph by paragraph (Word: body and table
cells; PowerPoint: every text box), so styles, tables and pictures stay where they were.

The text goes to the AI through AiRouter.complete — personal data is masked there and restored
in the answer on this PC; the request is paid only after «Ha» with the price.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

LANGS = {
    "ingliz": "English", "english": "English", "rus": "Russian", "o‘zbek": "Uzbek (Latin script)",
    "ozbek": "Uzbek (Latin script)", "kirill": "Uzbek (Cyrillic script)", "turk": "Turkish",
    "nemis": "German", "fransuz": "French", "arab": "Arabic", "xitoy": "Chinese (Simplified)",
    "koreys": "Korean", "yapon": "Japanese", "qozoq": "Kazakh", "qirg‘iz": "Kyrgyz",
    "tojik": "Tajik", "ispan": "Spanish", "italyan": "Italian",
}  # fmt: skip
SUFFIX = {"English": "EN", "Russian": "RU", "Uzbek (Latin script)": "UZ",
          "Uzbek (Cyrillic script)": "UZ-kirill", "Turkish": "TR", "German": "DE",
          "French": "FR", "Arabic": "AR", "Chinese (Simplified)": "ZH", "Korean": "KO",
          "Japanese": "JA", "Kazakh": "KK", "Kyrgyz": "KY", "Tajik": "TG", "Spanish": "ES",
          "Italian": "IT"}  # fmt: skip
STYLES = {
    "rasmiy": "formal, official business style (rasmiy uslub)",
    "sodda": "simple, clear words that a schoolchild understands",
    "qisqa": "shorter: keep every fact but use fewer words",
    "chiroyli": "polished, well-written literary style",
}
BATCH_CHARS = 6000
MAX_CHARS = 120_000


def what_to_do(text: str) -> dict[str, str] | None:
    """{"mode": "translate", "lang": "English"} / {"mode": "rewrite", "style": …} / None."""
    from nexvara.knowledge.textnorm import fold

    f = fold(text)
    if re.search(r"\b(tarjima|ogir|translate)\w*", f):
        for word, lang in LANGS.items():
            if re.search(rf"\b{fold(word)}\w*", f):
                return {"mode": "translate", "lang": lang}
        return {"mode": "translate", "lang": "English"}
    if re.search(r"\bqayta\s+yoz\w*|\bsoddalashtir\w*|\bqisqartir\w*|\btahrirla\w*\s+(ai|uslub)",
                 f):  # fmt: skip
        style = next((s for w, s in STYLES.items() if re.search(rf"\b{w}\w*", f)), STYLES["rasmiy"])
        if re.search(r"\bsoddalashtir", f):
            style = STYLES["sodda"]
        if re.search(r"\bqisqartir", f):
            style = STYLES["qisqa"]
        return {"mode": "rewrite", "style": style}
    return None


def output_path(src: Path, job: dict[str, str]) -> Path:
    from nexvara.fileagent import free_name

    tag = SUFFIX.get(job.get("lang", ""), "") if job["mode"] == "translate" else "qayta"
    return free_name(src.with_name(f"{src.stem}_{tag}{src.suffix}"))


def system_prompt(job: dict[str, str]) -> str:
    if job["mode"] == "translate":
        task = f"Translate every item into {job['lang']}."
    else:
        task = f"Rewrite every item in the same language, {job['style']}."
    return (f"You edit a document item by item. {task} Return ONLY a JSON array of strings with "
            "exactly as many items as given, in the same order. Keep numbers, dates, file names, "
            "formulas and ⟦…⟧ markers exactly as they are. An item that is only a number, code or "
            "name stays unchanged. Never add comments.")  # fmt: skip


def batches(texts: list[str]) -> list[list[int]]:
    """Indexes of non-empty texts grouped so a request stays small."""
    out, cur, size = [], [], 0
    for i, t in enumerate(texts):
        if not t.strip():
            continue
        if cur and size + len(t) > BATCH_CHARS:
            out.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += len(t)
    if cur:
        out.append(cur)
    return out


def parse_items(reply: str, n: int) -> list[str] | None:
    m = re.search(r"\[.*\]", reply, re.S)
    if not m:
        return None
    try:
        items = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(items, list) or len(items) != n or not all(isinstance(x, str) for x in items):
        return None
    return items


def transform(texts: list[str], job: dict[str, str], ask: Any) -> list[str]:
    """`ask(system, user_json) -> reply text` (the router). Empty texts stay empty."""
    out = list(texts)
    system = system_prompt(job)
    for idx in batches(texts):
        chunk = [texts[i] for i in idx]
        items = parse_items(ask(system, json.dumps(chunk, ensure_ascii=False)), len(chunk))
        if items is None:
            from nexvara.core.task import UserError

            raise UserError("AI javobi hujjat tuzilishiga mos kelmadi — qayta urinib ko‘ring")
        for i, new in zip(idx, items, strict=True):
            out[i] = new
    return out


# ---------------- Word ----------------
def _word_cells(doc: Any) -> list[Any]:
    return [c for t in range(1, doc.Tables.Count + 1) for c in doc.Tables(t).Range.Cells]


def word_texts(doc: Any) -> list[str]:
    """Body paragraphs outside tables, then every table cell (end marks removed)."""
    out = []
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i).Range
        out.append("" if p.Information(12) else p.Text.rstrip("\r\x07"))  # wdWithInTable
    out += [c.Range.Text[:-2] for c in _word_cells(doc)]
    return out


def word_write(doc: Any, new: list[str], old: list[str]) -> int:
    n_par = doc.Paragraphs.Count
    changed = 0
    for i in range(1, n_par + 1):
        if not old[i - 1] or new[i - 1] == old[i - 1]:
            continue
        rng = doc.Paragraphs(i).Range  # found again each time: never kept between edits
        rng.MoveEnd(1, -1)  # wdCharacter: keep the paragraph mark (and its style)
        rng.Text = new[i - 1]
        changed += 1
    for k, c in enumerate(_word_cells(doc)):
        j = n_par + k
        if old[j] and new[j] != old[j]:
            rng = c.Range
            rng.MoveEnd(1, -1)
            rng.Text = new[j]
            changed += 1
    return changed


# ---------------- PowerPoint ----------------
def _ppt_frames(pres: Any) -> list[Any]:
    out = []
    for s in range(1, pres.Slides.Count + 1):
        slide = pres.Slides(s)
        for k in range(1, slide.Shapes.Count + 1):
            sh = slide.Shapes(k)
            if sh.HasTextFrame and sh.TextFrame.HasText:
                out.append(sh.TextFrame.TextRange)
    return out


def ppt_texts(pres: Any) -> list[str]:
    return [r.Text.replace("\r", "\n") for r in _ppt_frames(pres)]


def ppt_write(pres: Any, new: list[str], old: list[str]) -> int:
    changed = 0
    for r, n, o in zip(_ppt_frames(pres), new, old, strict=True):
        if o and n != o:
            r.Text = n.replace("\n", "\r")
            changed += 1
    return changed


def run(task: Any, src: Path, job: dict[str, str], ask: Any, keep_open: bool = True,
        visible: bool = True) -> dict[str, Any]:  # fmt: skip
    """The task: copy, read, AI, write, save. Office is visible (spec: Office in view)."""
    from nexvara.core.task import UserError

    out = output_path(src, job)
    shutil.copy2(src, out)
    word = src.suffix.lower() in (".docx", ".doc", ".rtf")
    if word:
        from nexvara.skills.word.ops import WordSession as Session
    else:
        from nexvara.skills.powerpoint.ops import PowerPointSession as Session
    with Session(visible=visible, keep_open=keep_open) as app:
        doc = app.open_document(out) if word else app.open_presentation(out)
        with task.step(f"Matnni o‘qish: {src.name}") as s:
            old = word_texts(doc) if word else ppt_texts(doc)
            total = sum(len(t) for t in old)
            if not total:
                raise UserError("Faylda matn topilmadi")
            if total > MAX_CHARS:
                raise UserError(f"Fayl juda katta ({total} belgi) — {MAX_CHARS} gacha")
            s.detail = f"{sum(1 for t in old if t.strip())} ta qism, {total} belgi"
        what = "Tarjima" if job["mode"] == "translate" else "Qayta yozish"
        with task.step(f"{what} (AI)") as s:
            new = transform(old, job, ask)
            s.detail = job.get("lang") or job.get("style", "")
        with task.step("Yangi faylga yozish") as s:
            n = word_write(doc, new, old) if word else ppt_write(doc, new, old)
            doc.Save()
            s.detail = f"{n} ta qism o‘zgardi"
        if hasattr(app, "show"):
            app.show()
        del doc
    return {"path": str(out), "files": [str(out)],
            "report": [f"{what}: {out.name} (asl fayl o‘zgarmadi)"]}  # fmt: skip
