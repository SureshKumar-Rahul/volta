# pipeline.py
"""Two ways to fill the database. fetch_entsoe pulls real day-ahead prices and
needs an ENTSO-E API token. load_sample_into_db generates a deterministic
synthetic price series so development and tests run with no network or token."""

import datetime as dt
import os
import random

from volta.config import ZONE
from volta.market import storage

# A realistic-shaped daily price curve in EUR/MWh: overnight trough, evening peak.
_DAILY_SHAPE = [
    35, 33, 31, 30, 31, 38, 52, 68, 74, 69, 63, 60,
    58, 60, 63, 69, 78, 90, 95, 90, 78, 63, 50, 42,
]
_SHAPE_MEAN = sum(_DAILY_SHAPE) / len(_DAILY_SHAPE)
_SAMPLE_SEED = 20250101  # fixed so the synthetic series is reproducible


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def load_sample_into_db(conn, start_date: str, days: int, seed: int = _SAMPLE_SEED) -> None:
    """Insert `days` of synthetic hourly prices starting at start_date (YYYY-MM-DD).

    Deterministic given (start_date, days, seed), so runs and tests are reproducible.
    The series is built so day-to-day forecasting is non-trivial: the overall price
    level and the size of the daily swing each follow a slow random walk, weekends are
    cheaper and flatter, every hour carries independent noise, and evenings
    occasionally spike. Yesterday is a useful but imperfect guide to today, which is
    what makes the backtest worth running."""
    start = dt.date.fromisoformat(start_date)
    rng = random.Random(seed)
    level = 0.0       # slow random walk on the overall price level (EUR/MWh)
    amplitude = 1.0   # slow random walk on how pronounced the daily swing is
    rows = []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        level = _clamp(level + rng.uniform(-6.0, 6.0), -18.0, 35.0)
        amplitude = _clamp(amplitude + rng.uniform(-0.12, 0.12), 0.55, 1.45)
        # Draw spike variables every day so the rng sequence stays day-stable.
        spike = rng.random() < 0.18
        spike_hour = rng.randint(16, 20)
        spike_mag = rng.uniform(40.0, 80.0)
        weekend = day.weekday() >= 5
        amp = amplitude * (0.6 if weekend else 1.0)        # weekends are flatter
        base_level = level - (8.0 if weekend else 0.0)     # and a bit cheaper
        for h in range(24):
            deviation = _DAILY_SHAPE[h] - _SHAPE_MEAN
            wobble = rng.uniform(-6.0, 6.0)                # per-hour shape noise
            price = _SHAPE_MEAN + base_level + amp * deviation + wobble
            if spike and h == spike_hour:
                price += spike_mag
            rows.append((f"{day.isoformat()}T{h:02d}:00:00", round(max(0.0, price), 2)))
    storage.upsert_prices(conn, rows)


def fetch_entsoe(conn, start_date: str, end_date: str) -> None:
    """Fetch real DE-LU day-ahead prices into the database.
    Requires ENTSOE_API_TOKEN in the environment (free, from the ENTSO-E
    Transparency Platform)."""
    from entsoe import EntsoePandasClient
    import pandas as pd

    token = os.environ.get("ENTSOE_API_TOKEN")
    if not token:
        raise SystemExit("ENTSOE_API_TOKEN is not set. Request a free token from the "
                         "ENTSO-E Transparency Platform and pass it in the environment.")
    client = EntsoePandasClient(api_key=token)
    start = pd.Timestamp(start_date, tz="Europe/Berlin")
    end = pd.Timestamp(end_date, tz="Europe/Berlin")
    series = client.query_day_ahead_prices(ZONE, start=start, end=end)
    rows = [(ts.tz_convert("Europe/Berlin").strftime("%Y-%m-%dT%H:00:00"), float(price))
            for ts, price in series.items()]
    storage.upsert_prices(conn, rows)
