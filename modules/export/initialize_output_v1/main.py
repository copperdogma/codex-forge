"""Initialize output directory structure for the pipeline run.

This module runs at the very beginning of the pipeline to ensure the output/
directory structure exists before any other stages run. It creates:
- output/ directory
- output/images/ directory
- output/validator/ (copies validator from module)
- output/README.md

This ensures all stages can rely on output/ existing and having the correct structure.
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import Any, Dict

from modules.common.utils import ProgressLogger
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_recipe(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_recipe_path(run_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    repo_root = _repo_root()
    current = run_dir
    checked: list[Path] = []
    while True:
        candidates = [
            current / "snapshots" / "recipe.yaml",
            current / "snapshots" / "recipe.yml",
        ]
        checked.extend(candidates)
        for candidate in candidates:
            if candidate.exists():
                return candidate
        if current == repo_root or current.parent == current:
            break
        current = current.parent
    raise FileNotFoundError(
        f"Recipe not found. Looked for {checked[0]} and {checked[1]}."
    )


def _find_validator_stage(recipe: Dict[str, Any]) -> Dict[str, Any]:
    stages = recipe.get("stages") or []
    for stage in stages:
        if stage.get("module") == "validate_ff_engine_node_v1":
            return stage
    for stage in stages:
        module_id = stage.get("module") or ""
        if module_id.startswith("validate_") and stage.get("stage") in ("validate", "export"):
            params = stage.get("params") or {}
            if "validator_dir" in params:
                return stage
    raise ValueError("Validator stage not found in recipe. Expected validate_ff_engine_node_v1 or a stage with validator_dir param.")


def _resolve_validator_dir(stage: Dict[str, Any]) -> Path:
    params = stage.get("params") or {}
    validator_dir = params.get("validator_dir")
    if validator_dir:
        return Path(validator_dir)
    module_id = stage.get("module")
    if not module_id:
        raise ValueError("Validator stage missing module id; cannot resolve validator directory.")
    return _repo_root() / "modules" / "validate" / module_id / "validator"


def _write_readme(dest: Path, validator_stage: Dict[str, Any]) -> None:
    module_id = validator_stage.get("module") or "<validator>"
    text = (
        "# Game-Ready Output Package\n\n"
        "This folder contains the artifacts that must ship together into the game engine.\n\n"
        "## Contents\n"
        "- `gamebook.json`: Final gamebook output (created by pipeline stages).\n"
        "- `images/`: Illustration images associated with gamebook sections.\n"
        "- `validator/`: Validator bundle and schema for the gamebook.\n\n"
        "## Usage\n"
        "Copy `gamebook.json`, `images/`, and the entire `validator/` directory into your game engine build.\n"
        "Then run the validator before loading the gamebook:\n\n"
        "```bash\n"
        "node validator/gamebook-validator.bundle.js gamebook.json --json\n"
        "```\n\n"
        f"Validator module: `{module_id}`\n"
    )
    dest.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize output directory structure for pipeline run."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory path")
    parser.add_argument("--recipe", help="Optional path to recipe yaml; defaults to snapshots/recipe.yaml in run dir")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("initialize_output", "running", message="Initializing output directory structure", module_id="initialize_output_v1")

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run dir not found: {run_dir}")

    # Create output directory
    out_dir = run_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.log("initialize_output", "running", message=f"Created output directory: {out_dir}", module_id="initialize_output_v1")

    # Create output/images directory
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    logger.log("initialize_output", "running", message=f"Created images directory: {images_dir}", module_id="initialize_output_v1")

    # Load recipe to find validator stage
    recipe_path = _resolve_recipe_path(run_dir, args.recipe)
    recipe = _load_recipe(recipe_path)
    validator_stage = _find_validator_stage(recipe)
    validator_dir = _resolve_validator_dir(validator_stage)
    
    if not validator_dir.exists():
        raise FileNotFoundError(f"Validator directory not found: {validator_dir}")

    # Copy validator folder
    dest_validator = out_dir / "validator"
    shutil.copytree(validator_dir, dest_validator, dirs_exist_ok=True)
    logger.log("initialize_output", "running", message=f"Copied validator from {validator_dir} to {dest_validator}", module_id="initialize_output_v1")

    # Create README
    _write_readme(out_dir / "README.md", validator_stage)
    logger.log("initialize_output", "running", message=f"Created README.md", module_id="initialize_output_v1")

    logger.log(
        "initialize_output",
        "done",
        message=f"Initialized output directory structure -> {out_dir}",
        module_id="initialize_output_v1",
        artifact=str(out_dir),
    )
    print(f"Initialized output directory structure -> {out_dir}")


if __name__ == "__main__":
    main()
