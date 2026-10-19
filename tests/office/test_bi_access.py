"""BI from a real Microsoft Access database (.accdb), read through the installed Access.
Run with NEXVARA_RUN_OFFICE=1 (Access starts in the background for a moment)."""

import datetime as dt
import os

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to drive real Access",
    ),
]


@pytest.fixture
def accdb(tmp_path):
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    p = tmp_path / "Maktab.accdb"
    app = win32com.client.DispatchEx("Access.Application")
    try:
        app.NewCurrentDatabase(str(p))
        d = app.CurrentDb()
        d.Execute("CREATE TABLE Baholar (Ism TEXT(50), Sinf TEXT(10), Fan TEXT(30), "
                  "Baho INTEGER, Sana DATETIME, Tolov CURRENCY)")  # fmt: skip
        for row in (("Ali", "7-A", "Fizika", 5, "2026-10-01", 120000),
                    ("Vali", "7-A", "Fizika", 4, "2026-10-02", 95000.5),
                    ("Gulnoza", "7-B", "Kimyo", 5, "2026-10-03", 130000)):  # fmt: skip
            d.Execute("INSERT INTO Baholar VALUES ('{}', '{}', '{}', {}, #{}#, {})".format(*row))
        d.Execute("CREATE TABLE Bosh (A TEXT(5))")
        app.CloseCurrentDatabase()
    finally:
        app.Quit()
    return p


def test_access_tables_rows_types_and_query(accdb):
    from nexvara.bi.data import load, sheets, typed

    before = accdb.read_bytes()
    assert sheets(accdb) == ["Baholar", "Bosh"]
    t = typed(load(accdb, "Baholar"))
    assert t.columns == ["Ism", "Sinf", "Fan", "Baho", "Sana", "Tolov"] and len(t.rows) == 3
    assert t.types["Baho"] == "number" and t.types["Sana"] == "date"
    assert t.rows[0][4] == dt.date(2026, 10, 1)  # no 5-hour shift from pywin32
    assert t.rows[1][5] == pytest.approx(95000.5)
    q = load(accdb, "SELECT Sinf, AVG(Baho) AS Ortacha FROM Baholar GROUP BY Sinf ORDER BY Sinf")
    assert q.columns == ["Sinf", "Ortacha"] and [r[0] for r in q.rows] == ["7-A", "7-B"]
    assert load(accdb, "Bosh").rows == []
    with pytest.raises(ValueError):
        load(accdb, "DELETE FROM Baholar")
    assert accdb.read_bytes() == before  # opened read-only
