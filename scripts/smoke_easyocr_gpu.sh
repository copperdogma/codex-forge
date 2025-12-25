#!/usr/bin/env bash
set -euo pipefail

# 5-page EasyOCR-only GPU smoke + regression check.
# Usage (from repo root):
#   ./scripts/smoke_easyocr_gpu.sh /tmp/cf-easyocr-mps-5
# If no arg is supplied, defaults to /tmp/cf-easyocr-mps-5

OUTDIR=${1:-/tmp/cf-easyocr-mps-5}

python driver.py \
  --recipe configs/recipes/legacy/recipe-ff-canonical.yaml \
  --settings configs/settings.easyocr-gpu-test.yaml \
  --end-at intake \
  --run-id cf-easyocr-mps-5 \
  --output-dir "$OUTDIR" \
  --force

python scripts/regression/check_easyocr_gpu.py \
  --debug-file "$OUTDIR/ocr_ensemble/easyocr_debug.jsonl"

echo "[OK] EasyOCR GPU smoke + check succeeded (output: $OUTDIR)"
