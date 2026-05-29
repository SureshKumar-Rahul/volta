# tests/test_pipeline.py
import sqlite3

from volta.market import storage
from volta.market.pipeline import load_sample_into_db


def _load(days, **kw):
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    load_sample_into_db(conn, start_date="2025-01-01", days=days, **kw)
    return conn


def test_sample_is_deterministic():
    # The generator uses randomness, but a fixed seed must give a reproducible series
    # so runs and tests are repeatable.
    a, b = _load(5), _load(5)
    dates = storage.get_dates(a)
    assert dates == storage.get_dates(b)
    for d in dates:
        assert storage.get_prices_for_date(a, d) == storage.get_prices_for_date(b, d)


def test_consecutive_days_differ_in_shape():
    # The old generator shifted every hour by the same constant from one day to the
    # next, so yesterday was a near-perfect forecast of today and the backtest was
    # trivial. A useful series needs the day-over-day change to vary across hours,
    # not be a single uniform offset (which would give a per-hour-difference range of 0).
    conn = _load(14)
    dates = storage.get_dates(conn)
    ranges = []
    for prev, cur in zip(dates, dates[1:]):
        p = storage.get_prices_for_date(conn, prev)
        c = storage.get_prices_for_date(conn, cur)
        diffs = [ci - pi for pi, ci in zip(p, c)]
        ranges.append(max(diffs) - min(diffs))
    assert sum(ranges) / len(ranges) > 5.0


def test_retains_diurnal_structure():
    # Nights should still be cheaper than evenings on average, so arbitrage exists.
    conn = _load(14)
    night, evening = [], []
    for d in storage.get_dates(conn):
        pr = storage.get_prices_for_date(conn, d)
        night += pr[1:5]      # 01:00-04:00 trough
        evening += pr[17:21]  # 17:00-20:00 peak
    assert sum(night) / len(night) < sum(evening) / len(evening)


def test_prices_are_non_negative():
    conn = _load(30)
    for d in storage.get_dates(conn):
        assert min(storage.get_prices_for_date(conn, d)) >= 0.0
