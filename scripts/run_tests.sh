#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/run_tests.sh api
#   ./scripts/run_tests.sh persistence
#   ./scripts/run_tests.sh resizer
#   ./scripts/run_tests.sh textgen
#   ./scripts/run_tests.sh sentiment
#   ./scripts/run_tests.sh all
#   ./scripts/run_tests.sh none

SCOPE="${1:-all}"

run_marker () {
  local marker="$1"
  echo "== pytest -m ${marker} =="
  pytest -m "${marker}" -q
}

case "$SCOPE" in
  api|persistence|resizer|textgen|sentiment)
    run_marker "$SCOPE"
    ;;
  all)
    run_marker api
    run_marker persistence
    run_marker resizer
    run_marker textgen
    run_marker sentiment
    ;;
  none)
    echo "Tests übersprungen (SCOPE=none)"
    ;;
  *)
    echo "Unbekannter Test-Scope: '$SCOPE'"
    echo "Erwartet: api | persistence | resizer | textgen | sentiment | all | none"
    exit 1
    ;;
esac
