# main.py
"""Volta CLI.

  python main.py fetch --start 2025-01-01 --end 2025-04-01     # real ENTSO-E data
  python main.py sample --start 2025-01-01 --days 90           # synthetic data, offline
  python main.py backtest                                      # score the agent
  python main.py today --date 2025-01-15                       # plan one day

Needs an LLM provider key for backtest/today (see llm.py) and ENTSOE_API_TOKEN
for fetch. Keys are read from the environment only."""

import argparse
import sqlite3

import storage
from config import DB_PATH, default_battery


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    storage.init_db(conn)
    return conn


def cmd_fetch(args):
    from pipeline import fetch_entsoe
    conn = _conn()
    fetch_entsoe(conn, args.start, args.end)
    print(f"Fetched. Dates in store: {len(storage.get_dates(conn))}")


def cmd_sample(args):
    from pipeline import load_sample_into_db
    conn = _conn()
    load_sample_into_db(conn, args.start, args.days)
    print(f"Loaded {args.days} synthetic days. Dates in store: {len(storage.get_dates(conn))}")


def cmd_backtest(args):
    from agent import run_agent
    from tools import make_tools
    from backtester import run_backtest
    from report import write_report
    from llm import get_client_and_model

    conn = _conn()
    battery = default_battery()
    dates = storage.get_dates(conn)
    client, model = get_client_and_model()
    tools = make_tools(conn, battery)

    def agent_fn(date_str):
        return run_agent(date_str, tools, client=client, model=model)

    summary, day_results = run_backtest(conn, battery, dates, agent_fn, log=True)
    write_report(summary, day_results)
    print(f"Agent captured {summary['pct_of_optimum']:.1f}% of optimum over "
          f"{summary['days']} days. Report written to results.md.")


def cmd_today(args):
    from agent import run_agent
    from tools import make_tools
    from llm import get_client_and_model

    conn = _conn()
    battery = default_battery()
    client, model = get_client_and_model()
    tools = make_tools(conn, battery)
    result = run_agent(args.date, tools, client=client, model=model)
    print(f"Decision for {args.date}: {result['action']}")
    print(f"Rationale: {result['rationale']}")
    for step in result["trace"]:
        print(f"  called {step['tool']}({step['args']})")


def main():
    p = argparse.ArgumentParser(prog="volta")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch"); f.add_argument("--start", required=True)
    f.add_argument("--end", required=True); f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("sample"); s.add_argument("--start", required=True)
    s.add_argument("--days", type=int, default=90); s.set_defaults(func=cmd_sample)

    b = sub.add_parser("backtest"); b.set_defaults(func=cmd_backtest)

    t = sub.add_parser("today"); t.add_argument("--date", required=True)
    t.set_defaults(func=cmd_today)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
