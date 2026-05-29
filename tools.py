# tools.py
"""Agent-callable tools, bound to a database connection and a battery config.
Each returns a plain dict so results serialize cleanly into the LLM transcript."""

import datetime as dt
from dataclasses import asdict

import storage
from optimizer import optimize_dispatch
from simulate import simulate_soc
from strategies import naive_forecast


def make_tools(conn, battery):
    def get_forecast(date_str):
        """Naive forecast: the previous day's realized prices."""
        prev = (dt.date.fromisoformat(date_str) - dt.timedelta(days=1)).isoformat()
        prices = naive_forecast(storage.get_prices_for_date(conn, prev))
        return {"date": date_str, "forecast_source": prev, "prices": prices}

    def get_battery_state():
        state = asdict(battery)
        state["start_soc_mwh"] = battery.start_soc_frac * battery.capacity_mwh
        return state

    def run_optimizer(prices):
        schedule, revenue = optimize_dispatch(prices, battery, cyclic=True)
        return {"schedule": schedule, "expected_revenue": round(revenue, 2)}

    def check_schedule(schedule):
        _, violations = simulate_soc(schedule, battery)
        return {"valid": len(violations) == 0, "violations": violations}

    return {
        "get_forecast": get_forecast,
        "get_battery_state": get_battery_state,
        "run_optimizer": run_optimizer,
        "check_schedule": check_schedule,
    }
