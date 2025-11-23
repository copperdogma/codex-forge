# Story: Consolidate section target adapters

**Status**: To Do

---

## Acceptance Criteria
- Replace the current map_targets_v1 + backfill_missing_sections_v1 chain with a single adapter that maps targets, backfills missing sections, and emits a coverage summary/exit code.
- Update the no-consensus section recipe to use the consolidated adapter and keep zero-missing-target behavior.
- Add or update tests to cover pass/fail paths of the consolidated adapter.
- Document the new adapter and usage (command example) in AGENTS.md and the relevant story logs.

## Tasks
- [x] Design the consolidated adapter contract (inputs/outputs, flags such as allow-missing).
- [x] Implement the adapter (map + backfill + coverage report) and module.yaml.
- [x] Update recipes (at least `configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml`) to use the new adapter.
- [x] Update tests (reuse or extend `tests/assert_section_targets_test.py`) to cover both success and failure cases.
- [x] Refresh docs (AGENTS safe command + story log) with the new adapter usage.
- [x] Define coverage summary fields + exit code/`--allow-missing` semantics for the consolidated adapter.
- [x] Decide how to sunset or retain `map_targets_v1` and `backfill_missing_sections_v1` (deprecation note, recipe outputs naming).

## Notes
- Keep portionize_sections_v1 and section_enrich_v1 separate to preserve swap flexibility across book types; consolidation targets only the tiny adapter tail.

## Proposed Consolidated Adapter Contract (draft)
- **Name:** `section_target_guard_v1` (stage: adapter); replaces `map_targets_v1` + `backfill_missing_sections_v1` entirely (no backwards-compat shims).
- **CLI:** `python modules/adapter/section_target_guard_v1.py --inputs portions_enriched.jsonl [extra_enriched.jsonl ...] --out portions_enriched_guard.jsonl --report section_target_report.json [--allow-missing]`
- **Behavior:** (1) Build `known_ids` set from all inputs (`portion_id` or `section_id`, stringified) and gather all `targets`/`choices[].target`. (2) For rows in first input only, add `target_hits` (targets in known_ids) and `target_misses` (not in known_ids). (3) Append backfill stubs for each missing target with minimal `enriched_portion_v1` stub (module_id set to guard adapter, zeroed pages, empty text). (4) Emit coverage report JSON with counts and sample, and write to `--report`.
- **Coverage report fields:** `section_count`, `targets_count`, `targets_present`, `missing_count`, `missing_sample` (<=50), `hit_rate` (targets_present/targets_count), `stubbed_count` (=missing_count), `inputs` (paths), `out_path`, `allow_missing`.
- **Exit semantics:** Default exit 1 if `missing_count > 0`; `--allow-missing` forces exit 0 while still writing report/backfill. Print report to stdout for easy CI visibility.
- **Outputs / recipes:** Replace `map_targets` and `backfill` outputs with a single `portions_enriched_guard.jsonl`; recipes keep `section_target_report.json` path for the report. Drop `assert_section_targets_v1` stage once guard is in place (optional to keep during transition, but not required).

## Work Log
### 20251123-1116 — Story intake and baseline review
- **Result:** Completed story intake; no code changes yet.
- **Notes:** Read current `map_targets_v1` (`modules/adapter/map_targets_v1/main.py`), `backfill_missing_sections_v1` (`modules/adapter/backfill_missing_sections_v1.py`), validation step `modules/validate/assert_section_targets_v1.py`, and the no-consensus recipe `configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml`. Existing flow maps targets, then backfills, then validates with allow-missing flag. New adapter needs to merge map+backfill and emit coverage summary/exit code.
- **Next:** Draft consolidated adapter contract (inputs, outputs, coverage report shape, failure rules) and decide deprecation/migration for old adapters.
### 20251123-1118 — Drafted adapter contract and migration approach
- **Result:** Added proposed contract to story with CLI, behaviors, coverage report fields, and exit semantics; clarified recipe output naming and optional removal of standalone validator.
- **Notes:** Name proposed `section_target_guard_v1`; keeps old adapters for reproducibility but deprecates in docs once recipes migrate. Report includes hit_rate and stubbed count; default fail on missing unless `--allow-missing`.
- **Next:** Decide deprecation note placement (AGENTS/CHANGELOG), align recipe update plan, and start implementation in new adapter module + module.yaml.
### 20251123-1120 — Removed backward-compatibility plan per guidance
- **Result:** Updated contract to drop backward-compat/deprecation shims; new adapter fully replaces map/backfill chain.
- **Notes:** Recipes will switch directly to `section_target_guard_v1`; `assert_section_targets_v1` can be removed once guard is in place.
- **Next:** Proceed to implementation and recipe updates without retaining legacy adapters in new flows.
### 20251123-1154 — Implemented guard adapter, recipes, tests, docs
- **Result:** Added `modules/adapter/section_target_guard_v1` (map + backfill + coverage/exit), module.yaml, and tests (`tests/section_target_guard_test.py`). Updated noconsensus recipes to use guard adapter and emit reports; AGENTS command updated. Tests run: `python -m pytest tests/section_target_guard_test.py tests/assert_section_targets_test.py` (pass).
- **Notes:** Guard writes mapped rows + stubbed missing targets and coverage JSON; fails on missing unless `--allow-missing`. Recipes now write reports under run output dirs.
- **Next:** Consider removing/archiving old adapters in docs once pipeline stable; optionally add integration run sample artifact for story.
### 20251123-1205 — Full pipeline run + evaluation
- **Result:** Ran `python driver.py --recipe configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml --force`. Guard exited 1 (expected) with 7 missing targets; coverage report stored at `output/runs/ocr-enrich-sections-noconsensus/section_target_report.json`. Artifact `portions_enriched_guard.jsonl` contains 494 rows (487 original + 7 stubs). Full test suite passes (`python -m pytest`).
- **Notes:** Missing target sample: 131, 132, 164, 166, 169, 170, 340. Hit rate 0.982. Need follow-up to trace missing sections or allow-missing for downstream consumers.
- **Next:** Investigate missing target IDs in enriched/portionized data; once satisfied, update docs to remove legacy map/backfill references and optionally keep guard report example.
### 20251123-1317 — Portionizer fix + successful run
- **Result:** Updated `portionize_sections_v1` to capture multi-number headers and inline-only ids as sections. Re-ran `python driver.py --recipe configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml --force`; guard now passes with zero missing targets. Coverage report: section_count 400, targets_count 385, missing_count 0, hit_rate 1.0. Outputs stamped; guard artifact has 1092 rows.
- **Notes:** Portionizer changes: extract extra ids from header lines (e.g., “130 131-132”) and add inline-referenced ids when not anchored. This added sections to cover previously missing 169/170, etc.
- **Next:** Clean up docs mentioning legacy map/backfill; consider trimming portionization duplicates if needed.
### 20251123-1405 — Portionizer dedupe & doc cleanup
- **Result:** Added per-page dedupe in `portionize_sections_v1` to drop duplicate ids while retaining header/inline coverage. Re-ran full recipe: guard still passes (section_count 400, targets_count 384, missing_count 0) with reduced portions (1057). Updated AGENTS.md to note legacy map/backfill adapters are obsolete; prefer `section_target_guard_v1`.
- **Notes:** Tests re-run (`python -m pytest`) all pass. Older stories now reference guard as the preferred path; historical mentions remain for context.
- **Next:** None; doc cleanup complete.
