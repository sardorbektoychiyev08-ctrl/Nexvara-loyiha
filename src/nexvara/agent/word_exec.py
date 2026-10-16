"""Execute a parsed Word plan live in Word. The original stays untouched unless the user
says "ustiga saqla" (a backup is made first); results go to "<name>_NEXVARA.docx"."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from nexvara.agent import files
from nexvara.agent.excel_exec import CommandError
from nexvara.agent.parse import DESCRIBE, Plan
from nexvara.core.task import Task

WD_LINE_SPACE_MULTIPLE = 5
WD_ALIGN_JUSTIFY = 3


def run_word_plan(
    task: Task,
    plan: Plan,
    source: Path,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.3,
) -> dict[str, Any]:
    from nexvara.skills.word.ops import WordSession

    if plan.app != "word":
        raise CommandError("Bu reja Word uchun emas")
    overwrite = any(a.kind == "save" and a.args.get("overwrite") for a in plan.actions)
    out = source if overwrite and source.suffix.lower() == ".docx" else files.output_path(
        source, ".docx"
    )  # fmt: skip
    with WordSession(visible=visible, keep_open=keep_open) as w:
        return _execute(task, w, plan, source, out, overwrite, visible, pause, keep_open)


def _execute(task, w, plan, source, out, overwrite, visible, pause, keep_open) -> dict[str, Any]:
    # COM objects live only in this frame, so they are released before Word quits.
    from nexvara.skills.word import ops

    report: list[str] = []
    checks: list[dict[str, Any]] = []
    expect: list[tuple[str, Any]] = []  # things to verify after reopening

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with task.step(f"Faylni ochish: {source.name}") as s:
        doc = w.open_document(source)
        w.show()
        s.detail = f"{doc.Paragraphs.Count} paragraf, {doc.ComputeStatistics(2)} sahifa"
    beat()

    pdf_path = None
    for a in plan.actions:
        if a.kind in ("open", "save"):
            continue
        title = "Hujjatni rasmiy formatlash" if a.kind == "format" else DESCRIBE.get(a.kind, a.kind)
        with task.step(title) as s:
            k = a.kind
            if k == "replace":
                n = ops.find_replace(doc, a.args["find"], a.args["replace"])
                if n == 0:
                    raise CommandError(f"Hujjatda «{a.args['find']}» topilmadi")
                s.detail = f"«{a.args['find']}» → «{a.args['replace']}»: {n} ta"
                expect.append(("replace", a.args))
            elif k == "font":
                if not a.args.get("name") and not a.args.get("size"):
                    raise CommandError("Qaysi shrift yoki o‘lcham kerakligini yozing")
                font = doc.Content.Font
                if a.args.get("name"):
                    font.Name = a.args["name"]
                if a.args.get("size"):
                    font.Size = a.args["size"]
                del font
                s.detail = " ".join(str(x) for x in (a.args.get("name"), a.args.get("size")) if x)
                expect.append(("font", a.args))
            elif k == "spacing":
                pf = doc.Content.ParagraphFormat
                pf.LineSpacingRule = WD_LINE_SPACE_MULTIPLE
                pf.LineSpacing = 12 * float(a.args["value"])  # Word expresses "lines" in points
                del pf
                s.detail = f"{a.args['value']} qator"
                expect.append(("spacing", a.args["value"]))
            elif k == "indent":
                _set_body(doc, FirstLineIndent=ops.cm_to_pt(a.args["cm"]))
                s.detail = f"{a.args['cm']} sm"
                expect.append(("indent", a.args["cm"]))
            elif k == "page_setup":
                ops.page_setup(doc)
                s.detail = "A4, chetlar: yuqori 2, o‘ng 1,5, past 2, chap 3 sm"
                expect.append(("page_setup", None))
            elif k == "page_numbers":
                footer = doc.Sections(1).Footers(ops.WD_HEADER_FOOTER_PRIMARY)
                if footer.PageNumbers.Count == 0:
                    footer.PageNumbers.Add(ops.WD_PAGE_NUMBER_CENTER, True)
                del footer
                s.detail = "pastda, markazda"
                expect.append(("page_numbers", None))
            elif k == "toc":
                if not ops.outline(doc):
                    raise CommandError("Mundarija uchun hujjatda sarlavha uslubidagi qatorlar yo‘q")
                if doc.TablesOfContents.Count:
                    doc.TablesOfContents(1).Update()
                else:
                    rng = doc.Range(0, 0)
                    rng.InsertParagraphBefore()
                    rng = doc.Range(0, 0)
                    toc = doc.TablesOfContents.Add(rng, True, 1, 3)
                    toc.Update()
                    del toc
                    del rng
                s.detail = f"{len(ops.outline(doc))} ta sarlavha"
                expect.append(("toc", None))
            elif k == "spelling":
                n = ops.spelling_error_count(doc)
                s.detail = (
                    f"{n} ta imlo xatosi belgilangan (o‘zbek lug‘ati bo‘lmasa hammasi ko‘rinmaydi)"
                )
            elif k == "format":
                ops.page_setup(doc)
                font = doc.Content.Font
                font.Name, font.Size = "Times New Roman", 14
                del font
                pf = doc.Content.ParagraphFormat
                pf.LineSpacingRule, pf.LineSpacing = WD_LINE_SPACE_MULTIPLE, 18
                del pf
                _set_body(doc, FirstLineIndent=ops.cm_to_pt(1.25), Alignment=WD_ALIGN_JUSTIFY)
                s.detail = "rasmiy hujjat: A4, Times New Roman 14, 1,5 qator, xatboshi 1,25 sm"
                expect.append(("font", {"name": "Times New Roman", "size": 14}))
            elif k == "pdf":
                pdf_path = True
                s.detail = "saqlashda yaratiladi"
            else:
                raise CommandError(f"Word uchun bu buyruq hali qo‘llanmaydi: «{a.text}»")
            report.append(f"{title}: {s.detail}")
        beat()

    with task.step("Saqlash") as s:
        if overwrite:
            files.backup(source)
            report.append("Asl fayl ustiga saqlandi (oldin .bak nusxasi olindi)")
        w.save_as(doc, out, overwrite=overwrite)
        if pdf_path:
            pdf_path = files.output_path(source, ".pdf")
            ops.export_pdf(doc, pdf_path)
        s.detail = out.name
        w.disown(doc)
        doc.Close(ops.WD_DO_NOT_SAVE)
        del doc
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        doc2 = w.open_document(out)
        w.show()
        text = str(doc2.Content.Text)
        for kind, arg in expect:
            if kind == "replace":
                ok = arg["find"] not in text or arg["find"] in arg["replace"]
                checks.append({"name": "Almashtirildi", "ok": ok and arg["replace"] in text})
            elif kind == "font":
                f = _first_body(doc2).Range.Font
                ok = (not arg.get("name") or f.Name == arg["name"]) and (
                    not arg.get("size") or abs(f.Size - arg["size"]) < 0.01
                )
                checks.append({"name": "Shrift", "ok": ok, "detail": f"{f.Name} {f.Size}"})
                del f
            elif kind == "spacing":
                ls = _first_body(doc2).LineSpacing
                checks.append({"name": "Qator oralig‘i", "ok": abs(ls - 12 * arg) < 0.1})
            elif kind == "page_setup":
                ps = doc2.PageSetup
                checks.append({"name": "A4", "ok": abs(ps.PageWidth - 595.3) < 1})
                del ps
            elif kind == "page_numbers":
                n = doc2.Sections(1).Footers(ops.WD_HEADER_FOOTER_PRIMARY).PageNumbers.Count
                checks.append({"name": "Sahifa raqamlari", "ok": n >= 1})
            elif kind == "toc":
                checks.append({"name": "Mundarija", "ok": doc2.TablesOfContents.Count >= 1})
        if pdf_path:
            ok = Path(pdf_path).is_file() and Path(pdf_path).read_bytes()[:5] == b"%PDF-"
            checks.append({"name": "PDF", "ok": ok, "detail": Path(pdf_path).name})
        checks.append({"name": "Fayl ochiladi", "ok": True, "detail": out.name})
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o‘tdi"
        if failed:
            raise CommandError("Tekshiruv o‘tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            w.disown(doc2)
            doc2.Close(ops.WD_DO_NOT_SAVE)
    return {
        "path": str(out),
        "source": str(source),
        "pdf": str(pdf_path) if pdf_path else "",
        "report": report,
        "checks": checks,
        "unknown": plan.unknown,
    }


def _set_body(doc: Any, **props: Any) -> None:
    """Set paragraph properties on normal text paragraphs only (not headings or table cells)."""
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        if int(p.OutlineLevel) == 10 and not p.Range.Information(12) and str(p.Range.Text).strip():
            for name, value in props.items():
                setattr(p, name, value)


def _first_body(doc: Any) -> Any:
    """First normal text paragraph (skips headings, table cells and the table of contents)."""
    toc = doc.TablesOfContents(1).Range if doc.TablesOfContents.Count else None
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        in_toc = toc is not None and toc.Start <= p.Range.Start < toc.End
        if (
            int(p.OutlineLevel) == 10
            and not in_toc
            and not p.Range.Information(12)
            and str(p.Range.Text).strip()
        ):
            return p
    return doc.Paragraphs(1)
