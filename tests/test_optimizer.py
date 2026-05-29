# tests/test_optimizer.py
import pytest

from config import BatteryConfig
from optimizer import optimize_dispatch


def test_simple_arbitrage_lossless():
    # Cheap hour then expensive hour. Lossless. Start empty, no cyclic constraint.
    # Optimal: buy 10 MWh at 10, sell 10 MWh at 50 -> revenue 50*10 - 10*10 = 400.
    b = BatteryConfig(capacity_mwh=10, power_mw=10, efficiency=1.0,
                      soc_min_frac=0.0, soc_max_frac=1.0, start_soc_frac=0.0)
    schedule, revenue = optimize_dispatch([10.0, 50.0], b, cyclic=False)
    assert revenue == pytest.approx(400.0, abs=1e-4)
    assert schedule[0] == pytest.approx(-10.0, abs=1e-4)  # charge
    assert schedule[1] == pytest.approx(10.0, abs=1e-4)   # discharge


def test_flat_prices_no_trade():
    # No spread means no profit, so the optimizer should not trade.
    b = BatteryConfig(capacity_mwh=10, power_mw=10, efficiency=1.0,
                      soc_min_frac=0.0, soc_max_frac=1.0, start_soc_frac=0.0)
    schedule, revenue = optimize_dispatch([30.0, 30.0, 30.0], b, cyclic=False)
    assert revenue == pytest.approx(0.0, abs=1e-4)


def test_power_limit_caps_trade():
    # Power limit 4 MW means at most 4 MWh moved per hour despite 10 MWh capacity.
    b = BatteryConfig(capacity_mwh=10, power_mw=4, efficiency=1.0,
                      soc_min_frac=0.0, soc_max_frac=1.0, start_soc_frac=0.0)
    schedule, revenue = optimize_dispatch([10.0, 50.0], b, cyclic=False)
    assert schedule[0] == pytest.approx(-4.0, abs=1e-4)
    assert revenue == pytest.approx(50.0 * 4 - 10.0 * 4, abs=1e-4)


def test_negative_prices_yield_valid_schedule():
    # Negative prices must not produce simultaneous charge+discharge. The returned
    # schedule must be physically valid (passes the SOC simulator).
    from simulate import is_valid
    b = BatteryConfig()  # defaults, round-trip efficiency 0.9
    prices = [-5.0, -10.0, 80.0, 90.0, -5.0, -10.0, 80.0, 90.0] + [40.0] * 16
    schedule, revenue = optimize_dispatch(prices, b, cyclic=True)
    assert is_valid(schedule, b) is True
