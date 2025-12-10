# Story: Section Detection & Boundary Improvements

**Status**: Open  
**Created**: 2025-12-09  
**Parent Story**: story-054 (canonical recipe - COMPLETE)

## Goal
Improve section detection and boundary metadata quality. Fix issues where section boundaries are missing required fields, improve section detection to find all expected sections, and handle OCR errors in section numbers.

## Success Criteria
- [ ] Section boundaries have all required fields populated (page, start_element_id)
- [ ] Section detection finds all expected sections (at minimum sections 1-17 for pages 1-20)
- [ ] OCR errors in section numbers are handled (e.g., "in 4" → "4")
- [ ] Section detection works with various formats (standalone, bold, at start of line)
- [ ] Section coverage validation ensures expected number of sections are found

## Context

**Issues Identified** (from artifact analysis - see `docs/artifact-issues-analysis.md`):

1. **Section Boundaries Missing Page/Element IDs**
   - All 4 detected boundaries have `page: None` and `start_element_id: None`
   - Boundaries only have `section_id` and `evidence`
   - **Root Cause**: `portionize_ai_scan_v1` module bug - not populating required fields

2. **Missing Section Boundaries**
   - Expected sections: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
   - Found sections: [1, 2, 7, 12]
   - Missing: 3, 4, 5, 6, 8, 9, 10, 11, 13, 14, 15, 16, 17
   - **Root Cause**: Section detection too strict; OCR errors in section numbers; sections may be on pages beyond page 20

3. **Section Number OCR Errors**
   - Page 018L: "in 4" instead of "4" - section number partially OCR'd
   - **Root Cause**: OCR merged section number with preceding text; no post-processing to extract section numbers

**Root Causes**:
- Section detection relies on finding standalone numbers followed by narrative text
- Some sections may not follow this pattern
- OCR errors in section numbers (e.g., "in 4" instead of "4")
- Module bug: boundaries not populating required metadata fields
- Sections may be on pages beyond the test range (pages 1-20)

## Tasks

### High Priority

- [ ] **Fix Section Boundary Page/Element IDs**
  - **Issue**: All 4 detected boundaries have `page: None` and `start_element_id: None`
  - **Root Cause**: `portionize_ai_scan_v1` module bug - not populating required fields
  - **Mitigations**:
    - Fix module bug: ensure `portionize_ai_scan_v1` populates `page` and `start_element_id`
    - Add validation: validate that boundaries have required fields
    - Post-process boundaries: if missing, try to infer from `evidence` text by searching elements
    - Test: verify all boundaries have required fields after fix

- [ ] **Improve Section Detection**
  - **Issue**: Expected 17 sections, found only 4 (1, 2, 7, 12); missing 13 sections
  - **Root Cause**: Section detection too strict; OCR errors in section numbers; sections may be beyond page 20
  - **Mitigations**:
    - Improve section detection: look for section numbers in various formats (standalone, bold, at start of line)
    - Handle OCR errors: use fuzzy matching for section numbers (e.g., "in 4" → "4")
    - Cross-reference with known sections: if we know sections 1-400 exist, search more aggressively
    - Use LLM for section detection: LLM can understand context better than pattern matching
    - Validate section coverage: after detection, check if we found expected number of sections
    - Test on full book: verify section detection finds all sections 1-400

- [ ] **Section Number Extraction**
  - **Issue**: Page 018L has "in 4" instead of "4" - section number partially OCR'd
  - **Root Cause**: OCR merged "4" with preceding text; no post-processing to extract section numbers
  - **Mitigations**:
    - Section number extraction: after OCR, extract section numbers even if merged with text
    - Fuzzy matching: when looking for section numbers, use fuzzy matching
    - Context-aware extraction: use LLM to identify section numbers in context
    - Test: verify section numbers are extracted correctly even when merged with text

### Medium Priority

- [ ] **Section Header Detection Improvements**
  - Look for section numbers in various formats (standalone, bold, at start of line)
  - Handle OCR errors in section numbers (fuzzy matching)
  - Cross-reference with known sections (if we know sections 1-400 exist, search more aggressively)
  - Use LLM for section detection (LLM can understand context better than pattern matching)

- [ ] **Section Coverage Validation**
  - After detection, check if we found expected number of sections
  - Validate section coverage: ensure all expected sections are found
  - Flag missing sections for targeted re-detection
  - Test on full book: verify section detection finds all sections 1-400

- [ ] **Boundary Metadata Quality**
  - Ensure all boundaries have required fields (page, start_element_id, end_element_id)
  - Validate boundary metadata before downstream stages
  - Add forensics: trace boundaries back to source elements/pages

- [ ] **Section Header Detection and Content Extraction Separation**
  - Section header detection and section content extraction must be discrete steps
  - Each step must have its own resolve-or-escalate gate before downstream stages run
  - This ensures header detection completes before content extraction begins

- [ ] **Targeted Escalation for Missing Sections**
  - If boundaries remain short, add targeted escalation for missing sections before proceeding
  - Run lightweight LLM boundary finder over page text/lines for missing IDs
  - Re-evaluate coverage gate after targeted escalation

- [ ] **Specialized Section Extractors**
  - Build specialized section extractors: frontmatter-specific, gameplay-specific
  - Endmatter may remain as a single portion
  - Each extractor optimized for its section type

## Related Work

**Previous Improvements** (from story-054):
- ✅ Section coverage guard added (`validate_sections_coverage_v1`)
- ✅ Boundary sanity gate added (`validate_boundaries_gate_v1`)
- ✅ Structure globally has resolve-or-escalate path
- ✅ Numeric boundary detector with OCR-glitch normalization
- ✅ Boundary merge and deduplication implemented

**Related Stories**:
- Story-054: Canonical recipe (provides pipeline context)
- Story-057: OCR quality improvements (affects section detection input quality)
- Story-058: Post-OCR text quality (affects section number extraction)

## Work Log

### 2025-12-09 — Story created from story-054
- **Context**: Story-054 (canonical recipe) is complete. Section detection and boundary improvements were identified as separate domain concerns.
- **Action**: Extracted section detection & boundary improvement tasks from story-054 into this focused story.
- **Scope**: Focus on fixing boundary metadata bugs, improving section detection recall, and handling OCR errors in section numbers.
- **Next**: Fix `portionize_ai_scan_v1` to populate required boundary fields, improve section detection to find all expected sections, add section number extraction.

