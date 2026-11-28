#!/usr/bin/env bash
# Every check CI runs, in order: Python tests, build, all Node suites, then a
# byte-for-byte reproducibility rebuild. Run from the repository root:
#   scripts/check_all.sh            (uses python3, or $PYTHON if set)
# Needs Python 3.10+ with requirements.txt, Node, and Poppler's pdftotext.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

"$PYTHON" -m unittest discover -s tests
"$PYTHON" scripts/build.py
for suite in tests/*.js; do
  echo "node $suite"
  node "$suite"
done
"$PYTHON" scripts/check_reproducible_build.py
