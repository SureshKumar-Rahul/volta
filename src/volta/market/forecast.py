# forecast.py
"""The single seam for the price forecast Volta plans against.

Two forecasters live behind one call. The default is naive: tomorrow is assumed to
look like the previous day's realized prices. Set VOLTA_FORECASTER=lear to use the
LEAR learned model instead, which falls back to naive until it has enough history.
The agent's get_forecast tool and the backtester's fair baseline both call
forecast_prices, so swapping the forecaster is a one-place change every caller
inherits."""

import datetime as dt
import os

from volta.market import storage
from volta.market.lear import lear_forecast
from volta.optimize.strategies import naive_forecast


def forecast_prices(conn, date_str):
    """Forecast hourly prices for date_str. Returns [] when there is no prior day in
    the store (the cold-start day, which has no history to forecast from)."""
    prev = (dt.date.fromisoformat(date_str) - dt.timedelta(days=1)).isoformat()
    naive = naive_forecast(storage.get_prices_for_date(conn, prev))

    if os.environ.get("VOLTA_FORECASTER", "naive").lower() == "lear":
        learned = lear_forecast(conn, date_str)
        if learned:
            return learned
    return naive
