#!/usr/bin/env bash
# Every check CI runs, in order: Python tests, build, all Node suites, then a
# byte-for-byte reproducibility rebuild. Run from the repository root:
#   scripts/check_all.sh            (uses python3, or $PYTHON if set)
#   COVERAGE=.qa/coverage scripts/check_all.sh
#                                   also records which code the checks run into
#                                   that folder and prints the test coverage
# Needs Python 3.10+ with requirements.txt, Node, and Poppler's pdftotext.
set -euo pipefail
if [ -n "${COVERAGE:-}" ]; then
  # Resolved before leaving the caller's directory; only an earlier recording is cleared.
  mkdir -p "$COVERAGE/v8"
  COVERAGE="$(cd "$COVERAGE" && pwd)"
  rm -f "$COVERAGE/python" "$COVERAGE"/v8/coverage-*.json
fi
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

python_step() {
  if [ -n "${COVERAGE:-}" ]; then
    COVERAGE_FILE="$COVERAGE/python" "$PYTHON" -m coverage run --append --source=scripts "$@"
  else
    "$PYTHON" "$@"
  fi
}
node_step() {
  if [ -n "${COVERAGE:-}" ]; then
    NODE_V8_COVERAGE="$COVERAGE/v8" node "$@"
  else
    node "$@"
  fi
}

python_step -m unittest discover -s tests
python_step scripts/build.py
for suite in tests/*.js; do
  echo "node $suite"
  node_step "$suite"
done
python_step scripts/check_reproducible_build.py
if [ -n "${COVERAGE:-}" ]; then
  "$PYTHON" scripts/code_coverage.py "$COVERAGE"
fi
