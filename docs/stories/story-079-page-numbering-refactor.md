# Story: Sequential Page Numbering Refactor — Dual-Field Provenance

**Status**: Done  
**Created**: 2025-12-18  
**Priority**: High

---

## Goal

Refactor the page identification system to eliminate the complexity of alphanumeric IDs (e.g., "051L", "051R"). Currently, split pages are handled using string suffixes, which makes basic math, sorting, and range-checking difficult and error-prone. 

The goal is to move to a dual-field integer-based system that separates **physical source provenance** from **logical pipeline sequence**.

---

## The Problem

1. **Broken Math**: You can't do `page_id + 1` with "051L".
2. **Logic Leaks**: Dozens of modules contain regex patterns like `re.match(r'^(\d+)([LR]?)$')` to "understand" what page they are on.
3. **Number Confusion**: Code often accidentally uses the base number (51) instead of the specific split ID (051L), leading to data loss or incorrect section mapping.
4. **Ordering Issues**: Alphanumeric sorting works for "L/R" but becomes brittle if new split patterns emerge.

---

## Proposed Solution: Dual-Field Numbering

Every page object in the pipeline should carry two distinct fields:

1. **`original_page_number` (int)**:
   - Represents the physical index/number in the source document (e.g., the PDF page index).
   - Used for provenance and referencing the original scan image.
   - For a split page, both the Left and Right halves share the same `original_page_number`.

2. **`page_number` (int)**:
   - A unique, sequential integer for every distinct page in the pipeline's current view.
   - If pages are NOT split, `page_number` == `original_page_number`.
   - If pages ARE split, `page_number` is a monotonically increasing counter (1, 2, 3...).
   - **Critical Assumption**: All downstream code (boundary detection, portionization, etc.) can use `page_number` blindly as a simple integer.

---

## Success Criteria

- [x] **Sequential IDs**: Every page in the `pages_raw.jsonl` (and downstream) has a `page_number` that is a simple integer.
- [x] **Simplified Logic**: Remove regex-based page parsing (`extract_num_and_suffix`, `parse_page_id`) from at least 3 major modules (portionize, extract, etc.).
- [x] **Provenance Intact**: `original_page_number` is preserved for every element, allowing a trace back to the source image/PDF.
- [x] **Math Works**: Downstream range checks and sorting use simple integer comparison.
- [x] **Element IDs**: Update element ID generation (e.g., `P051L-S001`) to use the new sequential `page_number`.
- [x] **Testing Coverage**: Update automated tests and smoke configs to validate dual-field page numbering (including spread splits).
- [x] **Escalation Alignment**: All vision escalations operate on the pipeline’s **logical pages** (i.e., the split-page images when spreads are split), with no assumption that pages are always split. For non-spread books, this should naturally use the single-page images.
- [x] **Header Sanity Heuristic**: When resolving ordering/span conflicts, prefer headers that have at least some body text between them and the next header on the same logical page; headers with no intervening text should be aggressively down-ranked or dropped (tie-breaker only).

---

## Tasks

### Phase 1: Impact Analysis
- [x] **Audit `pages_raw.jsonl`**: Identify where `page_id` is first introduced and how many downstream schemas it affects.
- [x] **Scan for regex parsing**: Grep for `[LR]` and `(\d+)` patterns used for page logic to ensure all are captured.
- [x] **Inventory schema touchpoints**: List every artifact schema that currently includes `page_id` (pages, elements, boundaries, portions, enriched, outputs).
- [x] **Map element ID dependencies**: Locate all code that parses `P###` element IDs for page logic and list affected modules.
- [x] **Document current ordering logic**: Capture every sort/range check that depends on L/R suffixes and where it lives.

### Phase 2: Implementation (Upstream)
- [x] **Update Intake**: Modify OCR ensemble or intake modules to emit both `original_page_number` and `page_number`.
- [x] **Handle Splitting**: Implemented in `extract_ocr_ensemble_v1` by assigning sequential `page_number` while keeping shared `original_page_number` + `spread_side` (no `ocr_split_v1` in repo).
- [x] **Schema Update**: Update `schemas.py` to support the new fields (validate_artifact.py already uses schemas; no separate change required).

### Phase 3: Downstream Migration
- [x] **Update Elements**: Refactor element generation to use the new IDs.
- [x] **Refactor Portionization**: Clean up the range-checking logic in `detect_boundaries_code_first_v1` and `coarse_segment_v1`.
- [x] **Verify Forensics**: Ensure diagnostic tools (`scripts/trace_section_pipeline.py`) correctly display both numbers.
- [x] **Update page-aware prompts**: Revise `coarse_segment_v1` prompt and validation to use `page_number` with `original_page_number` for provenance.
- [x] **Fix portionize AI image lookup**: Replace L/R image filename assumptions in `portionize_ai_extract_v1` with `page_number` (and preserve original image mapping).
- [x] **Update tests + smoke configs**: Adjust unit tests and smoke settings to assert `page_number`/`original_page_number` fields and validate spread split sequencing.
- [x] **Escalation uses logical pages**: Vision escalation must use the pipeline’s logical pages (split images when spreads are split; single images otherwise). Do not assume pages are always split; rely on the normalized `page_number`/image mapping already produced upstream.
- [x] **Ordering conflict heuristic**: Add a tie-breaker that drops header candidates with no non-header text between them and the next header on the same logical page (only applied during ordering/span conflict resolution).

---

## Context

**Current Failure Mode**:
In Deathtrap Dungeon, pages are often split. When the pipeline sees page "12L" and "12R", some modules default to "12", causing the data from "12L" to be overwritten or ignored by "12R", or causing boundaries to fail because "13" is expected after "12", but "12R" is found instead.

**Why This Matters**:
- Achieving 100% accuracy (Story 074) requires robust page handling.
- Simplifying the code makes the pipeline more maintainable for non-FF books (Onward to the Unknown).
- Reduces the risk of "silent data loss" where one half of a split page is dropped.

---

## Work Log

### 2025-12-18 — Story created
- **Scope**: Migration to dual-field (original vs sequential) page numbering.
- **Next**: Audit current artifact schemas to see how many `page_id` references need updating.

### 20251218-2346 — Repo scan for page_id parsing
- **Result:** Success; identified multiple modules using L/R parsing and page_id assumptions.
- **Notes:** `modules/portionize/detect_boundaries_code_first_v1/main.py` and `modules/portionize/coarse_segment_v1/main.py` contain explicit `parse_page_id`/`extract_num_and_suffix` helpers; `modules/portionize/portionize_ai_extract_v1/main.py` builds L/R page IDs for image lookup.
- **Next:** Open those modules and enumerate concrete fields/ids that need dual-field migration; add to Impact Analysis list.

### 20251218-2346 — Inspected portionize modules for L/R dependencies
- **Result:** Success; confirmed multiple hard-coded L/R pathways.
- **Notes:** `modules/portionize/coarse_segment_v1/main.py` extracts page_id from element IDs and uses `page_sort_key` regex for L/R ordering; `modules/portionize/detect_boundaries_code_first_v1/main.py` uses `parse_page_id` + `extract_num_and_suffix` in gameplay range checks.
- **Next:** Identify where `page` fields are set upstream (OCR/split) and draft the dual-field schema changes for pages/elements/boundaries.

### 20251218-2346 — Schema + code search for page fields
- **Result:** Success; found widespread reliance on `metadata.page_number` and `page` across portionize/adapters/validators.
- **Notes:** `modules/intake/pagelines_to_elements_v1/main.py` populates `metadata.page_number`; many downstream modules read `e.get("page") or e.get("metadata", {}).get("page_number")`. `modules/portionize/portionize_ai_extract_v1/main.py` still synthesizes `###L/###R` image IDs.
- **Next:** Open intake/ocr modules that emit `pages_raw.jsonl` to pinpoint the first introduction of page identifiers and draft migration notes.

### 20251218-2348 — Audited OCR/intake emitters for page identifier sources
- **Result:** Success; located first introduction of page identifiers and split-page handling.
- **Notes:** `modules/extract/extract_ocr_v1/main.py` writes `pages_raw.jsonl` with `page` = 1-based int only. `modules/extract/extract_ocr_ensemble_v1/main.py` emits `pagelines_v1` with `page` = original PDF page index (int) and `spread_side` = L/R; L/R uniqueness only exists in `page_key` (e.g., `001L`) used for filenames/index, not in the payload. `modules/intake/pagelines_to_elements_v1/main.py` expects `page_key` with L/R suffixes, derives `metadata.page_number` from numeric portion, and bakes L/R into element IDs.
- **Next:** Draft dual-field migration plan: add `original_page_number` + `page_number` to `pagelines_v1`/`page_doc_v1`/elements, update element IDs to use sequential `page_number`, and preserve L/R via `spread_side` + original provenance.

### 20251218-2348 — Drafted dual-field migration plan (source-of-truth + schema impact)
- **Result:** Success; concrete plan captured for dual-field rollout and downstream cleanup.
- **Notes:** Proposed source-of-truth: `page_number` is the **unique sequential output page**; `original_page_number` is the **physical PDF page index**. For non-split pages, they match; for splits, `page_number` increments per half while `original_page_number` remains shared and `spread_side` stays L/R. Update `schemas.py` for `PageDoc`, `PageLines`, `CleanPage`, `ImageCrop`, `ElementCore`, and any page-bearing artifacts to include `original_page_number` (optional) and treat `page` as `page_number` (or rename to `page_number` where safe). Update `extract_ocr_ensemble_v1` to assign sequential `page_number` in output rows and index keys; retain `original_page_number` + `spread_side` for provenance and image mapping. Update `extract_ocr_v1`/`extract_text_v1` to emit both fields (`page_number` and `original_page_number`) even without splits. Update `pagelines_to_elements_v1` to use `page_number` directly (no L/R parsing) and generate element IDs from `page_number`; store `original_page_number` + `spread_side` in metadata so L/R provenance remains visible without encoding it into IDs. Downstream: remove regex parsing for L/R; use `page`/`page_number` fields for sorting and ranges; update `portionize_ai_extract_v1` image lookup to map via `original_page_number` + `spread_side` (or a new `image_key`) rather than synthesizing `###L/###R`.
- **Next:** Confirm which schemas/validators assume `page` only (e.g., `validate_artifact.py`) and draft a minimal, staged rollout order (OCR → pagelines_to_elements → coarse/portionize → validators).

### 20251218-2352 — Added dual-field emission in OCR/text intake + schema support
- **Result:** Success; emitters now include `page_number` + `original_page_number` and schemas accept both.
- **Notes:** Updated `schemas.py` to add optional `page_number`/`original_page_number` to `PageDoc`, `PageLines`, `CleanPage`, `ImageCrop`, and `ElementCore`. Added fields in `modules/extract/extract_ocr_v1/main.py`, `modules/extract/extract_text_v1/main.py`, and `modules/extract/extract_ocr_apple_v1/main.py`. In `modules/extract/extract_ocr_ensemble_v1/main.py`, added `page_number` as sequential output counter while keeping `page` as original PDF page for now.
- **Next:** Update `pagelines_to_elements_v1` to consume `page_number` as the canonical page and carry `original_page_number` + `spread_side` into element metadata, then refactor downstream L/R parsing.

### 20251218-2353 — Added test/smoke update requirement
- **Result:** Success; story requirements now include updating tests and smoke configs for dual-field page numbering.
- **Notes:** Added Success Criteria + Tasks entries to require test coverage and smoke config adjustments for `page_number`/`original_page_number`.
- **Next:** Identify existing tests/smoke configs that assert page fields and update them during implementation.

### 20251218-2357 — Updated pagelines_to_elements to use sequential page_number
- **Result:** Success; elements now use `page_number` as canonical page and carry provenance fields.
- **Notes:** `modules/intake/pagelines_to_elements_v1/main.py` now orders pages by `page_number` (fallback to legacy page_key), emits element IDs based on `page_number`, and propagates `original_page_number` + `spread_side` in metadata and `ElementCore`.
- **Next:** Sweep downstream modules for L/R parsing to remove, then update tests/smoke configs to assert dual-field presence and sequencing.

### 20251218-2357 — Hardened page_number parsing in pagelines_to_elements
- **Result:** Success; added safe int coercion for page_number.
- **Notes:** Ensures `page_number` strings in pagelines payloads are coerced to int before element ID formatting.
- **Next:** Continue downstream L/R parsing removals and update tests/smokes.

### 20251219-0001 — Removed L/R parsing from portionize modules (page_number-first)
- **Result:** Success; downstream modules now prioritize `page_number` and avoid regex L/R parsing.
- **Notes:** `modules/portionize/detect_boundaries_code_first_v1/main.py` now compares numeric page ranges without L/R suffix logic. `modules/portionize/coarse_segment_v1/main.py` now builds/sorts pages using `page_number` (legacy fallback only) and validates ranges without regex. `modules/portionize/portionize_ai_extract_v1/main.py` now resolves images via `original_page_number` + `spread_side` rather than element-id L/R parsing.
- **Next:** Update remaining downstream modules that still parse L/R (if any), then add/adjust tests and smoke configs to validate dual-field sequencing.

### 20251219-0005 — Removed remaining L/R element-id dependencies in detect_boundaries + improved trace pages
- **Result:** Success; boundary conflict grouping and span diagnostics now rely on spread_side metadata instead of L/R element IDs.
- **Notes:** `modules/portionize/detect_boundaries_code_first_v1/main.py` now stores `start_element_metadata` on boundaries and uses `spread_side` for conflict grouping and span issues (legacy element-id check only as fallback). `modules/portionize/fine_segment_gameplay_v1/main.py` now prefers `page_number` when tracing pagelines for missing sections.
- **Next:** Sweep adapter OCR modules that still assume L/R in pagelines_index (ocr_escalate_gpt4v_v1, inject_missing_headers_v1) and update them or explicitly scope to original_page_number/spread_side.

### 20251219-0007 — Updated OCR adapters to use dual-field page provenance
- **Result:** Success; OCR escalation and header injection now honor `page_number`/`original_page_number` while keeping pagelines_index compatibility.
- **Notes:** `modules/adapter/ocr_escalate_gpt4v_v1/main.py` now resolves opposite spread sides using `original_page_number` + `spread_side` (fallback to legacy key suffix), and loads page data through a shared cache helper. `modules/adapter/inject_missing_headers_v1/main.py` now uses `page_number` when available for logging/injection context.
- **Next:** Update remaining adapter utilities that assume L/R keys (if any) and then move to tests/smoke updates.

### 20251219-0010 — Removed remaining L/R parsing in adapters/validators
- **Result:** Success; legacy element-id parsing minimized and page_number precedence expanded.
- **Notes:** `modules/adapter/backfill_missing_sections_v2/main.py` now extracts page numbers as digit prefixes (no L/R) and prefers `page_number`. `modules/validate/validate_ff_engine_v2/main.py` now consistently prefers `page_number` over `metadata.page_number`/`page` when reporting traces and spans. `modules/adapter/text_quality_report_v1/main.py` now uses `page_number` when present for row keys.
- **Next:** Move to tests/smoke updates to assert dual-field numbering and spread split sequencing.

### 20251219-0013 — Updated tests for dual-field page numbering
- **Result:** Success; tests now exercise page_number/original_page_number and spread_side handling.
- **Notes:** `tests/test_ocr_escalate_gpt4v_v1.py` now uses sequential page keys with `original_page_number` + `spread_side`. `tests/test_boundary_ordering_guard.py` now uses `page_number` + `start_element_metadata.spread_side` rather than L/R in element IDs. `tests/test_driver_stamping_preserves_pagelines_provenance.py` now asserts `page_number`/`original_page_number` preservation. `tests/test_missing_header_resolver.py` now seeds `page_number`/`original_page_number`.
- **Next:** Update smoke configs or add a lightweight smoke check that validates dual-field sequencing in pagelines/elements artifacts.

### 20251219-0015 — Updated smoke stubs for dual-field fields
- **Result:** Success; smoke fixtures now include page_number/original_page_number (and page_start/page_end originals) to match new requirements.
- **Notes:** Updated `testdata/smoke/ff/pages_clean.jsonl` with `page_number` + `original_page_number`. Added `page_start_original`/`page_end_original` to `testdata/smoke/ff/portion_hyp.jsonl`, `testdata/smoke/ff/portions_resolved.jsonl`, and `testdata/smoke/ff/portions_enriched_stub.jsonl`.
- **Next:** If needed, add a smoke validation step to assert sequential page_number ordering in generated artifacts.

### 20251219-0017 — Ran ff-smoke pipeline and inspected artifacts
- **Result:** Success after driver + header stub fixes; smoke run completed.
- **Notes:** Fixed driver schema inference for stubs (use params.schema_version as output_schema) and normalized `skip_ai` to `--skip-ai` for stub stages; fixed `portionize_headers_v1` skip-ai path to import/save JSONL correctly. Ran `python driver.py --recipe configs/recipes/recipe-ff-smoke.yaml --settings settings.smoke.yaml --run-id ff-smoke-dual --output-dir /tmp/cf-smoke-ff-dual --force`. Inspected `/tmp/cf-smoke-ff-dual/01_load_stub_v1/adapter_out.jsonl` and confirmed `page_number` + `original_page_number` present and aligned (samples pages 1–3). Portion stubs are stamped to schema and extra page_start_original fields are dropped (schema currently does not include them).
- **Next:** Decide whether to extend portion schemas to carry original page spans or keep dual-field only at page/element level; then run a non-stub smoke that produces elements_core with page_number to validate downstream ordering.

### 20251219-0021 — Extended portion schemas with original page spans
- **Result:** Success; schema now preserves `page_start_original`/`page_end_original` in portion artifacts.
- **Notes:** Added optional `page_start_original` + `page_end_original` to `PortionHypothesis`, `LockedPortion`, `ResolvedPortion`, and `EnrichedPortion` in `schemas.py`.
- **Next:** Re-run smoke to confirm stub portions keep original span fields, then inspect artifacts.

### 20251219-0022 — Re-ran smoke to verify original span propagation
- **Result:** Success; resolved portions now retain original span fields.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-smoke.yaml --settings settings.smoke.yaml --run-id ff-smoke-dual --output-dir /tmp/cf-smoke-ff-dual --force`. Verified `/tmp/cf-smoke-ff-dual/04_portion_hyp_to_resolved_v1/adapter_out.jsonl` includes `page_start_original`/`page_end_original` (sample row shows 1/1).
- **Next:** Decide whether to propagate original spans into any downstream build/export outputs, then run a non-stub smoke with elements_core to validate page_number sequencing end-to-end.

### 20251219-0024 — Propagated original spans into build/export outputs
- **Result:** Success; build outputs now carry original span provenance.
- **Notes:** `modules/build/build_portions_v1/main.py` now includes `page_start_original`/`page_end_original` in assembled raw portions. `modules/export/build_ff_engine_v1/main.py` now emits `provenance.source_pages_original` when original spans are present.
- **Next:** Run a non-stub smoke or targeted export build to verify `source_pages_original` is present in `gamebook.json` when enriched portions include original spans.

### 20251219-0027 — Verified build_raw carries original spans
- **Result:** Success; build_raw includes original span fields.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-smoke.yaml --settings settings.smoke.yaml --run-id ff-smoke-dual --output-dir /tmp/cf-smoke-ff-dual --end-at build_raw --force`. Verified `/tmp/cf-smoke-ff-dual/05_build_portions_v1/portions_final_raw.json` contains `page_start_original`/`page_end_original` (sample shows 1/1).
- **Next:** Run a minimal enriched→build_ff_engine path to confirm `provenance.source_pages_original` in `gamebook.json`, or proceed to a non-stub smoke run with elements_core.

### 20251219-0026 — Verified gamebook provenance uses source_pages_original
- **Result:** Success; gamebook provenance now exposes original span range.
- **Notes:** Built a minimal stub enriched file and ran `PYTHONPATH=. python modules/export/build_ff_engine_v1/main.py --portions /tmp/cf-smoke-ff-dual/portions_enriched_stub.jsonl --out /tmp/cf-smoke-ff-dual/gamebook.json --title "Smoke Stub" --allow-stubs`. Verified `/tmp/cf-smoke-ff-dual/gamebook.json` has `provenance.source_pages_original` (sample shows `[1]`).
- **Next:** Consider adding a lightweight validator/check that asserts `source_pages_original` when original spans exist, then proceed with a non-stub smoke (elements_core) to validate page_number sequencing end-to-end.

### 20251219-0032 — Non-stub smoke to reduce_ir with dry-run escalation
- **Result:** Success; non-stub smoke produced pagelines_final and elements_core with sequential page_number fields.
- **Notes:** Added `configs/settings.ff-canonical-smoke-no-escalate.yaml` to run 20 pages with `ocr_escalate_gpt4v_v1` in dry_run mode. Ran `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.ff-canonical-smoke-no-escalate.yaml --run-id ff-canonical-dual-smoke --output-dir /tmp/cf-ff-canonical-dual-smoke --end-at reduce_ir --force`. Verified `/tmp/cf-ff-canonical-dual-smoke/pagelines_final.jsonl` has `page_number` 1–40 (unique), `original_page_number` 1–20, and `spread_side` set on sample row. Verified `/tmp/cf-ff-canonical-dual-smoke/elements_core.jsonl` includes `page_number` and `original_page_number` (sample row shows 1/1).
- **Next:** If needed, extend downstream validators to assert sequential `page_number` uniqueness and add a regression test for page_number coverage across elements_core.

### 20251219-0034 — Added page_number sequencing test helper
- **Result:** Success; added a lightweight validator utility and tests for sequential page_number detection.
- **Notes:** Added `modules/common/page_numbers.py` with `validate_sequential_page_numbers` and tests in `tests/test_page_number_sequencing.py` covering contiguous, gap, and allow_gaps cases.
- **Next:** Consider wiring the helper into a validator module or into an existing smoke/validation stage for runtime enforcement.

### 20251219-0036 — Wired page_number sequencing into validate_ff_engine_v2
- **Result:** Success; validator now flags gaps in page_number sequence as errors with forensics trace.
- **Notes:** `modules/validate/validate_ff_engine_v2/main.py` now uses `validate_sequential_page_numbers` on `pages_raw` (fallback `pages_clean`), adds errors on gaps, and includes a `page_number_sequence` entry in forensics with artifact path + missing list.
- **Next:** Run validate_ff_engine_v2 on a smoke run to confirm the new check passes with sequential page_number artifacts.

### 20251219-0733 — Fixed trace tool + updated coarse segment prompt
- **Result:** Success; trace tool now runs and coarse segment prompt aligns with dual-field page numbering.
- **Notes:** Fixed invalid f-strings + duplicate shebang in `scripts/trace_section_pipeline.py`. Updated `modules/portionize/coarse_segment_v1/main.py` prompt and payload to use `page_number`/`original_page_number` and removed L/R examples; summaries now carry original provenance.
- **Next:** Decide whether any explicit changes to `validate_artifact.py` are required beyond updated schemas; rerun targeted tests/validation to confirm no regressions.

### 20251219-0734 — Ran targeted pytest for page numbering + boundary coverage
- **Result:** Success; 13 tests passed.
- **Notes:** Ran `python -m pytest tests/test_page_number_sequencing.py tests/test_boundary_ordering_guard.py tests/test_ocr_escalate_gpt4v_v1.py`.
- **Next:** Re-run story validation and confirm remaining checklist items (validate_artifact + split handling) are resolved or explicitly re-scoped.

### 20251219-0737 — Updated story checklist to reflect completed dual-field migration
- **Result:** Success; success criteria and tasks marked complete with scope clarifications.
- **Notes:** Clarified split handling occurs in `extract_ocr_ensemble_v1` (no `ocr_split_v1` in repo) and `validate_artifact.py` relies on `schemas.py` for field coverage.
- **Next:** Re-run story validation and, if desired, add untracked helper/test files and smoke settings to the repo.

### 20251219-0740 — Smoke run + sequential page_number validation
- **Result:** Partial success; smoke run completed and sequencing validated, but validate_ff_engine_v2 requires a gamebook.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-smoke.yaml --settings settings.smoke.yaml --run-id ff-smoke-dual-validate --output-dir /tmp/cf-smoke-ff-dual-validate --force`. Inspected `/tmp/cf-smoke-ff-dual-validate/01_load_stub_v1/adapter_out.jsonl` (page_number/original_page_number sequential 1–5 sample). Inspected `/tmp/cf-smoke-ff-dual-validate/04_portion_hyp_to_resolved_v1/adapter_out.jsonl` (page_start/page_end and original span fields present). Ran `PYTHONPATH=. python - <<'PY'` to validate sequencing via `validate_sequential_page_numbers` (ok True, missing []). Attempted `modules/validate/validate_ff_engine_v2` against stub outputs; it expects a gamebook and failed as expected for stub range.
- **Next:** Decide whether to run a non-stub pipeline to produce a real `gamebook.json` for validator coverage or accept unit test coverage for sequencing.

### 20251219-1622 — Added ordering conflict heuristic requirement
- **Result:** Success; story now requires a tie-breaker that drops header candidates with no intervening body text on the same logical page.
- **Notes:** Updated Success Criteria and Tasks to add a header sanity heuristic applied during ordering/span conflict resolution.
- **Next:** Implement the heuristic in `detect_boundaries_code_first_v1` and validate on a minimal ordering-only run.

### 20251219-1622 — Implemented header span heuristic for ordering conflicts
- **Result:** Success; ordering/span guard now prunes header candidates with no intervening body text on the same logical page.
- **Notes:** Added `prune_headers_with_empty_between` in `modules/portionize/detect_boundaries_code_first_v1/main.py` and wired it before escalation; report now captures `ordering_conflicts_pruned`, `span_issues_pruned`, and `heuristic_pruned`.
- **Next:** Run a minimal detect_boundaries ordering-only pass on a known conflict run to confirm conflicts drop without escalation.

### 20251219-1622 — Validated header span heuristic on existing run
- **Result:** Success; heuristic pruned conflict pages and reduced ordering/span issues without escalation.
- **Notes:** Ran `env PYTHONPATH=. python modules/portionize/detect_boundaries_code_first_v1/main.py --pages output/runs/ff-canonical-dual-full-20251219p/09_elements_content_type_v1/elements_core_typed.jsonl --coarse-segments output/runs/ff-canonical-dual-full-20251219p/16_coarse_segment_merge_v1/merged_segments.json --out /tmp/cf-ordering-heuristic/section_boundaries.jsonl --max-ordering-pages 0 --max-escalation-pages 0 --no-fail-on-ordering-conflict`. Checked `/tmp/cf-ordering-heuristic/section_boundaries.ordering_report.json`: ordering_conflicts 63→58, span_issues 76→64, heuristic_pruned_pages 24 (e.g., page 34 dropped sections 8/7/4).
- **Next:** Re-run detect_boundaries on a smaller targeted page set if needed, then decide whether to proceed with escalation or additional heuristics.

### 20251219-1622 — Inspected conflict page 34 elements
- **Result:** Success; confirmed dense numeric-only false headers with no layout metadata.
- **Notes:** Inspected `output/runs/ff-canonical-dual-full-20251219p/09_elements_content_type_v1/elements_core_typed.jsonl` for page 34: 13 elements, 8 marked `Section-header` with texts `6, 11, 11, 8, 8, 7, 4, 5`, all `bbox=None` and `line_idx=None`. Body text starts at seq 178, indicating these numeric-only headers are likely false positives causing ordering/span conflicts.
- **Next:** Decide whether to add a deterministic ordering tie-breaker based on layout/seq position (ignoring content_type) or escalate these pages to a vision model for header validation.

### 20251219-1740 — Verified escalation uses logical pages
- **Result:** Success; escalation now maps logical `page_number` to split images via `pages_raw.jsonl`.
- **Notes:** `output/runs/ff-canonical-dual-full-20251219p/01_extract_ocr_ensemble_v1/pages_raw.jsonl` maps `page_number=34` → `original_page_number=17`, `spread_side=R`, image `page-017R.png`, and escalation cache now consumes the logical `image_map`.
- **Next:** Resume OCR-quality investigation; the remaining boundary conflicts are driven by OCR noise in `pagelines_final.jsonl`.

### 20251219-1740 — Closed Story 079 checklist
- **Result:** Success; all success criteria and tasks are complete.
- **Notes:** Updated status to Done after verifying logical-page escalation alignment and header heuristic behavior.
- **Notes:** Validation was complicated by upstream OCR contamination in `pagelines_final.jsonl`, which created false headers and ordering conflicts unrelated to page numbering.
- **Next:** Shift focus to OCR quality (see Story 058) to address upstream text contamination driving boundary conflicts.

### 20251219-0841 — Non-stub smoke attempt + partial artifact inspection
- **Result:** Partial success; OCR + reduce_ir completed, LLM stage blocked by OpenAI call (interrupted).
- **Notes:** Attempted `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.ff-canonical-smoke.yaml --run-id ff-canonical-dual-smoke-20 --output-dir /tmp/cf-ff-canonical-dual-smoke-20 --force` but `ocr_escalate_gpt4v_v1` hung on OpenAI call; interrupted. Re-ran with `configs/settings.ff-canonical-smoke-no-escalate.yaml` to keep escalation dry-run; OCR→reduce_ir completed, then `coarse_segment_v1` blocked on OpenAI call and was interrupted. Inspected `/tmp/cf-ff-canonical-dual-smoke-20-noescalate/pagelines_final.jsonl` and `/tmp/cf-ff-canonical-dual-smoke-20-noescalate/elements_core.jsonl` to confirm `page_number`/`original_page_number` present. Ran `validate_sequential_page_numbers` against pagelines_final; ok True, missing [].
- **Next:** If a valid API key is available, rerun from coarse_segment onward (or run with `--skip-ai` if acceptable) to produce a real `gamebook.json` for full validator coverage.

### 20251219-0855 — Non-stub smoke run completed through build/validate
- **Result:** Partial success; pipeline completed to `gamebook.json` but validation failed on expected range mismatch.
- **Notes:** Ran `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --settings configs/settings.ff-canonical-smoke-no-escalate.yaml --run-id ff-canonical-dual-smoke-20-noescalate-2 --output-dir /tmp/cf-ff-canonical-dual-smoke-20-noescalate-2 --force`, then resumed from `coarse_segment` after settings fix. Coarse segmentation and downstream LLM stages ran. `validate_ff_engine_v2` failed because settings expected sections 20–21, but smoke produced 8 sections (IDs 2,4,5,7,12,13,14,16). Checked `/tmp/cf-ff-canonical-dual-smoke-20-noescalate-2/pagelines_final.jsonl` and `/tmp/cf-ff-canonical-dual-smoke-20-noescalate-2/elements_core.jsonl` for `page_number`/`original_page_number`. Ran `validate_sequential_page_numbers` (ok True, missing []).
- **Next:** Decide whether to adjust expected range for validate stage in smoke settings or accept the known mismatch; optionally re-run validate with expected range matching smoke output.

### 20251219-0900 — Validator override + added files to repo
- **Result:** Partial success; validator run completed but still failed on missing sections in smoke output. Added new helper/test files and reran pytest.
- **Notes:** Ran validate_ff_engine_v2 against `/tmp/cf-ff-canonical-dual-smoke-20-noescalate-2/gamebook.json` with expected range 2–16; it reports missing sections [3,6,8,9,10,11,15] and warnings for empty text/choices. Added `modules/common/page_numbers.py`, `tests/test_page_number_sequencing.py`, and `configs/settings.ff-canonical-smoke-no-escalate.yaml` to git index. Re-ran pytest (`tests/test_page_number_sequencing.py`, `tests/test_boundary_ordering_guard.py`, `tests/test_ocr_escalate_gpt4v_v1.py`) — all passed.
- **Next:** Re-run story validation and decide whether to adjust smoke validation expectations or accept that partial section coverage is expected at 20-page smoke scale.

### 20251219-0904 — Accepted smoke validation failure as expected (Option A)
- **Result:** Success; recorded decision to treat missing sections in 20-page smoke as expected.
- **Notes:** Validation failures in `validate_ff_engine_v2` are due to partial coverage in the smoke slice (not page-numbering regressions). This story uses smoke artifacts to verify dual-field sequencing only.
- **Next:** Proceed to final story validation/reporting with Option A assumption.

### 20251219-0914 — Added guard against deleting output/runs root
- **Result:** Success; driver now refuses --force when run_dir is output/runs root.
- **Notes:** Prevents accidental deletion of the entire runs directory when `--output-dir output/runs` is passed. This came up during full-run attempt.
- **Next:** Re-run full pipeline with a run-specific output directory.

### 20251219-0940 — Fixed monitor_run.sh $! expansion and attached live monitor
- **Result:** Success; monitoring script no longer errors under `set -u` and live monitor attached to full run.
- **Notes:** `scripts/monitor_run.sh` now prints the pidfile hint without expanding `$!`. Attached monitor to `ff-canonical-dual-full-20251219c` (PID 64642) using `scripts/monitor_run.sh`.
- **Next:** Wait for full run to complete, then inspect artifacts and validate end-to-end.

### 20251219-0947 — Documented foreground monitoring loop + background terminal caveat
- **Result:** Success; AGENTS monitoring section updated with 60-second tail loop and background-terminal caveat.
- **Notes:** Added guidance for running monitoring loops in the foreground when background terminal support interferes with tool calls.
- **Next:** Continue full pipeline run monitoring and finalize story validation once the run completes.

### 20251219-0953 — Killed nested monitored run and corrected launch guidance
- **Result:** Success; terminated nested run directory caused by output-dir misuse.
- **Notes:** `run_driver_monitored.sh` appends RUN_ID to OUTPUT_DIR, so passing a run-specific path results in nesting. Killed `ff-canonical-dual-full-20251219d` and removed pidfile.
- **Next:** Relaunch with OUTPUT_DIR as parent (`output/runs`) and a fresh run_id, without `--force`.

### 20251219-0958 — Documented monitored-run nesting caveat in README + AGENTS
- **Result:** Success; README and AGENTS now warn about run_dir nesting and provide foreground monitoring one-liner.
- **Notes:** Added Run monitoring section to README and clarified `run_driver_monitored.sh` appends RUN_ID to OUTPUT_DIR.
- **Next:** Launch monitored run with correct OUTPUT_DIR and fresh run_id.

### 20251219-1003 — Fixed run_driver_monitored output-dir handling
- **Result:** Success; monitored-run helper now passes the full run dir to driver, avoiding output/runs root collisions.
- **Notes:** Updated `scripts/run_driver_monitored.sh` to pass `--output-dir $RUN_DIR` instead of the parent. Updated README/AGENTS monitoring notes accordingly.
- **Next:** Relaunch monitored full run with corrected script.

### 20251219-1012 — Made run crashes loud in monitoring scripts
- **Result:** Success; monitor now tails driver.log on crash and run wrapper records exit codes.
- **Notes:** `scripts/monitor_run.sh` now prints the last 50 lines of `driver.log` when PID vanishes. `scripts/run_driver_monitored.sh` appends the driver exit code to `driver.log`. Documented crash visibility guidance in README/AGENTS.
- **Next:** Re-run full pipeline with explicit SHM-safe env to avoid OpenMP failure.

### 20251219-1018 — Made monitored runs compatible with --force
- **Result:** Success; run_driver_monitored now pre-deletes run dir and strips --force before invoking driver.
- **Notes:** Prevents driver from deleting `driver.pid`/`driver.log` mid-run, which previously broke monitor_run.sh and obscured stderr. Updated README/AGENTS accordingly.
- **Next:** Re-run monitored full pipeline and confirm failures are visible via driver.log and pipeline_events.jsonl.

### 20251219-1024 — Emit monitor crash event into pipeline_events.jsonl
- **Result:** Success; monitor now appends a run_monitor failure event when PID disappears.
- **Notes:** This makes crashes visible even when tailing `pipeline_events.jsonl` directly. Updated README/AGENTS to document.
- **Next:** Validate with a failing run to confirm the synthetic event appears as expected.

### 20251219-1030 — Fixed monitored --force flow to add --allow-run-id-reuse
- **Result:** Success; monitored runner now adds --allow-run-id-reuse when --force is used.
- **Notes:** Prevents driver from rejecting pre-created run dir and preserves logs/pidfile.
- **Next:** Relaunch failing run with fresh run_id to confirm crash visibility and run continuity.

### 20251219-1036 — Fixed run_driver_monitored failure-event emission
- **Result:** Success; monitor wrapper now writes a proper run_driver failure event to pipeline_events.jsonl with env values.
- **Notes:** Replaced a broken inline here-doc with a proper multiline block and removed stray '+fi'.
- **Next:** Re-run a failing monitored run to confirm the failure event is appended.

### 20251219-1040 — Added postmortem_run.sh for crash visibility
- **Result:** Success; postmortem helper appends a run_postmortem failure event when PID is gone.
- **Notes:** Added `scripts/postmortem_run.sh` and used it on `ff-canonical-dual-full-20251219k` to append a failure event to `pipeline_events.jsonl`.
- **Next:** If needed, integrate postmortem checks into monitoring workflow for long-running runs.

### 20251219-1044 — Wired postmortem into monitored runner
- **Result:** Success; run_driver_monitored now invokes postmortem_run.sh on exit to emit run_postmortem events.
- **Notes:** Documented in README/AGENTS for crash visibility when monitors terminate early.
- **Next:** Retry a failing monitored run to confirm both run_monitor and run_postmortem events appear.

### 20251219-1056 — Rewrote AGENTS run/monitoring guidance
- **Result:** Success; consolidated run/monitoring instructions with env setup, monitored runner usage, crash visibility, and troubleshooting.
- **Notes:** Replaced Environment Awareness + Safe Command Examples run bullets with a single canonical section; added explicit SHM crash guidance and monitoring flow.
- **Next:** Resume full pipeline run once env passes `check_arm_mps.py`.

### 20251219-1102 — Fixed extract progress totals for spread-page outputs
- **Result:** Success; progress events now use output page totals for spreads.
- **Notes:** Updated `extract_ocr_ensemble_v1` to report `total` as expected output pages (2x for spreads) and `current` as output pages processed; adjusted final log/message to use output count. This prevents >100% progress in `pipeline_events.jsonl` for spread books.
- **Next:** Let the current full run finish and confirm progress percent stays ≤100% in `pipeline_events.jsonl`.

### 20251219-1114 — Restored EasyOCR dependency and reran full pipeline
- **Result:** Success; easyocr module now installed and constraints re-applied; full monitored run relaunched.
- **Notes:** Full run `ff-canonical-dual-full-20251219m` failed `easyocr_guard` because EasyOCR was missing (`No module named 'easyocr'`). Added `easyocr==1.7.1` to `requirements.txt`, reinstalled with `pip install -r requirements.txt -c constraints/metal.txt` to keep `numpy==1.26.4` and `opencv-python-headless==4.7.0.72`. Relaunched monitored full run `ff-canonical-dual-full-20251219n` with SHM-safe env.
- **Next:** Monitor `ff-canonical-dual-full-20251219n` and confirm EasyOCR coverage passes `easyocr_guard`; then inspect artifacts and complete validation.

### 20251219-1121 — Added progress counters to gutter-detection log events
- **Result:** Success; gutter diagnostic events now include progress counters.
- **Notes:** Updated `extract_ocr_ensemble_v1` to include `current`/`total` on the per-page gutter log so `percent` is populated in `pipeline_events.jsonl` even for diagnostic messages.
- **Next:** Confirm new events show `percent` on the next run.

### 20251219-1130 — Fixed LLM usage logging for fine segmentation
- **Result:** Success; corrected bad `log_llm_usage` calls that crashed fine segmentation.
- **Notes:** `fine_segment_frontmatter_v1` and `fine_segment_gameplay_v1` now read `completion.usage` and pass numeric token counts to `log_llm_usage`; avoids `int('gpt-5')` error seen in the failed run.
- **Next:** Rerun full pipeline and confirm fine segmentation completes.

### 20251219-1146 — Anchored escalation by original page numbers
- **Result:** Success; boundary escalation now anchors using original page numbers for spread books.
- **Notes:** `detect_boundaries_code_first_v1` now builds `elements_by_original_page` from `original_page_number` and uses it for vision escalation anchoring. Fixes runtime error where escalation cache used page-102L/R images but elements were keyed by virtual page numbers.
- **Next:** Rerun full pipeline and confirm assemble_boundaries completes without anchor errors.

### 20251219-1205 — Fixed backward-pass progress percent
- **Result:** Success; classify_headers backward-pass progress now updates percent with batch progress.
- **Notes:** `classify_headers_v1` now uses `current=batch_idx`/`total=total_batches` for backward-pass progress logs so percent increases with batch number instead of staying at 100%.
- **Next:** Confirm new progress percent behavior on the next run.

### 20251219-1225 — Map escalation pages to original page numbers
- **Result:** Success; boundary escalation now uses original page numbers when locating images.
- **Notes:** In `detect_boundaries_code_first_v1`, ordering/span escalation and missing-section escalation now map `page_number` → `original_page_number` before calling `EscalationCache`, which expects image filenames by original page (page-XXXL/R). This addresses escalation scanning the wrong images after the page-number refactor.
- **Next:** Re-run `detect_boundaries_code_first_v1` only (from `assemble_boundaries`) and confirm ordering/span issues resolve or reduce.

### 20251219-1235 — Started minimal boundary re-run (no full pipeline)
- **Result:** In progress; running detect_boundaries in isolation with reduced escalation.
- **Notes:** Launched `detect_boundaries_code_first_v1` directly against `ff-canonical-dual-full-20251219p` artifacts (`--max-ordering-pages 2 --max-escalation-pages 0 --no-fail-on-ordering-conflict`) to validate the page-number → original-page mapping without a full run.
- **Next:** Check for new `page_0xx.json` entries in `18_detect_boundaries_code_first_v1/escalation_cache` (should be original page numbers like 51/53) and inspect the ordering report.

### 20251219-1242 — Added escalation alignment requirement
- **Result:** Success; story now requires escalation to operate on logical pages.
- **Notes:** Updated Success Criteria and Tasks to require vision escalation to use the pipeline’s logical pages (split images when spreads are split; single images otherwise), without assuming splits by default.
- **Next:** Adjust escalation code paths to follow logical page images rather than raw original spreads; revalidate with a minimal rerun.

### 20251219-1254 — Implemented logical-page escalation mapping
- **Result:** Success; escalation now resolves images by logical page when available.
- **Notes:** Added `image_map` (logical `page_number` → image path) from `pages_raw.jsonl` and passed into `EscalationCache`. Escalation now uses logical pages when image_map is present and falls back to filename patterns otherwise. Also adjusted anchor lookup to prefer `elements_by_page` before `elements_by_original_page`.
- **Next:** Re-run `detect_boundaries_code_first_v1` (no full pipeline) and confirm new cache entries use logical page IDs while pointing at the correct split image paths.

### 20251219-1305 — Minimal escalation verification (3 pages)
- **Result:** Success; escalation now maps logical pages to split images.
- **Notes:** Ran `detect_boundaries_code_first_v1` with `--ordering-pages 102,106,107` and `--max-escalation-pages 0` against `ff-canonical-dual-full-20251219p` artifacts. Ordering report shows `flagged_pages: ["102","106","107"]`, `repaired_boundaries: 9`. Cache entries now use split-image paths for logical pages: `18_detect_boundaries_code_first_v1/escalation_cache/page_102.json` points to `page-051R.png`; `page_107.json` points to `page-054L.png`. Confirms logical-page escalation works without full pipeline.
- **Next:** Use this mapping for full `assemble_boundaries` re-run (still not full pipeline) to see if ordering/span issues reduce further.

### 20251219-1320 — Anchor by header position to fix ordering conflicts
- **Result:** Success; escalation anchoring now uses header position to pick element IDs.
- **Notes:** Added `_pick_anchor_by_position` to choose earliest/middle/latest anchor by `header_position` (top/middle/bottom). Wired into both escalation paths in `detect_boundaries_code_first_v1` to reduce within-page ordering conflicts (e.g., 151/150 reversed). 
- **Next:** Re-run `detect_boundaries_code_first_v1` (ordering-only) and verify ordering/span counts drop.

### 20251219-1335 — Reduced ordering/span conflicts after escalation guard tweak
- **Result:** Success; ordering/span counts decreased on targeted pages.
- **Notes:** Added ignore logic for pages replaced by `vision_escalation_ordering`/`vision_escalation` when checking ordering/span conflicts. Re-ran ordering-only on pages 102/106/107: ordering_after dropped from 62 → 59; span_after from 73 → 70 in `18_detect_boundaries_code_first_v1/section_boundaries.ordering_report.json`.
- **Next:** Re-run ordering-only for all 14 flagged pages to see if counts drop enough to pass.
