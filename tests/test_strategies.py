# tests/test_strategies.py
import pytest

from volta.config import BatteryConfig
from volta.optimize.strategies import do_nothing_schedule, threshold_schedule, naive_forecast
from volta.optimize.simulate import is_valid, score_schedule


def test_do_nothing_is_zeros():
    assert do_nothing_schedule(24) == [0.0] * 24


def test_naive_forecast_returns_previous_day():
    assert naive_forecast([1.0, 2.0, 3.0]) == [1.0, 2.0, 3.0]


def test_threshold_schedule_is_valid_and_profitable():
    b = BatteryConfig()
    prices = [20.0] * 6 + [80.0] * 6 + [20.0] * 6 + [80.0] * 6  # volatile day
    sched = threshold_schedule(prices, b)
    assert is_valid(sched, b) is True
    assert score_schedule(sched, prices) > 0.0


def test_threshold_schedule_flat_prices_no_trade():
    b = BatteryConfig()
    sched = threshold_schedule([50.0] * 24, b)
    assert sched == [0.0] * 24


def test_threshold_is_energy_neutral_and_never_loses():
    # On a realistic single-trough single-peak day the baseline must be valid,
    # move equal grid energy in and out (neutral around the start), and not lose money.
    b = BatteryConfig()
    prices = [float(x) for x in
              [30, 28, 26, 25, 27, 35, 55, 75, 80, 72, 64, 60,
               58, 62, 68, 76, 88, 95, 90, 78, 64, 52, 42, 36]]
    sched = threshold_schedule(prices, b)
    assert is_valid(sched, b) is True
    charged = -sum(s for s in sched if s < 0)
    discharged = sum(s for s in sched if s > 0)
    assert charged == pytest.approx(discharged, abs=1e-6)
    assert score_schedule(sched, prices) >= 0.0
