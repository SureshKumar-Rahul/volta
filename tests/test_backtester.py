# tests/test_backtester.py
import sqlite3

import pytest

from volta.config import BatteryConfig
from volta.market import storage
from volta.market.pipeline import load_sample_into_db
from volta.optimize.optimizer import optimize_dispatch
from volta.optimize.simulate import score_schedule
from volta.optimize.strategies import threshold_schedule
from volta.eval.backtester import run_backtest, summarize


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
    # The earliest day has no prior day to forecast from, so it is not scored.
    assert len(day_results) == len(dates) - 1


def test_cold_start_day_is_skipped():
    conn = _conn(days=4)
    b = BatteryConfig()
    dates = storage.get_dates(conn)

    def hold_agent(date_str):
        return {"date": date_str, "action": "hold", "schedule": [0.0] * 24}

    _, day_results = run_backtest(conn, b, dates, hold_agent, log=False)
    assert [r["date"] for r in day_results] == dates[1:]  # first day dropped


def test_threshold_baseline_plans_on_forecast():
    # The baseline must plan on the same forecast the agent sees (the previous day),
    # then be paid on realized prices. It must not peek at realized prices to build
    # its schedule. Two days with reversed price shapes make the difference visible.
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    b = BatteryConfig()
    cheap_then_dear = [20.0] * 12 + [80.0] * 12
    dear_then_cheap = [80.0] * 12 + [20.0] * 12
    storage.upsert_prices(conn, [(f"2025-01-01T{h:02d}:00:00", cheap_then_dear[h]) for h in range(24)])
    storage.upsert_prices(conn, [(f"2025-01-02T{h:02d}:00:00", dear_then_cheap[h]) for h in range(24)])
    dates = storage.get_dates(conn)

    def hold_agent(date_str):
        return {"date": date_str, "action": "hold", "schedule": [0.0] * 24}

    _, day_results = run_backtest(conn, b, dates, hold_agent, log=False)
    assert [r["date"] for r in day_results] == ["2025-01-02"]  # cold start skipped

    forecast, realized = cheap_then_dear, dear_then_cheap
    fair = score_schedule(threshold_schedule(forecast, b), realized)
    peeking = score_schedule(threshold_schedule(realized, b), realized)
    assert day_results[0]["threshold"] == pytest.approx(fair)
    assert fair != pytest.approx(peeking)  # proves it is not peeking at realized


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
