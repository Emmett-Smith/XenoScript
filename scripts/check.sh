#!/usr/bin/env bash
# CI-style check: lint + tests + the corpus-agnostic invariant.
# See specs/00_ARCHITECTURE.md #3 and specs/ORCHESTRATOR.md Phase 0.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== ruff =="
uv run ruff check ashlar eval 2>&1 || { echo "ruff FAILED"; exit 1; }

echo "== pytest =="
uv run pytest -q

echo "== corpus-agnostic invariant =="
if grep -rlE '\bplinth\b|\bcobol\b' ashlar/ --include='*.py' | grep -v ashlar/tests; then
  echo "FAIL: language-specific reference found under ashlar/"
  exit 1
fi
echo "OK: no 'plinth' or 'cobol' reference under ashlar/ (excluding tests)"

echo "== all checks passed =="
