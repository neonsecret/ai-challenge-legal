#!/usr/bin/env bash
# Run the speed pipeline with PyPy (stdlib + page cache + optional Google AI).
# Usage:
#   export GOOGLE_AI_API_KEY=...   # required for LLM-backed answers
#   ./speed_agent/run_pipeline.sh [extra args passed to fast_pipeline.py]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${OUT:-speed_agent/submission_pypy.json}"
QS="${QUESTIONS:-data/questions.json}"
WORKERS="${WORKERS:-4}"
exec pypy3 speed_agent/fast_pipeline.py \
  --questions "$QS" \
  --output "$OUT" \
  --workers "$WORKERS" \
  "$@"
