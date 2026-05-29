# storage.py
"""SQLite storage for day-ahead prices. One row per hourly timestamp."""

import sqlite3


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS day_ahead_prices ("
        "  ts TEXT PRIMARY KEY,"      # ISO timestamp, hourly
        "  price REAL NOT NULL"        # EUR/MWh
        ")"
    )
    conn.commit()


def upsert_prices(conn: sqlite3.Connection, rows) -> None:
    """rows: iterable of (ts_iso, price). Re-running is idempotent."""
    conn.executemany(
        "INSERT INTO day_ahead_prices (ts, price) VALUES (?, ?) "
        "ON CONFLICT(ts) DO UPDATE SET price = excluded.price",
        list(rows),
    )
    conn.commit()


def get_prices_for_date(conn: sqlite3.Connection, date_str: str) -> list:
    """Return the 24 hourly prices for date_str (YYYY-MM-DD), ordered by hour."""
    cur = conn.execute(
        "SELECT price FROM day_ahead_prices WHERE ts LIKE ? ORDER BY ts",
        (f"{date_str}T%",),
    )
    return [r[0] for r in cur.fetchall()]


def get_dates(conn: sqlite3.Connection) -> list:
    """Return sorted distinct dates (YYYY-MM-DD) present in the table."""
    cur = conn.execute(
        "SELECT DISTINCT substr(ts, 1, 10) AS d FROM day_ahead_prices ORDER BY d"
    )
    return [r[0] for r in cur.fetchall()]
