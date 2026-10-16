import pytest

from nexvara.skills.excel.demo import PRODUCTS, demo_spec, expected_totals
from nexvara.skills.excel.table import TableSpec, col_letter, excel_color, validate_save_path


@pytest.mark.parametrize(
    ("n", "letter"), [(1, "A"), (6, "F"), (26, "Z"), (27, "AA"), (702, "ZZ"), (703, "AAA")]
)
def test_col_letter(n, letter):
    assert col_letter(n) == letter


def test_col_letter_rejects_zero():
    with pytest.raises(ValueError):
        col_letter(0)


def test_excel_color_is_bgr():
    assert excel_color("#FF0000") == 255
    assert excel_color("#0000FF") == 255 * 65536
    assert excel_color("6366F1") == 0x63 + 0x66 * 256 + 0xF1 * 65536


def test_validate_save_path(tmp_path):
    ok = validate_save_path(tmp_path / "a.xlsx")
    assert ok.name == "a.xlsx"

    with pytest.raises(ValueError):
        validate_save_path("relative.xlsx")
    with pytest.raises(ValueError):
        validate_save_path(tmp_path / "a.xls")

    existing = tmp_path / "b.xlsx"
    existing.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        validate_save_path(existing)
    assert validate_save_path(existing, overwrite=True) == existing.resolve()


def test_table_spec_validation():
    TableSpec(["a", "b"], [[1, 2]], [1, 2]).validate()
    with pytest.raises(ValueError):
        TableSpec(["a", "b"], [[1]], [1]).validate()
    with pytest.raises(ValueError):
        TableSpec(["a"], [[1]], [2]).validate()
    with pytest.raises(ValueError):
        TableSpec([], [], []).validate()


def test_demo_spec_shape():
    spec = demo_spec()
    spec.validate()
    assert len(PRODUCTS) == 10
    assert len(spec.rows) == 11  # 10 data rows + total row
    assert spec.address() == "A1:F12"
    assert spec.rows[0][5] == "=D2*E2"
    assert spec.rows[-1][3] == "=SUM(D2:D11)"
    assert spec.rows[-1][5] == "=SUM(F2:F11)"


def test_expected_totals():
    qty, amount = expected_totals()
    assert qty == 609
    assert amount == sum(q * p for _, _, q, p in PRODUCTS)


def test_is_date_format():
    from nexvara.skills.excel.table import is_date_format

    assert is_date_format("dd.mm.yyyy")
    assert is_date_format("hh:mm")
    assert not is_date_format("#,##0.00")
    assert not is_date_format("0.0%")
    assert not is_date_format('#,##0 "so\'m"')  # 's' and 'm' inside quotes
    assert not is_date_format("[Red]#,##0")
    assert not is_date_format("General")


def test_localize_number_format():
    from nexvara.skills.excel.table import localize_number_format

    assert localize_number_format("#,##0", ",", " ") == "# ##0"
    assert localize_number_format("#,##0.00", ",", " ") == "# ##0,00"
    assert localize_number_format("0.0%", ",", " ") == "0,0%"
    assert localize_number_format('#,##0 "a,b."', ",", " ") == '# ##0 "a,b."'
    assert localize_number_format("#,##0.00", ".", ",") == "#,##0.00"


def test_excel_date_roundtrip_values():
    import datetime as dt

    from nexvara.skills.excel.table import from_excel_value, to_excel_value

    assert to_excel_value(dt.date(1900, 1, 1)) == 2.0
    assert to_excel_value(dt.datetime(2026, 10, 16, 12, 0)) == 46311.5
    aware = dt.datetime(2026, 10, 16, 14, 30, tzinfo=dt.UTC)
    assert from_excel_value(aware) == dt.datetime(2026, 10, 16, 14, 30)
    assert to_excel_value("x") == "x"
