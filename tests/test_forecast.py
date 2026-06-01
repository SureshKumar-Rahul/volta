# tests/test_forecast.py
import datetime as dt
import sqlite3

from volta.market import storage
from volta.market.forecast import forecast_prices
from volta.market.lear import lear_forecast

_SHAPE = [35, 33, 31, 30, 31, 38, 52, 68, 74, 69, 63, 60,
          58, 60, 63, 69, 78, 90, 95, 90, 78, 63, 50, 42]


def _seed(conn, start_date, days, day_prices):
    start = dt.date.fromisoformat(start_date)
    rows = []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        for h, p in enumerate(day_prices(day)):
            rows.append((f"{day.isoformat()}T{h:02d}:00:00", float(p)))
    storage.upsert_prices(conn, rows)


def test_default_forecaster_is_naive(monkeypatch):
    # With no override, the seam returns the previous day's realized prices.
    monkeypatch.delenv("VOLTA_FORECASTER", raising=False)
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    _seed(conn, "2025-01-01", 2, lambda day: [40.0 + day.day] * 24)
    assert forecast_prices(conn, "2025-01-02") == storage.get_prices_for_date(conn, "2025-01-01")


def test_lear_mode_uses_lear(monkeypatch):
    # Selecting the LEAR forecaster makes the seam return the learned prediction.
    monkeypatch.setenv("VOLTA_FORECASTER", "lear")
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)

    def periodic(day):
        base = 30.0 if day.weekday() >= 5 else 60.0
        return [base + s for s in _SHAPE]

    _seed(conn, "2025-01-06", 49, periodic)
    target = "2025-02-24"
    assert forecast_prices(conn, target) == lear_forecast(conn, target)


def test_lear_mode_falls_back_to_naive_without_history(monkeypatch):
    # Before LEAR has enough history it returns [], and the seam must fall back to the
    # naive forecast rather than handing the backtester an empty forecast.
    monkeypatch.setenv("VOLTA_FORECASTER", "lear")
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    _seed(conn, "2025-01-01", 3, lambda day: [50.0] * 24)
    assert forecast_prices(conn, "2025-01-04") == [50.0] * 24
