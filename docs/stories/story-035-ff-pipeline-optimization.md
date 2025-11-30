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

