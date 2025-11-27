import json
import os
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path("modules/intake/tests/fixtures")


def run(cmd):
    env = dict(**{k: v for k, v in dict(**os.environ).items()})
    env["PYTHONPATH"] = str(Path(".").resolve())
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode, result.stdout, result.stderr


def test_intake_chain_with_mocks(tmp_path):
    out_dir = tmp_path / "run"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) builder (use real script to avoid LLM)
    code, _, err = run([
        "python", "modules/intake/contact_sheet_builder_v1/main.py",
        "--input_dir", "input/onward-to-the-unknown-images",
        "--output_dir", str(out_dir / "contact-sheets"),
        "--max_width", "200",
        "--grid_cols", "5",
        "--grid_rows", "4",
    ])
    assert code == 0, err

    manifest = out_dir / "contact-sheets" / "contact_sheet_manifest.jsonl"
    assert manifest.exists()

    # 2) overview (mocked)
    code, out, err = run([
        "python", "modules/intake/contact_sheet_overview_v1/main.py",
        "--manifest", str(manifest),
        "--sheets_dir", str(out_dir / "contact-sheets"),
        "--out", str(out_dir / "plan.json"),
        "--mock_output", str(FIXTURES / "overview_mock.json"),
    ])
    assert code == 0, err

    # 3) zoom refine (mocked)
    code, out, err = run([
        "python", "modules/intake/zoom_refine_v1/main.py",
        "--plan_in", str(out_dir / "plan.json"),
        "--out", str(out_dir / "plan.json"),
        "--mock_output", str(FIXTURES / "zoom_mock.json"),
        "--source_images_dir", "input/onward-to-the-unknown-images",
    ])
    assert code == 0, err

    # 4) gap analysis (no signals file)
    code, out, err = run([
        "python", "modules/intake/gap_analyzer_v1/main.py",
        "--plan_in", str(out_dir / "plan.json"),
        "--out", str(out_dir / "plan.json"),
        "--catalog_path", "modules/module_catalog.yaml",
    ])
    assert code == 0, err
    plan = json.loads(Path(out_dir / "plan.json").read_text())
    assert plan.get("recommended_recipe") == "configs/recipes/recipe-genealogy.yaml"

    # 5) confirm (auto approve)
    code, out, err = run([
        "python", "modules/intake/confirm_plan_v1/main.py",
        "--plan", str(out_dir / "plan.json"),
        "--out", str(out_dir / "plan.json"),
        "--auto-approve",
    ])
    assert code == 0, err

    # 6) dispatch hint
    code, out, err = run([
        "python", "modules/intake/dispatch_hint_v1/main.py",
        "--plan", str(out_dir / "plan.json"),
        "--out", str(out_dir / "dispatch_hint.json"),
    ])
    assert code == 0, err
    hint = json.loads(Path(out_dir / "dispatch_hint.json").read_text())
    assert hint.get("recommended_recipe") == "configs/recipes/recipe-genealogy.yaml"

    # 7) run dispatch (dry run)
    code, out, err = run([
        "python", "modules/intake/run_dispatch_v1/main.py",
        "--dispatch_hint", str(out_dir / "dispatch_hint.json"),
        "--default_recipe", "configs/recipes/recipe-ocr.yaml",
        "--dry_run",
    ])
    assert code == 0, err


@pytest.mark.skip(reason="requires network/vision model; integration path")
def test_overview_live_call():
    # Optional live test placeholder
    pass
