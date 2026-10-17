"""NEXVARA BI entirely from chat: formula columns, joining and appending files, cleaning
steps, widget editing, pages, dates, rename. Real files in a temp folder, no Office."""

from __future__ import annotations

from pathlib import Path

import pytest

SALES = """Sana;Filial;Mahsulot;Daromad;Xarajat
05.01.2026;Toshkent;Daftar;1 200 000;700 000
20.01.2026;Samarqand;Ruchka;800 000;500 000
03.02.2026;Toshkent;Ruchka;1 500 000;800 000
03.02.2026;Toshkent;Ruchka;1 500 000;800 000
01.03.2026;Buxoro;Kitob;;900 000
"""
MARCH = """Sana;Filial;Mahsulot;Daromad;Xarajat
10.03.2026;Andijon;Daftar;600 000;300 000
"""
PRICES = """Mahsulot;Narx;Yetkazuvchi
Daftar;5 000;Sharq
Ruchka;2 000;Matbaa
Kitob;30 000;Sharq
"""


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXVARA_DATA", str(tmp_path / "data"))
    from nexvara.app.api import Api

    work = tmp_path / "Ish"
    work.mkdir()
    (work / "savdo.csv").write_text(SALES, encoding="utf-8")
    (work / "mart.csv").write_text(MARCH, encoding="utf-8")
    (work / "narxlar.csv").write_text(PRICES, encoding="utf-8")
    a = Api()
    a._context_file = str(work / "savdo.csv")
    r = a.chat(f"{work / 'savdo.csv'} dan dashboard yarat va «Savdo» deb saqla")
    assert "saqlandi" in r["reply"], r
    a.work = work
    return a


def cfg(api):
    return api.bi_open(api.bi_list()[0]["file"])["config"]


def table(api):
    return api._bi_table(cfg(api))


def test_formula_columns(api):
    base = len(cfg(api)["steps"])  # the automatic dashboard already adds "Sof foyda"
    r = api.chat("«Savdo» dashboardiga «Foyda» = Daromad - Xarajat ustunini qo‘sh")
    assert "Foyda = [Daromad] - [Xarajat]" in r["reply"], r
    t = table(api)
    assert t.values("Foyda")[0] == 500_000
    r = api.chat("Savdo dashboardiga Ulush = [Foyda] / [Daromad] * 100 formula qo‘sh")
    assert round(table(api).values("Ulush")[0]) == 42
    r = api.chat("«Savdo» dashboardiga «Yomon» = [Soliq] * 2 ustunini qo‘sh")
    assert "qo‘shilmadi" in r["reply"] and len(cfg(api)["steps"]) == base + 2  # not saved


def test_join_and_append_files(api):
    w = api.work
    r = api.chat(f"«Savdo» dashboardini {w / 'narxlar.csv'} bilan Mahsulot bo‘yicha birlashtir")
    assert "mos keldi" in r["reply"], r
    t = table(api)
    assert "Narx" in t.columns and t.values("Yetkazuvchi")[0] == "Sharq"
    r = api.chat(f"{w / 'mart.csv'} qatorlarini «Savdo» dashboardi ostiga qo‘sh")
    t = table(api)
    assert len(t.rows) == 6 and t.values("Manba")[-1] == "mart.csv", r
    assert (
        "Boshqa fayl qatorlarini qo‘shish"
        in api.chat("«Savdo» dashboardi qadamlarini ko‘rsat")["reply"]
    )


def test_cleaning_steps_and_undo(api):
    api.chat("«Savdo» dashboardida takroriy qatorlarni o‘chir")
    assert len(table(api).rows) == 4
    api.chat("«Savdo» dashboardida «Daromad» ustunidagi bo‘sh joylarni 0 bilan to‘ldir")
    assert table(api).values("Daromad")[-1] == 0
    api.chat("«Savdo» dashboardida «Mahsulot» ustunini «Tovar» deb nomla")
    assert "Tovar" in table(api).columns
    api.chat("«Savdo» dashboardida Daromad 1000000 dan katta qatorlar qolsin")
    assert len(table(api).rows) == 2
    api.chat("«Savdo» dashboardida «Xarajat» ustunini olib tashla")
    assert "Xarajat" not in table(api).columns
    n = len(cfg(api)["steps"])
    steps = api.chat("«Savdo» dashboardi qadamlarini ko‘rsat")["reply"]
    assert f"{n}." in steps and "Filtr" in steps
    api.chat(f"«Savdo» dashboardidagi {n}-qadamni bekor qil")  # the column comes back
    assert "Xarajat" in table(api).columns and len(cfg(api)["steps"]) == n - 1
    r = api.chat(f"«Savdo» dashboardidagi {n - 2}-qadamni o‘chir")  # the rename
    assert "Olib tashlandi" in r["reply"] and "Mahsulot" in table(api).columns


def test_widgets_list_edit_remove_and_pages(api):
    lst = api.chat("«Savdo» dashboardi vidjetlarini ko‘rsat")["reply"]
    assert "1." in lst and "ustunli" in lst
    n = len([x for p in cfg(api)["pages"] for x in p["widgets"]])
    bar = next(i for i, w in enumerate([x for p in cfg(api)["pages"] for x in p["widgets"]], 1)
               if w["type"] == "bar")  # fmt: skip
    r = api.chat(f"«Savdo» dashboardidagi {bar}-vidjetni doiraviy qil")
    assert "tur: doiraviy" in r["reply"], r
    msg = f"«Savdo» dashboardidagi {bar}-vidjet sarlavhasini «Filiallar ulushi» qil"
    r = api.chat(msg + ", o‘rtacha hisoblasin")
    w = [x for p in cfg(api)["pages"] for x in p["widgets"]][bar - 1]
    assert (w["type"], w["title"], w["agg"]) == ("pie", "Filiallar ulushi", "avg"), r
    r = api.chat("«Savdo» dashboardidagi «Filiallar ulushi» diagrammasini Mahsulot bo‘yicha qil")
    assert [x for p in cfg(api)["pages"] for x in p["widgets"]][bar - 1]["x"] == "Mahsulot", r
    api.chat("«Savdo» dashboardidagi «Filiallar ulushi» vidjetini olib tashla")
    assert len([x for p in cfg(api)["pages"] for x in p["widgets"]]) == n - 1
    r = api.chat("«Savdo» dashboardiga «Mahsulotlar» sahifasini qo‘sh")
    assert len(cfg(api)["pages"]) >= 2 and cfg(api)["pages"][-1]["title"] == "Mahsulotlar", r
    last = len(cfg(api)["pages"])
    api.chat(f"«Savdo» dashboardiga {last}-sahifaga Mahsulot bo‘yicha Daromad jadval vidjet qo‘sh")
    assert cfg(api)["pages"][-1]["widgets"][0]["type"] == "table"


def test_dates_rename_and_open(api):
    s = api.chat("«Savdo» dashboardi ko‘rsatkichlarini 01.02.2026 dan 31.03.2026 gacha ayt")[
        "reply"
    ]
    assert "3 ta qator" in s, s
    r = api.chat("«Savdo» dashboardini 2026-01-01 dan 2026-01-31 gacha och")
    assert r["bi_ui"]["state"]["date_to"] == "2026-01-31"
    r = api.chat("«Savdo» dashboardini «Savdo 2026» deb nomla")
    assert [d["name"] for d in api.bi_list()] == ["Savdo 2026"], r
    assert Path(api.bi_list()[0]["file"]).is_file()
