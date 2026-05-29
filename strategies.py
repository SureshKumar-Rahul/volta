# strategies.py
"""Baselines to beat and the naive forecast the agent plans against."""

from config import BatteryConfig


def do_nothing_schedule(n: int) -> list:
    return [0.0] * n


def naive_forecast(prev_day_prices) -> list:
    """The simplest forecast: tomorrow looks like the previous comparable day."""
    return list(prev_day_prices)


def threshold_schedule(prices, battery: BatteryConfig) -> list:
    """Greedy rule: charge when price is well below the daily mean, discharge when
    well above, always respecting SOC and power limits. Meant as a baseline."""
    eff = battery.one_way_eff()
    cap = battery.capacity_mwh
    soc_lo = battery.soc_min_frac * cap
    soc_hi = battery.soc_max_frac * cap
    soc = battery.start_soc_frac * cap
    p_max = battery.power_mw
    if not prices:
        return []
    mean = sum(prices) / len(prices)
    low, high = mean * 0.9, mean * 1.1

    sched = []
    for price in prices:
        if price < low:  # cheap: charge as much as fits
            room_grid = (soc_hi - soc) / eff
            c = min(p_max, max(0.0, room_grid))
            soc += c * eff
            sched.append(-c)
        elif price > high:  # expensive: discharge what we can
            avail_grid = (soc - soc_lo) * eff
            d = min(p_max, max(0.0, avail_grid))
            soc -= d / eff
            sched.append(d)
        else:
            sched.append(0.0)
    return sched
