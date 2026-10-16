import pytest

from nexvara.skills.excel import dashboard
from nexvara.skills.excel.formulas import growth, lookup, sheet_ref, sumifs


def test_lookup_fallback():
    assert lookup("A1", "B:B", "C:C", xlookup=True) == 'XLOOKUP(A1,B:B,C:C,"")'
    assert lookup("A1", "B:B", "C:C", xlookup=False) == 'IFERROR(INDEX(C:C,MATCH(A1,B:B,0)),"")'


def test_sumifs_and_growth():
    assert sumifs("E:E", ("B:B", "D4")) == "SUMIFS(E:E,B:B,D4)"
    assert sumifs("E:E", ("B:B", "D4"), ("C:C", '"x"')) == 'SUMIFS(E:E,B:B,D4,C:C,"x")'
    with pytest.raises(ValueError):
        sumifs("E:E")
    assert growth("E5", "E4") == 'IF(OR(E4="",E4=0),"",E5/E4-1)'


def test_sheet_ref_escapes_quotes():
    assert sheet_ref("Ma'lumot", "$A$1") == "'Ma''lumot'!$A$1"


def test_dashboard_data_and_expectations():
    rows = dashboard.data_rows()
    assert len(rows) == 12 * len(dashboard.REGIONS) * len(dashboard.CATEGORIES)
    exp = dashboard.expected_figures(rows)
    assert exp["profit"] == exp["revenue"] - exp["cost"]
    assert exp["loss_months"] == 1  # only LOSS_MONTH runs at a loss
    assert exp["best_region"] == "Toshkent"
    assert sum(exp["by_region"].values()) == exp["revenue"]
    assert sum(exp["by_cat"].values()) == exp["revenue"]
