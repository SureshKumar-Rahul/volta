# tests/test_strategies.py
import pytest

from config import BatteryConfig
from strategies import do_nothing_schedule, threshold_schedule, naive_forecast
from simulate import is_valid, score_schedule


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
