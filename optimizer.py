# optimizer.py
"""Linear-program battery dispatch. Given an hourly price series, return the
revenue-maximizing schedule and its revenue. A binary per-hour mode variable
forbids simultaneous charge and discharge, so schedules stay physical even when
prices are negative. Run on realized prices this is the perfect-foresight
optimum; run on a forecast it is the agent's planning tool."""

import pulp

from config import BatteryConfig


def optimize_dispatch(prices, battery: BatteryConfig, cyclic: bool = True):
    """Return (schedule, revenue).

    schedule[t] is grid-side power: positive discharge, negative charge.
    cyclic=True forces end-of-day SOC back to the start so days are comparable.
    """
    n = len(prices)
    eff = battery.one_way_eff()
    cap = battery.capacity_mwh
    p_max = battery.power_mw
    soc_lo = battery.soc_min_frac * cap
    soc_hi = battery.soc_max_frac * cap
    start = battery.start_soc_frac * cap

    prob = pulp.LpProblem("dispatch", pulp.LpMaximize)
    charge = [pulp.LpVariable(f"c_{t}", lowBound=0, upBound=p_max) for t in range(n)]
    discharge = [pulp.LpVariable(f"d_{t}", lowBound=0, upBound=p_max) for t in range(n)]
    soc = [pulp.LpVariable(f"s_{t}", lowBound=soc_lo, upBound=soc_hi) for t in range(n)]
    mode = [pulp.LpVariable(f"y_{t}", cat="Binary") for t in range(n)]

    prob += pulp.lpSum(prices[t] * discharge[t] - prices[t] * charge[t] for t in range(n))

    for t in range(n):
        prev = start if t == 0 else soc[t - 1]
        prob += soc[t] == prev + charge[t] * eff - discharge[t] / eff
        prob += charge[t] <= p_max * mode[t]
        prob += discharge[t] <= p_max * (1 - mode[t])
    if cyclic and n > 0:
        prob += soc[n - 1] == start

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    schedule = [float(discharge[t].value() or 0.0) - float(charge[t].value() or 0.0)
                for t in range(n)]
    revenue = float(pulp.value(prob.objective) or 0.0)
    return schedule, revenue
