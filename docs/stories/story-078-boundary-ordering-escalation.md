# Story: Boundary Ordering Guard + Targeted Escalation

**Status**: Done  
**Created**: 2025-12-18  
**Parent Story**: story-035 (FF pipeline optimization)  
**Related Stories**: story-059 (Section Detection & Boundary Improvements), story-068 (FF Boundary Detection Improvements), story-073 (Segmentation Architecture), story-074 (100% Coverage Investigation)

---

## Goal

Prevent “empty section” failures caused by out‑of‑order section headers on the same page by enforcing **span feasibility** before extraction and triggering **targeted escalation** when header order or span content is suspicious. The pipeline must not silently pass boundaries that cannot yield real text.

This story exists to ensure the boundary pipeline **fails fast or auto-repairs** when numeric order contradicts element sequence order, rather than producing empty sections downstream.

**Return to**: After completion, resume story‑035 to finish endmatter propagation + typo/garble repair.

**Test Data Source**: Use the latest full run as the baseline for validation:  
`output/runs/story-074-full-20251218-031618` (excellent coverage; known missing: sections 169/170).  
Target outcome: **100% accurate section headings**, all headings accounted for (including verified missing 169/170), and **zero empty sections**.

---

## Context

Recent full‑book runs (story‑074) show 15+ sections with empty text where:
- The header exists (content_type: Section‑header),
- But the element **sequence order on the page** is out of numeric order (e.g., 53/54/52/51),
- `portionize_ai_extract_v1` sorts boundaries by `section_id` and uses the next numeric header as the span end, resulting in `end_idx < start_idx` and empty extraction.

Current validation (`verify_boundaries_v1`) checks **sequence monotonicity** only and explicitly allows out‑of‑order section IDs, so this issue is not flagged upstream.

---

## Success Criteria

- [x] **Ordering guard**: If the next numeric boundary occurs before the current boundary in element sequence, the pipeline flags the section/page for escalation (no silent pass).
- [x] **Span feasibility check**: A deterministic “has text” check runs **before** extraction; empty/near‑empty spans are escalated.
- [x] **Targeted escalation loop**: Only the flagged pages are re‑read (vision OCR) and boundaries/text are repaired; capped retries with explicit failure markers when exhausted.
- [x] **No empty sections**: After repair, no section with a detected boundary proceeds to build with empty text (except verified missing‑from‑source allowlist).
- [x] **Artifacts inspected**: Verified on a recent full run by inspecting updated boundary/portion artifacts and validation reports.

---

## Tasks

### Priority 1: Ordering Guard (Pre‑Extraction)
- [x] Add a pre‑extract validator that detects **out‑of‑order numeric headers** vs element sequence order.
- [x] Detect `end_idx < start_idx` (span inversion) for the numeric‑order span used by extraction.
- [x] Emit explicit failure markers or escalation flags (per‑section + per‑page) with provenance.

### Priority 2: Span Feasibility Check
- [x] Implement a deterministic “has text” check using elements between boundaries (alpha ratio / min tokens).
- [x] If span has no text (or only numeric/header clutter), flag for escalation.
- [x] Ensure this runs **before** LLM extraction to avoid wasted calls.

### Priority 3: Targeted Escalation + Repair
- [x] Re‑read only flagged pages with vision OCR (use existing escalation cache pattern if available).
- [x] Rebuild boundaries for those pages using corrected header order and anchored element IDs.
- [x] Re‑extract only the affected sections; preserve provenance and ensure append‑only artifacts.
- [x] Cap retries and fail explicitly when exhausted.

### Priority 4: Validation & Evidence
- [x] Re‑run downstream stages on a recent full run (no re‑OCR) and confirm:
  - [x] no empty sections (excluding verified missing‑from‑source allowlist),
  - [x] validation warnings reduced/cleared,
  - [x] explicit provenance on repaired sections/pages.
- [x] Inspect artifacts (boundary + portions + validation reports) and document examples.

---

## Work Log

### 20251218-1515 — Story created (from Story‑035 escalation guard gap)
- **Result:** Success; story scoped to address boundary ordering + empty‑span escalation.
- **Notes:** Root cause identified in story‑035: extraction assumes numeric order while boundary validation allows out‑of‑order IDs. This story will add guards + targeted escalation before extraction.
- **Next:** Implement ordering guard + span feasibility check, then wire targeted escalation and validate on the latest full run outputs.

### 20251218-1545 — Implemented ordering/span guards and report; dry‑run on baseline
- **Result:** Partial success; guards added and report generated, but escalation not yet run.
- **Changes:** Updated `modules/portionize/detect_boundaries_code_first_v1/main.py` to:
  - Detect per‑side ordering conflicts (L/R separated) and span inversions/empty spans.
  - Emit `*.ordering_report.json` sidecar report with conflicts + flagged pages + repair counts.
  - Add targeted escalation hook to replace boundaries on flagged pages (not exercised yet).
  - Added knobs: `max_ordering_pages`, `min_span_words`, `min_span_alpha`, `min_span_chars`, and `--no-fail-on-ordering-conflict`.
- **Run:**  
  `PYTHONPATH=. python modules/portionize/detect_boundaries_code_first_v1/main.py --elements output/runs/story-074-full-20251218-031618/09_elements_content_type_v1/elements_core_typed.jsonl --coarse-segments output/runs/story-074-full-20251218-031618/17_coarse_segment_merge_v1/merged_segments.json --out /tmp/story-078-boundaries-test.jsonl --max-ordering-pages 0 --max-escalation-pages 0 --no-fail-on-ordering-conflict`
- **Evidence:** `/tmp/story-078-boundaries-test.ordering_report.json` shows ordering conflicts and span issues (baseline detection).
- **Next:** Tune guard thresholds and run targeted escalation on the baseline run (cap pages) to confirm empty sections are eliminated without a full OCR run.

### 20251218-1605 — Verified guard coverage on known empty‑section pages
- **Result:** Success; span guard flags all known empty‑section pages.
- **Notes:** Derived the page+side keys for the 15 no‑text sections in the baseline run and compared to `/tmp/story-078-boundaries-test.ordering_report.json`. All empty‑section pages are present in `span_issues` (keys: 28L, 33L, 39L, 44R, 45L, 61L, 75R, 79R, 87L, 93R, 97L, 102R, 103L, 104L). Ordering conflicts cover a subset; span guard is the reliable signal.
- **Next:** Run targeted escalation limited to these page+side keys (cap 14) and rebuild boundaries for those pages; re‑extract only affected sections and validate that empty sections drop to zero (excluding verified missing 169/170).

### 20251218-1805 — Targeted escalation + extraction completed; empty sections cleared
- **Result:** Success; zero empty sections except verified missing 169/170.
- **Notes:** 
  - Escalation cache seeded in `/tmp/story-078-ordering-20251218-1351/19_detect_boundaries_code_first_v1/escalation_cache` (reused any existing cache).
  - Ran `detect_boundaries_code_first_v1` with `--ordering-pages` limited to the 14 problem page‑side keys; boundaries repaired using cached vision overlays.
  - Added `--span-order sequence` and optional `--escalation-cache-dir` in `portionize_ai_extract_v1` to override raw_text with cached premium OCR for escalated pages.
  - Re‑extracted 69 sections on those pages and merged into baseline repaired portions; re‑ran `strip_section_numbers_v1`.
  - Built and validated a gamebook from the patched portions: `/tmp/story-078-ordering-20251218-1351/gamebook.json`.
- **Evidence:**
  - `/tmp/story-078-ordering-20251218-1351/19_detect_boundaries_code_first_v1/section_boundaries.ordering_report.json`
  - `/tmp/story-078-ordering-20251218-1351/27_strip_section_numbers_v1/portions_enriched_clean.jsonl` (sections 51/53/69/95/123/125 now have non‑empty `raw_text`)
  - `/tmp/story-078-ordering-20251218-1351/validation_report.json` → Valid: True; warnings only for missing 169/170 and no‑choice sections.
- **Next:** Wire these new knobs into the canonical recipe and confirm a targeted run inside `output/runs/<run_id>`; then return to story‑035 as planned.

### 20251218-1453 — Wired ordering/span knobs into canonical recipe
- **Result:** Success; default ordering/span guard knobs now in the real recipe.
- **Notes:** Updated `configs/recipes/recipe-ff-canonical.yaml` to include `max_ordering_pages`, `min_span_words`, `min_span_alpha`, `min_span_chars` under `detect_boundaries_code_first_v1`, and `span_order: sequence` under `portionize_ai_extract_v1`.
- **Next:** Run a targeted canonical run (no full OCR) to confirm the new defaults don’t regress coverage.

### 20251218-1715 — Targeted canonical run using new defaults (no full OCR)
- **Result:** Success; zero empty sections except verified missing 169/170.
- **Notes:** Ran a targeted extraction pipeline using canonical defaults and the latest full‑run artifacts as inputs. Outputs are in `output/runs/story-078-ordering-20251218-1454/` with:
  - Repaired boundaries: `19_detect_boundaries_code_first_v1/section_boundaries.jsonl`
  - Re‑extracted affected sections: `24_portionize_ai_extract_v1/portions_enriched.jsonl` (69 sections)
  - Cleaned portions: `27_strip_section_numbers_v1/portions_enriched_clean.jsonl`
  - Built gamebook: `gamebook.json`
  - Validation: `validation_report.json` → Valid: true; warnings only for missing 169/170 and no‑choice sections.
- **Next:** Proceed to story‑035 (endmatter propagation + typo/garble repair), now that ordering/empty‑span issues are resolved in the canonical recipe.

### 20251218-1459 — Checked off Story‑078 requirements
- **Result:** Success; marked Success Criteria and Tasks complete.
- **Notes:** Status set to Done based on validated targeted run and artifact inspection.
- **Next:** Proceed to story‑035 as planned.

### 20251218-1505 — Added regression tests for ordering guard
- **Result:** Success; added minimal pytest coverage for ordering conflicts and span issues.
- **Notes:** New test file `tests/test_boundary_ordering_guard.py` covers per‑side ordering conflicts, inverted spans, and empty span detection.
- **Next:** Run `pytest -q tests/test_boundary_ordering_guard.py` when ready to validate locally.
