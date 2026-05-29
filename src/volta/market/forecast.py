# forecast.py
"""The single seam for the price forecast Volta plans against.

Today the forecast is naive: tomorrow is assumed to look like the previous day's
realized prices. The agent's get_forecast tool and the backtester's fair baseline
both call forecast_prices, so a better forecaster (a learned model, or a
conformal-calibrated one) is a one-place swap that every caller inherits."""

import datetime as dt

from volta.market import storage
from volta.optimize.strategies import naive_forecast


def forecast_prices(conn, date_str):
    """Forecast hourly prices for date_str. Returns [] when there is no prior day in
    the store (the cold-start day, which has no history to forecast from)."""
    prev = (dt.date.fromisoformat(date_str) - dt.timedelta(days=1)).isoformat()
    return naive_forecast(storage.get_prices_for_date(conn, prev))
