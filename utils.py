import json
import os
import yaml
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


def load_settings(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_jsonl(path: str, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str, row):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


class ProgressLogger:
    """
    Lightweight progress/state emitter.
    - Appends JSONL events to progress_path (append-only).
    - Updates pipeline_state.json with stage status + progress counters.
    Designed to be safe if called repeatedly from long-running modules.
    """

    def __init__(self, state_path: Optional[str] = None, progress_path: Optional[str] = None,
                 run_id: Optional[str] = None):
        self.state_path = state_path
        self.progress_path = progress_path
        self.run_id = run_id
        if progress_path:
            Path(progress_path).parent.mkdir(parents=True, exist_ok=True)
        if state_path:
            Path(state_path).parent.mkdir(parents=True, exist_ok=True)

    def log(self, stage: str, status: str, current: Optional[int] = None, total: Optional[int] = None,
            message: Optional[str] = None, artifact: Optional[str] = None, module_id: Optional[str] = None,
            schema_version: Optional[str] = None, extra: Optional[Dict[str, Any]] = None):
        now = _utc()
        percent = None
        if current is not None and total:
            percent = round((current / total) * 100, 1)

        event = {
            "timestamp": now,
            "run_id": self.run_id,
            "stage": stage,
            "status": status,
            "current": current,
            "total": total,
            "percent": percent,
            "message": message,
            "artifact": artifact,
            "module_id": module_id,
            "schema_version": schema_version,
            "extra": extra or {},
        }

        if self.progress_path:
            append_jsonl(self.progress_path, event)

        if self.state_path:
            state = {}
            if os.path.exists(self.state_path):
                try:
                    with open(self.state_path, "r", encoding="utf-8") as f:
                        state = json.load(f)
                except Exception:
                    state = {}
            stages = state.get("stages", {})
            if self.run_id:
                state["run_id"] = self.run_id
            stage_state = stages.get(stage, {})
            stage_state.update({
                "status": status,
                "artifact": artifact or stage_state.get("artifact"),
                "updated_at": now,
                "module_id": module_id or stage_state.get("module_id"),
                "schema_version": schema_version or stage_state.get("schema_version"),
                "progress": {
                    "current": current,
                    "total": total,
                    "percent": percent,
                    "message": message,
                }
            })
            stages[stage] = stage_state
            state["stages"] = stages
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

        return event
