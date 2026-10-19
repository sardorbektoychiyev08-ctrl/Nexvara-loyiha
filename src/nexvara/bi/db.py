"""Databases as BI sources, read-only: SQLite (.db/.sqlite/.sqlite3) and Microsoft Access
(.accdb/.mdb).

A database is shown like a workbook: its tables (and saved views/queries) are the "sheets".
Instead of a table name a single SELECT query may be given. Nothing is ever written: SQLite
is opened with mode=ro and query_only, Access through DAO with read-only=True. Access goes
through the installed Access (COM, out of process: Office is 32-bit, Python 64-bit) and its
window is never shown — only data is read, the owner's database stays closed in Access.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

SQLITE_EXT = (".db", ".sqlite", ".sqlite3")
ACCESS_EXT = (".accdb", ".mdb")
DB_EXT = SQLITE_EXT + ACCESS_EXT
_QUERY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_WRITE = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|pragma|vacuum|"
                    r"into)\b", re.IGNORECASE)  # fmt: skip


def is_db(path: str | Path) -> bool:
    return Path(path).suffix.lower() in DB_EXT


def _check_query(q: str) -> str:
    q = q.strip().rstrip(";")
    if ";" in q or not _QUERY.match(q) or _WRITE.search(q):
        raise ValueError("Faqat bitta SELECT so‘rovi yoki jadval nomi mumkin (bazaga yozilmaydi)")
    return q


# ---------------- SQLite ----------------


def _sqlite(p: Path) -> sqlite3.Connection:
    if p.read_bytes()[:16] != b"SQLite format 3\x00":
        raise ValueError(f"«{p.name}» SQLite bazasi emas")
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def _sqlite_tables(p: Path) -> list[str]:
    con = _sqlite(p)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def _sqlite_read(p: Path, what: str, limit: int) -> tuple[list[str], list[list[Any]]]:
    names = _sqlite_tables(p)
    if what in names:
        sql = 'SELECT * FROM "{}"'.format(what.replace('"', '""'))
    elif _QUERY.match(what) or len(what.split()) > 1:  # a query: only one SELECT passes
        sql = _check_query(what)
    else:
        raise LookupError(f"«{what}» jadvali bazada yo‘q. Bor: {', '.join(names[:20])}")
    con = _sqlite(p)
    try:
        cur = con.execute(f"SELECT * FROM ({sql}) LIMIT {int(limit) + 1}")
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
    finally:
        con.close()
    return cols, rows


# ---------------- Access ----------------


def _access_open(p: Path) -> tuple[Any, Any]:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    app = win32com.client.DispatchEx("Access.Application")
    try:
        db = app.DBEngine.OpenDatabase(str(p), False, True)  # exclusive=False, read-only
    except Exception:
        app.Quit()
        raise
    return app, db


def _access_close(app: Any, db: Any) -> None:
    try:
        db.Close()
    finally:
        app.Quit()


def _access_names(db: Any) -> list[str]:
    hidden = 0x80000002  # dbSystemObject | dbHiddenObject
    tables = [t.Name for t in db.TableDefs
              if not t.Name.startswith(("MSys", "~")) and not t.Attributes & hidden]  # fmt: skip
    queries = [q.Name for q in db.QueryDefs if not q.Name.startswith("~") and q.Type == 0]
    return tables + queries


def _value(v: Any) -> Any:
    if isinstance(v, dt.datetime):  # pywintypes datetime: tz-aware, wall-clock value
        v = dt.datetime(v.year, v.month, v.day, v.hour, v.minute, v.second)
        return v.date() if (v.hour, v.minute, v.second) == (0, 0, 0) else v
    if isinstance(v, Decimal):  # Access Currency / Decimal
        return float(v)
    return v


def _access_read(p: Path, what: str, limit: int) -> tuple[list[str], list[list[Any]]]:
    app, db = _access_open(p)
    try:
        names = _access_names(db)
        if what in names:
            sql = "SELECT * FROM [{}]".format(what.replace("]", "]]"))
        elif _QUERY.match(what) or len(what.split()) > 1:  # a query: only one SELECT passes
            sql = _check_query(what)
        else:
            raise LookupError(f"«{what}» jadvali bazada yo‘q. Bor: {', '.join(names[:20])}")
        rs = db.OpenRecordset(sql, 4)  # dbOpenSnapshot: read-only copy
        try:
            cols = [rs.Fields(i).Name for i in range(rs.Fields.Count)]
            rows: list[list[Any]] = []
            if not (rs.BOF and rs.EOF):
                data = rs.GetRows(int(limit) + 1)  # field-major: data[col][row]
                rows = [[_value(c[i]) for c in data] for i in range(len(data[0]))] if data else []
        finally:
            rs.Close()
    finally:
        _access_close(app, db)
    return cols, rows


# ---------------- common ----------------


def tables(path: str | Path) -> list[str]:
    p = Path(path)
    if p.suffix.lower() in SQLITE_EXT:
        return _sqlite_tables(p)
    app, db = _access_open(p)
    try:
        return _access_names(db)
    finally:
        _access_close(app, db)


def read(path: str | Path, what: str | None, limit: int) -> tuple[list[str], list[list[Any]]]:
    """Columns and rows of a table (default: the first one) or of one SELECT query."""
    p = Path(path)
    if not what:
        names = tables(p)
        if not names:
            raise ValueError("Bazada jadval yo‘q")
        what = names[0]
    if p.suffix.lower() in SQLITE_EXT:
        return _sqlite_read(p, what, limit)
    return _access_read(p, what, limit)
