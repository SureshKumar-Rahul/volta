# report.py
"""Render the backtest into a revenue chart and a markdown results table."""

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt


def report_paths(forecaster):
    """Output file paths for a backtest run, keyed by the active forecaster. The
    default (naive) forecaster keeps the canonical results.md / revenue.png that the
    README references; any other forecaster writes to its own files so an A/B run does
    not overwrite the baseline."""
    name = (forecaster or "naive").lower()
    if name == "naive":
        return "results.md", "revenue.png"
    return f"results.{name}.md", f"revenue.{name}.png"


def write_report(summary, day_results, md_path="results.md", chart_path="revenue.png"):
    _write_chart(day_results, chart_path)
    _write_markdown(summary, day_results, md_path, chart_path)


def _write_chart(day_results, chart_path):
    dates = [d["date"] for d in day_results]
    x = range(len(dates))
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x, [d["optimum"] for d in day_results], label="perfect-foresight optimum")
    ax.plot(x, [d["agent"] for d in day_results], label="agent")
    ax.plot(x, [d["threshold"] for d in day_results], label="threshold heuristic")
    ax.set_xlabel("day")
    ax.set_ylabel("revenue (EUR)")
    ax.set_title("Daily revenue by strategy")
    ax.legend()
    fig.tight_layout()
    fig.savefig(chart_path, dpi=120)
    plt.close(fig)


def _write_markdown(summary, day_results, md_path, chart_path):
    lines = [
        "# Volta backtest results",
        "",
        f"Over {summary['days']} days of DE-LU day-ahead prices, the agent captured "
        f"**{summary['pct_of_optimum']:.1f}%** of the perfect-foresight optimum.",
        "",
        f"![revenue]({chart_path})",
        "",
        "| Strategy | Total revenue (EUR) |",
        "| --- | --- |",
        f"| Perfect-foresight optimum | {summary['optimum_revenue']:.0f} |",
        f"| Agent | {summary['agent_revenue']:.0f} |",
        f"| Threshold heuristic | {summary['threshold_revenue']:.0f} |",
        f"| Do nothing | {summary['do_nothing_revenue']:.0f} |",
        "",
    ]
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
