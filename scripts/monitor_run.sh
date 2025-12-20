#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="${1:-}"
PIDFILE="${2:-}"
INTERVAL="${3:-5}"

if [[ -z "$RUN_DIR" || -z "$PIDFILE" ]]; then
  echo "usage: $0 <run_dir> <pidfile> [interval_seconds]" >&2
  exit 2
fi

if [[ ! -f "$PIDFILE" ]]; then
  echo "pidfile not found: $PIDFILE" >&2
  exit 2
fi

PID="$(cat "$PIDFILE")"
EVENTS="$RUN_DIR/pipeline_events.jsonl"
LOGFILE="$RUN_DIR/driver.log"

echo "Monitoring run_dir=$RUN_DIR pid=$PID interval=${INTERVAL}s"
echo "Ctrl+C to stop."
echo "Tip: run driver in background and write its pid to the pidfile, e.g.:"
printf '  python driver.py ... & echo $! > "%s"\n' "$PIDFILE"

while true; do
  if ! ps -p "$PID" >/dev/null 2>&1; then
    echo "Process $PID is not running."
    if [[ -f "$EVENTS" ]]; then
      echo "--- last 25 events ---"
      tail -n 25 "$EVENTS" || true
    fi
    if [[ -f "$LOGFILE" ]]; then
      echo "--- driver.log tail ---"
      tail -n 50 "$LOGFILE" || true
    fi
    if [[ -n "$EVENTS" ]]; then
      RUN_DIR="$RUN_DIR" PID="$PID" python - <<'PY' >>"$EVENTS"
import datetime
import json
import os
from pathlib import Path

run_dir = Path(os.environ.get("RUN_DIR", ""))
pid = os.environ.get("PID")
run_id = ""
state_path = run_dir / "pipeline_state.json"
if state_path.exists():
    try:
        run_id = json.loads(state_path.read_text()).get("run_id", "") or ""
    except Exception:
        run_id = ""
timestamp = datetime.datetime.utcnow().isoformat(timespec="microseconds") + "Z"
event = {
    "timestamp": timestamp,
    "run_id": run_id,
    "stage": "run_monitor",
    "status": "failed",
    "current": None,
    "total": None,
    "percent": None,
    "message": f"Process {pid} is not running.",
    "artifact": None,
    "module_id": "monitor_run.sh",
    "schema_version": None,
    "stage_description": "monitor detected driver process exit",
    "extra": {"pid": pid},
}
print(json.dumps(event))
PY
    fi
    exit 0
  fi

  if [[ -f "$EVENTS" ]]; then
    tail -n 1 "$EVENTS" || true
  else
    echo "(waiting for $EVENTS ...)"
  fi
  sleep "$INTERVAL"
done
