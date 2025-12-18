#!/usr/bin/env bash
set -euo pipefail

RECIPE=""
SETTINGS=""
RUN_ID=""
OUTPUT_DIR=""
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recipe)
      RECIPE="${2:-}"; shift 2;;
    --settings)
      SETTINGS="${2:-}"; shift 2;;
    --run-id|--run_id)
      RUN_ID="${2:-}"; shift 2;;
    --output-dir|--output_dir)
      OUTPUT_DIR="${2:-}"; shift 2;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break;;
    *)
      EXTRA_ARGS+=("$1"); shift;;
  esac
done

if [[ -z "$RECIPE" || -z "$RUN_ID" || -z "$OUTPUT_DIR" ]]; then
  echo "usage: $0 --recipe <recipe.yaml> --run-id <run_id> --output-dir <output_parent_dir> [--settings <settings.yaml>] [-- <extra driver.py args>]" >&2
  echo "example:" >&2
  echo "  $0 --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.ff-canonical-smoke.yaml --run-id story-074-full-20251218-XXXXXX --output-dir output/runs" >&2
  exit 2
fi

RUN_DIR="$OUTPUT_DIR/$RUN_ID"
mkdir -p "$RUN_DIR"

PIDFILE="$RUN_DIR/driver.pid"
LOGFILE="$RUN_DIR/driver.log"

DRIVER_ARGS=(--recipe "$RECIPE" --run-id "$RUN_ID" --output-dir "$OUTPUT_DIR")
if [[ -n "$SETTINGS" ]]; then
  DRIVER_ARGS+=(--settings "$SETTINGS")
fi
DRIVER_ARGS+=("${EXTRA_ARGS[@]}")

echo "Run dir: $RUN_DIR"
echo "Starting: python driver.py ${DRIVER_ARGS[*]}"
echo "Logging to: $LOGFILE"

(
  PYTHONPATH=. python driver.py "${DRIVER_ARGS[@]}" 2>&1 | tee -a "$LOGFILE"
) &

PID="$!"
echo "$PID" >"$PIDFILE"
echo "PID: $PID (pidfile: $PIDFILE)"

./scripts/monitor_run.sh "$RUN_DIR" "$PIDFILE" 5

wait "$PID"
EXIT_CODE="$?"
echo "driver.py exited with code $EXIT_CODE"
exit "$EXIT_CODE"

