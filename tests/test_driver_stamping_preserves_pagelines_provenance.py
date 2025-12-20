import sys
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_stamp_artifact_preserves_optional_pagelines_fields(tmp_path: Path):
    from driver import stamp_artifact

    p = tmp_path / "pagelines.jsonl"
    row = {
        "schema_version": "pagelines_v1",
        "module_id": "unit_test",
        "run_id": "test-run",
        "page": 1,
        "page_number": 1,
        "original_page_number": 1,
        "image": "x.png",
        "lines": [{"text": "Hello", "source": "tesseract"}],
        "needs_escalation": True,
        "engines_raw": {"tesseract": "Hello"},
        "quality_metrics": {"dictionary_score": 0.5},
        "column_spans": [[0.0, 1.0]],
        "ivr": 0.42,
        "meta": {"note": "keep"},
        "escalation_reasons": ["dictionary_oov"],
    }
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")

    stamp_artifact(str(p), "pagelines_v1", module_id="unit_test", run_id="test-run")

    out = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert out["engines_raw"] == {"tesseract": "Hello"}
    assert out["quality_metrics"] == {"dictionary_score": 0.5}
    assert out["column_spans"] == [[0.0, 1.0]]
    assert out["ivr"] == 0.42
    assert out["meta"] == {"note": "keep"}
    assert out["escalation_reasons"] == ["dictionary_oov"]
    assert out["page_number"] == 1
    assert out["original_page_number"] == 1
