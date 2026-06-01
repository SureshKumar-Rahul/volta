# lear.py
"""A LEAR-style learned price forecaster for the forecast seam.

LEAR (Lago et al. 2021) is the standard strong baseline for day-ahead electricity
price forecasting: a LASSO-regularized linear model, one per target hour, trained on
recent price lags and calendar features. It slots in where the naive forecast sits,
and every caller (the agent's get_forecast tool, the backtester baseline) inherits it.

The feature vector for a target day is the full 24 prices of the previous days at
lags 1, 2, 3, and 7 (yesterday, the two days before, and the same weekday last week),
plus a day-of-week one-hot. Each hour gets its own LASSO, which selects from those
lagged prices the ones that matter for that hour. Training uses only days strictly
before the target, so there is no lookahead.

Prices are fit in a variance-stabilized space via the asinh transform (Uniejewski
et al. 2018): z = asinh((price - median) / MAD), inverted on prediction. Day-ahead
prices spike and their lagged features are collinear, which makes a plain LASSO on
raw prices converge poorly; the transform pulls the spikes toward a Gaussian scale,
which both stabilizes the fit and improves accuracy.
"""

import datetime as dt

import numpy as np
from sklearn.linear_model import LassoCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from volta.market import storage

HOURS = 24
_LAG_DAYS = (1, 2, 3, 7)
_MIN_TRAIN_ROWS = 14  # below this, defer to the naive forecast


def _prices_before(conn, date_str):
    """All full-24h days strictly before date_str, as {date_str: [24 prices]}."""
    out = {}
    for d in storage.get_dates(conn):
        if d >= date_str:
            continue
        pr = storage.get_prices_for_date(conn, d)
        if len(pr) == HOURS:
            out[d] = pr
    return out


def _robust_scale(values):
    """Center and scale for the asinh transform: median and MAD of the training
    prices. The scale is floored at 1.0 so a near-flat history can't blow it up."""
    arr = np.asarray(values, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    return median, max(mad, 1.0)


def _feature_row(prices, day):
    """Feature vector for target `day` (a date), or None if any lag day is missing.
    `prices` holds already-transformed price series."""
    feats = []
    for lag in _LAG_DAYS:
        lag_day = (day - dt.timedelta(days=lag)).isoformat()
        if lag_day not in prices:
            return None
        feats.extend(prices[lag_day])
    dow = [0.0] * 7
    dow[day.weekday()] = 1.0
    feats.extend(dow)
    return feats


def lear_forecast(conn, date_str):
    """Predict 24 hourly prices for date_str, training only on prices strictly before
    it. Returns [] when there is not enough history to train, so callers fall back to
    the naive forecast."""
    prices = _prices_before(conn, date_str)
    if not prices:
        return []

    median, mad = _robust_scale([p for day in prices.values() for p in day])
    tprices = {d: list(np.arcsinh((np.asarray(day) - median) / mad))
               for d, day in prices.items()}

    X, ys = [], [[] for _ in range(HOURS)]
    for d_str in sorted(tprices):
        row = _feature_row(tprices, dt.date.fromisoformat(d_str))
        if row is None:
            continue
        X.append(row)
        for h in range(HOURS):
            ys[h].append(tprices[d_str][h])

    if len(X) < _MIN_TRAIN_ROWS:
        return []

    x_pred = _feature_row(tprices, dt.date.fromisoformat(date_str))
    if x_pred is None:
        return []

    X = np.asarray(X, dtype=float)
    x_pred = np.asarray([x_pred], dtype=float)
    preds = []
    for h in range(HOURS):
        model = make_pipeline(StandardScaler(), LassoCV(cv=3, max_iter=50000))
        model.fit(X, np.asarray(ys[h], dtype=float))
        z = float(model.predict(x_pred)[0])
        preds.append(float(median + mad * np.sinh(z)))  # invert the asinh transform
    return preds
