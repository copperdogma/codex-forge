import json
import sys
from pathlib import Path

from modules.common.utils import read_jsonl


def _write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_orphan_similar_target_prefers_clean_text(tmp_path):
    rows = [
        {
            "portion_id": "1",
            "section_id": "398",
            "raw_html": '<p>If you want to get in the lift and press the button, turn to <a href="#397"> 397 </a>.</p>',
            "clean_text": "If you want to get in the lift and press the button, turn to 307.",
            "repair_hints": {"escalation_reasons": ["orphan_similar_target"]},
        }
    ]
    in_path = tmp_path / "in.jsonl"
    out_path = tmp_path / "out.jsonl"
    _write_jsonl(in_path, rows)

    from modules.extract.extract_choices_relaxed_v1.main import main as run

    argv = [
        "extract_choices_relaxed_v1",
        "--inputs",
        str(in_path),
        "--out",
        str(out_path),
        "--expected-range",
        "1-400",
    ]
    sys_argv = sys.argv
    try:
        sys.argv = argv
        run()
    finally:
        sys.argv = sys_argv

    out_rows = list(read_jsonl(out_path))
    assert len(out_rows) == 1
    choices = out_rows[0].get("choices") or []
    targets = {c.get("target") for c in choices}
    assert "307" in targets
    assert "397" not in targets
