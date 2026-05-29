#!/usr/bin/env bash
# Easy runner for Volta.
#
#   ./run.sh sample [start] [days]   # load synthetic prices (no key, runs offline)
#   ./run.sh fetch  <start> <end>    # load real DE-LU prices (needs ENTSOE_API_TOKEN)
#   ./run.sh backtest                # score the agent over stored days (needs an LLM key)
#   ./run.sh today  <date>           # plan a single day (needs an LLM key)
#
# Choose the model with LLM_PROVIDER and pass its key on the same line, for example:
#   LLM_PROVIDER=groq GROQ_API_KEY=... ./run.sh backtest
set -euo pipefail

py="${PYTHON:-.venv/bin/python}"
cmd="${1:-backtest}"
shift || true

case "$cmd" in
  sample)   "$py" -m volta sample --start "${1:-2025-01-01}" --days "${2:-60}" ;;
  fetch)    "$py" -m volta fetch --start "${1:?need a start date}" --end "${2:?need an end date}" ;;
  backtest) "$py" -m volta backtest ;;
  today)    "$py" -m volta today --date "${1:?need a date}" ;;
  *) echo "usage: ./run.sh [sample|fetch|backtest|today] ..." >&2; exit 1 ;;
esac
