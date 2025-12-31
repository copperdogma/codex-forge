# Story: Game-Ready Output Package

**Status**: Done  
**Created**: 2025-01-28  
**Priority**: High  
**Parent Story**: story-030 (FF Engine format export), story-083 (Game-ready validation checklist), story-107 (Shared Validator Unification)

---

## Goal

Create a clean, ready-to-ship output package for each pipeline run containing the `gamebook.json` and the recipe-specific validator module that must be copied together into the game engine's input folder.

---

## Motivation

When a gamebook is ready to be used in the game engine, two items must be copied together:
1. `output/runs/<run>/gamebook.json` 
2. The validator module folder (e.g., `modules/validate/validate_ff_engine_node_v1/validator`)

Currently, users must manually locate both files and understand which validator corresponds to which recipe. This story automates the creation of a clean `output/` folder within each run directory that bundles these items together with documentation, making it clear what needs to be copied and where it should go.

---

## Success Criteria

- [x] **Output folder created**: Every pipeline run creates `output/runs/<run>/output/` directory containing the game-ready artifacts.
- [x] **Gamebook copied**: `gamebook.json` is copied from the run root to `output/runs/<run>/output/gamebook.json`.
- [x] **Validator copied**: The recipe-specified validator folder is copied to `output/runs/<run>/output/validator/` (preserving directory structure).
- [x] **Recipe-aware validator selection**: The module determines which validator to copy based on the recipe configuration (from the validation stage's `module` and `validator_dir` params).
- [x] **README added**: `output/runs/<run>/output/README.md` is generated explaining:
  - What these files are
  - That they're meant to be copied into the game engine's input folder
  - How to use the validator
- [x] **Driver integration**: This packaging step runs automatically after the pipeline completes (or can be triggered manually).
- [x] **No breaking changes**: Existing artifact structure remains unchanged; this is purely additive.

---

## Approach

1. **Create packaging module**: Add a new module in `modules/export/` (e.g., `package_game_ready_v1`) that:
   - Takes the run directory and recipe as inputs
   - Identifies the validator module from the recipe's validation stage
   - Copies `gamebook.json` from run root to `output/gamebook.json`
   - Copies the validator folder to `output/validator/`
   - Generates `output/README.md` with usage instructions

2. **Recipe integration**: Add the packaging stage to recipes (after validation stages, depends on `clean_presentation` and validator stage).

3. **Validator detection**: Extract validator module ID and path from recipe's validation stage:
   - Module ID from `module` field (e.g., `validate_ff_engine_node_v1`)
   - Validator directory from `params.validator_dir` if present, else default to `modules/validate/<module_id>/validator`

4. **Documentation generation**: Create a README.md template that explains:
   - What `gamebook.json` is
   - What the `validator/` folder contains
   - Instructions to copy both to the game engine's input folder
   - How to run the validator

---

## Tasks

- [x] Create `modules/export/package_game_ready_v1/` module:
  - [x] `module.yaml` definition
  - [x] `main.py` implementation with:
    - [x] Recipe parsing to find validator stage
    - [x] Validator module/directory detection logic
    - [x] File copying (gamebook.json and validator folder)
    - [x] README.md generation
- [x] Add packaging stage to canonical recipes (`recipe-ff-ai-ocr-gpt51.yaml`, etc.):
  - [x] Stage depends on `clean_presentation` and validator stage
  - [x] Stage outputs to `output/` folder (not a JSONL artifact)
  - [x] Stage is additive only (must not delete or rewrite existing run artifacts)
- [x] Test with a pipeline run (resume from `package_game_ready` is acceptable):
  - [x] Verify `output/runs/<run>/output/` is created
  - [x] Verify `gamebook.json` is copied correctly
  - [x] Verify `validator/` folder is copied correctly (all files preserved)
  - [x] Verify `README.md` content is accurate and helpful
- [x] Add a guard that fails if the validator directory cannot be resolved from the recipe
- [x] Update documentation (AGENTS.md, README.md) to reference the new `output/` folder as the game-ready package location

---

## Work Log

### 2025-01-28 — Story created
- **Result**: Story stubbed for game-ready output packaging feature.
- **Notes**: User requested a clean output folder per run containing gamebook.json and validator, plus README, to simplify copying artifacts into the game engine.
- **Next**: Design module structure and recipe integration approach.

### 20251231-1128 — Story review + repo scan
- **Result**: Success; reviewed existing export modules and searched for packaging patterns.
- **Notes**: No existing `package_game_ready` module; export stage list contains `build_ff_engine_v1` and `clean_html_presentation_v1` only. Will need new export module + recipe wiring.
- **Next**: Draft module design (inputs: run dir + recipe snapshot), then implement `modules/export/package_game_ready_v1/`.

### 20251231-1248 — Implemented packaging module + recipe wiring
- **Result**: Success; added `package_game_ready_v1` module, wired to canonical recipes, and updated docs.
- **Notes**: Module resolves validator from recipe (or snapshot), copies `gamebook.json` + validator folder into `output/`, and generates README. Added guard for missing validator directory; packaging is additive only.
- **Next**: Run a full pipeline to verify `output/runs/<run>/output/` contents and README accuracy.

### 20251231-1253 — Resume-run validation of game-ready package
- **Result**: Success; packaging module ran from `package_game_ready` stage and generated output bundle.
- **Notes**: Ran `python driver.py --recipe configs/recipes/recipe-ff-ai-ocr-gpt51.yaml --run-id ff-ai-ocr-gpt51-pristine-fast-full --allow-run-id-reuse --output-dir output/runs/ff-ai-ocr-gpt51-pristine-fast-full --start-from package_game_ready`. Verified `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/output/` contains `gamebook.json`, `validator/`, and README. README usage text matches validator bundle invocation.
- **Evidence:** `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/output/gamebook.json`, `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/output/validator`, `output/runs/ff-ai-ocr-gpt51-pristine-fast-full/output/README.md`.
- **Next**: Mark story done once desired.
