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

echo "Monitoring run_dir=$RUN_DIR pid=$PID interval=${INTERVAL}s"
echo "Ctrl+C to stop."
echo "Tip: run driver in background and write its pid to the pidfile, e.g.:"
echo "  python driver.py ... & echo \\$! > \"$PIDFILE\""

while true; do
  if ! ps -p "$PID" >/dev/null 2>&1; then
    echo "Process $PID is not running."
    if [[ -f "$EVENTS" ]]; then
      echo "--- last 25 events ---"
      tail -n 25 "$EVENTS" || true
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
