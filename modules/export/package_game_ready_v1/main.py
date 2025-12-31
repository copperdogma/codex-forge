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
    candidates = [
        run_dir / "snapshots" / "recipe.yaml",
        run_dir / "snapshots" / "recipe.yml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Recipe not found. Looked for {candidates[0]} and {candidates[1]}."
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
        "- `gamebook.json`: Final gamebook output.\n"
        "- `validator/`: Validator bundle and schema for the gamebook.\n\n"
        "## Usage\n"
        "Copy `gamebook.json` and the entire `validator/` directory into your game engine build.\n"
        "Then run the validator before loading the gamebook:\n\n"
        "```bash\n"
        "node validator/gamebook-validator.bundle.js gamebook.json --json\n"
        "```\n\n"
        f"Validator module: `{module_id}`\n"
    )
    dest.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package game-ready artifacts for engine consumption.")
    parser.add_argument("--input")
    parser.add_argument("--gamebook")
    parser.add_argument("--recipe")
    parser.add_argument("--run-dir")
    parser.add_argument("--out")
    parser.add_argument("--outdir")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("package_game_ready", "running", message="Resolving paths", module_id="package_game_ready_v1")

    gamebook_arg = args.gamebook or args.input
    if not gamebook_arg:
        raise SystemExit("--input or --gamebook is required")
    gamebook_path = Path(gamebook_arg)
    if not gamebook_path.exists():
        raise FileNotFoundError(f"gamebook.json not found at {gamebook_path}")

    run_dir = Path(args.run_dir) if args.run_dir else gamebook_path.parent
    if not run_dir.exists():
        raise FileNotFoundError(f"Run dir not found: {run_dir}")

    out_dir = Path(args.out) if args.out else run_dir / "output"
    if args.outdir and not out_dir.is_absolute():
        out_dir = Path(args.outdir) / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    recipe_path = _resolve_recipe_path(run_dir, args.recipe)
    recipe = _load_recipe(recipe_path)
    validator_stage = _find_validator_stage(recipe)
    validator_dir = _resolve_validator_dir(validator_stage)
    if not validator_dir.exists():
        raise FileNotFoundError(f"Validator directory not found: {validator_dir}")

    # Copy gamebook
    shutil.copy2(gamebook_path, out_dir / "gamebook.json")

    # Copy validator folder (additive; does not delete extras)
    dest_validator = out_dir / "validator"
    shutil.copytree(validator_dir, dest_validator, dirs_exist_ok=True)

    # README
    _write_readme(out_dir / "README.md", validator_stage)

    logger.log(
        "package_game_ready",
        "done",
        message=f"Packaged game-ready artifacts -> {out_dir}",
        module_id="package_game_ready_v1",
        artifact=str(out_dir),
    )
    print(f"Packaged game-ready artifacts -> {out_dir}")


if __name__ == "__main__":
    main()
