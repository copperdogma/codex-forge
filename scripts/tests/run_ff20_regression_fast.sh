#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
start=$(date +%s)
python -m unittest discover -s tests -p "test_ff_20_page_regression.py" -v
elapsed=$(( $(date +%s) - start ))
echo "FF20 fast regression elapsed ${elapsed}s"
if [ "${elapsed}" -gt 300 ]; then
  echo "FAIL: FF20 fast regression exceeded 300s budget (${elapsed}s)" >&2
  exit 1
fi
