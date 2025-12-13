# Story: Fighting Fantasy Boundary Detection Improvements

**Status**: Active
**Created**: 2025-12-13
**Updated**: 2025-12-13
**Parent Story**: story-035 (pipeline optimization - PAUSED)

---

## Goal

Improve section boundary detection coverage in the Fighting Fantasy pipeline from 87% (348/400) to >95% (380+/400). The extraction quality is proven excellent (99% success rate), but boundary detection is the bottleneck preventing full section recall.

**Current Baseline** (from story-035):
- **Boundary detection:** 348/400 (87% coverage)
- **Extraction success:** 345/348 (99% - only 3 failed)
- **Missing sections:** 52 total
  - 9 completely missing (no boundaries detected): 9, 90, 91, 95, 174, 183, 211, 347, 365
  - 43 additional sections flagged as stubs (boundaries exist but weak/problematic)
  - 3 sections with boundaries but extraction failed: 23, 166, 203

**Target**: Reduce missing sections to <20, achieve >95% boundary detection coverage.

---

## Success Criteria

- [ ] Boundary detection coverage >95% (380+/400 sections)
- [ ] Missing sections reduced to <20 (currently 52)
- [ ] Completely missing sections addressed (currently 9)
- [ ] Validation passes with minimal gaps
- [ ] Improvements verified by manual artifact inspection

---

## Tasks

### Priority 1: Investigate Missing Sections

**9 completely missing sections**: 9, 90, 91, 95, 174, 183, 211, 347, 365

- [ ] **Check upstream presence**:
  - [ ] Verify these sections exist in source PDF images
  - [ ] Check if section numbers appear in `elements_core.jsonl`
  - [ ] Check if detected in `header_candidates.jsonl` but filtered in Stage 2
  - [ ] Document where detection breaks down for each section

- [ ] **Identify failure patterns**:
  - [ ] Are they clustered on specific pages?
  - [ ] Do they have special formatting (colon prefixes, unusual fonts)?
  - [ ] Are they at page boundaries or column breaks?
  - [ ] Do they lack clear numeric headers?

### Priority 2: Improve Detection Modules

- [ ] **Analyze header_candidates.jsonl**:
  - [ ] Check false negatives (sections in elements but not detected)
  - [ ] Check false positives (non-sections detected as sections)
  - [ ] Review confidence scores for missed sections
  - [ ] Identify prompt/logic improvements

- [ ] **Improve Stage 1 (classify_headers_v1)**:
  - [ ] Review prompt effectiveness for edge cases
  - [ ] Consider adding examples for tricky formats
  - [ ] Test on known missing sections
  - [ ] Validate improvements don't harm existing detection

- [ ] **Improve Stage 2 (structure_globally_v1)**:
  - [ ] Check if Stage 2 is being too conservative
  - [ ] Review filtering logic for "uncertain" sections
  - [ ] Ensure edge cases (90, 91, 95) aren't filtered out
  - [ ] Validate against ground truth

### Priority 3: Address Extraction Failures

**3 sections with boundaries but failed extraction**: 23, 166, 203

- [ ] **Investigate extraction failures**:
  - [ ] Check boundary definitions in `section_boundaries_merged.jsonl`
  - [ ] Verify elements exist between start/end boundaries
  - [ ] Check for element filtering issues (content_type)
  - [ ] Review extraction logs for these specific sections

- [ ] **Fix or document**:
  - [ ] If boundaries are wrong, improve boundary detection
  - [ ] If elements are missing, check filtering logic
  - [ ] If extraction logic fails, improve `portionize_ai_extract_v1`

### Priority 4: Validation & Testing

- [ ] **Create test harness**:
  - [ ] Script to check boundary detection coverage on known sections
  - [ ] Regression tests for currently-working sections
  - [ ] Spot-check tool for manual verification of improvements

- [ ] **Measure improvements**:
  - [ ] Run full pipeline with improved detection
  - [ ] Compare boundary count before/after
  - [ ] Verify no regressions in existing detection
  - [ ] Check extraction success rate remains >95%

---

## Baseline Artifacts

**Clean Run** (story-035, 2025-12-13):
- `output/runs/ff-canonical-20251213-121801-68047c/`
- `elements_core.jsonl` - Reduced IR with content_type filtering
- `header_candidates.jsonl` - Stage 1 header classifications
- `section_boundaries_merged.jsonl` - Final boundary set (348 boundaries)
- `portions_enriched.jsonl` - Extracted sections (345 sections)
- `validation_report.json` - Missing sections list

---

## Investigation Plan

1. **Forensic Analysis** (Priority 1)
   - Start with the 9 completely missing sections
   - Trace each through: PDF → elements_core → header_candidates → boundaries
   - Document exact failure point and reason

2. **Pattern Detection** (Priority 1)
   - Look for common characteristics in missing sections
   - Check for systematic issues (page breaks, formatting, OCR quality)

3. **Module Improvements** (Priority 2)
   - Based on patterns, improve detection prompts/logic
   - Test improvements on failing cases
   - Validate no regressions

4. **Full Pipeline Verification** (Priority 4)
   - Run complete pipeline with improvements
   - Verify boundary detection >95%
   - Confirm extraction still at >95%
   - Return to story-035 for final validation

---

## Notes

- **Keep prompts simple**: Per AGENTS.md guidance, trust AI intelligence rather than over-engineering
- **Verify artifacts**: Always inspect actual output files, not just metrics
- **Evidence-driven**: Document root causes with specific examples from artifacts
- **Incremental**: Make small improvements, verify, iterate
- **No regressions**: Ensure improvements don't break currently-working detection

---

## Work Log

### 20251213-1356 — Story created from story-035 handoff
- **Result:** Story initialized with clear scope and baseline.
- **Context:** Story-035 identified boundary detection as the bottleneck (87% coverage). Extraction quality is excellent (99% success), so focus is purely on improving boundary detection.
- **Baseline:** Clean run from 2025-12-13 with 348/400 boundaries detected, 345/348 extracted successfully.
- **Missing sections:**
  - 9 completely missing (no boundaries): 9, 90, 91, 95, 174, 183, 211, 347, 365
  - 43 with weak boundaries (stubs/flagged)
  - 3 with boundaries but extraction failed: 23, 166, 203
- **Target:** >95% boundary detection coverage (380+/400), <20 total missing.
- **Next:** Begin forensic analysis of the 9 completely missing sections - trace through artifacts to find exact failure points.
