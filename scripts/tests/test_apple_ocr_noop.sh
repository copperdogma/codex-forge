#!/usr/bin/env bash
# Smoke/guard test: Apple Vision OCR should no-op cleanly off macOS.
# Requires: PYTHONPATH=. and testdata/tbotb-mini.pdf present.

set -euo pipefail

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "[apple-noop] running on macOS; skipping noop test."
  exit 0
fi

OUTDIR="/tmp/cf-apple-noop-test-$$"
rm -rf "$OUTDIR"

PYTHONPATH=. python modules/extract/extract_ocr_apple_v1/main.py \
  --pdf testdata/tbotb-mini.pdf \
  --outdir "$OUTDIR" \
  --start 1 --end 1

PAGELINES="$OUTDIR/ocr_apple/pagelines.jsonl"
ERROR_JSON="$OUTDIR/ocr_apple/error.json"

if [[ ! -f "$PAGELINES" ]]; then
  echo "[apple-noop] missing pagelines output at $PAGELINES" >&2
  exit 1
fi

if [[ ! -f "$ERROR_JSON" ]]; then
  echo "[apple-noop] missing error artifact at $ERROR_JSON" >&2
  exit 1
fi

LINES="$(wc -l < "$PAGELINES" | tr -d ' ')"
if [[ "$LINES" != "0" ]]; then
  echo "[apple-noop] expected empty pagelines, got $LINES lines" >&2
  exit 1
fi

python - <<'PY'
import json, sys, pathlib
p=pathlib.Path(sys.argv[1])
data=json.loads(p.read_text())
assert data.get("skipped") is True, data
print("[apple-noop] ok")
PY "$ERROR_JSON"

rm -rf "$OUTDIR"

