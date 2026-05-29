# tests/test_storage.py
import sqlite3
from volta.market import storage


def test_roundtrip_prices_for_date():
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    rows = [(f"2025-01-01T{h:02d}:00:00", 50.0 + h) for h in range(24)]
    storage.upsert_prices(conn, rows)
    prices = storage.get_prices_for_date(conn, "2025-01-01")
    assert len(prices) == 24
    assert prices[0] == 50.0
    assert prices[23] == 73.0


def test_upsert_is_idempotent():
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    rows = [(f"2025-01-01T{h:02d}:00:00", 10.0) for h in range(24)]
    storage.upsert_prices(conn, rows)
    storage.upsert_prices(conn, rows)  # second time must not duplicate
    assert len(storage.get_prices_for_date(conn, "2025-01-01")) == 24


def test_get_dates_sorted():
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    storage.upsert_prices(conn, [(f"2025-01-02T{h:02d}:00:00", 1.0) for h in range(24)])
    storage.upsert_prices(conn, [(f"2025-01-01T{h:02d}:00:00", 1.0) for h in range(24)])
    assert storage.get_dates(conn) == ["2025-01-01", "2025-01-02"]


def test_sample_loader_fills_n_days():
    import sqlite3
    from volta.market import storage
    from volta.market.pipeline import load_sample_into_db
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    load_sample_into_db(conn, start_date="2025-01-01", days=3)
    assert storage.get_dates(conn) == ["2025-01-01", "2025-01-02", "2025-01-03"]
    prices = storage.get_prices_for_date(conn, "2025-01-01")
    assert len(prices) == 24
    assert min(prices) >= 0  # synthetic prices are non-negative
