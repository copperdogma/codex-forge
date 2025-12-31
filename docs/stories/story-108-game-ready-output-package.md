# Story: Game-Ready Output Package

**Status**: To Do  
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

- [ ] **Output folder created**: Every pipeline run creates `output/runs/<run>/output/` directory containing the game-ready artifacts.
- [ ] **Gamebook copied**: `gamebook.json` is copied from the run root to `output/runs/<run>/output/gamebook.json`.
- [ ] **Validator copied**: The recipe-specified validator folder is copied to `output/runs/<run>/output/validator/` (preserving directory structure).
- [ ] **Recipe-aware validator selection**: The module determines which validator to copy based on the recipe configuration (from the validation stage's `module` and `validator_dir` params).
- [ ] **README added**: `output/runs/<run>/output/README.md` is generated explaining:
  - What these files are
  - That they're meant to be copied into the game engine's input folder
  - How to use the validator
- [ ] **Driver integration**: This packaging step runs automatically after the pipeline completes (or can be triggered manually).
- [ ] **No breaking changes**: Existing artifact structure remains unchanged; this is purely additive.

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

- [ ] Create `modules/export/package_game_ready_v1/` module:
  - [ ] `module.yaml` definition
  - [ ] `main.py` implementation with:
    - [ ] Recipe parsing to find validator stage
    - [ ] Validator module/directory detection logic
    - [ ] File copying (gamebook.json and validator folder)
    - [ ] README.md generation
- [ ] Add packaging stage to canonical recipes (`recipe-ff-ai-ocr-gpt51.yaml`, etc.):
  - [ ] Stage depends on `clean_presentation` and validator stage
  - [ ] Stage outputs to `output/` folder (not a JSONL artifact)
- [ ] Test with a full pipeline run:
  - [ ] Verify `output/runs/<run>/output/` is created
  - [ ] Verify `gamebook.json` is copied correctly
  - [ ] Verify `validator/` folder is copied correctly (all files preserved)
  - [ ] Verify `README.md` content is accurate and helpful
- [ ] Update documentation (AGENTS.md, README.md) to reference the new `output/` folder as the game-ready package location

---

## Work Log

### 2025-01-28 — Story created
- **Result**: Story stubbed for game-ready output packaging feature.
- **Notes**: User requested a clean output folder per run containing gamebook.json and validator, plus README, to simplify copying artifacts into the game engine.
- **Next**: Design module structure and recipe integration approach.
