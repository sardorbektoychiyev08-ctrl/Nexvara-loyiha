"""First real Excel task: build a 10-row table live, save it, reopen and verify.

Spec section 6, "Birinchi real test".
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from nexvara.core.task import Task
from nexvara.skills.excel.table import XL_CENTER, TableSpec, validate_save_path

SHEET_NAME = "Hisobot"
TOP, LEFT = 1, 1

PRODUCTS: list[tuple[str, str, int, int]] = [
    ("Daftar A4", "Kanselyariya", 120, 4500),
    ("Ruchka ko'k", "Kanselyariya", 300, 1500),
    ("Printer qog'ozi", "Ofis", 40, 52000),
    ("Kartrij HP 85A", "Ofis", 6, 310000),
    ("Papka-registr", "Kanselyariya", 55, 18000),
    ("Kalkulyator", "Texnika", 10, 95000),
    ("Sichqoncha", "Texnika", 15, 85000),
    ("Klaviatura", "Texnika", 8, 160000),
    ("Stepler", "Kanselyariya", 25, 27000),
    ("Marker to'plami", "Kanselyariya", 30, 22000),
]

HEADERS = ["№", "Mahsulot", "Kategoriya", "Soni", "Narxi (so'm)", "Jami (so'm)"]
NUMERIC_COLUMNS = [1, 4, 5, 6]


def demo_spec() -> TableSpec:
    rows: list[list[object]] = []
    for i, (name, cat, qty, price) in enumerate(PRODUCTS, start=1):
        r = TOP + i
        rows.append([i, name, cat, qty, price, f"=D{r}*E{r}"])
    first, last = TOP + 1, TOP + len(PRODUCTS)
    rows.append(["", "JAMI", "", f"=SUM(D{first}:D{last})", "", f"=SUM(F{first}:F{last})"])
    return TableSpec(HEADERS, rows, NUMERIC_COLUMNS)


def expected_totals() -> tuple[int, int]:
    qty = sum(p[2] for p in PRODUCTS)
    amount = sum(p[2] * p[3] for p in PRODUCTS)
    return qty, amount


def default_output_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.home() / "Documents" / "NEXVARA" / f"nexvara-jadval-{stamp}.xlsx"


class VerificationError(Exception):
    pass


def verify_workbook(ws: Any) -> list[dict[str, Any]]:
    """Read the saved sheet back and check values, formulas and formatting."""
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("Sheet nomi", ws.Name == SHEET_NAME, ws.Name)
    header = [ws.Cells(TOP, LEFT + i).Value for i in range(len(HEADERS))]
    check("Sarlavhalar", header == HEADERS, str(header))

    bad_rows = []
    for i, (name, _cat, qty, price) in enumerate(PRODUCTS, start=1):
        r = TOP + i
        got = (ws.Cells(r, 2).Value, ws.Cells(r, 4).Value, ws.Cells(r, 5).Value)
        total = ws.Cells(r, 6).Value
        if got != (name, qty, price) or total != qty * price or not ws.Cells(r, 6).HasFormula:
            bad_rows.append(r)
    check("10 qator ma'lumot va formulalar", not bad_rows, f"xato qatorlar: {bad_rows}")

    total_row = TOP + len(PRODUCTS) + 1
    exp_qty, exp_amount = expected_totals()
    got_qty, got_amount = ws.Cells(total_row, 4).Value, ws.Cells(total_row, 6).Value
    check(
        "JAMI qatori",
        got_qty == exp_qty and got_amount == exp_amount,
        f"Soni={got_qty} (kutilgan {exp_qty}), Jami={got_amount} (kutilgan {exp_amount})",
    )

    misaligned = []
    for c in NUMERIC_COLUMNS:
        for r in range(TOP + 1, total_row + 1):
            cell = ws.Cells(r, LEFT + c - 1)
            if cell.HorizontalAlignment != XL_CENTER or cell.VerticalAlignment != XL_CENTER:
                misaligned.append(cell.Address)
    check("Raqamlar markazda", not misaligned, ", ".join(misaligned[:5]))

    check("Sarlavha qalin", bool(ws.Cells(TOP, LEFT).Font.Bold))

    # What the user sees: thousands grouped with Excel's own separator, no decimals.
    from nexvara.skills.excel.ops import separators

    _dec, thou = separators(ws.Application)
    want = f"{exp_amount:,}".replace(",", thou)
    shown = ws.Cells(total_row, 6).Text
    check("Raqam formati ekranda", shown == want, f"{shown!r} (kutilgan {want!r})")
    return checks


def run_demo(
    task: Task,
    out_path: str | Path | None = None,
    *,
    visible: bool = True,
    keep_open: bool = True,
    pause: float = 0.4,
) -> dict[str, Any]:
    """Run the full demo as a task. `pause` slows steps so a watching user can follow."""
    from nexvara.skills.excel.bridge import ExcelSession

    out = Path(out_path) if out_path else default_output_path()
    # Fail before Excel starts if the target is unusable.
    validate_save_path(out)
    spec = demo_spec()

    def beat() -> None:
        if visible and pause:
            time.sleep(pause)
        task.check_cancelled()

    with ExcelSession(visible=visible, keep_open=keep_open) as xl:
        saved, checks = _build_and_verify(task, xl, spec, out, beat, visible, keep_open)
    return {"path": str(saved), "checks": checks}


def _build_and_verify(
    task: Task,
    xl: Any,
    spec: TableSpec,
    out: Path,
    beat: Any,
    visible: bool,
    keep_open: bool,
) -> tuple[Path, list[dict[str, Any]]]:
    # COM objects live only in this frame, so they are released before Excel quits.
    from nexvara.skills.excel.bridge import format_table, freeze_header, write_table

    with task.step("Excel'ni ochish") as s:
        xl.show()
        s.detail = f"Excel {xl.version}"
    beat()

    with task.step("Yangi workbook yaratish"):
        wb = xl.new_workbook()
        ws = wb.Worksheets(1)
        ws.Name = SHEET_NAME
        xl.show()
    beat()

    with task.step("10 qatorli jadvalni kiritish") as s:
        rng = write_table(ws, spec, TOP, LEFT)
        s.detail = rng.Address
    beat()

    with task.step("Formatlash"):
        format_table(ws, rng, spec, TOP, LEFT)
        ws.Rows(TOP + len(spec.rows)).Font.Bold = True
        if visible:
            freeze_header(xl.app, TOP)
    beat()

    with task.step("Saqlash") as s:
        saved = xl.save_as(wb, out)
        s.detail = str(saved)
        wb.Close(SaveChanges=False)
    beat()

    with task.step("Qayta ochib tekshirish") as s:
        wb2 = xl.open_workbook(saved)
        xl.show()
        checks = verify_workbook(wb2.Worksheets(SHEET_NAME))
        failed = [c for c in checks if not c["ok"]]
        s.detail = f"{len(checks) - len(failed)}/{len(checks)} tekshiruv o'tdi"
        if failed:
            names = ", ".join(c["name"] for c in failed)
            raise VerificationError(f"Tekshiruv o'tmadi: {names}")
        if not keep_open:
            wb2.Close(SaveChanges=False)
    return saved, checks
