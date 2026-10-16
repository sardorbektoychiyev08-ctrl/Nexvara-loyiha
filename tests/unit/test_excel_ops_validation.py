"""Argument checks in ops.py that must fail before any COM call."""

import pytest

from nexvara.skills.excel import ops


class Untouchable:
    def __getattr__(self, name):
        raise AssertionError(f"COM object touched: {name}")


def test_highlight_rejects_bad_operator_and_decimals():
    with pytest.raises(ValueError):
        ops.highlight_cells(Untouchable(), "!=", 5)
    with pytest.raises(ValueError):
        ops.highlight_cells(Untouchable(), ">", 1.5)


def test_add_chart_rejects_unknown_kind():
    with pytest.raises(ValueError):
        ops.add_chart(Untouchable(), Untouchable(), "radar3d")


def test_write_rows_validates_shape():
    with pytest.raises(ValueError):
        ops.write_rows(Untouchable(), [])
    with pytest.raises(ValueError):
        ops.write_rows(Untouchable(), [[1, 2], [3]])


def test_export_paths_validated(tmp_path):
    with pytest.raises(ValueError):
        ops.export_csv(Untouchable(), "relative.csv")
    with pytest.raises(ValueError):
        ops.export_csv(Untouchable(), tmp_path / "x.txt")
    with pytest.raises(ValueError):
        ops.export_pdf(Untouchable(), tmp_path / "x.csv")


def test_number_format_lookup():
    class App:
        International = (None, None, ",", " ")  # decimal, thousands at [2], [3]

    class Rng:
        Application = App()
        NumberFormat = None
        NumberFormatLocal = None

    r = Rng()
    ops.set_number_format(r, "date")
    assert r.NumberFormat == "dd.mm.yyyy"
    ops.set_number_format(r, "decimal")
    assert r.NumberFormatLocal == "# ##0,00"
    ops.set_number_format(r, "0.000")
    assert r.NumberFormatLocal == "0,000"
