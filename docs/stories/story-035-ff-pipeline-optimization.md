# Story: Fighting Fantasy Pipeline Optimization

**Status**: Open  
**Created**: 2025-11-30  
**Parent Story**: story-031 (pipeline redesign - COMPLETE)

---

## Goal

Optimize the redesigned Fighting Fantasy pipeline to achieve near-perfect section recall and improve data quality. The core pipeline architecture is complete and working (story-031), but there are remaining optimization opportunities.

**Current Baseline** (from story-031 completion):
- 232 sections detected (vs 216 baseline) - **+16 sections**
- 24 missing sections (vs 50 baseline) - **26 fewer missing!**
- 157 sections with no text (vs 177 baseline) - **20 fewer empty sections**
- 67 gameplay sections with no choices

**Target**: Reduce missing sections to <10, empty sections to <50, improve choices detection.

---

## Success Criteria

- [ ] Missing sections reduced to <10 (currently 24)
- [ ] Empty sections reduced to <50 (currently 157)
- [ ] Choices detection improved (currently 67 sections with no choices)
- [ ] Validation passes (currently fails due to missing sections)
- [ ] All improvements verified by manual artifact inspection

---

## Tasks

### Priority 1: Improve Section Recall

**Missing Sections** (24 total): 11, 46, 68, 153, 158, 159, 169, 227, 273, 278, 281, 296, 303, 314, 329, 337, 338, 339, 346, 350, 355, 359, 367, 375

- [ ] **Investigate missing sections**:
  - [ ] Check if these sections exist in `elements_core.jsonl`
  - [ ] Check if they're detected in `header_candidates.jsonl` but filtered out in Stage 2
  - [ ] Identify patterns (page breaks, special formatting, edge cases)
  - [ ] Document root causes with evidence

- [ ] **Improve Stage 1 detection**:
  - [ ] Analyze why specific sections aren't detected
  - [ ] Refine prompts if needed (but keep them simple per AGENTS.md guidance)
  - [ ] Consider edge cases (colon prefixes, page breaks, special formatting)

- [ ] **Improve Stage 2 filtering**:
  - [ ] Review why candidates might be filtered out
  - [ ] Ensure Stage 2 isn't being too conservative
  - [ ] Verify uncertain sections are handled correctly

- [ ] **Add targeted detection** (if needed):
  - [ ] Consider a "backfill" stage to catch missed sections
  - [ ] Or improve Stage 1/2 to catch edge cases
  - [ ] Implement gap-based backfill module: given consecutive detected sections, ask LLM to scan the interstitial elements/text to find missing headers (e.g., 43-46 block hides 46). Insert boundaries without disturbing confirmed ones.

### Priority 2: Address Empty Sections

**157 sections with no text** - Investigate why sections are created without text content.

- [ ] **Investigate root causes**:
  - [ ] Check if boundaries are correct but extraction fails
  - [ ] Check if boundaries are wrong (pointing to empty elements)
  - [ ] Verify these aren't false positives from Stage 2

- [ ] **Fix boundary detection** (if needed):
  - [ ] Ensure boundaries point to elements with actual text
  - [ ] Verify end_seq calculations are correct

- [ ] **Fix extraction** (if needed):
  - [ ] Ensure Stage 6 (ai_extract) properly extracts text
  - [ ] Verify text isn't being lost in transformation

### Priority 2c: Typo / garble repair

- [ ] Add a post-extraction typo repair pass for sections with garbled text (e.g., section 277) that prefers re-reading from source OCR/page snippets over guessing.
- [ ] Heuristic triage: flag sections with low alpha ratio, excessive non-words, or very short text for repair.
- [ ] Repair strategy: (a) re-OCR snippets if available, then (b) use LLM with page text/image context and strict “do not invent” prompt to normalize spelling while keeping semantics.
- [ ] Validate on sample garbled sections (44, 277, 381) to ensure readability improves without content drift.

### Priority 2b: Strip section/page numbers from text while keeping structure

- [ ] Ensure final `text` fields do **not** include section numbers or page-number artifacts (e.g., "47-50" headers), while preserving paragraph breaks and legitimate in-text numbers.
- [ ] Keep section numbers in structured JSON fields (e.g., `section`, `id`) but not in `text` content.
- [ ] Build this as a **dedicated cleanup module** (not jammed into existing extraction) to avoid harming primary extraction quality.
- [ ] Validate on sample outputs that numbering is removed and paragraph integrity (no spurious newlines) is retained.

### Priority 3: Improve Choices Detection

**67 gameplay sections with no choices** - May be legitimate dead ends, but should verify.

- [ ] **Investigate**:
  - [ ] Check if these are actually dead ends (endings, deaths, etc.)
  - [ ] Or if choices aren't being detected properly
  - [ ] Sample 10-20 sections to verify

- [ ] **Improve extraction** (if needed):
  - [ ] Refine Stage 6 prompts to better detect choice patterns
  - [ ] Consider edge cases (conditional choices, test-your-luck, etc.)

### Priority 4: Validation & Quality

- [ ] **Achieve validation pass**:
  - [ ] Reduce missing sections to <10
  - [ ] Ensure all validation checks pass
  - [ ] Verify no critical errors

- [ ] **Quality improvements**:
  - [ ] Reduce empty sections to <50
  - [ ] Improve text quality (no mid-sentence starts, proper formatting)
  - [ ] Ensure all extracted data is accurate

---

## Artifacts for Reference

**Baseline Run** (ff-redesign-v2-improved):
- `output/runs/ff-redesign-v2-improved/elements_core.jsonl` - Reduced IR (1153 elements)
- `output/runs/ff-redesign-v2-improved/header_candidates.jsonl` - Header classifications (239 unique sections)
- `output/runs/ff-redesign-v2-improved/sections_structured.json` - Global structure (232 certain sections)
- `output/runs/ff-redesign-v2-improved/section_boundaries.jsonl` - Section boundaries (232 boundaries)
- `output/runs/ff-redesign-v2-improved/portions_enriched.jsonl` - Extracted gameplay data (232 sections)
- `output/runs/ff-redesign-v2-improved/gamebook.json` - Final gamebook output (376 sections)
- `output/runs/ff-redesign-v2-improved/validation_report.json` - Validation report

**Previous Baseline** (ff-redesign-v2):
- `output/runs/ff-redesign-v2/gamebook.json` - Baseline output (350 sections, 50 missing)
- `output/runs/ff-redesign-v2/validation_report.json` - Baseline validation

---

## Notes

- **Keep prompts simple**: Per AGENTS.md guidance, trust AI intelligence rather than over-engineering
- **Verify artifacts**: Always inspect actual output files, not just metrics
- **Evidence-driven**: Document root causes with specific examples from artifacts
- **Incremental**: Make small improvements, verify, iterate

---

## Work Log

### 2025-11-30 — Story Created

**Status**: Story created to track optimization work after story-031 completion.

**Context**: Story-031 achieved core goals (pipeline redesign complete, significant improvements). Remaining work is optimization/fine-tuning, better suited for a focused story.

**Baseline Established**:
- 24 missing sections (down from 50)
- 157 empty sections (down from 177)
- 67 sections with no choices
- Validation still fails but significantly improved

**Next Steps**: Begin Priority 1 - investigate missing sections to understand root causes.

### 20251129-2320 — Initial artifact triage on missing sections
- **Result:** Partial success; located several failure points in section detection.
- **Findings:** Of 24 missing sections, only 7 show up as standalone numeric elements in `elements_core.jsonl` (46, 68, 153, 158, 159, 169, 296). Only section 169 appears in `header_candidates.jsonl` (seq 1236, page 103) but is not present in `section_boundaries.jsonl`, indicating Stage 2 filtering dropped it. The rest of the missing list is absent from `header_candidates`. Many IDs (11, 227, 273, 278, 281, 303, 314, 329, 337, 338, 339, 346, 350, 355, 359, 367, 375) are not even present as digit-only elements in `elements_core`, suggesting OCR/IR loss. Spot checks show clear headers that were missed: page 26 has `43-46` grouping with a standalone `46`; page 32 has `67-68` grouping with standalone `68` and full text; page 52 has `152-153` with standalone `153`; page 84 shows `296`; page 103 shows `169`.
- **Next:** 1) Investigate why Stage 1 missed obvious numeric headers (e.g., 46/68/153/296) despite clean OCR; try extracting page-level text passed to the model and review prompts/thresholds. 2) For numbers absent from `elements_core`, inspect raw OCR (`elements.jsonl`) and page images to determine if numbers were dropped or merged; consider adding a light heuristic to surface isolated numeric spans before Stage 1. 3) Re-run Stage 2 logic on section 169 to see why it was filtered out.

### 20251129-2324 — Captured new requirement on text cleanliness
- **Result:** Recorded requirement to strip section/page numbers from final `text` while preserving paragraphs and structured section IDs.
- **Notes:** Added Priority 2b tasks: remove leading section numbers and page-number artifacts (e.g., "47-50" headers), avoid extra newlines, keep section numbers in metadata. Need to decide between extending extraction prompt vs dedicated cleanup stage to avoid degrading main extraction quality.
- **Next:** Prototype a cleanup stage that operates post-extraction to remove numeric headers and normalize paragraphs; validate on sample outputs.

### 20251129-2326 — Strategy update and module plan
- **Result:** Adopted policy to ship new behavior as a separate module first, baseline it, then merge only after comparing baselines; added this guidance to AGENTS.md.
- **Notes:** Priority 2b now explicitly requires a dedicated cleanup module (no prompt jamming) to strip section/page numbers and normalize paragraphs.
- **Next:** Design cleanup module interface (inputs/outputs), choose stage placement (post `ai_extract`), and draft baseline plan (run standalone, then merged) for comparison.

### 20251129-2335 — Built cleanup module & first baseline
- **Result:** Created `modules/clean/strip_section_numbers_v1` (stage: clean) with module.yaml + main.py. Runs post-`portions_enriched` to remove section/page numbers and collapse extra blank lines while preserving paragraphs.
- **Run:** `PYTHONPATH=. python modules/clean/strip_section_numbers_v1/main.py --portions output/runs/ff-redesign-v2-improved/portions_enriched.jsonl --out /tmp/portions_enriched_clean.jsonl`
- **Observations:** After cleanup, zero sections start with numeric header clutter (down from dozens). Section 1 text keeps paragraph breaks; section 331 header gibberish stripped to start at narrative. Residual OCR noise remains (e.g., misspelled words) but numbering artifacts removed. Source list now includes module tag.
- **Next:** Integrate module into a recipe after `portionize_ai_extract_v1`, produce a named run for comparison vs original, and sample-check that no legitimate leading numerals (e.g., quantities) were lost.

### 20251129-2338 — Integrated cleanup into pipeline + catalog
- **Result:** Added new recipe `configs/recipes/recipe-ff-redesign-v2-clean.yaml` inserting `strip_section_numbers_v1` after `ai_extract`; updated module catalog to register the module under `clean` with `cyoa` capability.
- **Run:** Produced a persistent cleaned artifact using existing baseline output: `PYTHONPATH=. python modules/clean/strip_section_numbers_v1/main.py --portions output/runs/ff-redesign-v2-improved/portions_enriched.jsonl --out output/runs/ff-redesign-v2-improved/portions_enriched_clean.jsonl` (no re-OCR/LLM cost). Zero sections now begin with numeric clutter.
- **Observations:** Samples: section 1 starts directly with prose; section 331 now begins at narrative (header numbers removed). Remaining OCR noise (typos) untouched by this stage by design.
- **Next:** Execute full clean recipe run (`recipe-ff-redesign-v2-clean.yaml`) to compare validation and text quality vs original; spot-check that genuine leading numerals (quantities) remain.

### 20251130-0000 — Gibberish scrub + created_at removal
- **Result:** Enhanced `strip_section_numbers_v1` to drop gibberish/separator lines and strip `created_at` if empty. Upstream `portionize_ai_extract_v1` now writes enriched portions with `exclude_none=True`, removing null `created_at` entirely.
- **Run:** Re-ran cleaner on baseline: `PYTHONPATH=. python modules/clean/strip_section_numbers_v1/main.py --portions output/runs/ff-redesign-v2-improved/portions_enriched.jsonl --out /tmp/portions_enriched_clean.jsonl` → section 44 gibberish reduced to empty (all noise dropped); sections now free of leading numbers and dash separators; no `created_at` keys present.
- **Observations:** Remaining issues to consider: section 277 still has heavily garbled text; section 381 retains OCR typos (“roo pounds”), and some sections still empty after gibberish removal (e.g., 44). These may require upstream OCR/LLM re-extract rather than heuristic cleaning.
- **Next:** Run the full clean recipe to produce a fresh run; compare `portions_enriched` vs `portions_enriched_clean` on 10–15 sections for legitimate leading numerals and note any overzealous removals; decide if further OCR correction (clean_llm_v1) should be inserted.

### 20251129-2347 — Clean build/validate attempt
- **Result:** Could not run full recipe due to OpenMP SHM permission error in intake; workaround: reused baseline artifacts, built cleaned gamebook manually.
- **Run:** `PYTHONPATH=. python modules/export/build_ff_engine_v1/main.py --portions /tmp/portions_enriched_clean.jsonl --out output/runs/ff-redesign-v2-clean/gamebook.json --title "Deathtrap Dungeon" --author "Ian Livingstone" --start_section 1 --format_version 1.0.0` then `PYTHONPATH=. python modules/validate/validate_ff_engine_v2/main.py --gamebook output/runs/ff-redesign-v2-clean/gamebook.json --out output/runs/ff-redesign-v2-clean/validation_report.json --expected-range-start 1 --expected-range-end 400`.
- **Observations:** Validation still failing: 24 sections missing (same set as baseline), 184 sections with no text, 67 sections without choices. Clean stage successfully removed `created_at` and numeric clutter but didn’t fix upstream missing/garbled content. Section 44 now empty after gibberish removal; section 277 still garbled; numeric headers gone globally.
- **Next:** Need to resolve intake OpenMP SHM issue or rerun using existing elements; investigate upstream missing sections (Stage 1/2) and OCR quality; consider inserting clean_llm_v1 before extraction for heavily garbled portions.

### 20251129-2350 — Plan to recover missing sections
- **Result:** Decided on gap-based backfill module instead of over-tuning header detector. Idea: for each missing section number between two detected sections, feed the elements/text span to LLM and ask it to locate the missing header and boundary; add synthetic boundary without altering existing ones.
- **Notes:** Missing sections likely fused into neighbors (e.g., 43–46 block). Backfill can operate after `assemble_boundaries` using `elements_core` to avoid re-OCR. Will keep Stage 1/2 untouched to preserve their improved recall while supplementing gaps.
- **Next:** Design `adapter/backfill_missing_sections_v2` (or similar) that: (1) identifies numeric gaps, (2) extracts span between adjacent boundaries, (3) LLM finds header and start element id, (4) emits patched `section_boundaries.jsonl`. Then rerun extract + cleanup + validation.

### 20251129-2352 — Typo/garble repair plan
- **Result:** Captured need for a typo/garble repair pass. Will target sections flagged by heuristics (low alpha ratio, very short text, many non-words) and prefer re-reading source OCR/page snippets over free-form guessing.
- **Notes:** Candidate strategy: re-OCR span (if images available) and/or use an LLM with strict "do not invent" prompt plus local context (page text, optional image) to normalize spelling. Test on known bad sections (44, 277, 381).
- **Next:** Prototype a repair module after cleanup: input `portions_enriched_clean.jsonl`, output repaired portions; compare before/after readability while ensuring choices/targets unchanged.

### 20251130-0006 — Backfill module v2 + partial recovery
- **Result:** Built `modules/adapter/backfill_missing_sections_v2` (digit-hit based boundary backfill) and registered in module_catalog. Added `--target-ids` filter to constrain backfill to known missing list.
- **Run:** Backfilled boundaries for missing list (24 ids) using elements_core hits → added 7 boundaries (46, 68, 153, 158, 159, 169, 296). Re-extracted with new boundaries (`portionize_ai_extract_v1`, 239 sections) → cleaned → built gamebook → validation: 379 sections, 21 missing (down from 24). Warnings: 185 no-text, 57 no-choices.
- **Observations:** Missing list now: 11, 96, 103, 127, 227, 273, 281, 300, 312, 314, 329, 337, 338, 339, 346, 350, 355, 359, 367, 375, + one more (see validation file). Several new gaps (96, 103, 127, 300, 312) were not on the original 24, suggesting some numbers never present in boundaries; need gap-driven LLM backfill next.
- **Next:** Implement gap-based LLM backfill (uses interstitial elements) to target remaining 21 missing; also address no-text sections via typo/garble repair or re-OCR. Fix intake SHM to rerun full pipeline on clean recipe.

### 20251130-0020 — LLM gap backfill attempt
- **Result:** Added `backfill_missing_sections_llm_v1` (gap-based, LLM) and ran it on the digit-backfilled boundaries. LLM added 38 boundaries; re-extracted (277 sections), cleaned, built, validated.
- **Run outputs:**
  - Boundaries: `/tmp/section_boundaries_backfilled_llm.jsonl`
  - Portions: `/tmp/portions_enriched_backfilled_llm.jsonl` → cleaned → `/tmp/portions_enriched_backfilled_llm_clean.jsonl`
  - Gamebook: `/tmp/gamebook_backfilled_llm.json`
  - Validation: `/tmp/validation_backfilled_llm.json`
- **Metrics:** Sections=382 (up from 379). Missing sections now 18 (was 21). No-text sections reduced to 163 (from 185). No-choice sections increased to 65 (from 57) — possibly due to added stubs lacking choices.
- **Remaining missing:** 11, 39, 127, 227, 273, 281, 300, 312, 314, 337, 338, 339, 346, 350, 355, 359, 393, 399 (per validation file).
- **Notes:** LLM gap backfill improved coverage but still leaves 18 missing and many empty sections. Need a more targeted approach: inspect spans for the remaining gaps (e.g., 11/39/127) and possibly re-OCR/LLM with images. Also need typo/garble repair to reduce no-text counts.

### 20251130-0037 — Partial success & handoff
- **Result:** Pipeline improved to 382 sections (18 missing), numeric clutter removed, but OCR loss blocks full recall; many sections still empty/garbled. Declaring partial success for story-035 and spinning remaining work into new story-036 (OCR recovery & text repair).
- **Notes:** Remaining issues: recover missing IDs (11, 39, 127, 227, 273, 281, 300, 312, 314, 337, 338, 339, 346, 350, 355, 359, 393, 399); reduce 163 no-text sections; fix intake OpenMP SHM issue; add typo/garble repair; re-OCR or multimodal header hunt on gap spans.
- **Next:** Track follow-up in story-036; keep current best artifacts noted above as baseline.
### 20251129-2318 — Story review and plan kickoff
- **Result:** Reviewed story format; Tasks section already present and actionable, no structural edits needed.
- **Notes:** Priorities and success criteria are clear. Immediate focus should be evidence gathering on missing sections list using existing artifacts from `ff-redesign-v2-improved` run.
- **Next:** Pull sample rows for a few missing sections from `elements_core.jsonl` and `header_candidates.jsonl` to map where detection fails (Stage 1 vs Stage 2).
