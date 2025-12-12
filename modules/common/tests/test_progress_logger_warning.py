import json
from pathlib import Path

from modules.common.utils import ProgressLogger, validate_progress_event


def test_validate_progress_event_allows_warning():
    event = {
        "timestamp": "2025-12-12T00:00:00Z",
        "run_id": "run-1",
        "stage": "extract",
        "status": "warning",
        "current": None,
        "total": None,
        "percent": None,
        "message": "something non-fatal happened",
        "artifact": None,
        "module_id": "mod-1",
        "schema_version": None,
        "stage_description": None,
        "extra": {},
    }
    validate_progress_event(event)


def test_progress_logger_warning_does_not_overwrite_stage_lifecycle_status(tmp_path: Path):
    state_path = tmp_path / "pipeline_state.json"
    progress_path = tmp_path / "pipeline_events.jsonl"
    logger = ProgressLogger(state_path=str(state_path), progress_path=str(progress_path), run_id="run-1")

    logger.log("extract", "running", message="started")
    logger.log("extract", "warning", message="non-fatal", extra={"level": "warning"})

    state = json.loads(state_path.read_text())
    assert state["stages"]["extract"]["status"] == "running"

