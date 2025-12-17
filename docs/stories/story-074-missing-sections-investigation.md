# Story: Missing Sections Investigation — Complete 100% Coverage

**Status**: To Do
**Created**: 2025-12-16
**Parent Story**: story-073 (100% Section Detection — Segmentation Architecture Complete)

---

## Goal

Complete the remaining work from Story-073 to achieve **100% section detection** (400/400 sections) for Fighting Fantasy gamebooks. Story-073 successfully implemented the segmentation architecture and fixed critical bugs, but the final goal of 100% coverage remains. This story focuses on investigating and fixing all missing sections to reach complete coverage.

**Current State** (from Story-073 work):
- Segmentation architecture: ✅ Complete (semantic + pattern + FF override + merge)
- Boundary detection: 377/400 (94.25%) — **23 sections missing**
- Portion extraction: 369/400 (92.25%) — **31 sections missing**
- Gamebook coverage: 381/400 (95.25%, 19 stubs) — **19 sections requiring stubs**

**Target**: 100% accuracy — every section (1-400) must be detected, extracted, and included in final gamebook.json with zero stubs.

---

## Success Criteria

- [ ] **100% boundary detection**: All 400 sections have boundaries in `section_boundaries_merged.jsonl`
- [ ] **100% portion extraction**: All 400 sections have portions in `portions_enriched_clean.jsonl`
- [ ] **100% gamebook coverage**: Final `gamebook.json` contains all 400 sections with no stubs
- [ ] **Zero false positives**: No duplicate sections or incorrect boundaries
- [ ] **Forensics complete**: All missing sections have diagnostic traces showing where they were lost
- [ ] **Regression tests**: Test that all 400 sections are detected in full dataset

---

## Context

**Story-073 Accomplishments**:
- ✅ Implemented multi-stage segmentation architecture (semantic + pattern + FF override + merge)
- ✅ Fixed critical bug in `pick_best_engine_v1` (BACKGROUND text was being lost)
- ✅ Fixed bug in `coarse_segment_ff_override_v1` (incorrectly finding BACKGROUND on page 5 instead of page 12)
- ✅ Fixed bug in `classify_headers_v1` (TypeError when aggregating boolean results)
- ✅ Created diagnostic tool (`scripts/trace_section_pipeline.py`) for tracing sections through pipeline
- ✅ Created integration tests (`tests/test_segmentation_pipeline_integration.py`)
- ✅ Verified segmentation works correctly: Frontmatter [1,11], Gameplay [12,111], Endmatter [112,113]

**Remaining Gaps**:
- 23 sections missing from boundaries (need investigation and fixes)
- 31 sections missing from portions (need investigation and fixes)
- 19 sections requiring stubs in gamebook (need investigation and fixes)

**Related Work**:
- Story-073: Segmentation Architecture (COMPLETE)
- Story-070: OCR Split Refinement (fixed pick_best_engine and boundary detection)
- Story-068: FF Boundary Detection Improvements (achieved 100% on test dataset)

---

## Missing Sections Analysis

### Sections Missing from Boundaries (23 total)

**Confirmed Missing** (not in `section_boundaries.jsonl`):
- `[17, 25, 42, 55, 64, 76, 78, 80, 82, 84, 86, 91, 92, 105, 159, 166, 169, 170, 175, 202, 233, 259, 270]`

**Investigation Notes** (from Story-073):
- Section 17: In elements (page 5, 10, 20) but filtered as frontmatter (page 5 < main_start_page 12)
- Section 25: In elements (pages 14, 22) but missing from boundaries — needs investigation
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

## Requirements for Improvement

### Requirement: Enhanced Page Number / Running Header Classification
**Status**: PARTIALLY IMPLEMENTED (from Story-073)
**Priority**: High

**Status from Story-073**:
- Pattern-based page number detection implemented in `elements_content_type_v1`
- Pattern detection working (62 running headers detected)
- However, some page numbers may still be misclassified as Section-headers

**Remaining Work**:
- Verify all page numbers correctly classified (not just running headers)
- Ensure no false positives where page numbers are classified as Section-headers
- Test on full 113-page book to ensure no regressions

---

## Failure Mode Analysis

### Mode 1: Lost at pick_best_engine_v1
**Status**: ✅ Fixed (Story-073)
**Sections Recovered**: N/A (was fixed before this investigation)

### Mode 2: Lost at Boundary Detection
**Status**: 🔍 Needs Investigation
**Sections**: 17, 25, 42, 55, 64, 76, 78, 82, 84, 105, 159, 166, 169, 170, 175, 202, 233, 259, 270

**Investigation Needed**:
- Use `scripts/trace_section_pipeline.py` to trace each missing section
- Check if sections are in elements but rejected by validation
- Verify frontmatter filtering logic (section 17 on page 5 - is it actually frontmatter?)
- Check for duplicate resolution issues
- Check for context validation rejections

### Mode 3: Never in Raw OCR
**Status**: 🔍 Needs Investigation
**Sections**: 80, 86, 91, 92 (only appear in ranges, not standalone)

**Root Cause**: May be OCR corruption, or sections truly don't exist as standalone headers
**Action**: 
- Verify against source PDF/images
- If they exist, improve OCR extraction to handle range-to-standalone conversion
- If they don't exist, mark as expected missing (not a bug)

### Mode 4: Lost at Portion Extraction
**Status**: 🔍 Needs Investigation
**Sections**: Have boundaries but no portions

**Root Cause**: `portionize_ai_extract_v1` may be skipping sections or failing validation
**Action**: 
- Use trace script to identify sections with boundaries but no portions
- Check `portionize_ai_extract_v1` logs for these sections
- Review validation logic and fix extraction failures

### Mode 5: Lost at Gamebook Build
**Status**: 🔍 Needs Investigation
**Sections**: 19 sections requiring stubs

**Root Cause**: Sections have boundaries/portions but fail validation during build
**Action**:
- Extract exact list of 19 sections from build error
- Trace each section to find where validation fails
- Fix validation logic or data quality issues

---

## Tasks

### Priority 1: Complete Boundary Detection (23 missing)

- [ ] **Systematically investigate all 23 missing sections**:
  - [ ] Use `scripts/trace_section_pipeline.py` to trace each missing section
  - [ ] For each section, document:
    - Whether it appears in elements_core_typed.jsonl
    - If in elements, why boundary detection rejected it
    - If not in elements, where it was lost upstream
  - [ ] Categorize failures by failure mode

- [ ] **Fix boundary detection issues**:
  - [ ] Fix frontmatter filtering edge cases (e.g., section 17 on page 5)
  - [ ] Fix duplicate resolution logic if valid instances are being lost
  - [ ] Fix context validation if sections are incorrectly rejected
  - [ ] Verify content type classification (page numbers not misclassified as Section-headers)

- [ ] **Handle OCR corruption cases**:
  - [ ] Sections 80, 86, 91, 92: Verify against source PDF/images
  - [ ] If they exist, improve OCR extraction to handle range-to-standalone conversion
  - [ ] If they don't exist, document as expected missing (not a bug)

- [ ] **Verify fixes**:
  - [ ] Re-run boundary detection and verify all 400 sections found
  - [ ] Verify no false positives introduced
  - [ ] Verify frontmatter filtering still works correctly

### Priority 2: Complete Portion Extraction (31 missing)

- [ ] **Identify sections with boundaries but no portions**:
  - [ ] Compare `section_boundaries_merged.jsonl` vs `portions_enriched_clean.jsonl`
  - [ ] List all sections that have boundaries but missing portions
  - [ ] Use trace script to understand extraction failures

- [ ] **Fix portion extraction failures**:
  - [ ] Review `portionize_ai_extract_v1` validation logic
  - [ ] Check if sections are being skipped due to empty text or other validation failures
  - [ ] Fix extraction logic to handle edge cases
  - [ ] Ensure all valid boundaries result in portions

- [ ] **Handle frontmatter sections**:
  - [ ] Verify which missing sections are actually frontmatter (should be excluded)
  - [ ] Ensure frontmatter sections are correctly excluded from gameplay portions
  - [ ] Document expected missing sections (frontmatter)

- [ ] **Verify fixes**:
  - [ ] Re-run portion extraction and verify all sections with boundaries have portions
  - [ ] Verify frontmatter sections correctly excluded

### Priority 3: Complete Gamebook Build (19 stubs)

- [ ] **Identify stub sections**:
  - [ ] Run full pipeline and extract exact list of 19 sections requiring stub backfill
  - [ ] Use trace script to trace each stub section through pipeline
  - [ ] Categorize by failure mode (boundary missing, portion missing, validation failure)

- [ ] **Fix root causes**:
  - [ ] Address boundary detection issues (Priority 1)
  - [ ] Address portion extraction issues (Priority 2)
  - [ ] Fix any validation failures preventing sections from being included

- [ ] **Verify 100% coverage**:
  - [ ] Run full pipeline and verify all 400 sections in gamebook.json
  - [ ] Confirm zero stubs required
  - [ ] Validate all sections have text and choices where expected

### Priority 4: Documentation & Testing

- [ ] **Document expected missing sections**:
  - [ ] Create allowlist of sections that are truly frontmatter (should be excluded)
  - [ ] Document sections that don't exist in source (not a bug)
  - [ ] Update validation to explicitly handle expected missing sections

- [ ] **Add regression tests**:
  - [ ] Test that all 400 sections are detected in full dataset
  - [ ] Test that fixes don't introduce false positives
  - [ ] Test that frontmatter filtering works correctly
  - [ ] Add test for edge cases (sections in ranges, OCR corruption, etc.)

---

## Implementation Notes

**Key Files to Modify**:
- `modules/portionize/detect_boundaries_code_first_v1/main.py`: Boundary detection logic
- `modules/portionize/portionize_ai_extract_v1/main.py`: Portion extraction logic
- `modules/adapter/build_ff_engine_v1/main.py`: Gamebook build logic
- `modules/adapter/elements_content_type_v1/main.py`: Content type classification (if needed)

**Investigation Tools**:
- `scripts/trace_section_pipeline.py`: Trace sections through pipeline (from Story-073)
- Manual artifact inspection: Check elements_core_typed.jsonl, boundaries, portions for missing sections

**Testing Strategy**:
- Use trace script to investigate each missing section
- Run boundary detection on full 113-page book
- Run portion extraction on full book
- Run full pipeline end-to-end and verify 100% coverage
- Regression tests to ensure fixes don't break existing sections

---

## Work Log

### 2025-12-16 — Story Created
- **Context**: Story-073 segmentation architecture complete, but 100% coverage goal remains
- **Action**: Created new story to focus on remaining missing sections investigation
- **Next**: Begin systematic investigation of 23 missing boundaries using trace script

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
- Fixed boundary detection (all 400 sections)
- Fixed portion extraction (all sections with boundaries have portions)
- Fixed gamebook build (zero stubs)
- Documentation of expected missing sections (if any)
- Regression tests for 100% coverage

