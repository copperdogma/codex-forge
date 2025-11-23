import json
import pytest

from schemas import LLMCallUsage, StageInstrumentation, RunInstrumentation
from validate_artifact import SCHEMA_MAP


def test_instrumentation_models_roundtrip(tmp_path):
    call = LLMCallUsage(
        model="gpt-4.1-mini",
        prompt_tokens=10,
        completion_tokens=5,
        cached=False,
        request_ms=123.4,
        request_id="req-1",
        cost=0.001,
        stage_id="clean",
        run_id="run-1",
    )
    stage = StageInstrumentation(
        id="clean",
        stage="clean",
        module_id="clean_llm_v1",
        status="done",
        artifact="pages_clean.jsonl",
        schema_version_output="clean_page_v1",
        started_at="2025-11-22T22:00:00Z",
        ended_at="2025-11-22T22:00:05Z",
        wall_seconds=5.0,
        cpu_user_seconds=1.2,
        cpu_system_seconds=0.3,
        llm_calls=[call],
        llm_totals={
            "calls": 1,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost": 0.001,
        },
    )
    run = RunInstrumentation(
        run_id="run-1",
        recipe_name="test-recipe",
        recipe_path="configs/recipes/recipe-text.yaml",
        started_at="2025-11-22T22:00:00Z",
        ended_at="2025-11-22T22:00:10Z",
        wall_seconds=10.0,
        cpu_user_seconds=2.0,
        cpu_system_seconds=0.5,
        stages=[stage],
        totals={
            "calls": 1,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost": 0.001,
            "per_model": {
                "gpt-4.1-mini": {
                    "calls": 1,
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "cost": 0.001,
                }
            },
        },
        pricing={"currency": "USD"},
        env={"platform": "test"},
    )

    # round-trip via JSON and SCHEMA_MAP to mirror validate_artifact usage
    out_path = tmp_path / "instrumentation.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(run.model_dump(), f)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    model_cls = SCHEMA_MAP["instrumentation_run_v1"]
    reloaded = model_cls(**data)
    assert reloaded.run_id == "run-1"
    assert reloaded.stages[0].llm_totals["cost"] == pytest.approx(0.001)


def test_llm_usage_validation_negative_tokens():
    with pytest.raises(ValueError):
        LLMCallUsage(model="gpt-4.1-mini", prompt_tokens=-1, completion_tokens=0)
