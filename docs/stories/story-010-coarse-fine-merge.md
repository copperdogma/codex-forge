# Story: Coarse+fine portionizer & continuation merge

**Status**: Done

---

## Acceptance Criteria
- Add coarse large-window pass merged with fine
- Continuation-based merge step for long spans

## Tasks
- [x] Implement coarse pass (large-window portionizer)
  - [x] Add coarse module that emits portion hypotheses over wide page windows
  - [x] Wire coarse stage into a DAG recipe with configurable window size + stride
  - [x] Validate coarse output with `validate_artifact.py --schema portion_hyp_v1` on sample run
- [x] Merge hypotheses (coarse + fine)
  - [x] Document merge rules (overlap resolution, confidence, tie-breaks)
  - [x] Implement merge stage that produces consolidated locked portions
  - [x] Add integration test/run on `input/06 deathtrap dungeon.pdf` to confirm merged coverage
- [x] Continuation merge logic
  - [x] Define continuation detection + confidence propagation across spans
  - [x] Implement continuation handling in merge stage output fields
  - [x] Add regression check for multi-page continuations (schema/validator update if needed)
- [x] Documentation & recipes
  - [x] Update story notes/README with usage and expected artifacts
  - [x] Add/update `configs/recipes` entries and smoke recipe covering coarse+fine merge
  - [x] Add regression helper script

## Notes
- Merge rules (current): fine-first; coarse spans added when ≥50% of their pages are uncovered by fine; duplicate spans collapsed keeping highest confidence and unioned sources; continuation heuristic uses gap ≤1 and title/type similarity; continuation fields preserved through consensus, resolve, and build.
- Smoke recipe: `configs/recipes/recipe-ocr-coarse-fine-smoke.yaml` runs first 10 pages with coarse+fine+merge.
- Regression: `python scripts/regression/check_continuation_propagation.py --hypotheses <adapter_out> --locked <locked> --resolved <resolved>`

## Work Log
- Pending
### 20251123-1358 — Story audit and task expansion
- **Result:** Success; no coarse/fine merge implementation found.
- **Notes:** Searched `modules/portionize/*`; existing modules are page, numbered, sections, sliding; no coarse-pass or merge logic; continuation fields present but unused in merge.
- **Next:** Implement coarse pass module, merge stage, and continuation handling per expanded tasks.
### 20251123-1402 — Added coarse module and merge adapter draft
- **Result:** Success; new `portionize_coarse_v1` module with large-window defaults and updated prompt; new `merge_coarse_fine_v1` adapter merging fine+coarse with uncovered threshold and continuation detection.
- **Notes:** Updated DAG recipes (`configs/recipes/recipe-ocr-dag.yaml`, `configs/recipes/recipe-text-dag.yaml`) to use new modules; merge attaches continuation_of when spans touch/overlap within gap and titles align. No validation run yet.
- **Next:** Run sample recipe to validate outputs against `portion_hyp_v1`, tune thresholds, and document merge rules in story/README.
### 20251123-2038 — Ran text DAG recipe with coarse/fine merge
- **Result:** Success; `python driver.py --recipe configs/recipes/recipe-text-dag.yaml --force` completed end-to-end. Coarse, fine, and merged outputs each validate with `portion_hyp_v1`.
- **Notes:** Merge adapter now accepts driver `--inputs`; handles underscore/dash params. Sample run produced 1 portion; continuation heuristic exercised but simple input limited coverage. Validated `window_hypotheses_coarse.jsonl` and `adapter_out.jsonl` via `validate_artifact.py`.
- **Next:** Run full PDF recipe (`recipe-ocr-dag.yaml`) to observe behavior on multi-page spans; document merge rules and add regression check for multi-page continuations.
### 20251123-2055 — Ran full OCR DAG on deathtrap PDF
- **Result:** Success; `python driver.py --recipe configs/recipes/recipe-ocr-dag.yaml --force` completed. Outputs: coarse 18 rows, fine 85 rows, merged 83 rows; locked/normalized/resolved 14 portions. Validated coarse and merged hypotheses with `validate_artifact.py --schema portion_hyp_v1`.
- **Notes:** Continuation heuristic ran; need to inspect portions for long-span continuity and tune uncovered threshold if necessary. Runtime ~7.8 minutes (clean + portionize dominated).
- **Next:** Document merge rules/tie-breaks, analyze merged coverage vs fine-only, and add regression for continuations.
### 20251123-2105 — Inspection of merged artifacts (deathtrap run)
- **Result:** Success; reviewed `adapter_out.jsonl` (83 rows, 36 with continuation_of) and resolved outputs.
- **Notes:** Coverage complete for pages 1–20. Merge kept many duplicate hypotheses (e.g., multiple page 4 entries; repeated S14-17/S12-13) which consensus trimmed to 14 locked portions. Continuation links present in hypotheses but dropped after consensus/resolve (schema lacks continuation). Locked normalized portions show clean titles/types but no continuation metadata.
- **Next:** Document merge rules and clarify how/if continuation should survive locking; consider dedup before consensus to reduce noise; add regression focusing on continuation propagation/metrics.
### 20251123-2135 — Continuation propagation + dedupe pass
- **Result:** Success; schemas updated to carry continuation fields through locked/resolved/enriched; consensus now preserves continuation from highest-confidence span; resolve/build retain fields. Merge adapter now dedupes duplicate spans and tightens uncovered threshold (0.5 default), reducing merged hypotheses (83→76 in deathtrap run). Driver rerun succeeded; artifacts validate.
- **Notes:** Latest run (deathtrap) produced coarse 13, fine 81, merged 76; locked 18, resolved 16. Continuation links now present in locked/resolved (3 spans). Validation OK for portion_hyp_v1/locked_portion_v1/resolved_portion_v1.
- **Next:** Document merge rules, add regression for continuation propagation/coverage, and decide if further threshold tuning is needed.
### 20251123-2155 — Added continuation regression check + documented merge rules
- **Result:** Success; added `scripts/regression/check_continuation_propagation.py` to ensure continuation metadata survives to locked/resolved. Script passes on deathtrap run. Documented merge rules/heuristics in Notes.
- **Notes:** Merge rules (current): fine-first; coarse spans added when ≥50% of their pages are uncovered by fine; duplicate spans collapsed keeping highest confidence and unioned sources; continuation heuristic uses gap≤1 and title/type similarity. Continuation fields preserved through consensus, resolve, build.
- **Next:** Consider adding a lightweight smoke recipe entry and optional stricter uncovered threshold for rule-heavy books.
### 20251123-2115 — Smoke recipe added and docs updated
- **Result:** Success; added `configs/recipes/recipe-ocr-coarse-fine-smoke.yaml` (10-page subset) for quick manual validation; updated Notes with merge rules, smoke recipe, and regression command.
- **Notes:** No CI hook (per guidance), but smoke recipe + regression script give a fast manual check.
- **Next:** Use smoke recipe before tuning thresholds; optionally add a README snippet when stabilizing.
### 20251123-2120 — Merge unit tests added
- **Result:** Success; added `tests/test_merge_coarse_fine_v1.py` covering uncovered threshold, duplicate-span collapse, and continuation attachment.
- **Notes:** Tests are lightweight and manual (no CI); improve confidence for merge heuristics.
- **Next:** Run tests manually when adjusting merge heuristics; consider adding more cases for continuation gap >1 if needed.
