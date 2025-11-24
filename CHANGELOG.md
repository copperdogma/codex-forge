## [2025-11-21] - Pluginized modules and validated pipelines

### Added
- Moved all pipeline modules into self-contained plugin folders under `modules/<stage>/<module_id>/` with `module.yaml` manifests.
- Updated driver to scan plugin folders, merge defaults, and run modules from their encapsulated paths.
- Added stories 016–018 to track DAG/schema, module UX, and enrichment/alt modules.

### Tested
- `python driver.py --recipe configs/recipes/recipe-text.yaml --force` (passes; stamps/validates).
- `python driver.py --recipe configs/recipes/recipe-ocr-1-20.yaml --skip-done` (passes; stamps/validates).

## [2025-11-21] - Legacy cleanup and DAG-style recipes

### Changed
- Removed legacy `run_pipeline.py`, `llm_clean.py`, and `validate.py` now that plugins/driver supersede them.
- Converted core recipes to DAG-style ids/needs/inputs so driver runs without legacy assumptions.
- README now points to modular driver only (legacy quickstart removed).

### Tested
- `python driver.py --recipe configs/recipes/recipe-text.yaml --force`
- `python driver.py --recipe configs/recipes/recipe-ocr-1-20.yaml --force`

## [2025-11-21] - Added modular pipeline story

### Added
- New story 015 document outlining modular pipeline and registry plan.
- Indexed story 015 in `docs/stories.md` to track status.
- Scaffolded `modules/registry.yaml`, sample recipes under `configs/recipes/`, `extract_text.py` stub, and `validate_artifact.py` validator CLI.
- Added pipeline driver with stamping/validation hooks and resume/skip toggles; added schemas for page/clean/resolved/enriched artifacts.
- Reorganized modules into per-module plugin folders with manifests; driver now scans `modules/` for entrypoints.
## [2025-11-22] - DAG driver, adapter merge, and CI tests

### Added
- DAG-capable driver plan/validation with schema-aware resume checks and adapter stage support.
- `merge_portion_hyp_v1` adapter module plus DAG recipes (`recipe-ocr-dag.yaml`, `recipe-text-dag.yaml`) using coarse+fine portionize branches.
- GitHub Actions workflow `tests.yml` running driver unit tests; README badge and DAG usage notes.

### Fixed/Changed
- Portionize fine params cleaned up (removed unsupported `min_conf`), OCR recipe simplified (no `images` flag, end page capped).
- Resume skips now verify artifact schema_version; multi-input consensus uses deduped merge helper.

## [2025-11-22] - Pipeline visibility dashboard & progress logging

### Added
- Progress event schema validation and append-only logger with tests; driver/module commands now inject `--state-file/--progress-file/--run-id` by default.
- Dashboard fixture run (`output/runs/dashboard-fixture`) plus README note on serving `docs/pipeline-visibility.html` via `python -m http.server`.
- New dashboard UI features: run selector, auto-refresh, stage cards, event timeline, artifact pane/new-tab viewer, metrics loader.

### Changed
- Story 019 marked complete; follow-on UI polish tracked in new Story 021 (highlighting/pane sizing).
- `docs/stories.md` updated with Story 021; story log entries added for work performed.

### Tested
- `python -m pytest tests/progress_logger_test.py`
- `python -m pytest tests/driver_plan_test.py`

### Tested
- `python -m unittest discover -s tests -p 'driver_*test.py'` (passes; 9 tests).
- `python driver.py --recipe configs/recipes/recipe-text-dag.yaml --force` (passes; artifacts stamped/validated).
- `python driver.py --recipe configs/recipes/recipe-ocr-dag.yaml --skip-done` (passes; OCR pages 1–20 end-to-end).

## [2025-11-22] - Shared common package and module import cleanup

### Added
- Introduced `modules/common` package consolidating shared helpers (utils, ocr) with explicit public surface.
- Driver now executes module entrypoints via `python -m modules.<...>.main`, enabling package-relative imports without sys.path tweaks.

### Fixed/Changed
- All module mains import from `modules.common.*` and no longer mutate `sys.path`.
- Driver skips None-valued params when building CLI flags to avoid invalid arguments.
- Documentation updated (AGENTS, README, story log) to reflect common package usage.

### Tested
- `python -m compileall modules/common driver.py validate_artifact.py`
- `python driver.py --recipe configs/recipes/recipe-text.yaml --mock --force`
- `python driver.py --recipe configs/recipes/recipe-ocr.yaml --mock --force`

## [2025-11-22] - Param schemas and stage output overrides

### Added
- JSON-Schema-lite `param_schema` support in `driver.py` with fail-fast validation (type/enum/range/pattern, required/unknown detection, schema defaults).
- Stage-level `out:` override for artifact filenames (higher precedence than recipe `outputs:`) wired through resume/skip-done.
- `param_schema` definitions added to key modules (OCR/text extract, clean, portionize, adapter merge, consensus vote).
- `param_schema` placeholders added for dedupe/normalize/resolve/build to block typos and allow future tunables.
- Added doc snippets for `out:` usage and a multi-stage custom-output smoke test verifying downstream propagation.

### Tested
- `python -m pytest tests/driver_plan_test.py tests/driver_integration_test.py` (13 total; includes param validation errors, out precedence, resume honors custom out, multi-stage custom outputs).

## [2025-11-22] - Enrichment stage + alternate modules

### Added
- Enrichment module `enrich_struct_v1` producing `enriched_portion_v1`; low-cost deterministic portionizer `portionize_page_v1`; greedy gap-fill consensus `consensus_spanfill_v1`.
- New recipes showcasing swapability and enrichment: `configs/recipes/recipe-text-enrich-alt.yaml` (text ingest) and `configs/recipes/recipe-ocr-enrich-alt.yaml` (OCR, pages 1–2).
- Driver enrich stage wiring (pages/portions inputs) and `cleanup_artifact` helper to remove stale outputs on `--force`.

### Fixed
- `stamp_artifact` now backfills `module_id`, `run_id`, and `created_at` when missing.

### Tested
- `python driver.py --recipe configs/recipes/recipe-text-enrich-alt.yaml --registry modules` (passes; enriched output with choices).
- `python driver.py --recipe configs/recipes/recipe-ocr-enrich-alt.yaml --registry modules` (passes; intro pages enriched with images).
- `python -m pytest tests/driver_plan_test.py` (11 tests, includes stamp backfill and cleanup helpers; existing pydantic warning).
## [2025-11-23] - Section target guard, portionizer fixes, doc cleanup

### Added
- Consolidated adapter `section_target_guard_v1` (maps targets, backfills, coverage report/exit) with module manifest and unit tests.
- Story 099 to track removal of the dev-only backcompat disclaimer when production-ready.

### Changed
- Updated section recipes to use the guard adapter and emit coverage reports; legacy map/backfill path marked obsolete in docs.
- Portionizer `portionize_sections_v1` now captures multi-number headers/inline ids and dedupes per page to reduce duplicate portions while keeping coverage.
- AGENTS and story logs refreshed to reflect guard as the canonical path; legacy mentions updated.

### Tested
- `python driver.py --recipe configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml --force` (0 missing targets; guard passes, 400 sections/384 targets).
- `python -m pytest` (all suites; existing pydantic deprecation warning only).

## [2025-11-23] - Section coverage pipeline and validator guard

### Added
- No-consensus section recipe `configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml` (full book) plus chunked variants; full run produced `portions_enriched_backfill.jsonl` with zero missing targets.
- Validation guard module `modules/validate/assert_section_targets_v1.py` and unit test `tests/assert_section_targets_test.py` covering pass/fail paths.
- Story 023 to consolidate section target adapters; Story 006 marked Done in story index.
- Story 007 marked Done (turn-to validation delivered via section target guard/reporting tools).

### Changed
- Pruned obsolete/failed recipe variants to reduce config clutter.
- AGENTS safe command updated with section target validation usage.
- Story index now marks pipeline visibility (019) and enrichment (006) as Done.

### Tested
- `python driver.py --recipe configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml --registry modules --force` (full run, 0 missing targets).
- `pytest tests/assert_section_targets_test.py`

## [2025-11-23] - Instrumentation & dashboard surfacing

### Added
- Instrumentation schemas (`instrumentation_call_v1`, `_stage_v1`, `_run_v1`) and validation hook in `validate_artifact.py`.
- Driver `--instrument`/`--price-table` flags with per-stage wall/CPU timing, sink-based LLM usage aggregation, cost estimation via `configs/pricing.default.yaml`, and reports (`instrumentation.json` + markdown).
- Module helper `log_llm_usage` for modules to append per-call token/model data to the driver-provided sink.
- Dashboard now shows instrumentation summaries (run totals, top models, per-stage cost/time chips) and newest-first run ordering/auto-select logic.

### Changed
- Story 022 marked Done; README updated with instrumentation enablement notes.

### Tested
- `python -m pytest -q tests/test_instrumentation_schema.py`
- `python driver.py --recipe configs/recipes/recipe-text.yaml --instrument --mock --force`

## [2025-11-24] - Coarse+fine merge, continuation propagation, and smoke/regression

### Added
- Coarse portionizer module `portionize_coarse_v1` and merge adapter `merge_coarse_fine_v1` with continuation-aware heuristics and duplicate-span collapse.
- Smoke recipe `configs/recipes/recipe-ocr-coarse-fine-smoke.yaml` for 10-page coarse+fine validation.
- Regression helper `scripts/regression/check_continuation_propagation.py` to ensure continuation metadata survives to locked/resolved outputs.
- Unit tests for merge heuristics `tests/test_merge_coarse_fine_v1.py`.

### Changed
- DAG recipes now use the new coarse/merge modules; uncovered threshold tightened to 0.5 to reduce noise.
- Schemas plus consensus/resolve/build stages now preserve `continuation_of`/`continuation_confidence` through final artifacts.
- README and story notes updated with merge rules, smoke recipe, and regression command.
