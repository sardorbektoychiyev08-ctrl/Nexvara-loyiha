"""Execute a parsed Word plan live in Word. The original stays untouched unless the user
says "ustiga saqla" (a backup is made first); results go to "<name>_NEXVARA.docx"."""

from __future__ import annotations

import re
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
                if doc.Tables.Count:
                    s.detail += "; " + _wd_tables(doc, a, ops, expect)
            elif k == "pdf":
                pdf_path = True
                s.detail = "saqlashda yaratiladi"
            elif k in _EXTRA:
                s.detail = _EXTRA[k](doc, a, ops, expect)
            else:
                raise CommandError(f"Word uchun bu buyruq hali qo‘llanmaydi: «{a.text}»")
            report.append(f"{title}: {s.detail}")
        beat()

    if all(a.kind in ("open", "check", "count", "spelling") for a in plan.actions):
        if not keep_open:  # a report only: the document is not copied or changed
            w.disown(doc)
            doc.Close(ops.WD_DO_NOT_SAVE)
        del doc
        return {"path": str(source), "source": str(source), "pdf": "", "report": report,
                "checks": [{"name": "Tekshiruv", "ok": True}], "unknown": plan.unknown}  # fmt: skip

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
            else:
                checks.append(_verify(doc2, kind, arg, ops))
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


# ---------------- professional commands ----------------
def _headings(doc: Any) -> list[Any]:
    return [doc.Paragraphs(i) for i in range(1, doc.Paragraphs.Count + 1)
            if 1 <= int(doc.Paragraphs(i).OutlineLevel) <= 9]  # fmt: skip


def _wd_align(doc: Any, a: Any, ops: Any, expect: list) -> str:
    how = a.args.get("how", "justify")
    value = ops.ALIGN[how]
    if a.args.get("target") == "headings":
        heads = _headings(doc)
        if not heads:
            raise CommandError("Hujjatda sarlavha uslubidagi qator yo‘q")
        for p in heads:
            p.Alignment = value
        expect.append(("align_headings", value))
        return f"{len(heads)} ta sarlavha: {_ALIGN_UZ[how]}"
    _set_body(doc, Alignment=value)
    expect.append(("align", value))
    return f"asosiy matn: {_ALIGN_UZ[how]}"


_ALIGN_UZ = {"left": "chapga", "center": "markazga", "right": "o‘ngga",
             "justify": "kenglik bo‘yicha (ikki tomonga)"}  # fmt: skip


def _wd_header(doc: Any, a: Any, ops: Any, expect: list) -> str:
    text, where = a.args["text"], a.args.get("where", "header")
    for i in range(1, doc.Sections.Count + 1):
        sec = doc.Sections(i)
        hf = sec.Footers(1) if where == "footer" else sec.Headers(1)
        rng = hf.Range
        if where == "footer" and hf.PageNumbers.Count and str(rng.Text).strip():
            rng.InsertBefore(text + "\t")  # keep the page number that is already there
        else:
            rng.Text = text
            rng.ParagraphFormat.Alignment = ops.ALIGN["center" if where == "footer" else "right"]
            rng.Font.Size = 10
        del rng, hf, sec
    expect.append((where, text))
    return f"{'pastki' if where == 'footer' else 'yuqori'} kolontitul: «{text}»"


def _wd_orientation(doc: Any, a: Any, ops: Any, expect: list) -> str:
    value = ops.ORIENTATION["landscape" if a.args.get("landscape") else "portrait"]
    for i in range(1, doc.Sections.Count + 1):
        doc.Sections(i).PageSetup.Orientation = value
    expect.append(("orientation", value))
    return "albom (yotiq)" if value == 1 else "kitob (tik)"


def _wd_margins(doc: Any, a: Any, ops: Any, expect: list) -> str:
    names = {"top": "TopMargin", "right": "RightMargin", "bottom": "BottomMargin",
             "left": "LeftMargin"}  # fmt: skip
    uz = {"top": "yuqori", "right": "o‘ng", "bottom": "past", "left": "chap"}
    for i in range(1, doc.Sections.Count + 1):
        ps = doc.Sections(i).PageSetup
        for side, cm in a.args.items():
            setattr(ps, names[side], ops.cm_to_pt(cm))
        del ps
    expect.append(("margins", dict(a.args)))
    return ", ".join(f"{uz[s]} {str(v).replace('.', ',').removesuffix(',0')} sm"
                     for s, v in a.args.items())  # fmt: skip


def _wd_clean(doc: Any, a: Any, ops: Any, expect: list) -> str:
    """Double spaces, spaces before punctuation, empty paragraphs (outside tables)."""
    fixed = 0
    for find, repl in (("  ", " "), (" ,", ","), (" .", "."), (" ;", ";"), (" :", ":"),
                       (" !", "!"), (" ?", "?")):  # fmt: skip
        for _ in range(30):  # "    " needs several passes
            n = str(doc.Content.Text).count(find)
            if not n:
                break
            # One pass turns "    " into "  "; find_replace would call that a failure.
            ops._find_execute(doc.Content, find, True, repl, ops.WD_REPLACE_ALL)
            fixed += n
    empty = 0
    for i in range(doc.Paragraphs.Count, 1, -1):
        p = doc.Paragraphs(i)
        rng = p.Range
        if (str(rng.Text).strip() == "" and not rng.Information(12)
                and rng.InlineShapes.Count == 0 and rng.ShapeRange.Count == 0):  # fmt: skip
            prev = str(doc.Paragraphs(i - 1).Range.Text).strip()
            if prev == "" or i == doc.Paragraphs.Count:
                rng.Delete()
                empty += 1
        del rng, p
    expect.append(("clean", None))
    return f"{fixed} ta ortiqcha bo‘sh joy, {empty} ta bo‘sh qator olib tashlandi"


def _wd_count(doc: Any, a: Any, ops: Any, expect: list) -> str:
    words, chars, pages = (int(doc.ComputeStatistics(k)) for k in (0, 3, 2))
    paras = int(doc.ComputeStatistics(4))
    return f"{words} so‘z, {chars} belgi, {paras} xatboshi, {pages} sahifa"


def _wd_title(doc: Any, a: Any, ops: Any, expect: list) -> str:
    for i in range(1, doc.Paragraphs.Count + 1):
        p = doc.Paragraphs(i)
        text = str(p.Range.Text).strip()
        if text and not p.Range.Information(12):
            p.Style = ops.STYLE_HEADING[1]
            p.Alignment = ops.ALIGN["center"]
            expect.append(("title", text))
            return f"«{text[:60]}» — 1-darajali sarlavha (mundarijaga kiradi)"
    raise CommandError("Hujjatda matn yo‘q")


def _wd_tables(doc: Any, a: Any, ops: Any, expect: list) -> str:
    from nexvara.skills.excel.table import excel_color

    n = doc.Tables.Count
    if not n:
        raise CommandError("Hujjatda jadval yo‘q")
    for i in range(1, n + 1):
        t = doc.Tables(i)
        t.Borders.Enable = True
        head = t.Rows(1)
        head.Range.Font.Bold = True
        head.HeadingFormat = -1  # repeat the header row on every page
        head.Shading.BackgroundPatternColor = excel_color("#E0E7FF")
        t.AutoFitBehavior(ops.WD_AUTOFIT_WINDOW)
        del head, t
    expect.append(("tables", n))
    return f"{n} ta jadval: chegaralar, qalin sarlavha, sarlavha har sahifada"


_ODD_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b")


def _wd_check(doc: Any, a: Any, ops: Any, expect: list) -> str:
    """Official rules (knowledge/office_guide.py: Microsoft, VM 140-son qarori): a report."""
    problems: list[str] = []
    n = doc.Paragraphs.Count
    pages = int(doc.ComputeStatistics(2))
    heads = ops.outline(doc)
    fake, empty_runs, run, sizes, fonts = [], 0, 0, set(), set()
    for i in range(1, min(n, 1500) + 1):
        p = doc.Paragraphs(i)
        rng = p.Range
        text = str(rng.Text).strip()
        in_table = bool(rng.Information(12))
        if not text and not in_table and rng.InlineShapes.Count == 0:
            run += 1
            if run == 2:
                empty_runs += 1
        else:
            run = 0
        if text and not in_table and int(p.OutlineLevel) == 10:
            if len(text) < 80 and rng.Font.Bold == -1 and not text.endswith((".", ":", ",")):
                fake.append(text[:40])  # looks like a heading but has no heading style
            if rng.Font.Size and float(rng.Font.Size) < 900:  # 9999999 = mixed
                sizes.add(float(rng.Font.Size))
            if str(rng.Font.Name):
                fonts.add(str(rng.Font.Name))
        del rng, p
    if fake:
        problems.append("Sarlavhaga o‘xshash, lekin sarlavha uslubisiz qatorlar (mundarijaga "
                        "kirmaydi): " + "; ".join(f"«{t}»" for t in fake[:4]))  # fmt: skip
    if pages >= 3 and not heads:
        problems.append("Uzun hujjatda sarlavha uslublari yo‘q — mundarija tuzib bo‘lmaydi")
    if empty_runs:
        problems.append(f"{empty_runs} joyda ketma-ket bo‘sh qatorlar (oraliq paragraf oralig‘i "
                        "bilan beriladi)")  # fmt: skip
    text_all = str(doc.Content.Text)
    if "  " in text_all:
        problems.append(f"{text_all.count('  ')} joyda ikkita bo‘sh joy («ortiqcha bo‘sh joylarni "
                        "tozala»)")  # fmt: skip
    if len(fonts) > 2:
        problems.append("Asosiy matnda shriftlar aralash: " + ", ".join(sorted(fonts)[:4]))
    if sizes and min(sizes) < 12:
        problems.append(f"Asosiy matn {min(sizes):g} pt — rasmiy hujjat uchun 12–14 pt")
    if pages >= 2 and doc.Sections(1).Footers(1).PageNumbers.Count == 0:
        problems.append("Sahifa raqamlari yo‘q («sahifa raqamlarini qo‘y»)")
    odd = sorted(set(_ODD_DATE.findall(text_all)))
    if odd:
        problems.append("Sana shakli: " + ", ".join(odd[:3]) + " — rasmiy hujjatda «2026-yil "
                        "18-oktabr» yoki «18.10.26» (VM 140-son qarori, 16-band)")  # fmt: skip
    for i in range(1, doc.Tables.Count + 1):
        if not doc.Tables(i).Uniform:
            problems.append(f"{i}-jadvalda birlashtirilgan kataklar bor")
    no_alt = sum(1 for i in range(1, doc.InlineShapes.Count + 1)
                 if not str(doc.InlineShapes(i).AlternativeText).strip())  # fmt: skip
    if no_alt:
        problems.append(f"{no_alt} ta rasmda izoh (alt matn) yo‘q")
    spell = ops.spelling_error_count(doc)
    if spell:
        problems.append(f"{spell} ta imlo belgisi (o‘zbek lug‘ati bo‘lmasa ba’zilari xato emas)")
    if not problems:
        return "Kamchilik topilmadi (Microsoft va VM 140-son qarori talablari bo‘yicha)"
    return f"{len(problems)} ta tavsiya: " + "; ".join(problems)


_UZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr",
              "oktabr", "noyabr", "dekabr"]  # fmt: skip


def _uz_date(raw: str) -> str | None:
    """2026-10-18 or 18/10/2026 -> «2026-yil 18-oktabr» (VM 140-son qarori, 16-band)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw) or None
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", raw)
        if not m:
            return None
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y}-yil {d}-{_UZ_MONTHS[mo - 1]}"


def _wd_fix(doc: Any, a: Any, ops: Any, expect: list) -> str:
    """Fix what «tekshir» finds: spaces and empty lines, bold lines without a heading style,
    small or mixed body text, page numbers, non-standard dates."""
    done: list[str] = []
    cleaned = _wd_clean(doc, a, ops, [])
    if not cleaned.startswith("0 ta ortiqcha bo‘sh joy, 0"):
        done.append(cleaned)
    heads = 0
    for i in range(1, min(doc.Paragraphs.Count, 1500) + 1):
        p = doc.Paragraphs(i)
        rng = p.Range
        text = str(rng.Text).strip()
        if (text and int(p.OutlineLevel) == 10 and not rng.Information(12) and len(text) < 80
                and rng.Font.Bold == -1 and not text.endswith((".", ":", ","))):  # fmt: skip
            p.Style = ops.STYLE_HEADING[1 if heads == 0 else 2]
            heads += 1
        del rng, p
    if heads:
        done.append(f"{heads} ta qator sarlavha uslubiga o‘tkazildi (mundarijaga kiradi)")
    sizes, fonts = set(), set()
    for i in range(1, min(doc.Paragraphs.Count, 1500) + 1):
        p = doc.Paragraphs(i)
        if int(p.OutlineLevel) == 10 and not p.Range.Information(12) and str(p.Range.Text).strip():
            if p.Range.Font.Size and float(p.Range.Font.Size) < 900:
                sizes.add(float(p.Range.Font.Size))
            fonts.add(str(p.Range.Font.Name))
        del p
    if (sizes and min(sizes) < 12) or len(fonts) > 2:
        for i in range(1, min(doc.Paragraphs.Count, 1500) + 1):
            p = doc.Paragraphs(i)
            if int(p.OutlineLevel) == 10 and not p.Range.Information(12):
                p.Range.Font.Name, p.Range.Font.Size = "Times New Roman", 14
            del p
        done.append("asosiy matn: Times New Roman 14")
        expect.append(("font", {"name": "Times New Roman", "size": 14}))
    if int(doc.ComputeStatistics(2)) >= 2 and doc.Sections(1).Footers(1).PageNumbers.Count == 0:
        doc.Sections(1).Footers(1).PageNumbers.Add(ops.WD_PAGE_NUMBER_CENTER, True)
        done.append("sahifa raqamlari qo‘yildi")
        expect.append(("page_numbers", None))
    for raw in sorted(set(_ODD_DATE.findall(str(doc.Content.Text)))):
        new = _uz_date(raw)
        if new:
            ops.find_replace(doc, raw, new)
            done.append(f"sana «{raw}» → «{new}»")
    if doc.Tables.Count and any(
        not bool(doc.Tables(i).Borders.Enable) for i in range(1, doc.Tables.Count + 1)
    ):
        done.append(_wd_tables(doc, a, ops, expect))
    expect.append(("clean", None))
    return "; ".join(done) if done else "Tuzatiladigan kamchilik topilmadi"


def _wd_smartart(doc: Any, a: Any, ops: Any, expect: list) -> str:
    """A SmartArt diagram at the end of the document (inline, page width)."""
    from nexvara.skills import smartart

    kind, items = a.args["kind"], a.args["items"]
    app = doc.Application
    layout = smartart.find_layout(app, kind)
    if a.args.get("title"):
        ops.add_paragraph(doc, a.args["title"], ops.STYLE_HEADING[2])
    ops.add_paragraph(doc, "")
    rng = doc.Paragraphs(doc.Paragraphs.Count).Range
    shape = doc.InlineShapes.AddSmartArt(layout, rng)  # (Layout, Range): positional
    sec = doc.Sections(1).PageSetup
    shape.Width = float(sec.PageWidth - sec.LeftMargin - sec.RightMargin)
    got = smartart.fill(shape.SmartArt, kind, items)
    if got != items:
        raise CommandError(f"SmartArt matnlari mos kelmadi: {got}")
    return f"{smartart.LABELS[kind]} sxemasi, {len(items)} ta bo‘lak"


_EXTRA = {
    "smartart": _wd_smartart,
    "check": _wd_check,
    "fix": _wd_fix,
    "align": _wd_align, "header": _wd_header, "orientation": _wd_orientation,
    "margins": _wd_margins, "clean": _wd_clean, "count": _wd_count, "title": _wd_title,
    "tables": _wd_tables,
}  # fmt: skip


def _verify(doc: Any, kind: str, arg: Any, ops: Any) -> dict[str, Any]:
    """Re-read one property of the saved document."""
    if kind == "align":
        return {"name": "Tekislash", "ok": int(_first_body(doc).Alignment) == arg}
    if kind == "align_headings":
        return {"name": "Sarlavhalar", "ok": all(int(p.Alignment) == arg for p in _headings(doc))}
    if kind in ("header", "footer"):
        sec = doc.Sections(1)
        hf = sec.Footers(1) if kind == "footer" else sec.Headers(1)
        return {"name": "Kolontitul", "ok": arg in str(hf.Range.Text)}
    if kind == "orientation":
        return {"name": "Sahifa yo‘nalishi", "ok": int(doc.PageSetup.Orientation) == arg}
    if kind == "margins":
        names = {"top": "TopMargin", "right": "RightMargin", "bottom": "BottomMargin",
                 "left": "LeftMargin"}  # fmt: skip
        ps = doc.PageSetup
        ok = all(abs(getattr(ps, names[s]) - ops.cm_to_pt(v)) < 0.6 for s, v in arg.items())
        return {"name": "Chetlar", "ok": ok}
    if kind == "indent":
        got = float(_first_body(doc).FirstLineIndent)
        return {"name": "Xatboshi", "ok": abs(got - ops.cm_to_pt(arg)) < 0.6, "detail": f"{got}"}
    if kind == "clean":
        text = str(doc.Content.Text)
        return {"name": "Ortiqcha bo‘sh joy yo‘q", "ok": "  " not in text}
    if kind == "title":
        heads = [str(p.Range.Text).strip() for p in _headings(doc)]
        return {"name": "Sarlavha", "ok": arg in heads}
    if kind == "tables":
        ok = all(bool(doc.Tables(i).Borders.Enable) for i in range(1, doc.Tables.Count + 1))
        return {"name": "Jadvallar", "ok": ok and doc.Tables.Count == arg}
    return {"name": kind, "ok": True}
