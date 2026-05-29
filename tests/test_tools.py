import datetime as dt
import sqlite3

import storage
from config import BatteryConfig
from pipeline import load_sample_into_db
from tools import make_tools


def _conn_with_two_days():
    conn = sqlite3.connect(":memory:")
    storage.init_db(conn)
    load_sample_into_db(conn, start_date="2025-01-01", days=2)
    return conn


def test_get_forecast_uses_previous_day():
    conn = _conn_with_two_days()
    tools = make_tools(conn, BatteryConfig())
    out = tools["get_forecast"]("2025-01-02")
    expected = storage.get_prices_for_date(conn, "2025-01-01")
    assert out["prices"] == expected
    assert len(out["prices"]) == 24


def test_run_optimizer_returns_valid_schedule():
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    prices = storage.get_prices_for_date(conn, "2025-01-02")
    out = tools["run_optimizer"](prices)
    assert len(out["schedule"]) == 24
    assert "expected_revenue" in out


def test_check_schedule_reports_validity():
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    assert tools["check_schedule"]([0.0] * 24)["valid"] is True
