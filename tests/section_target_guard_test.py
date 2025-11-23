import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.adapter.section_target_guard_v1 import main as guard


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def test_guard_maps_and_passes_when_targets_present(tmp_path: Path, monkeypatch):
    primary = tmp_path / "primary.jsonl"
    secondary = tmp_path / "secondary.jsonl"
    out_path = tmp_path / "out.jsonl"
    report = tmp_path / "report.json"

    write_jsonl(
        primary,
        [
            {"portion_id": "1", "section_id": "1", "targets": ["2"]},
        ],
    )
    write_jsonl(
        secondary,
        [
            {"portion_id": "2", "section_id": "2", "targets": []},
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--inputs",
            str(primary),
            str(secondary),
            "--out",
            str(out_path),
            "--report",
            str(report),
        ],
    )

    guard.main()

    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["missing_count"] == 0
    assert data["targets_present"] == 1
    rows = list(read_jsonl(out_path))
    assert rows[0]["target_hits"] == ["2"]
    assert rows[0]["target_misses"] == []
    assert len(rows) == 1  # no stubs added


def test_guard_fails_and_backfills_missing_targets(tmp_path: Path, monkeypatch):
    primary = tmp_path / "primary.jsonl"
    out_path = tmp_path / "out.jsonl"
    report = tmp_path / "report.json"

    write_jsonl(
        primary,
        [
            {"portion_id": "1", "section_id": "1", "targets": ["2"]},
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--inputs",
            str(primary),
            "--out",
            str(out_path),
            "--report",
            str(report),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        guard.main()

    assert excinfo.value.code == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["missing_count"] == 1
    rows = list(read_jsonl(out_path))
    assert len(rows) == 2  # original + stub
    stub = rows[1]
    assert stub["section_id"] == "2"
    assert stub["portion_id"] == "2"
    assert stub["targets"] == []
    assert stub["raw_text"] == ""
