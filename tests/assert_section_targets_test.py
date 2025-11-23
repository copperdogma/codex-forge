import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.validate import assert_section_targets_v1 as mod


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_passes_when_all_targets_present(tmp_path: Path, monkeypatch):
    enriched = tmp_path / "enriched.jsonl"
    report = tmp_path / "report.json"
    rows = [
        {"portion_id": "1", "section_id": "1", "targets": ["2"]},
        {"portion_id": "2", "section_id": "2", "targets": []},
    ]
    write_jsonl(enriched, rows)

    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--inputs", str(enriched), "--out", str(report)],
    )

    mod.main()

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["missing_count"] == 0
    assert data["targets_present"] == 1


def test_fails_when_targets_missing(tmp_path: Path, monkeypatch):
    enriched = tmp_path / "enriched.jsonl"
    report = tmp_path / "report.json"
    rows = [
        {"portion_id": "1", "section_id": "1", "targets": ["2"]},  # target missing
    ]
    write_jsonl(enriched, rows)

    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--inputs", str(enriched), "--out", str(report)],
    )

    with pytest.raises(SystemExit) as excinfo:
        mod.main()

    assert excinfo.value.code == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["missing_count"] == 1
    assert data["missing_sample"] == ["2"]
