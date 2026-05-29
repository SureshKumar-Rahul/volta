# tests/test_simulate.py
import pytest

from config import BatteryConfig
from simulate import simulate_soc, is_valid, score_schedule


def test_score_schedule_sign():
    # Buy 5 at price 10 (cost 50), sell 5 at price 40 (revenue 200) -> net 150.
    assert score_schedule([-5.0, 5.0], [10.0, 40.0]) == pytest.approx(150.0)


def test_simulate_soc_tracks_charge_then_discharge():
    b = BatteryConfig(capacity_mwh=10, power_mw=10, efficiency=1.0,
                      soc_min_frac=0.0, soc_max_frac=1.0, start_soc_frac=0.0)
    soc_path, violations = simulate_soc([-10.0, 10.0], b)
    assert soc_path[0] == pytest.approx(10.0)
    assert soc_path[1] == pytest.approx(0.0)
    assert violations == []


def test_is_valid_flags_soc_breach():
    # Discharging 5 from an empty battery breaks the floor.
    b = BatteryConfig(capacity_mwh=10, power_mw=10, efficiency=1.0,
                      soc_min_frac=0.0, soc_max_frac=1.0, start_soc_frac=0.0)
    assert is_valid([5.0], b) is False


def test_is_valid_flags_power_breach():
    b = BatteryConfig(capacity_mwh=10, power_mw=4, efficiency=1.0,
                      soc_min_frac=0.0, soc_max_frac=1.0, start_soc_frac=0.5)
    assert is_valid([5.0], b) is False  # 5 MW exceeds the 4 MW limit
