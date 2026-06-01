# tests/test_lear.py
import datetime as dt
import sqlite3

from volta.market import storage
from volta.market.lear import lear_forecast


def _seed(conn, start_date, days, day_prices):
    """Insert `days` of hourly prices. day_prices(date) -> list of 24 floats."""
    start = dt.date.fromisoformat(start_date)
    rows = []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        prices = day_prices(day)
        for h in range(24):
            rows.append((f"{day.isoformat()}T{h:02d}:00:00", float(prices[h])))
    storage.upsert_prices(conn, rows)


_SHAPE = [35, 33, 31, 30, 31, 38, 52, 68, 74, 69, 63, 60,
          58, 60, 63, 69, 78, 90, 95, 90, 78, 63, 50, 42]


def test_returns_empty_without_enough_history():
    # With only a handful of prior days there is nothing to train on, so the
    # forecaster must return [] and let the caller fall back to the naive forecast.
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    _seed(conn, "2025-01-01", 3, lambda day: [50.0] * 24)
    assert lear_forecast(conn, "2025-01-04") == []


def test_returns_24_finite_predictions_with_history():
    # Given enough history, the forecaster returns one price per hour, all finite.
    import math
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    _seed(conn, "2025-01-01", 40, lambda day: _SHAPE)
    out = lear_forecast(conn, "2025-02-10")
    assert len(out) == 24
    assert all(isinstance(p, float) and math.isfinite(p) for p in out)


def _mae(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def test_learns_weekly_structure_and_beats_naive():
    # Prices are 7-day periodic: weekdays sit at a higher level than weekends, same
    # diurnal shape. Across the Sunday->Monday boundary the naive "yesterday" forecast
    # is badly wrong (it copies the cheap weekend), while LEAR should recover the
    # weekday level from the same-weekday-last-week lag and the day-of-week feature.
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)

    def periodic(day):
        base = 30.0 if day.weekday() >= 5 else 60.0
        return [base + s for s in _SHAPE]

    _seed(conn, "2025-01-06", 49, periodic)  # 2025-01-06 is a Monday
    target = "2025-02-24"                     # also a Monday, not yet in the store
    actual = [60.0 + s for s in _SHAPE]

    lear = lear_forecast(conn, target)
    naive = storage.get_prices_for_date(conn, "2025-02-23")  # the Sunday before

    naive_mae = _mae(naive, actual)
    lear_mae = _mae(lear, actual)
    assert naive_mae > 20            # naive copies the weekend and misses the level
    assert lear_mae < 5              # LEAR recovers the weekday level
    assert lear_mae < naive_mae / 3  # and is decisively better


def test_forecast_does_not_use_future_data():
    # A backtest forecast must depend only on days before the target. Adding or
    # changing prices on and after the target date must not move the forecast.
    def build():
        conn = sqlite3.connect(":memory:")
        storage.init_db(conn)
        _seed(conn, "2025-01-01", 40, lambda day: _SHAPE)
        return conn

    target = "2025-02-10"
    before = lear_forecast(build(), target)

    tampered = build()
    # Poison the target day and several days after it with absurd prices.
    _seed(tampered, target, 6, lambda day: [9999.0] * 24)
    after = lear_forecast(tampered, target)

    assert before == after
