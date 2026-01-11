import json
import sys
from pathlib import Path

import pytest


def _write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _read_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def test_orphan_reocr_flags_sources(tmp_path):
    portions = [
        {"portion_id": "100", "section_id": "100", "choices": [{"target": "397"}]},
        {"portion_id": "101", "section_id": "101", "choices": [{"target": "397"}]},
        {"portion_id": "307", "section_id": "307", "choices": []},
        {"portion_id": "397", "section_id": "397", "choices": []},
    ]
    in_path = tmp_path / "portions.jsonl"
    out_path = tmp_path / "out.jsonl"
    _write_jsonl(in_path, portions)

    from modules.adapter.orphan_reocr_candidates_v1.main import main as run

    argv = [
        "orphan_reocr_candidates_v1",
        "--portions",
        str(in_path),
        "--out",
        str(out_path),
        "--min-inbound",
        "2",
    ]
    sys_argv = sys.argv
    try:
        sys.argv = argv
        run()
    finally:
        sys.argv = sys_argv

    rows = _read_jsonl(out_path)
    flagged = {r["section_id"] for r in rows if r.get("repair_hints")}
    assert flagged == {"100", "101"}
    for row in rows:
        if row.get("section_id") in {"100", "101"}:
            hints = row.get("repair_hints") or {}
            reasons = hints.get("escalation_reasons") or []
            assert "orphan_similar_target" in reasons
            details = hints.get("orphan_similar_target") or []
            assert any(d.get("orphan_id") == "307" and d.get("suspect_target") == "397" for d in details)


@pytest.mark.parametrize("min_inbound,expected", [(3, set()), (2, {"100", "101"})])
def test_orphan_reocr_min_inbound(tmp_path, min_inbound, expected):
    portions = [
        {"portion_id": "100", "section_id": "100", "choices": [{"target": "397"}]},
        {"portion_id": "101", "section_id": "101", "choices": [{"target": "397"}]},
        {"portion_id": "307", "section_id": "307", "choices": []},
        {"portion_id": "397", "section_id": "397", "choices": []},
    ]
    in_path = tmp_path / "portions.jsonl"
    out_path = tmp_path / "out.jsonl"
    _write_jsonl(in_path, portions)

    from modules.adapter.orphan_reocr_candidates_v1.main import main as run

    argv = [
        "orphan_reocr_candidates_v1",
        "--portions",
        str(in_path),
        "--out",
        str(out_path),
        "--min-inbound",
        str(min_inbound),
    ]
    sys_argv = sys.argv
    try:
        sys.argv = argv
        run()
    finally:
        sys.argv = sys_argv

    rows = _read_jsonl(out_path)
    flagged = {r["section_id"] for r in rows if r.get("repair_hints")}
    assert flagged == expected
