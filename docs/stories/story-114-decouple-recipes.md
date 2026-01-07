# Story 114: Decouple Execution Context from Recipes

## Problem Statement
Currently, `recipe.yaml` files act as "wrappers" that mix generic processing logic with specific execution details like `input` PDF paths, `run_id`, and `output_dir`. This leads to:
1.  **Redundancy**: Creating a new run often feels like creating a duplicate recipe just to change the input file.
2.  **Confusion**: Users have to check both the recipe and the command line to know where outputs effectively go.
3.  **Lack of Reusability**: You cannot easily apply the "standard FF recipe" to 5 different books without editing the recipe file itself or relying heavily on CLI overrides.

## Goal
Decouple the "HOW" (Recipe) from the "WHAT" and "WHERE" (Run Configuration).
- **Recipes** should be pure logic templates (e.g., "Fighting Fantasy Logic v1").
- **Run Configs** (`config.yaml`) should specify the execution context: Input PDF, Run ID, Output Directory.

## Implementation Plan

### 1. Refactor `driver.py` Logic
- [x] Update `driver.main()` to strictly enforce the presence of `input_pdf`, `run_id`, and `output_dir` from the Run Config (or CLI args).
- [x] Use `RunConfig` as the primary source of truth for these values, falling back to the recipe ONLY for backward compatibility (with a deprecation warning if possible/desired), or removing support entirely if we want a clean break.
- [x] Logic: `Effective Input = RunConfig.input_pdf` (Must exist).

### 2. Update `run_manager.py`
- [x] Modify `create-run` to:
    - [x] Always populate `input_pdf` in the generated `config.yaml`.
    - [x] Always populate `run_id` and `output_dir`.
    - [x] Generate a config that references a "pure" recipe by default.

### 3. Purify Canonical Recipes
- [x] Refactor `recipe-ff-smoke.yaml` (and eventually others) to remove:
    - [x] `run_id`
    - [x] `output_dir`
    - [x] `input` block
- [x] This makes them true reusable templates.

### 4. Documentation
- [x] Update `README.md` to reflect the new philosophy: "Recipes are logic, Configs are instances".

## Work Log
- **2026-01-06**: Implemented `driver.py` logic to enforce input/output from `RunConfig`. Refactored `recipe-ff-smoke.yaml` to remove execution context. Validated with `pure-smoke-test` run. Updated `run_manager.py` to support explicit context generation.

## Status
Done
