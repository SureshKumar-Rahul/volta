import json
import sqlite3

from volta.config import BatteryConfig
from volta.market import storage
from volta.market.pipeline import load_sample_into_db
from volta.agent.tools import make_tools


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


def test_run_optimizer_accepts_string_numbers():
    # Some models emit tool-call array elements as JSON strings. The tool must
    # coerce them rather than passing strings into the LP solver.
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    prices = storage.get_prices_for_date(conn, "2025-01-02")
    floats = tools["run_optimizer"](prices)
    strings = tools["run_optimizer"]([str(p) for p in prices])
    assert "error" not in strings
    assert strings["schedule"] == floats["schedule"]
    assert strings["expected_revenue"] == floats["expected_revenue"]


def test_check_schedule_accepts_string_numbers():
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    assert tools["check_schedule"](["0.0"] * 24)["valid"] is True


def test_run_optimizer_accepts_json_string_array():
    # Some models serialize an array argument as one JSON string, e.g.
    # prices="[35.0, 33.0, ...]" instead of a JSON array. The tool must decode it.
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    prices = storage.get_prices_for_date(conn, "2025-01-02")
    floats = tools["run_optimizer"](prices)
    as_json = tools["run_optimizer"](json.dumps(prices))
    assert "error" not in as_json
    assert as_json["schedule"] == floats["schedule"]
    assert as_json["expected_revenue"] == floats["expected_revenue"]


def test_check_schedule_accepts_json_string_array():
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    assert tools["check_schedule"](json.dumps([0.0] * 24))["valid"] is True


def test_run_optimizer_rejects_non_numbers():
    # Genuinely non-numeric input returns an error the agent can read and retry on,
    # rather than crashing the whole backtest.
    conn = _conn_with_two_days()
    b = BatteryConfig()
    tools = make_tools(conn, b)
    out = tools["run_optimizer"](["abc"] * 24)
    assert "error" in out
