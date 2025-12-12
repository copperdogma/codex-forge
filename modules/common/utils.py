import json
import os
import yaml
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
from functools import lru_cache

# Progress event schema constants for lightweight validation/testing
PROGRESS_EVENT_SCHEMA: Dict[str, Tuple[type, ...]] = {
    "timestamp": (str,),
    "run_id": (str, type(None)),
    "stage": (str,),
    "status": (str,),
    "current": (int, type(None)),
    "total": (int, type(None)),
    "percent": (float, int, type(None)),
    "message": (str, type(None)),
    "artifact": (str, type(None)),
    "module_id": (str, type(None)),
    "schema_version": (str, type(None)),
    "stage_description": (str, type(None)),
    "extra": (dict,),
}
# Note: `warning` is an event-level status used to surface non-fatal issues while a stage is still running.
# Pipeline state should still reflect the stage lifecycle (running/done/failed/skipped/queued).
PROGRESS_STATUS_VALUES = {"running", "done", "failed", "skipped", "queued", "warning"}


def load_settings(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_json(path: str, data: Any):
    """Save JSON file, ensuring parent directory exists."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
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


def _type_ok(val: Any, allowed: Tuple[type, ...]) -> bool:
    if val is None:
        return type(None) in allowed
    for typ in allowed:
        if typ is float and isinstance(val, (int, float)) and not isinstance(val, bool):
            return True
        if typ is int and isinstance(val, int) and not isinstance(val, bool):
            return True
        if isinstance(val, typ):
            return True
    return False


@lru_cache(maxsize=1)
def english_wordlist():
    # Lightweight set; extend as needed for FF domain
    return set([
        "the", "and", "for", "with", "you", "your", "skill", "stamina", "luck",
        "gold", "sword", "provisions", "attack", "strength", "weapon", "armour",
        "deathtrap", "dungeon", "background", "equipment", "potions", "adventure",
        "fight", "creature", "escape", "turn", "roll", "dice", "test", "walk",
        "challenge", "champion", "trial", "fang", "labyrinth", "baron", "sukumvit",
        "item", "items", "use", "drink", "potion", "left", "right", "north", "south",
        "east", "west", "door", "hall", "tunnel", "room", "open", "close", "key",
        "keys", "monster", "monsters", "health", "damage", "shield", "helm", "helmet",
        "golden", "silver", "iron", "bronze", "treasure", "chest", "pack", "bag",
        "food", "meal", "river", "boat", "bridge", "stairs", "ladder", "gate",
        "rules", "combat", "spell", "magic", "turns", "page", "pages"
    ])


def validate_progress_event(event: Dict[str, Any]):
    """Lightweight runtime guard to keep progress events well-shaped."""
    missing = [k for k in PROGRESS_EVENT_SCHEMA if k not in event]
    if missing:
        raise ValueError(f"Missing progress event fields: {missing}")
    if event.get("status") not in PROGRESS_STATUS_VALUES:
        raise ValueError(f"Invalid progress status: {event.get('status')}")
    for key, allowed in PROGRESS_EVENT_SCHEMA.items():
        if not _type_ok(event.get(key), allowed):
            expected = ", ".join([t.__name__ if t is not type(None) else "None" for t in allowed])
            raise ValueError(f"Field '{key}' expected types [{expected}], got {type(event.get(key)).__name__}")


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
            schema_version: Optional[str] = None, stage_description: Optional[str] = None,
            extra: Optional[Dict[str, Any]] = None):
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
            "stage_description": stage_description,
            "extra": extra or {},
        }

        validate_progress_event(event)

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
            # Keep pipeline_state stage lifecycle statuses stable.
            # Warnings are recorded via events, but should not overwrite the stage lifecycle.
            state_status = status
            if status == "warning":
                prev = stage_state.get("status")
                state_status = prev if prev in {"done", "failed", "skipped"} else "running"
            stage_state.update({
                "status": state_status,
                "artifact": artifact or stage_state.get("artifact"),
                "updated_at": now,
                "module_id": module_id or stage_state.get("module_id"),
                "schema_version": schema_version or stage_state.get("schema_version"),
                "description": stage_description or stage_state.get("description"),
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


def log_llm_usage(model: str, prompt_tokens: int, completion_tokens: int, *,
                  cached: bool = False, provider: str = "openai", request_ms: float = None,
                  request_id: str = None, cost: float = None, stage_id: str = None,
                  run_id: str = None, sink_env: str = "INSTRUMENT_SINK"):
    """
    Append a lightweight LLM usage event to the instrumentation sink if enabled.
    No-op when sink env var is unset.
    """
    sink = os.getenv(sink_env)
    if not sink:
        return None
    if prompt_tokens is None or completion_tokens is None:
        raise ValueError("prompt_tokens and completion_tokens are required")
    event = {
        "schema_version": "instrumentation_call_v1",
        "model": model,
        "provider": provider,
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "cached": bool(cached),
        "request_ms": request_ms,
        "request_id": request_id,
        "cost": cost,
        "stage_id": stage_id or os.getenv("INSTRUMENT_STAGE"),
        "run_id": run_id or os.getenv("RUN_ID"),
        "created_at": _utc(),
    }
    append_jsonl(sink, event)
    return event
