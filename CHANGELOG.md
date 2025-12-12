## [2025-12-12] - GPU “pit of success” for EasyOCR on Apple Silicon

### Added
- Metal-friendly constraints file (`constraints/metal.txt`) and GPU regression helper (`scripts/regression/check_easyocr_gpu.py`) plus one-shot smoke runner (`scripts/smoke_easyocr_gpu.sh`).
- EasyOCR coverage guard warning when MPS is unavailable, keeping runs explicit about CPU fallback.
- macOS Apple Vision OCR engine (`extract_ocr_apple_v1`) and optional `apple` engine support in the OCR ensemble, with graceful non‑macOS no‑op and error artifacts.

### Changed
- EasyOCR warmup and run defaults now force MPS when present; docs (README.md, AGENTS.md) updated to make `pip install ... -c constraints/metal.txt` the default bootstrap and to include GPU smoke + check commands.
- Story 067 marked done; README/AGENTS include MPS troubleshooting and smoke guidance.
- OCR ensemble now records Apple helper build/run failures in `apple_errors.jsonl` and continues without Apple rather than silently dropping pages.
- Story 052 evaluation checklist updated to reflect completed Apple OCR adoption (see Story 064).
- Story index and open stories consolidated/re‑sequenced: merged Story 036 → 035, Story 051 → 058, refreshed Story 063 checklist, clarified dependencies (066→035, 026→009), and rebuilt Recommended Order around “OCR‑first, FF‑first”.

### Tested
- 5-page EasyOCR-only GPU smoke via `scripts/smoke_easyocr_gpu.sh` (intake only, MPS gpu:true, timing summary).
- Apple Vision OCR smoke on `testdata/tbotb-mini.pdf` page 1; ensemble baseline vs Apple on Deathtrap Dungeon pages 1–40 with artifact inspection.

## [2025-12-10] - FF20 regression suite and quality guards

### Added
- 20-page Fighting Fantasy regression test suite (`tests/test_ff_20_page_regression.py`) with goldens in `testdata/ff-20-pages/`, covering counts, schemas, per-page hashes, fragmentation, column layouts, forbidden OCR tokens, choice counts, and long-line guards.
- Fast local runner `scripts/tests/run_ff20_regression_fast.sh` with a 300s runtime budget.

### Changed
- `validate_artifact.py` now validates `element_core_v1`.
- Removed obsolete portionization integration cases referencing deleted modules; legacy driver/plan tests now pass cleanly alongside the new regression suite.
- Regression drift diagnostics now surface the first differing line on mismatch for easier debugging.

### Tested
- `python -m unittest discover -s tests -p '*test.py' -v`
- `scripts/tests/run_ff20_regression_fast.sh`

## [2025-12-01] - OCR ensemble retries, resolver, and fuzzy headers

### Added
- Pagelines-first recipes with GPT-4V escalation and missing-header resolver (`recipe-pagelines-two-pass.yaml`, `recipe-pagelines-to-gamebook.yaml`, `recipe-ocr-ensemble-gpt4v.yaml`).
- Missing-header resolver adapter with env-overridable params and logging; PageLines schema and validation support.
- Unit tests for fuzzy numeric headers and resolver dry-run; local smoke script to assert only 169–170 are missing.
- Pipeline doc for OCR/resolver env overrides (`docs/pipeline/ocr_ensemble.md`); Story 038 noted in stories index.

### Fixed/Changed
- Numeric header detector now defaults to fused/fuzzy matching; pagelines two-pass recipe rewrites headers after optional escalation.
- Module catalog expanded with OCR ensemble, resolver, and intake modules; Story 037 marked Done with source-integrity notes.

### Tested
- `python driver.py --recipe configs/recipes/recipe-pagelines-two-pass.yaml`
- `PYTHONPATH=. python tests/test_headers_numeric_fuzzy.py`
- `PYTHONPATH=. python tests/test_missing_header_resolver.py`

## [2025-11-27] - Intake dashboard fixes and reuse guidance

### Added
- AGENTS guide now reminds agents to reuse existing working patterns before inventing new solutions.

### Fixed/Changed
- Pipeline visibility Artifacts card now uses the same in-browser viewer as stage buttons for Final JSON and styles both input/final links as buttons; input link now adapts to pdf/images/text inputs instead of showing “Input PDF unknown.”

### Tested
- Manual dashboard reload and artifact open on intake runs (`intake-onward`, `intake-deathtrap`).

## [2025-11-26] - Dashboard stage help, metrics, and artifact links

### Added
- Pipeline visibility dashboard now shows per-stage help tooltips sourced from module notes and recipe descriptions; module notes rewritten verb-first for AI/human clarity.
- Artifacts summary card links directly to input PDF and detected final JSON output; stage ordering follows execution.
- New story 025 (module pruning & registry hygiene) added to track module audit.

### Fixed/Changed
- Load Metrics no longer errors; renders confidence stats with sample preview. Artifacts open with pretty-printed JSON in pane/new-tab, and anchor links render correctly.
- Run dropdown auto-sorts newest-first; dashboard filters to meaningful stage cards.

### Tested
- `python -m pytest tests/test_pipeline_visibility_path.py tests/progress_logger_test.py`
- `python driver.py --recipe /tmp/recipe-ocr-1-5.yaml --mock --instrument`
- `python driver.py --recipe /tmp/recipe-ocr-6-10.yaml --mock --instrument`

## [2025-11-25] - Stage elapsed UX and resumable long runs

### Added
- Pipeline visibility dashboard now shows per-stage elapsed time (live for running, final for done) using progress/event timestamps with `<1s` handling and fallbacks.
- Driver supports `--start-from/--end-at` to resume or bound runs while reusing cached artifacts.

### Fixed/Changed
- Removed remaining `sys.path` bootstraps and unused imports in module mains; all shared helpers imported from `modules.common.*`.
- Resume example and runtime note for long OCR runs added to README; story 020 marked done.

### Tested
- `python driver.py --recipe configs/recipes/recipe-text.yaml --mock --force`
- `python driver.py --recipe configs/recipes/recipe-ocr.yaml --skip-done --start-from portionize_fine --force`

## [2025-11-21] - Pluginized modules and validated pipelines

### Added
- Moved all pipeline modules into self-contained plugin folders under `modules/<stage>/<module_id>/` with `module.yaml` manifests.
- Updated driver to scan plugin folders, merge defaults, and run modules from their encapsulated paths.
- Added stories 016–018 to track DAG/schema, module UX, and enrichment/alt modules.

### Tested
- `python driver.py --recipe configs/recipes/recipe-text.yaml --force` (passes; stamps/validates).
- `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --skip-done` (passes; stamps/validates) — replaces legacy 20-page OCR smoke.

## [2025-11-21] - Legacy cleanup and DAG-style recipes

### Changed
- Removed legacy `run_pipeline.py`, `llm_clean.py`, and `validate.py` now that plugins/driver supersede them.
- Converted core recipes to DAG-style ids/needs/inputs so driver runs without legacy assumptions.
- README now points to modular driver only (legacy quickstart removed).

### Tested
- `python driver.py --recipe configs/recipes/recipe-text.yaml --force`
- `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --force`

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
- `merge_portion_hyp_v1` adapter module plus DAG recipes (`recipe-text-dag.yaml`) using coarse+fine portionize branches. (`recipe-ocr-dag.yaml` deprecated in favor of `recipe-ff-canonical.yaml`.)
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
- `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --skip-done` (passes; OCR pages 1–20 end-to-end).

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
## [2025-11-24] - Image cropper baseline & GT

### Added
- `image_crop_v1` schema and validation mapping; contour-based cropper module `modules/extract/image_crop_cv_v1` with tuned defaults (min_area_ratio=0.005, max_area_ratio=0.99, blur=3, topk=5).
- Sample recipe `configs/recipes/recipe-image-crop.yaml`; helper scripts `scripts/annotate_gt.py` (GT/overlays) and `scripts/build_ft_vision_boxes.py` (vision FT data prep).
- 12-page GT set with overlays in `configs/groundtruth/` and `output/overlays-ft/`; follow-up story doc `story-024-image-cropper-followup.md`.
- Manual validation script `scripts/tests/test_image_crop_cv.sh` and README section documenting how to run/validate the cropper.

### Changed
- Tuned CV detector parameters and documented manual validation results (Micro P=0.75 / R=0.95 / F1=0.84 on current GT); story-008 marked Done.

## [2025-11-24] - Driver snapshots & manifest links

### Added
- Driver now snapshots recipe, resolved plan, registry subset, optional settings/pricing, and instrumentation config into `snapshots/` per run, recording relative paths in `output/run_manifest.jsonl`.
- Integration tests cover snapshot creation, settings relpaths for out-of-repo runs, and pricing/instrumentation snapshot capture.
- README now documents snapshot bundle contents for reproducibility.

### Changed
- Snapshot/manifest side effects are skipped on `--dump-plan`; run directory creation deferred until execution.

### Tested
- `python -m pytest` (all suites; 34 passed, pre-existing pydantic warning).
## [2025-11-24] - Cost/perf benchmarks, presets, and instrumentation UX

### Added
- Bench harness writes per-session `bench_metrics.csv/jsonl` and `metadata.json` under `output/runs/bench-*`; presets in `configs/presets/` (speed text, cost OCR, balanced OCR, quality OCR) with usage examples in README.
- Story 013 completed with benchmark summary tables (OCR vs text, gpt-4.1-mini/4.1/5) and work log updates.
- Dashboard regression test for nested run paths (`tests/test_pipeline_visibility_path.py`); stage cards now always show cost chips (tooltip on zero-cost stages).

### Fixed
- Dashboard run loader honors manifest path for nested run dirs; zero-cost stages now display cost chips with explanatory tooltip.
- LLM modules (clean, portionize coarse/sliding, enrich) emit instrumentation events even when usage tokens missing (zero-fill), preventing missing stage cost data.

### Documentation
- README documents presets, benchmark artifact locations, and cost/perf usage examples.
## [2025-11-26] - Module registry prune (story 025)

### Removed
- Deleted unused modules: portionize_numbered_v1, merge_portion_hyp_v1, image_crop_cv_v1, portionize_page_v1, consensus_spanfill_v1, enrich_struct_v1, build_appdata_v1.
- Removed legacy/demo recipes relying on those modules: recipe-image-crop.yaml, recipe-ocr-enrich-{alt,app}.yaml, recipe-text-enrich-{alt,app}.yaml.

### Planned follow-ups
- Tag remaining experimental modules (section stack, coarse/merge) in manifests and rerun OCR/text smoke recipes.
## [2025-11-28] - FF output refinement paused, AI guardrails noted

### Added
- Issue 0 analysis updated with guidance to avoid overcoding and to use AI ensemble/arbiter patterns for high-stakes steps.
- Work log captured mock-free recomposition run findings (`deathtrap-ff-engine-nomock`) isolating remaining portionization/enrichment failures.

### Changed
- Story 031 status set to Paused pending planned intake/architecture overhaul (potential Unstructured adoption); guardrail implementation deferred until new direction is chosen.

### Tested
- Not run (story paused; analysis/documentation only).

## [2025-11-28] - Fighting Fantasy Engine export complete

### Added
- Official FF Engine validator bundled with Ajv and wrapped as `validate_ff_engine_node_v1`; recipe `recipe-ff-engine.yaml` builds and validates `gamebook.json`.
- Heuristic section typing/front-matter cues in `build_ff_engine_v1` plus provenance stub reporting; stub targets recorded in output metadata.
- Manual smoke script `scripts/smoke-ff-engine.sh` to run mock build+validate locally.

### Fixed/Changed
- Dashboard final-artifact selection now prefers `build_ff_engine` over validate stages and sorts cards by actual timestamps; stage meta display no longer shows placeholder counts.
- `section_enrich_v1` consumes `resolved_portion_v1` to align with the FF pipeline; recipe wires enrich → build → validate.

### Tested
- Mock smoke: `bash scripts/smoke-ff-engine.sh` (passes official validator).
- Full run: `python driver.py --recipe configs/recipes/recipe-ff-engine.yaml --instrument --start-from portionize_fine` (passes official validator; reachability warnings only due to stubbed targets).
## [2025-11-30] - FF cleanup/backfill modules and OCR recovery planning

### Added
- New cleaning module `strip_section_numbers_v1` to remove section/page numbers, gibberish lines, and null `created_at` while preserving paragraphs.
- Backfill adapters `backfill_missing_sections_v2` (digit/fuzzy hits) and `backfill_missing_sections_llm_v1` (gap-based LLM) plus registration in `module_catalog`.
- Story 036 (FF OCR Recovery & Text Repair) and story 037 (FF OCR Ensemble with BetterOCR) to track remaining OCR/header repair work; updated stories index accordingly.
- Recipe `recipe-ff-redesign-v2-clean.yaml` wiring cleanup stage after extraction (experimental baseline).

### Fixed/Changed
- `portionize_ai_extract_v1` now writes enriched portions with `exclude_none=True`, dropping null `created_at` fields.
- AGENTS guide reminds agents to ship new behavior as a separate module and baseline before merging.

### Tested
- Manual runs: backfill + LLM gap backfill + cleanup on `ff-redesign-v2-improved` artifacts; validation shows 382 sections (18 missing) as current best baseline.
## [2025-12-02] - Header/choice loops & pipeline hardening

### Added
- Header and choice loop runner modules to iterate detect→validate→escalate until clean; recipe `recipe-pagelines-repair-choices-r6.yaml` now runs the loops automatically.
- Presence-aware header coverage guard with per-ID debug bundles and hash guard in `missing_header_resolver_v1` to prevent stale OCR.
- BACKGROUND→1 rule in choice escalator and end_game propagation through build/validator; choice coverage emits text snippets for misses.
- New stories: 050 (ending verification), 051 (text-quality loop), 052 (Apple OCR evaluation), 053 (smoke test with mocked APIs).

### Fixed/Changed
- Numeric-only lines preserved in cleaning; header detector more tolerant; portion dedupe keeps best occurrence per section.
- Choice loop output normalized to JSONL for driver stamping; build/validate accept driver compatibility args.
- Story 036 marked Done; deferred text-quality/debug work consolidated into Story 051; smoke test work tracked in Story 053.

### Tested
- `python driver.py --recipe configs/recipes/recipe-pagelines-repair-choices-r6.yaml`
