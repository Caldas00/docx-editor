#!/usr/bin/env bash
# Quality gate: lint + offline tests (+ real-model evals with --evals).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check src tests evals scripts
uv run pytest -q
if [[ "${1:-}" == "--evals" ]]; then
  uv run python evals/run.py
fi
