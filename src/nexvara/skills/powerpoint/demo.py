"""First real PowerPoint task: a 6-slide presentation built live, saved, reopened, verified."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from nexvara.core.task import Task
from nexvara.skills.common import validate_output_path
from nexvara.skills.excel.dashboard import CATEGORIES, REGIONS, data_rows, expected_figures

TITLES = [
    "NEXVARA: 2026-yil savdo natijalari",
    "Kun tartibi",
    "Hududlar bo'yicha daromad",
    "Hududlar diagrammasi",
    "Kategoriyalar ulushi",
    "Xulosa va keyingi qadamlar",
]


def default_output_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.home() / "Documents" / "NEXVARA" / f"nexvara-taqdimot-{stamp}.pptx"


class VerificationError(Exception):
    pass


def mln(v: float) -> int:
    return round(v / 1_000_000)


def figures() -> dict[str, Any]:
    exp = expected_figures(data_rows())
    regions = sorted(REGIONS, key=lambda r: exp["by_region"][r], reverse=True)
    return {"exp": exp, "regions": regions}


def run_presentation(
    task: Task,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.4,
) -> dict[str, Any]:
    from nexvara.skills.powerpoint.ops import PowerPointSession

    out = Path(out_path) if out_path else default_output_path()
    validate_output_path(out, (".pptx",))
    pdf = out.with_suffix(".pdf")
    validate_output_path(pdf, (".pdf",))

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with PowerPointSession(visible=visible, keep_open=keep_open) as pp:
        checks = _build_and_verify(task, pp, out, pdf, beat, keep_open)
    return {"path": str(out), "pdf": str(pdf), "checks": checks}


def _build_and_verify(
    task: Task, pp: Any, out: Path, pdf: Path, beat: Any, keep_open: bool
) -> list[dict[str, Any]]:
    # COM objects live only in this frame, so they are released before PowerPoint quits.
    from nexvara.skills.png_chart import bar_chart_png
    from nexvara.skills.powerpoint import ops

    f = figures()
    exp, regions = f["exp"], f["regions"]

    with task.step("PowerPoint'ni ochish") as s:
        pres = pp.new_presentation()
        ops.apply_theme(pres)
        pp.show()
        s.detail = f"PowerPoint {pp.version}, 16:9"
    beat()

    with task.step("Sarlavha va kun tartibi"):
        sl = ops.add_title_slide(pres, TITLES[0], time.strftime("%d.%m.%Y") + " · NEXVARA")
        ops.set_notes(sl, "Salomlashish va taqdimot maqsadi.")
        # The conclusion is created early on purpose and moved to the end later (reorder check).
        revenue = f"{mln(exp['revenue']):,}".replace(",", " ")
        sl = ops.add_bullets_slide(
            pres,
            TITLES[5],
            [
                f"Yillik daromad: {revenue} mln so'm",
                f"Sof foyda marjasi: {exp['margin']:.1%}",
                f"Eng kuchli hudud: {exp['best_region']}",
                "Keyingi chorak: xarajatlarni nazorat qilish",
            ],
        )
        ops.set_notes(sl, "Asosiy xulosalarni qisqacha takrorlang.")
        sl = ops.add_bullets_slide(pres, TITLES[1], [*TITLES[2:5], "Xulosa"])
        ops.set_notes(sl, "Taqdimot tuzilmasini tushuntiring.")
        ops.animate(sl, sl.Shapes.Placeholders(2))
        pp.show()
    beat()

    with task.step("Jadval slaydi"):
        rows: list[list[Any]] = [["Hudud", "Daromad (mln so'm)", "Ulush"]]
        for r in regions:
            share = exp["by_region"][r] / exp["revenue"]
            rows.append([r, mln(exp["by_region"][r]), f"{share:.1%}"])
        sl = ops.add_table_slide(pres, TITLES[2], rows, numeric_columns=(2, 3))
        ops.set_notes(sl, "Toshkent eng katta ulushga ega.")
    beat()

    with task.step("Grafik slaydi"):
        values = [mln(exp["by_region"][r]) for r in regions]
        sl = ops.add_chart_slide(pres, TITLES[3], regions, {"Daromad (mln)": values})
        ops.set_notes(sl, "Hududlar o'rtasidagi farqni ko'rsating.")
        pp.show()
    beat()

    with task.step("Rasm slaydi"):
        with tempfile.TemporaryDirectory() as tmp:
            png = bar_chart_png([exp["by_cat"][c] for c in CATEGORIES], Path(tmp) / "cat.png")
            sl = ops.add_picture_slide(pres, TITLES[4], png, " · ".join(CATEGORIES))
        ops.set_notes(sl, "Texnika kategoriyasi yetakchi.")
    beat()

    with task.step("Tartib, o'tishlar, joylashuv") as s:
        ops.move_slide(pres, 2, pres.Slides.Count)  # conclusion to the end
        for i in range(1, pres.Slides.Count + 1):
            ops.set_transition(pres.Slides(i))
        problems = []
        for i in range(1, pres.Slides.Count + 1):
            problems += ops.layout_problems(pres.Slides(i))
        s.detail = f"{pres.Slides.Count} slayd, {len(problems)} ta joylashuv muammosi"
        if problems:
            raise VerificationError("Joylashuv: " + "; ".join(problems))
    beat()

    with task.step("Saqlash (PPTX + PDF)") as s:
        pp.save_as(pres, out)
        ops.export_pdf(pres, pdf)
        s.detail = f"{out.name}, {pdf.name}"
        pp.disown(pres)
        pres.Close()
        del pres, sl
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        pres2 = pp.open_presentation(out)
        pp.show()
        checks = verify_presentation(pres2, f, pdf)
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o'tdi"
        if failed:
            raise VerificationError("Tekshiruv o'tmadi: " + ", ".join(c["name"] for c in failed))
        if not keep_open:
            pp.disown(pres2)
            pres2.Close()
    return checks


def verify_presentation(pres: Any, f: dict[str, Any], pdf: Path) -> list[dict[str, Any]]:
    from nexvara.skills.powerpoint import ops

    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    exp, regions = f["exp"], f["regions"]
    n = pres.Slides.Count
    slides = [pres.Slides(i) for i in range(1, n + 1)]
    check("6 ta slayd", n == 6, str(n))
    titles = [ops.slide_title(s) for s in slides]
    check("Slaydlar tartibi", titles == TITLES, " | ".join(titles))
    ps = pres.PageSetup
    check("16:9", ps.SlideWidth == ops.SLIDE_W and ps.SlideHeight == ops.SLIDE_H)
    check("Ma'ruzachi izohlari", all(ops.notes(s).strip() for s in slides))
    effects = [s.SlideShowTransition.EntryEffect for s in slides]
    check("O'tishlar", all(e == ops.PP_EFFECT_FADE for e in effects), str(effects))
    check("Animatsiya", slides[1].TimeLine.MainSequence.Count >= 1)

    shapes = [s.Shapes(i) for s in slides for i in range(1, s.Shapes.Count + 1)]
    tables = [sh for sh in shapes if sh.HasTable]
    ok_t = len(tables) == 1
    if ok_t:
        t = tables[0].Table
        first = str(t.Cell(2, 1).Shape.TextFrame.TextRange.Text)
        ok_t = t.Rows.Count == len(regions) + 1 and first == regions[0]
    check("Jadval", ok_t)

    charts = [sh for sh in shapes if sh.HasChart]
    ok_c = len(charts) == 1
    vals: list[Any] = []
    if ok_c:
        vals = list(charts[0].Chart.SeriesCollection(1).Values)
        ok_c = vals == [mln(exp["by_region"][r]) for r in regions]
    check("Grafik qiymatlari", ok_c, str(vals))

    pics = sum(1 for sh in shapes if sh.Type == 13)  # msoPicture
    check("Rasm", pics == 1, str(pics))

    problems = [p for s in slides for p in ops.layout_problems(s)]
    check("Matn sig'adi, ustma-ust yo'q", not problems, "; ".join(problems)[:200])
    check("PDF", pdf.is_file() and pdf.read_bytes()[:5] == b"%PDF-", str(pdf))
    del shapes, slides, tables, charts
    return checks
