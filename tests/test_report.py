# tests/test_report.py
import os

from volta.eval.report import write_report


def test_write_report_creates_files(tmp_path):
    summary = {"days": 2, "agent_revenue": 120.0, "optimum_revenue": 200.0,
               "threshold_revenue": 80.0, "do_nothing_revenue": 0.0,
               "pct_of_optimum": 60.0}
    day_results = [
        {"date": "2025-01-01", "agent": 80.0, "optimum": 100.0, "threshold": 50.0, "do_nothing": 0.0},
        {"date": "2025-01-02", "agent": 40.0, "optimum": 100.0, "threshold": 30.0, "do_nothing": 0.0},
    ]
    md = tmp_path / "results.md"
    png = tmp_path / "revenue.png"
    write_report(summary, day_results, md_path=str(md), chart_path=str(png))
    assert md.exists() and png.exists()
    assert "60.0" in md.read_text()
