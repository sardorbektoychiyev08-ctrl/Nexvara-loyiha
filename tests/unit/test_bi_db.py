"""BI from a database: SQLite tables and views as "sheets", one SELECT query, read-only."""

import sqlite3

import pytest

from nexvara.bi import db
from nexvara.bi.dash import auto_dashboard, compute
from nexvara.bi.data import load, sheets, typed


@pytest.fixture
def shop(tmp_path):
    p = tmp_path / "Do‘kon.db"
    con = sqlite3.connect(p)
    con.executescript(
        """
        CREATE TABLE savdo (sana TEXT, filial TEXT, mahsulot TEXT, summa REAL);
        CREATE TABLE xodim (ism TEXT, filial TEXT);
        CREATE VIEW katta AS SELECT * FROM savdo WHERE summa > 100;
        """
    )
    rows = [
        ("2026-10-01", "Chilonzor", "Non", 50.0),
        ("2026-10-02", "Yunusobod", "Sut", 120.0),
        ("2026-10-03", "Chilonzor", "Go‘sht", 300.0),
        ("2026-10-03", "Yunusobod", "Non", 40.0),
    ]
    con.executemany("INSERT INTO savdo VALUES (?, ?, ?, ?)", rows)
    con.commit()
    con.close()
    return p


def test_tables_are_the_sheets_and_load_like_a_workbook(shop):
    assert sheets(shop) == ["savdo", "xodim", "katta"]  # tables first, then views
    t = typed(load(shop))  # no table given: the first one
    assert t.columns == ["sana", "filial", "mahsulot", "summa"] and len(t.rows) == 4
    assert t.types["summa"] == "number" and t.types["sana"] == "date"
    assert len(load(shop, "katta").rows) == 2
    cfg = auto_dashboard(t, str(shop), sheet="savdo")
    res = compute(cfg, {}, table=t)
    assert res["widgets"]  # a dashboard straight from the database


def test_one_select_query_and_nothing_is_written(shop):
    q = "SELECT filial, SUM(summa) AS jami FROM savdo GROUP BY filial ORDER BY filial"
    t = load(shop, q)
    assert t.columns == ["filial", "jami"] and t.rows == [
        ["Chilonzor", 350.0],
        ["Yunusobod", 160.0],
    ]
    before = shop.read_bytes()
    for bad in ("DELETE FROM savdo", "SELECT 1; DROP TABLE savdo", "UPDATE savdo SET summa = 0",
                "SELECT * INTO x FROM savdo", "PRAGMA writable_schema = 1"):  # fmt: skip
        with pytest.raises(ValueError):
            load(shop, bad)
    with pytest.raises(LookupError):
        load(shop, "yoq_jadval")
    assert shop.read_bytes() == before  # the owner's database is untouched
    # Even a direct write through our connection is refused by SQLite (mode=ro, query_only).
    con = db._sqlite(shop)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM savdo")
    con.close()


def test_not_a_database_and_empty_table(tmp_path):
    fake = tmp_path / "rasm.db"  # Paradox or anything else with a .db name
    fake.write_bytes(b"not sqlite at all")
    with pytest.raises(ValueError):
        load(fake)
    p = tmp_path / "bosh.sqlite"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE t (a INTEGER, b TEXT)")
    con.commit()
    con.close()
    t = load(p)
    assert t.rows == [] and "Jadval bo‘sh" in t.notes


def test_api_sheets_and_auto(shop, tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    api = Api()
    assert api.bi_sheets(str(shop)) == ["savdo", "xodim", "katta"]
    out = api.bi_auto(str(shop), "SELECT mahsulot, summa FROM savdo")
    assert out["ok"] and out["config"]["sheet"] == "SELECT mahsulot, summa FROM savdo"
    assert not api.bi_auto(str(shop), "DELETE FROM savdo")["ok"]
