import json
import os
import shutil
import subprocess

import pytest


def _bundle_path():
    return os.path.join(
        "modules",
        "validate",
        "validate_ff_engine_node_v1",
        "validator",
        "gamebook-validator.bundle.js",
    )


def _run_validator(path):
    if not shutil.which("node"):
        pytest.skip("node not available")
    bundle = _bundle_path()
    if not os.path.exists(bundle):
        pytest.skip(f"validator bundle missing at {bundle}")
    result = subprocess.run(
        ["node", bundle, path, "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result


def test_validator_flags_missing_combat_outcomes(tmp_path):
    gamebook = {
        "metadata": {
            "title": "Example",
            "startSection": "1",
            "formatVersion": "1.0.0",
            "sectionCount": 2,
        },
        "sections": {
            "1": {
                "id": "1",
                "presentation_html": "<p>Fight the beast.</p>",
                "isGameplaySection": True,
                "type": "section",
                "sequence": [
                    {
                        "kind": "combat",
                        "mode": "single",
                        "enemies": [{"enemy": "BEAST", "skill": 7, "stamina": 7}],
                        # outcomes intentionally missing
                    }
                ],
            },
            "2": {
                "id": "2",
                "presentation_html": "<p>End.</p>",
                "isGameplaySection": True,
                "type": "section",
                "sequence": [],
            },
        },
    }
    path = tmp_path / "gamebook.json"
    path.write_text(json.dumps(gamebook))
    result = _run_validator(str(path))
    assert result.returncode != 0
    report = json.loads(result.stdout)
    errors = report.get("errors", [])
    assert any(
        err.get("path", "").endswith("/sequence/0/outcomes") or "outcomes" in err.get("message", "")
        for err in errors
    )
