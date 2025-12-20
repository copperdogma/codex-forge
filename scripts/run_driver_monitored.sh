#!/usr/bin/env bash
set -euo pipefail

RECIPE=""
SETTINGS=""
RUN_ID=""
OUTPUT_DIR=""
EXTRA_ARGS=()
FORCE=0

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
if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
  for arg in "${EXTRA_ARGS[@]}"; do
    if [[ "$arg" == "--force" ]]; then
      FORCE=1
    fi
  done
  if [[ "$FORCE" -eq 1 ]]; then
    FILTERED=()
    for arg in "${EXTRA_ARGS[@]}"; do
      if [[ "$arg" != "--force" ]]; then
        FILTERED+=("$arg")
      fi
    done
    EXTRA_ARGS=("${FILTERED[@]}")
  fi
fi

if [[ "$FORCE" -eq 1 && -d "$RUN_DIR" ]]; then
  echo "⚠️  --force: Deleting existing directory: $RUN_DIR"
  rm -rf "$RUN_DIR"
fi

mkdir -p "$RUN_DIR"

PIDFILE="$RUN_DIR/driver.pid"
LOGFILE="$RUN_DIR/driver.log"

DRIVER_ARGS=(--recipe "$RECIPE" --run-id "$RUN_ID" --output-dir "$RUN_DIR")
if [[ "$FORCE" -eq 1 ]]; then
  DRIVER_ARGS+=(--allow-run-id-reuse)
fi
if [[ -n "$SETTINGS" ]]; then
  DRIVER_ARGS+=(--settings "$SETTINGS")
fi
DRIVER_ARGS+=("${EXTRA_ARGS[@]}")

echo "Run dir: $RUN_DIR"
echo "Starting: python driver.py ${DRIVER_ARGS[*]}"
echo "Logging to: $LOGFILE"
if [[ "$FORCE" -eq 1 ]]; then
  echo "Note: --force handled by run_driver_monitored.sh (pre-delete), not passed to driver.py"
fi

(
  PYTHONPATH=. python driver.py "${DRIVER_ARGS[@]}" 2>&1 | tee -a "$LOGFILE"
  echo "[driver] exit code: $?" >>"$LOGFILE"
) &

PID="$!"
echo "$PID" >"$PIDFILE"
echo "PID: $PID (pidfile: $PIDFILE)"

./scripts/monitor_run.sh "$RUN_DIR" "$PIDFILE" 5

wait "$PID"
EXIT_CODE="$?"
echo "driver.py exited with code $EXIT_CODE"

scripts/postmortem_run.sh "$RUN_DIR" || true

if [[ "$EXIT_CODE" -ne 0 ]]; then
  EVENTS="$RUN_DIR/pipeline_events.jsonl"
  RUN_ID_STATE="$RUN_DIR/pipeline_state.json"
  RUN_ID_VALUE="$RUN_ID"
  if [[ -f "$RUN_ID_STATE" ]]; then
    RUN_ID_VALUE="$(python - <<'PY' 2>/dev/null\nimport json\nfrom pathlib import Path\np=Path(\"$RUN_ID_STATE\")\nprint(json.loads(p.read_text()).get(\"run_id\", \"\"))\nPY)"
  fi
  RUN_ID_VALUE="$RUN_ID_VALUE" EXIT_CODE="$EXIT_CODE" python - <<'PY' >>"$EVENTS"
import datetime
import json
import os
run_id = os.environ.get("RUN_ID_VALUE", "")
exit_code = os.environ.get("EXIT_CODE", "")
message = f"driver.py exited with code {exit_code}"
now = datetime.datetime.utcnow().isoformat(timespec="microseconds") + "Z"
print(json.dumps({
    "timestamp": now,
    "run_id": run_id,
    "stage": "run_driver",
    "status": "failed",
    "current": None,
    "total": None,
    "percent": None,
    "message": message,
    "artifact": None,
    "module_id": "run_driver_monitored.sh",
    "schema_version": None,
    "stage_description": "driver process exited",
    "extra": {"exit_code": exit_code},
}))
PY
fi

exit "$EXIT_CODE"
