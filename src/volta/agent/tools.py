# tools.py
"""Agent-callable tools, bound to a database connection and a battery config.
Each returns a plain dict so results serialize cleanly into the LLM transcript."""

import datetime as dt
import json
from dataclasses import asdict

from volta.market.forecast import forecast_prices
from volta.optimize.optimizer import optimize_dispatch
from volta.optimize.simulate import simulate_soc


def _as_floats(values):
    """Coerce a model-supplied numeric array to floats. Returns (floats, error):
    error is None on success, or a short message when the input is not a list of
    numbers. Models sometimes serialize an array argument as one JSON string
    ("[35.0, 33.0, ...]") or emit individual elements as strings; accept both."""
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except json.JSONDecodeError:
            return None, f"expected a list of numbers, got string {values!r}"
    if not isinstance(values, (list, tuple)):
        return None, f"expected a list of numbers, got {type(values).__name__}"
    out = []
    for i, v in enumerate(values):
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            return None, f"element {i} ({v!r}) is not a number"
    return out, None


def make_tools(conn, battery):
    def get_forecast(date_str):
        """Naive forecast: the previous day's realized prices."""
        prev = (dt.date.fromisoformat(date_str) - dt.timedelta(days=1)).isoformat()
        return {"date": date_str, "forecast_source": prev,
                "prices": forecast_prices(conn, date_str)}

    def get_battery_state():
        state = asdict(battery)
        state["start_soc_mwh"] = battery.start_soc_frac * battery.capacity_mwh
        return state

    def run_optimizer(prices):
        nums, err = _as_floats(prices)
        if err:
            return {"error": err}
        schedule, revenue = optimize_dispatch(nums, battery, cyclic=True)
        return {"schedule": schedule, "expected_revenue": round(revenue, 2)}

    def check_schedule(schedule):
        nums, err = _as_floats(schedule)
        if err:
            return {"error": err}
        _, violations = simulate_soc(nums, battery)
        return {"valid": len(violations) == 0, "violations": violations}

    return {
        "get_forecast": get_forecast,
        "get_battery_state": get_battery_state,
        "run_optimizer": run_optimizer,
        "check_schedule": check_schedule,
    }
