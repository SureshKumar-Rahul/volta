# backtester.py
"""Replay historical days with no lookahead, score the agent against a do-nothing
baseline, a threshold heuristic, and the perfect-foresight optimum, and log to MLflow."""

import storage
from optimizer import optimize_dispatch
from simulate import score_schedule
from strategies import do_nothing_schedule, threshold_schedule


def run_backtest(conn, battery, dates, agent_fn, log=False, run_name="volta"):
    """For each date, run the agent and score every strategy on realized prices.

    agent_fn: callable(date_str) -> dict with a "schedule" key. The agent must use
    only information available at decision time (the tools enforce this by serving
    the previous day's prices as the forecast)."""
    day_results = []
    for date_str in dates:
        prices = storage.get_prices_for_date(conn, date_str)
        if len(prices) != 24:
            continue  # skip incomplete days

        agent = agent_fn(date_str)
        agent_rev = score_schedule(agent["schedule"], prices)
        opt_schedule, opt_rev = optimize_dispatch(prices, battery, cyclic=True)
        thr_rev = score_schedule(threshold_schedule(prices, battery), prices)
        none_rev = score_schedule(do_nothing_schedule(24), prices)

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
