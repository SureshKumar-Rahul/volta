# pipeline.py
"""Two ways to fill the database. fetch_entsoe pulls real day-ahead prices and
needs an ENTSO-E API token. load_sample_into_db generates a deterministic
synthetic price series so development and tests run with no network or token."""

import datetime as dt
import os

import storage
from config import ZONE

# A realistic-shaped daily price curve in EUR/MWh: overnight trough, evening peak.
_DAILY_SHAPE = [
    35, 33, 31, 30, 31, 38, 52, 68, 74, 69, 63, 60,
    58, 60, 63, 69, 78, 90, 95, 90, 78, 63, 50, 42,
]


def load_sample_into_db(conn, start_date: str, days: int) -> None:
    """Insert `days` of synthetic hourly prices starting at start_date (YYYY-MM-DD).
    Deterministic: a fixed daily shape plus a day-index drift, so it is reproducible."""
    start = dt.date.fromisoformat(start_date)
    rows = []
    for d in range(days):
        day = start + dt.timedelta(days=d)
        drift = (d % 7) * 1.5  # mild weekly variation, deterministic
        for h in range(24):
            price = _DAILY_SHAPE[h] + drift
            rows.append((f"{day.isoformat()}T{h:02d}:00:00", float(price)))
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
