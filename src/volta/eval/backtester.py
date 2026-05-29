# backtester.py
"""Replay historical days with no lookahead, score the agent against a do-nothing
baseline, a threshold heuristic, and the perfect-foresight optimum, and log to MLflow."""

import sys

from volta.market import storage
from volta.market.forecast import forecast_prices
from volta.optimize.optimizer import optimize_dispatch
from volta.optimize.simulate import score_schedule
from volta.optimize.strategies import do_nothing_schedule, threshold_schedule


def run_backtest(conn, battery, dates, agent_fn, log=False, run_name="volta", progress=False):
    """For each date, run the agent and score every strategy on realized prices.

    agent_fn: callable(date_str) -> dict with a "schedule" key. The agent must use
    only information available at decision time (the tools enforce this by serving
    the previous day's prices as the forecast).
    progress: print a per-day line to stderr so a long, LLM-bound run shows life."""
    day_results = []
    # Score only days we can evaluate fairly: a full 24h of realized prices and a full
    # forecast to plan against. The earliest day has no prior day to forecast from (the
    # cold start), so it is skipped rather than charged as a forced, information-free hold.
    scorable = [d for d in dates
                if len(storage.get_prices_for_date(conn, d)) == 24
                and len(forecast_prices(conn, d)) == 24]
    for i, date_str in enumerate(scorable):
        if progress:
            print(f"[{i + 1}/{len(scorable)}] planning {date_str} ...",
                  file=sys.stderr, flush=True)
        prices = storage.get_prices_for_date(conn, date_str)
        forecast = forecast_prices(conn, date_str)

        agent = agent_fn(date_str)
        agent_rev = score_schedule(agent["schedule"], prices)
        _, opt_rev = optimize_dispatch(prices, battery, cyclic=True)
        # The baseline plans on the same forecast the agent sees, then is paid on
        # realized prices. Scoring it on realized prices instead would hand it perfect
        # price foresight the agent never has, which is not a fair comparison.
        thr_rev = score_schedule(threshold_schedule(forecast, battery), prices)
        none_rev = score_schedule(do_nothing_schedule(24), prices)

        if progress:
            print(f"    {date_str}: agent={agent_rev:.0f}  threshold={thr_rev:.0f}  "
                  f"optimum={opt_rev:.0f}  ({agent['action']})",
                  file=sys.stderr, flush=True)

        day_results.append({"date": date_str, "agent": agent_rev, "optimum": opt_rev,
                            "threshold": thr_rev, "do_nothing": none_rev})

    summary = summarize(day_results)
    if log:
        log_to_mlflow(summary, battery, run_name)
    return summary, day_results


def summarize(day_results):
    """Aggregate per-day revenues into totals and the headline percentage."""
    agent = sum(d["agent"] for d in day_results)
    optimum = sum(d["optimum"] for d in day_results)
    threshold = sum(d["threshold"] for d in day_results)
    do_nothing = sum(d["do_nothing"] for d in day_results)
    pct = (agent / optimum * 100.0) if optimum > 0 else 0.0
    return {"days": len(day_results), "agent_revenue": agent,
            "optimum_revenue": optimum, "threshold_revenue": threshold,
            "do_nothing_revenue": do_nothing, "pct_of_optimum": pct}


def log_to_mlflow(summary, battery, run_name):
    """Log the run's battery config and headline metrics to MLflow."""
    import mlflow
    from dataclasses import asdict
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(asdict(battery))
        mlflow.log_metrics({k: float(v) for k, v in summary.items()})
