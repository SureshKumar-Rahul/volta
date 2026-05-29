# strategies.py
"""Baselines to beat and the naive forecast the agent plans against."""

from config import BatteryConfig
from simulate import is_valid, score_schedule


def do_nothing_schedule(n: int) -> list:
    return [0.0] * n


def naive_forecast(prev_day_prices) -> list:
    """The simplest forecast: tomorrow looks like the previous comparable day."""
    return list(prev_day_prices)


def threshold_schedule(prices, battery: BatteryConfig) -> list:
    """A naive price-rank arbitrage baseline. Charge during the cheapest hours and
    discharge during the dearest, moving the same grid energy each way so the day is
    energy-neutral around the starting charge, and only trade when the spread is
    actually profitable. Simple and beatable, but it never loses money. Meant as a
    baseline for the agent to clear."""
    n = len(prices)
    if n == 0:
        return []
    eff = battery.one_way_eff()
    cap = battery.capacity_mwh
    soc_lo = battery.soc_min_frac * cap
    soc_hi = battery.soc_max_frac * cap
    start = battery.start_soc_frac * cap
    p_max = battery.power_mw

    # Grid energy we can move each way while returning to the starting charge.
    charge_room = (soc_hi - start) / eff      # grid MWh that fits when charging
    discharge_room = (start - soc_lo) * eff   # grid MWh available when discharging
    cycle = max(0.0, min(charge_room, discharge_room))

    order = sorted(range(n), key=lambda i: prices[i])  # cheapest hour first
    sched = [0.0] * n

    remaining = cycle  # fill cheapest hours with charging, capped at power
    for i in order:
        if remaining <= 0:
            break
        amt = min(p_max, remaining)
        sched[i] = -amt
        remaining -= amt

    remaining = cycle  # fill dearest hours with discharging, skipping charge hours
    for i in reversed(order):
        if remaining <= 0:
            break
        if sched[i] < 0:
            continue
        amt = min(p_max, remaining)
        sched[i] = amt
        remaining -= amt

    if score_schedule(sched, prices) <= 0 or not is_valid(sched, battery):
        return [0.0] * n  # no profitable spread, or unsafe: hold
    return sched
