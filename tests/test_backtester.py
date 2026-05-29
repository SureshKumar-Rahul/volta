# tests/test_backtester.py
import sqlite3

import pytest

import storage
from config import BatteryConfig
from optimizer import optimize_dispatch
from pipeline import load_sample_into_db
from backtester import run_backtest, summarize


def _conn(days=4):
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    load_sample_into_db(conn, start_date="2025-01-01", days=days)
    return conn


def test_perfect_agent_hits_100_percent():
    conn = _conn()
    b = BatteryConfig()
    dates = storage.get_dates(conn)

    def perfect_agent(date_str):
        prices = storage.get_prices_for_date(conn, date_str)
        schedule, _ = optimize_dispatch(prices, b, cyclic=True)  # cheats: realized prices
        return {"date": date_str, "action": "trade", "schedule": schedule}

    summary, day_results = run_backtest(conn, b, dates, perfect_agent, log=False)
    assert summary["pct_of_optimum"] == pytest.approx(100.0, abs=0.5)
    assert len(day_results) == len(dates)


def test_do_nothing_agent_is_zero_percent():
    conn = _conn()
    b = BatteryConfig()
    dates = storage.get_dates(conn)

    def lazy_agent(date_str):
        return {"date": date_str, "action": "hold", "schedule": [0.0] * 24}

    summary, _ = run_backtest(conn, b, dates, lazy_agent, log=False)
    assert summary["agent_revenue"] == pytest.approx(0.0, abs=1e-6)
    assert summary["pct_of_optimum"] == pytest.approx(0.0, abs=1e-6)


def test_summarize_computes_percentages():
    day_results = [
        {"date": "d1", "agent": 80.0, "optimum": 100.0, "threshold": 50.0, "do_nothing": 0.0},
        {"date": "d2", "agent": 40.0, "optimum": 100.0, "threshold": 30.0, "do_nothing": 0.0},
    ]
    s = summarize(day_results)
    assert s["agent_revenue"] == pytest.approx(120.0)
    assert s["optimum_revenue"] == pytest.approx(200.0)
    assert s["pct_of_optimum"] == pytest.approx(60.0)
