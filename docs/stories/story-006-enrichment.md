# Story: Enrichment pass (choices/combat/items/endings)

**Status**: Done

---

## Acceptance Criteria
- Extract structured gameplay fields per portion
- Emit portions_enriched.jsonl
- Optionally build app-ready data.json

## Tasks
- [x] Design enriched_portion schema covering choices/combat/items/endings and add it to `schemas.py`
- [x] Add validator wiring for the new schema in `validate_artifact.py` (CLI flag + tests)
- [x] Draft enrichment LLM prompt templates and module contract (inputs/outputs, error handling)
- [x] Implement enrichment module (`modules/enrichment/...`) that produces `portions_enriched.jsonl`
- [x] Integrate module into a recipe (e.g., new DAG) and update sample settings if needed
- [x] Run a sample against a small input slice and validate artifact with the new schema
- [x] (Optional) Generate `data.json` for app-ready usage and document output location
- [x] Integrate section-based pipeline (portionize_sections_v1 → section_enrich_v1 → map_targets_v1 → backfill_missing_sections_v1) into a reusable recipe with no-consensus merging.
- [x] Add validation/CI guard that fails when section targets are missing or unmapped; document the command in this story and AGENTS.md.

## Notes
- 

## Work Log
### 20251121-2254 — Reviewed story and expanded task checklist
- **Result:** Success; clarified tasks and added integration/validation steps.
- **Notes:** Next steps hinge on defining `enriched_portion` schema fields and validator expectations.
- **Next:** Sketch schema and validator changes before coding the enrichment module.
### 20251121-2255 — Verified enrichment pipeline and validation
- **Result:** Success; ran `python driver.py --recipe configs/recipes/recipe-text-enrich-alt.yaml --registry modules --force` producing `output/runs/text-enrich-alt/portions_enriched.jsonl` (1 row).
- **Notes:** Validation via `python validate_artifact.py --schema enriched_portion_v1 --file output/runs/text-enrich-alt/portions_enriched.jsonl` passed. Sample entry includes choice target "2" with text "choose left". Schema/module already present (`schemas.py`, `modules/enrich/enrich_struct_v1`); recipes wired (`configs/recipes/recipe-text-enrich-alt.yaml`).
- **Next:** Optional app `data.json` merge not started; consider adding recipe stage if needed.
### 20251121-2302 — Added app export stage producing data.json
- **Result:** Success; added export module `modules/build/build_appdata_v1` and recipe `configs/recipes/recipe-text-enrich-app.yaml` to build `data.json` from enriched portions. Driver updated to support `export/app` stages. Run: `python driver.py --recipe configs/recipes/recipe-text-enrich-app.yaml --registry modules --force` → `output/runs/text-enrich-app/data.json` (1 node) with metadata and choices.
- **Notes:** Module accepts `--input/--enriched` and embeds run metadata; output location controlled by recipe `out`. Schema tag `app_data_v1`.
- **Next:** Consider expanding app schema (e.g., endings flags, graph validation) once real book enriched outputs are available.
### 20251121-2304 — Ran OCR path + enhanced app export fields
- **Result:** Created OCR recipe `configs/recipes/recipe-ocr-enrich-app.yaml` and ran `python driver.py --recipe configs/recipes/recipe-ocr-enrich-app.yaml --registry modules --force` → `output/runs/ocr-enrich-app/data.json` (2 nodes). Export now adds derived `targets` and `is_terminal` flags per portion.
- **Notes:** OCR slice limited to first 2 pages for cost; outputs include image paths, no choices detected yet. `build_appdata_v1` now derives `targets` list and `is_terminal` boolean for graph sanity checks.
- **Next:** Expand to more pages for richer enrichment; add validation utility for app_data (graph reachability/targets present) when data grows.
### 20251121-2306 — Added app_data validator and reran exports
- **Result:** Added `modules/validate/validate_app_data_v1.py` (checks ids, target existence, terminal flags; optional `--allow-unresolved-targets`). Validation: OCR app data passes clean; text app data passes with warnings due to target "2" missing node (expected because sample has single portion).
- **Notes:** Run examples: `python modules/validate/validate_app_data_v1.py --input output/runs/ocr-enrich-app/data.json --enriched output/runs/ocr-enrich-app/portions_enriched.jsonl` and same with `--allow-unresolved-targets` for text run.
- **Next:** Increase OCR slice beyond 2 pages to capture real choices and revalidate; consider making missing-targets non-optional once graph is complete.
### 20251121-2308 — Expanded OCR run to 10 pages and revalidated
- **Result:** Updated `recipe-ocr-enrich-app.yaml` (end=10) and reran `python driver.py --recipe configs/recipes/recipe-ocr-enrich-app.yaml --registry modules --force` → outputs now cover 10 pages (10 enriched nodes) with validation clean (`validate_app_data_v1`).
- **Notes:** Still no choices within first 10 pages (all terminal). Sample enriched rows confirmed via `head` on `portions_enriched.jsonl`. Runtime ~90s with LLM clean/enrich.
- **Next:** Push range deeper (post-branching pages) when ready; consider auto-detecting target coverage before treating missing targets as errors.
### 20251121-2318 — Added reachability checks; attempted deeper OCR slice
- **Result:** Validator now supports `--start-id` + reachability; missing targets/unreachable nodes can be warnings (`--allow-unresolved-targets`). Attempts to run OCR to 30/15/40 pages hit CLI timeout; kept recipe at end=10 for now (stable run). Validation on 10-page export remains clean.
- **Notes:** Longer OCR slices exceed current 120s command budget; need higher timeout or batch approach to capture branching content.
- **Next:** Re-run with extended timeout or page batching to reach branching sections; then enforce strict target presence/reachability.
### 20251121-2320 — Extended OCR slice to 20 pages with validation
- **Result:** Bumped `recipe-ocr-enrich-app.yaml` end=20 and reran with higher timeout (300s). Outputs: 20 enriched nodes in `output/runs/ocr-enrich-app/data.json`. Validator (`--start-id G001 --allow-unresolved-targets`) shows warnings: unreachable nodes (intro pages not linked) and missing target nodes because branching targets point beyond page 20 (e.g., 147, 310).
- **Notes:** We now capture early branching paragraphs (G016+ with turn-to targets), confirming enrichment emits targets; unresolved references expected until more pages processed.
- **Next:** Run deeper slice (or chunked batches) to include target destinations, then tighten validator (no unresolved targets, reachable graph).
### 20251121-2338 — Chunked run for pages 21-40
- **Result:** Added `configs/recipes/recipe-ocr-enrich-app-21-40.yaml` (start=21,end=40) and ran with 300s timeout → `output/runs/ocr-enrich-app-21-40/data.json` (20 nodes). Validator with reachability (`--start-id G021 --allow-unresolved-targets`) shows many missing targets (expected; destinations are beyond page 40 or in earlier chunk) and unreachable nodes relative to start.
- **Notes:** Both chunks (1-20 and 21-40) now exist separately; still need stitching and rerun without warnings once targets are covered.
- **Next:** Merge chunked enriched/app_data outputs or run a single longer slice that covers referenced targets; then validate without `--allow-unresolved-targets`.
### 20251121-2340 — Merged chunks into combined app data
- **Result:** Added merge helper `modules/export/merge_enriched_appdata.py`; merged 1–20 and 21–40 enriched outputs into `output/runs/ocr-enrich-app-merged/` (20 rows; deduped by portion_id) and built combined `data.json`. Validation with `--allow-unresolved-targets` passes; strict mode still fails on targets pointing beyond page 40 (e.g., 147, 270) and reachability from intro.
- **Notes:** To clear warnings we need additional pages covering referenced targets or a stitching strategy that spans further chunks.
- **Next:** Add another chunk (41–80) or raise end to 80 with higher timeout, then re-merge and validate without warnings.
### 20251121-2350 — Added chunk 41-60 and improved merging
- **Result:** Created `recipe-ocr-enrich-app-41-60.yaml` (20 pages) and ran successfully (300s). Extended merge tool to optionally rekey portion_ids by page to avoid collisions; merged 1–20, 21–40, 41–60 into `output/runs/ocr-enrich-app-merged/` (60 rows) and rebuilt `data.json`. Strict validation still fails (many targets beyond page 60, unreachable graph), as expected.
- **Notes:** Keys now page-based (`Pxxx`) in merged output; warnings list unresolved targets (e.g., 147, 270, 400). Need deeper pages to resolve.
- **Next:** Run additional chunk (61–80 or 61–100) or longer slice to cover targets, re-merge, and revalidate without `--allow-unresolved-targets`.
### 20251121-2357 — Added chunk 61-80 and re-merged (still unresolved)
- **Result:** Ran `recipe-ocr-enrich-app-61-80.yaml` (20 pages) under 300s. Merged all chunks (1–20, 21–40, 41–60, 61–80) with page-based IDs → `output/runs/ocr-enrich-app-merged/` (80 rows). Strict validation still fails due to many forward targets beyond page 80 and unreachable graph from start.
- **Notes:** Warnings list long tail of missing targets; merging is working but coverage insufficient. Next chunk(s) needed to capture later destinations.
- **Next:** Continue chunking (81–100) and revalidate; consider batching multiple chunks before merge to reduce repeated warnings.
### 20251122-0006 — Added chunk 81-100; coverage report tool
- **Result:** Ran `recipe-ocr-enrich-app-81-100.yaml` (20 pages) successfully; merged chunks 1–100 (page-keyed) → 100 rows. Strict validation still fails (targets up to 400 missing). Added `modules/validate/report_targets.py` to summarize coverage; current merged page-keyed set shows 247 unique targets, 0 present, missing range min=5 max=400.
- **Notes:** Targets are paragraph numbers; page-keying breaks matching. Re-merging without rekey keeps only 20 rows (ID collisions) and still has missing targets (15).
- **Next:** Need a mapping strategy for turn-to targets (e.g., run portionizer that emits paragraph IDs matching targets, or add adapter to map target numbers to page-based portions). Until then, adding more pages won’t close validation gaps.
### 20251122-0009 — Tried heuristic ID remap; confirmed need for numbered portions
- **Result:** Added `modules/adapter/remap_enriched_ids_v1.py` (detect leading integer in raw_text to remap portion_id and targets). Remapping merged 1–100 rows produced no coverage gains: `report_targets` still shows 247 targets, 0 present.
- **Notes:** Raw texts lack leading numbered paragraphs because current portionizer is page-based; the real fix is a portionizer that yields numbered sections so turn-to targets can resolve.
- **Next:** Design/implement paragraph/section portionizer that detects leading numbers and sets portion_id accordingly, then rerun enrich+merge+validate.
### 20251122-1507 — Built numbered portionizer and first pass
- **Result:** Added `portionize_numbered_v1` (leading-number splitter) and ran a fast pipeline on pages 1–20 (mock clean; numbered portionize → resolve → enrich). Produced 26 numbered portions but targets still missing (51 unresolved; ids not covering referenced range).
- **Notes:** Mock clean used for speed; need larger coverage with real cleaned text to capture numbered sections and turn-to targets. `portionize_numbered_v1` now accepts pipeline flags.
- **Next:** Run numbered portionizer over full cleaned pages (non-mock) with higher timeout or staged batches; then rerun enrichment and validation to see if targets resolve.
### 20251122-1540 — Numbered pipeline on pages 1–40 (real clean)
- **Result:** Ran `recipe-ocr-enrich-numbered-1-40.yaml` with real clean (boost off, max_chars 800). Output: 22 numbered portions, 19 targets referenced, 0 resolved (targets still beyond current coverage). Validation via `report_targets` confirms missing targets set {3..382 subset}.
- **Notes:** Runtime ~5.5 minutes within 600s timeout. Numbered headings are sparse in first 40 pages; many turn-to targets point deeper.
- **Next:** Process further ranges (e.g., 41–80) with numbered portionizer using existing OCR/clean pipeline to accumulate numbered ids, then re-run enrichment and validation on merged numbered outputs.
### 20251122-1610 — Numbered pipeline pages 41–80 + merge
- **Result:** Ran `recipe-ocr-enrich-numbered-41-80.yaml` (boost off, max_chars 800). Produced 28 numbered portions; targets present: 55 (0 resolved). Merged 1–40 and 41–80 numbered enriched outputs (page-keyed merge) → 50 portions, 70 targets, still 0 resolved.
- **Notes:** Runtime ~6 minutes. Missing targets still include early refs (e.g., 3, 74) and larger numbers (up to 389), indicating section numbering not captured consistently (likely because many sections start later or numbering is in-text rather than headings).
- **Next:** Need a numbering strategy that aligns with turn-to paragraph numbers (e.g., detect inline “Turn to 123” targets and assign synthetic portion_ids to the destination text, or run a dedicated “section finder” that splits on numeric anchors throughout the book). Also consider mapping targets to nearest page span when exact section not found.
### 20251122-1623 — Numbered chunk 81–100 (reuse clean), merged numbered set
- **Result:** Reused existing clean pages for 81–100; ran `portionize_numbered_v1` + resolve + enrich → 5 numbered portions, 15 targets (0 resolved). Merged numbered enriched outputs for 1–40, 41–80, 81–100 (no rekey) → 36 portions, 45 targets, still 0 resolved.
- **Notes:** Even with more pages, numbered headings remain sparse; targets span up to 389. The paragraph numbers are not exposed as headings in current cleaned text, so the numbered splitter can’t capture them.
- **Next:** Implement “section finder” that creates synthetic portions from inline numeric anchors (e.g., split on any “\\n<digits> ” anywhere, not just leading lines) or map targets to nearest page spans; then rerun merge + validation.
### 20251122-1635 — Added section_enrich_v1 (targets + section_id heuristics)
- **Result:** Added LLM-free `section_enrich_v1` and extended `EnrichedPortion` with optional `section_id` and `targets`. Running on numbered chunk 41–80 extracted targets (e.g., 397, 210, 78…) tied to existing portions; no resolution yet.
- **Notes:** Keeps `portion_id` intact; `section_id` is detected from leading numbers; targets from “turn/go to <num>”. Tooling works but doesn’t create missing sections.
- **Next:** Implement inline “section finder”/splitter to create synthetic sections for numeric anchors within text, then rerun enrichment and validation to align targets with sections.
### 20251122-1715 — Section finder + mapped run (41–80)
- **Result:** Added `portionize_sections_v1` (splits on any inline numeric anchor) and `map_targets_v1` adapter. Ran `recipe-ocr-enrich-sections-41-80.yaml` (real clean, no boost): 206 section hypotheses → 40 resolved portions; section_enrich added targets; map_targets annotated hits using known section_ids. Targets still unresolved globally pending other ranges.
- **Notes:** This path is LLM-free after cleaning; creates many section_ids in one pass. Need to run same pipeline on other ranges and then merge mapped outputs to see coverage improvements.
- **Next:** Run section-based pipeline on 1–40 and 81–100, merge all section_enriched outputs, rerun map_targets, and check coverage/resolution.
### 20251123-0010 — No-consensus section runs merged; targets fully resolved
- **Result:** Ran no-consensus section pipelines (keep all anchors) for 1–40, 41–80, 81–113. Merged outputs (no dedupe) and backfilled the last 4 missing sections; final coverage: section_ids 399, targets 385, targets_present 385, targets_missing 0 (`output/runs/ocr-enrich-sections-merged/portions_enriched_backfill.jsonl`).
- **Notes:** Consensus/dedupe had been dropping sections; removing them and avoiding merge dedupe fixed target resolution. Backfill tool: `modules/adapter/backfill_missing_sections_v1.py`. Diagnostics updated (`report_targets`, `report_missing_targets` count targets field and portion_ids).
- **Next:** Wire this section pipeline (no-consensus + backfill) into a reusable recipe or driver flag; optionally integrate merged section artifact into main run outputs and add validator step for target coverage.
### 20251123-1045 — Planned integration path for section coverage
- **Result:** Reviewed merged no-consensus artifacts and identified remaining gaps: pipeline not yet wired into a single recipe/run target and no automated guardrail to fail on missing section targets.
- **Notes:** Next steps captured as new tasks above; evidence-driven approach will reuse existing merged outputs and validate via `report_targets.py`/`report_missing_targets.py` before changing code.
- **Next:** Build reusable recipe wrapper for portionize_sections_v1 → section_enrich_v1 → section_target_guard_v1 (replaces map/backfill) and add validation step/CI check.
### 20251123-1406 — Superseded map/backfill by guard adapter
- **Result:** Document note: `section_target_guard_v1` now replaces the map_targets/backfill chain; use guard adapter going forward.
- **Notes:** Legacy adapters left for history; current recipes updated under Story 023.
- **Next:** None for this story (Done).
### 20251123-1125 — Added no-consensus recipe and target validation guard
- **Result:** Added reusable recipe `configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml` (portionize_sections → section_enrich → map_targets → backfill → assert_section_targets_v1) plus validation module `modules/validate/assert_section_targets_v1.py` (fails on missing targets, writes summary JSON). Updated AGENTS safe commands with the validation invocation.
- **Notes:** Ran `assert_section_targets_v1` on existing merged artifact `output/runs/ocr-enrich-sections-merged/portions_enriched_backfill.jsonl` → missing_count=0. Did not rerun full recipe yet (prior full run timed out) to avoid redundant long/LLM work.
- **Next:** When running new recipe, point it at the whole PDF or chunk as needed; validation stage will fail if coverage regresses. Consider CI wiring to call the validator on the merged artifact.
### 20251123-1335 — Ran full no-consensus section recipe end-to-end
- **Result:** `python driver.py --recipe configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml --registry modules --force` completed. Artifacts: `output/runs/ocr-enrich-sections-noconsensus/portions_enriched_backfill.jsonl` (490 rows). Validation stage `assert_section_targets_v1` reported section_count=399, targets_count=382, missing_count=0.
- **Notes:** Cleaning 113 pages took ~13 minutes; total runtime ~15 minutes. This run confirms the recipe/guard works without chunking.
- **Next:** Wire validator into CI or downstream pipelines; consider reusing this run output as the authoritative section set.
### 20251123-1355 — Section coverage guard (local-friendly)
- **Result:** Drafted a GH Actions workflow but removed it per preference; guard remains as a local script invocation: `python modules/validate/assert_section_targets_v1.py --inputs <path> --out section_target_report.json`.
- **Notes:** Keep validation manual or wire into non-GitHub CI if desired. No hosted artifact required.
- **Next:** Optionally add a make/just target to run the validator locally or in an alternate CI system.
### 20251123-1408 — Added unit tests for section target guard
- **Result:** Added `tests/assert_section_targets_test.py` to cover pass/fail paths of `assert_section_targets_v1` without external artifacts. Both tests pass locally via `pytest tests/assert_section_targets_test.py`.
- **Notes:** Test constructs small JSONL fixtures in tmpdir and asserts exit code/report content. Keeps regression safety without GH Actions.
- **Next:** Fold into default test suite (plain `pytest`) if desired.
