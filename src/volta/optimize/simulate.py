# simulate.py
"""Replay a schedule to track state of charge, check validity, and score revenue.
Uses the same sign convention and efficiency model as the optimizer."""

from volta.config import BatteryConfig

TOL = 1e-6


def score_schedule(schedule, prices) -> float:
    """Net revenue: positive entries sell, negative entries buy, priced hourly."""
    return float(sum(p * s for p, s in zip(prices, schedule)))


def simulate_soc(schedule, battery: BatteryConfig):
    """Return (soc_path, violations). soc_path is the SOC in MWh after each hour.
    violations is a list of human-readable strings, empty when the schedule is valid."""
    eff = battery.one_way_eff()
    cap = battery.capacity_mwh
    soc_lo = battery.soc_min_frac * cap
    soc_hi = battery.soc_max_frac * cap
    soc = battery.start_soc_frac * cap
    soc_path, violations = [], []

    for t, s in enumerate(schedule):
        if abs(s) > battery.power_mw + TOL:
            violations.append(f"hour {t}: |{s:.3f}| exceeds power limit {battery.power_mw}")
        charge = max(-s, 0.0)
        discharge = max(s, 0.0)
        soc = soc + charge * eff - discharge / eff
        if soc < soc_lo - TOL:
            violations.append(f"hour {t}: SOC {soc:.3f} below floor {soc_lo}")
        if soc > soc_hi + TOL:
            violations.append(f"hour {t}: SOC {soc:.3f} above ceiling {soc_hi}")
        soc_path.append(soc)

    return soc_path, violations


def is_valid(schedule, battery: BatteryConfig) -> bool:
    _, violations = simulate_soc(schedule, battery)
    return len(violations) == 0
