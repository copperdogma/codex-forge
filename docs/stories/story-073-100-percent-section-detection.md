# Story: 100% Section Detection — Complete Coverage

**Status**: To Do
**Created**: 2025-12-15
**Parent Story**: story-070 (OCR Split Refinement - COMPLETE), story-068 (FF Boundary Detection - COMPLETE)

---

## Goal

Achieve **100% section detection** for Fighting Fantasy gamebooks. Current state: 377/400 sections detected (94.25% coverage). Target: 400/400 sections (100% coverage) with zero missing sections.

**Current Problem**:
- 19 sections still missing from final gamebook build (down from 42 in previous run)
- 31 sections missing from portions extraction (some may be frontmatter)
- Boundary detection improved from 355 to 377 (+22 sections, +6.2%) but still incomplete

**Root Cause Analysis**:
- Multiple failure modes identified across pipeline stages
- Some sections lost at `pick_best_engine_v1` (FIXED in story-070)
- Some sections lost at `detect_gameplay_numbers_v1` boundary detection (PARTIALLY FIXED in story-070)
- Some sections never appear in raw OCR (may be OCR corruption or truly missing)
- Some sections appear in boundaries but not in portions (extraction failure)

**Target**: 100% accuracy — every section (1-400) must be detected, extracted, and included in final gamebook.json.

---

## Success Criteria

- [ ] **100% boundary detection**: All 400 sections have boundaries in `section_boundaries_merged.jsonl`
- [ ] **100% portion extraction**: All 400 sections have portions in `portions_enriched_clean.jsonl`
- [ ] **100% gamebook coverage**: Final `gamebook.json` contains all 400 sections with no stubs
- [ ] **Zero false positives**: No duplicate sections or incorrect boundaries
- [ ] **Forensics complete**: All missing sections have diagnostic traces showing where they were lost

---

## Context

**Previous Improvements** (Story-070):
- Fixed `pick_best_engine_v1` to preserve numeric headers from curated lines array
- Fixed `detect_gameplay_numbers_v1` to bypass strict validation for high-confidence Section-headers
- Result: Improved from 355 to 377 boundaries (+22 sections, +6.2%)

**Current State** (from full run `ff-full-070-fixes-test`):
- Boundaries detected: 377/400 (94.25%)
- Portions extracted: 369/400 (92.25%)
- Gamebook sections: 381/400 (95.25%, 19 stubs required)
- Missing sections: 19 (down from 42 in previous run)

**Missing Sections Identified**:
- From boundaries: 23 sections missing
- From portions: 31 sections missing
- From gamebook: 19 sections missing (stub backfill required)

**Related Work**:
- Story-070: OCR Split Refinement (fixed pick_best_engine and boundary detection)
- Story-068: FF Boundary Detection Improvements (achieved 100% on test dataset)
- Story-059: Section Detection & Boundary Improvements

---

## Missing Sections Analysis

### Sections Missing from Boundaries (23 total)

**Confirmed Missing** (not in `section_boundaries.jsonl`):
- `[17, 25, 42, 55, 64, 76, 78, 80, 82, 84, 86, 91, 92, 105, 159, 166, 169, 170, 175, 202, 233, 259, 270]`

**Investigation Notes**:
- Section 17: In elements (page 5) but filtered as frontmatter (page 5 < main_start_page 12)
- Section 25: Needs investigation
- Sections 42, 55, 64, 76, 78, 82, 84, 105, 159, 166, 175: Lost at boundary detection (need to check if in elements)
- Sections 80, 86, 91, 92: Never standalone in OCR (only appear in ranges like "180-181", "386-387")
- Sections 169, 170, 202, 233, 259, 270: Need investigation

### Sections Missing from Portions (31 total)

**Missing from `portions_enriched_clean.jsonl`**:
- `[17, 25, 42, 55, 64, 76, 78, 80, 82, 84, 86, 91, 92, 105, 159, 166, 169, 170, 175, 202, 233, 259, 270, 276, 313, 318, 330, 335, 350, 376, 400]`

**Investigation Notes**:
- Some sections have boundaries but no portions (extraction failure)
- Some sections are in frontmatter (correctly filtered)
- Some sections may have OCR corruption preventing detection

### Sections Requiring Stub Backfill (19 total)

**From build_ff_engine_v1 failure**:
- Exact list needs to be extracted from build error
- These are sections that have boundaries but failed extraction or validation

---

## Failure Mode Analysis

### Mode 1: Lost at pick_best_engine_v1 (FIXED in Story-070)
**Status**: ✅ Fixed
**Sections Recovered**: 6, 7, 8, 9, 38, 44, 46, 48, 49, 71, 95
**Root Cause**: Module was discarding numeric headers when rebuilding lines from engine raw text
**Fix Applied**: Preserve curated lines array, especially Section-header elements

### Mode 2: Lost at detect_gameplay_numbers_v1 (PARTIALLY FIXED in Story-070)
**Status**: ⚠️ Partially Fixed
**Sections Recovered**: 22, 318, 350, 7, 8 (via high-confidence bypass)
**Remaining Issues**: 
- Some sections still rejected by context validation
- Some sections not in elements (lost earlier)
- Some sections filtered as frontmatter incorrectly

**Investigation Needed**:
- Check if remaining missing sections are in elements but rejected
- Verify frontmatter filtering logic (section 17 on page 5)
- Check for OCR corruption cases

### Mode 3: Never in Raw OCR
**Status**: 🔍 Needs Investigation
**Sections**: 80, 86, 91, 92 (only appear in ranges, not standalone)
**Root Cause**: May be OCR corruption, or sections truly don't exist as standalone headers
**Action**: Verify against source PDF/images

### Mode 4: Lost at Portion Extraction
**Status**: 🔍 Needs Investigation
**Sections**: Have boundaries but no portions
**Root Cause**: `portionize_ai_extract_v1` may be skipping sections or failing validation
**Action**: Trace sections with boundaries but no portions

### Mode 5: Lost Sections from Previous Run
**Status**: 🔍 Needs Investigation
**Sections Lost**: 42, 55, 64, 76, 78, 82, 84, 105, 159, 166, 175, 235, 265, 286, 323, 331, 358
**Note**: These were in old run but not in new run - may have been false positives, or new issue introduced

---

## Tasks

### Priority 1: Complete Boundary Detection (23 missing)

- [ ] **Investigate missing boundaries**:
  - [ ] Check if sections 17, 25, 42, 55, 64, 76, 78, 82, 84, 105, 159, 166, 175 are in elements
  - [ ] If in elements, check why `detect_gameplay_numbers_v1` rejected them
  - [ ] If not in elements, trace back to see where they were lost
  - [ ] Verify frontmatter filtering (section 17 on page 5 - is it actually frontmatter?)

- [ ] **Fix frontmatter filtering** (if needed):
  - [ ] Review `main_start_page` logic in `detect_gameplay_numbers_v1`
  - [ ] Check if section 17 should be included (it's on page 5, main_start_page is 12)
  - [ ] Verify section 12, 16, 17, etc. are correctly classified

- [ ] **Handle OCR corruption cases**:
  - [ ] Sections 80, 86, 91, 92 only appear in ranges ("180-181", "386-387")
  - [ ] Check source PDF/images to verify if these sections exist as standalone headers
  - [ ] If they exist, improve OCR extraction to handle range-to-standalone conversion
  - [ ] If they don't exist, mark as expected missing (not a bug)

- [ ] **Investigate lost sections**:
  - [ ] Check why sections 169, 170, 202, 233, 259, 270 are missing
  - [ ] Verify if they were false positives in old run or if new issue introduced

### Priority 2: Complete Portion Extraction (31 missing)

- [ ] **Trace sections with boundaries but no portions**:
  - [ ] Identify sections that have boundaries in `section_boundaries_merged.jsonl` but no portions
  - [ ] Check `portionize_ai_extract_v1` logs for these sections
  - [ ] Verify if extraction failed, was skipped, or validation rejected

- [ ] **Fix portion extraction failures**:
  - [ ] Review `portionize_ai_extract_v1` validation logic
  - [ ] Check if sections are being skipped due to empty text or other validation failures
  - [ ] Ensure all valid boundaries result in portions

- [ ] **Handle frontmatter sections**:
  - [ ] Verify which missing sections are actually frontmatter
  - [ ] Ensure frontmatter sections are correctly excluded from gameplay portions
  - [ ] Document expected missing sections (frontmatter)

### Priority 3: Complete Gamebook Build (19 stubs)

- [ ] **Identify stub sections**:
  - [ ] Extract exact list of 19 sections requiring stub backfill from build error
  - [ ] Trace each section through pipeline to find where it was lost
  - [ ] Categorize by failure mode (boundary missing, portion missing, validation failure)

- [ ] **Fix root causes**:
  - [ ] Address boundary detection issues (Priority 1)
  - [ ] Address portion extraction issues (Priority 2)
  - [ ] Fix any validation failures preventing sections from being included

- [ ] **Verify 100% coverage**:
  - [ ] Run full pipeline and verify all 400 sections in gamebook.json
  - [ ] Confirm zero stubs required
  - [ ] Validate all sections have text and choices where expected

### Priority 4: Forensics & Diagnostics

- [ ] **Create diagnostic tool**:
  - [ ] Build script to trace any section ID through entire pipeline
  - [ ] Show where section appears/disappears at each stage
  - [ ] Include artifact paths, element IDs, page numbers, confidence scores

- [ ] **Document expected missing sections**:
  - [ ] Identify sections that are truly frontmatter (should be excluded)
  - [ ] Identify sections that don't exist in source (not a bug)
  - [ ] Create allowlist of expected missing sections

- [ ] **Add regression tests**:
  - [ ] Test that all 400 sections are detected in test dataset
  - [ ] Test that fixes don't introduce false positives
  - [ ] Test that frontmatter filtering works correctly

---

## Implementation Notes

**Key Files to Modify**:
- `modules/portionize/detect_gameplay_numbers_v1/main.py`: Boundary detection logic
- `modules/portionize/portionize_ai_extract_v1/main.py`: Portion extraction logic
- `modules/adapter/build_ff_engine_v1/main.py`: Gamebook build logic
- `modules/adapter/pick_best_engine_v1/main.py`: Already fixed, verify no regressions

**Investigation Tools Needed**:
- Section tracer: Given section ID, show pipeline trace
- Boundary analyzer: Compare boundaries vs expected sections
- Portion analyzer: Compare portions vs boundaries
- OCR corruption detector: Find sections only in ranges

**Testing Strategy**:
- Unit tests for boundary detection edge cases
- Integration tests for full pipeline on test dataset
- Regression tests to ensure fixes don't break existing sections
- Manual verification of missing sections against source PDF

---

## Work Log

### 2025-12-15 — Story Created
- **Context**: Full pipeline run `ff-full-070-fixes-test` completed with 377/400 boundaries (94.25%)
- **Improvement**: +22 sections recovered from previous run (355 → 377 boundaries)
- **Remaining**: 23 sections missing from boundaries, 31 missing from portions, 19 requiring stubs
- **Action**: Created comprehensive story document with failure mode analysis
- **Next**: Investigate missing sections systematically, starting with Priority 1 (boundary detection)

### 2025-12-15 — Initial Investigation Complete
- **Findings from Story-070 investigation**:
  - Sections 6, 7, 8, 9, 22, 38, 44, 46, 48, 49, 71, 95 were identified as lost at `pick_best_engine_v1` or `detect_gameplay_numbers_v1`
  - Fixes applied in Story-070 recovered these sections
  - Remaining missing sections need deeper investigation
- **Known Issues**:
  - Section 17: In elements but filtered as frontmatter (page 5 < main_start_page 12)
  - Sections 80, 86, 91, 92: Only appear in OCR ranges, not standalone
  - Sections 42, 55, 64, 76, 78, 82, 84, 105, 159, 166, 175: Lost at boundary detection (need to verify if in elements)
- **Next Steps**: Trace each missing section through pipeline to identify exact failure point

---

## Expected Outcomes

**Success Metrics**:
- Boundaries: 400/400 sections (100%)
- Portions: 400/400 sections (100%, excluding frontmatter)
- Gamebook: 400/400 sections (100%, zero stubs)

**Quality Metrics**:
- Zero false positives (no duplicate sections)
- Zero false negatives (no missing valid sections)
- All sections have valid text and choices where expected
- Frontmatter correctly excluded

**Deliverables**:
- Diagnostic tool for section tracing
- Documentation of expected missing sections (if any)
- Regression tests for 100% coverage
- Updated pipeline with fixes for all identified failure modes

