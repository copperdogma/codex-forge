# Story 115: Configuration Cleanup and Standardization

## Problem Statement
The `configs/` directory is cluttered with legacy recipes, outdated settings files, and confusing naming conventions. This makes it difficult for new users to know which recipe to use. Additionally, the canonical recipe (`recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`) still contains execution context that should be moved to the run configuration.

## Goal
Simplify the configuration landscape to just two primary recipes:
1.  `recipe-ff.yaml`: The production-ready Fighting Fantasy pipeline.
2.  `recipe-ff-smoke.yaml`: The testing pipeline.

## Implementation Plan

### 1. Spring Cleaning
- [x] **Move** all non-canonical recipes to `configs/recipes/legacy/`.
- [x] **Delete** obsolete `presets/*.yaml` and `settings/*.yaml` files that are no longer used.
- [x] **Keep** `configs/groundtruth/` and `configs/pricing.default.yaml`.

### 2. Rename and Purify Canonical Recipe
- [x] **Rename** `configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml` to `configs/recipes/recipe-ff.yaml`.
- [x] **Purify** `recipe-ff.yaml`: Remove `run_id`, `input`, and `output_dir`.

### 3. Update References
- [x] Update `run_manager.py` to use `recipe-ff.yaml` as the default potential recipe (or at least valid in checks).
- [x] Update `README.md` to reference the new clean `recipe-ff.yaml`.

## Work Log
- **2026-01-06**: Cleaned up `configs/` directory. Moved legacy recipes to `legacy/`. Renamed `recipe-ff-ai-ocr-gpt51-pristine-fast-with-images.yaml` to `recipe-ff.yaml` and purified it. Updated `run_manager.py` to use new default. Verified with dry run.

## Status
Done
