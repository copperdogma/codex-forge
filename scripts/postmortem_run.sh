#!/usr/bin/env bash
set -u

RUN_DIR="${1:-}"
if [[ -z "$RUN_DIR" ]]; then
  echo "usage: $0 <run_dir>" >&2
  exit 2
fi

PIDFILE="$RUN_DIR/driver.pid"
EVENTS="$RUN_DIR/pipeline_events.jsonl"
STATE="$RUN_DIR/pipeline_state.json"

if [[ ! -f "$PIDFILE" ]]; then
  echo "pidfile not found: $PIDFILE" >&2
  exit 2
fi

PID="$(cat "$PIDFILE")"
if ps -p "$PID" >/dev/null 2>&1; then
  echo "Process $PID is still running; no postmortem needed."
  exit 0
fi

RUN_ID=""
if [[ -f "$STATE" ]]; then
  RUN_ID="$(python - <<'PY' 2>/dev/null
import json
from pathlib import Path
p=Path("$STATE")
print(json.loads(p.read_text()).get("run_id", ""))
PY)"
fi

RUN_ID="$RUN_ID" PID="$PID" python - <<'PY' >>"$EVENTS"
import datetime
import json
import os
run_id = os.environ.get("RUN_ID", "")
pid = os.environ.get("PID", "")
now = datetime.datetime.utcnow().isoformat(timespec="microseconds") + "Z"
print(json.dumps({
    "timestamp": now,
    "run_id": run_id,
    "stage": "run_postmortem",
    "status": "failed",
    "current": None,
    "total": None,
    "percent": None,
    "message": f"Process {pid} is not running (postmortem)",
    "artifact": None,
    "module_id": "postmortem_run.sh",
    "schema_version": None,
    "stage_description": "postmortem detected driver process exit",
    "extra": {"pid": pid},
}))
PY

RUN_DIR="$RUN_DIR" PID="$PID" python - <<'PY'
import datetime
import json
import os
from pathlib import Path

run_dir = Path(os.environ.get("RUN_DIR", ""))
pid = os.environ.get("PID", "")
state_path = run_dir / "pipeline_state.json"
if not state_path.exists():
    raise SystemExit(0)

try:
    state = json.loads(state_path.read_text())
except Exception:
    state = {}

status = (state.get("status") or "").lower()
if status in {"done", "failed", "skipped", "crashed"}:
    raise SystemExit(0)

now = datetime.datetime.utcnow().isoformat(timespec="microseconds") + "Z"
state["status"] = "crashed"
state["status_reason"] = f"run_postmortem: process {pid} not running"
state["ended_at"] = now
state_path.write_text(json.dumps(state, indent=2))
PY

exit 0
