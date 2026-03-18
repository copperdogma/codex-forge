import json
import subprocess
import sys
from pathlib import Path

import modules.common.load_artifact_v1.main as load_artifact_main


def test_load_artifact_can_copy_sibling_images_dir(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_images = source_dir / "images"
    source_images.mkdir(parents=True, exist_ok=True)

    artifact = source_dir / "illustration_manifest.jsonl"
    artifact.write_text(
        json.dumps({"filename": "page-001-000.jpg", "source_page": 1}) + "\n",
        encoding="utf-8",
    )
    (source_images / "page-001-000.jpg").write_bytes(b"jpeg-bytes")

    out_dir = tmp_path / "out"
    out_path = out_dir / "illustration_manifest.jsonl"

    result = subprocess.run(
        [
            sys.executable,
            "modules/common/load_artifact_v1/main.py",
            "--path",
            str(artifact),
            "--out",
            str(out_path),
            "--copy-sibling-dir",
            "images",
            "--run-id",
            "load-artifact-test",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    copied = out_dir / "images" / "page-001-000.jpg"
    assert copied.exists()
    assert copied.read_bytes() == b"jpeg-bytes"


def test_load_artifact_ignores_missing_sibling_dir(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    artifact = source_dir / "rows.jsonl"
    artifact.write_text(json.dumps({"value": 1}) + "\n", encoding="utf-8")

    out_path = tmp_path / "out" / "rows.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "modules/common/load_artifact_v1/main.py",
            "--path",
            str(artifact),
            "--out",
            str(out_path),
            "--copy-sibling-dir",
            "images",
            "--run-id",
            "load-artifact-test",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert out_path.exists()
    assert not (tmp_path / "out" / "images").exists()


def test_resolve_source_artifact_path_falls_back_to_shared_output_root(
    tmp_path: Path, monkeypatch
) -> None:
    shared_project = tmp_path / "shared-project"
    shared_output = shared_project / "output"
    artifact = shared_output / "runs" / "story143" / "stage" / "rows.jsonl"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"value": 1}) + "\n", encoding="utf-8")

    worktree = tmp_path / "worktree"
    worktree.mkdir()

    monkeypatch.setattr(
        load_artifact_main,
        "resolve_output_root",
        lambda **_: str(shared_output),
    )

    resolved = load_artifact_main._resolve_source_artifact_path(
        "output/runs/story143/stage/rows.jsonl",
        cwd=str(worktree),
    )

    assert resolved == str(artifact.resolve(strict=False))
