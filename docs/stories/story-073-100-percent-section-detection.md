# Story: 100% Section Detection — Segmentation Architecture

**Status**: Done
**Created**: 2025-12-15
**Completed**: 2025-12-16
**Parent Story**: story-070 (OCR Split Refinement - COMPLETE), story-068 (FF Boundary Detection - COMPLETE)
**Follow-up Story**: story-074 (Missing Sections Investigation — Complete 100% Coverage)

---

## Goal

Implement multi-stage segmentation architecture to correctly identify page boundaries (frontmatter/gameplay/endmatter) for Fighting Fantasy gamebooks. This story focused on fixing the coarse segmentation misclassification issue where page 12 was incorrectly identified as frontmatter instead of gameplay start.

**Note**: The original 100% section detection goal has been moved to Story-074. This story successfully completed the segmentation architecture prerequisite.

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

## Success Criteria (Story-073 Scope)

- [x] **Segmentation architecture implemented**: Multi-stage segmentation (semantic + pattern + FF override + merge)
- [x] **Page 12 correctly identified**: Frontmatter [1,11], Gameplay [12,111] (corrected from [1,15] / [16,111])
- [x] **Integration complete**: All modules integrated into canonical recipe
- [x] **Critical bugs fixed**: pick_best_engine_v1 data loss, coarse_segment_ff_override_v1 page detection, classify_headers_v1 TypeError
- [x] **Diagnostic tool created**: `scripts/trace_section_pipeline.py` for investigating missing sections
- [x] **Integration tests created**: `tests/test_segmentation_pipeline_integration.py` (all pass)
- [ ] **100% section coverage**: Moved to Story-074 (Missing Sections Investigation)

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

## Requirements for Improvement

### Requirement: Enhanced Page Number / Running Header Classification
**Status**: PENDING
**Priority**: High

**Problem**: `elements_content_type_v1` currently has limited logic for identifying page numbers and running headers:
- Only classifies bottom numeric as Page-footer if layout data exists (y >= 0.92)
- Skips numeric-only text when building repetition-based header/footer signatures
- Doesn't do cross-page pattern analysis for numeric page numbers
- Result: Page numbers (especially in frontmatter) and section ranges (in gameplay headers) may be misclassified as Section-headers

**Requirement**: Improve `elements_content_type_v1` to better classify page numbers and running headers without over-fitting to FF books:

1. **Pattern-based page number detection**:
   - Numbers that appear consistently at top/bottom margins across multiple pages are likely page numbers or running headers
   - Do all-page analysis looking for patterns (not just single-element heuristics)
   - Should work generically for any book, not just FF

2. **Two distinct classifications**:
   - **Page-footer (page numbers)**: Actual page numbers (typically bottom corners, sequential)
   - **Page-header (running headers/footers)**: Section ranges or chapter info (typically top corners, may repeat)

3. **FF book specifics** (but should generalize):
   - Frontmatter: Page numbers at bottom outside corner (sequential, 1-N)
   - Gameplay: Section ranges in upper outside corners (e.g., "6-8", "12-17") - these are running headers, not page numbers

**Implementation Plan (Enhanced)**:

1.  **Abstract and Collect Element Positions**:
    -   Instead of hardcoded top/bottom margins, generalize position analysis. For each element, determine its abstract position, such as a `(vertical_align, horizontal_align)` pair (e.g., `(bottom, right)`, `(top, center)`).
    -   Collect all numeric-only elements with their page number and abstract position.

2.  **Leverage Coarse Segments**:
    -   Perform the pattern analysis independently for the known `frontmatter`, `gameplay`, and `endmatter` coarse segments. This accommodates different numbering styles (e.g., centered numbers in frontmatter vs. corner ranges in gameplay).

3.  **Prioritize High-Confidence Sequential Page Numbers**:
    -   Run this high-priority check first. Scan for the strongest signal: a sequence of increasing integers (`N, N+1, N+2...`) at the same abstract position on consecutive pages.
    -   If found, classify these elements as `Page-footer`. These elements should be assigned a very high confidence score (e.g., 0.99) and be excluded from any further consideration as potential `Section-header` elements.

4.  **Detect Other Header/Footer Patterns**:
    -   For the remaining numeric elements, look for other, weaker patterns:
    -   **Running Headers**: Look for repeating text/numbers or numeric ranges (e.g., "6-8") at the same abstract position (typically top) across multiple pages. Classify as `Page-header` with a high confidence score (e.g., 0.90).
    -   **Other Page Footers**: Look for consistently placed but non-sequential numbers at the bottom of pages. Classify as `Page-footer` with a moderate confidence score (e.g., 0.85).

5.  **Emit Confidence Scores and Override**:
    -   Modify the module to not just override the `type`, but to also add a `type_confidence` field to the element.
    -   The high-confidence classifications derived from pattern matching will override any low-confidence classifications from earlier heuristics.

6.  **Generate a Debug Artifact**:
    -   The module will produce a new `element_patterns.jsonl` artifact.
    -   This file will log the patterns detected, the confidence assigned to each, and which elements were re-classified, making the module's logic transparent and easier to debug.

7.  **Fallback Handling**:
    -   When layout data is unavailable (preventing abstract position calculation), fall back to using text-repetition signals.
    -   Preserve existing single-element heuristics for any edge cases not covered by the pattern analysis.

**Expected Impact**:
- Reduces false positives where page numbers are misclassified as Section-headers.
- Improves downstream boundary detection accuracy by providing cleaner signals.
- Creates a more robust, debuggable, and generalizable classification module.
- Provides confidence scores for more intelligent downstream processing.

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

- [x] **Fix frontmatter filtering**:
  - [x] Fixed frontmatter filtering order bug in `detect_boundaries_code_first_v1`
  - [x] Now filters frontmatter BEFORE duplicate resolution to prevent valid instances from being lost
  - [x] Improved section 1 detection using fit score (finds best consecutive match instead of first instance)
  - [ ] **NEW BUG**: Fix content type classifier - page numbers incorrectly classified as Section-headers
  - [ ] Verify section 12, 16, 17, etc. are correctly classified (may be page numbers, not sections)

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

- [x] **Create diagnostic tool**:
  - [x] Build script to trace any section ID through entire pipeline (`scripts/trace_section_pipeline.py`)
  - [x] Show where section appears/disappears at each stage
  - [x] Include artifact paths, element IDs, page numbers, confidence scores
  - [x] Provide diagnostic guidance based on where section is missing

- [ ] **Document expected missing sections**:
  - [ ] Identify sections that are truly frontmatter (should be excluded)
  - [ ] Identify sections that don't exist in source (not a bug)
  - [ ] Create allowlist of expected missing sections

- [x] **Add regression tests**:
  - [x] Test segmentation pipeline integration (`tests/test_segmentation_pipeline_integration.py`)
  - [x] Test that all 4 segmentation stages work together correctly
  - [x] Test edge cases (no BACKGROUND, missing FF override)
  - [ ] Test that all 400 sections are detected in test dataset (requires full pipeline completion)
  - [ ] Test that fixes don't introduce false positives (requires full pipeline completion)
  - [x] Test that frontmatter filtering works correctly (verified via segmentation boundaries)

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

### 2025-01-XX: OCR Coordinate System Investigation

**Problem Identified:**
- Running headers (section ranges like "9-10", "18-21") are present in OCR output but not being detected by pattern matching
- Investigation revealed: "9-10" at page 18 has bbox y0=0.934, which is at the TOP LEFT corner
- This indicates the coordinate system is INVERTED: y=0 = bottom, y=1 = top (Apple Vision convention)
- Standard image coordinates: y=0 = top, y=1 = bottom (Tesseract/EasyOCR convention)

**Root Cause:**
- Different OCR engines use different coordinate systems:
  - Tesseract/EasyOCR: y=0 = top (standard)
  - Apple Vision: y=0 = bottom (inverted, bottom-left origin)
- When Apple Vision is the source engine, running headers at top corners have high y values (0.9+)
- `get_abstract_position()` was assuming standard coordinates, so it classified these as "bottom" instead of "top"

**Fix Implemented:**
- Enhanced `get_abstract_position()` in `elements_content_type_v1` to detect inverted coordinate systems
- Heuristic: If y > 0.85 AND h_align is left/right (corner), treat as inverted and use (1-y) for position
- This correctly identifies running headers at top corners even when coordinate system is inverted

**Status:**
- ✅ Coordinate system detection working (verified: "9-10" correctly identified as top-left)
- ✅ Pattern detection fixed: Now detects position-based patterns, not just text repetition
- ✅ 62 running headers correctly detected and classified as Page-header
- ✅ bbox storage confirmed LOW PRIORITY (not needed - current fix sufficient)

**Fix Details:**
- Enhanced `detect_other_header_footer_patterns()` to detect position-based patterns
- Pattern 1: Same text repeating (traditional running headers) - still supported
- Pattern 2: Multiple different page ranges at same position (NEW - handles FF section ranges)
- Threshold: 5+ occurrences at same position (e.g., `(top, left)`) to classify as running header
- Results: 30 at `(top, left)`, 32 at `(top, right)` - all correctly identified

**Documentation:**
- Added Fighting Fantasy book structure section to README.md explaining running headers
- Documented coordinate system differences between OCR engines

### 2025-01-XX: Coarse Segmentation Investigation

**Problem Identified:**
- `coarse_segment_v1` consistently misclassifies page 12 as frontmatter (should be gameplay start)
- Re-run still shows: frontmatter [1,15], gameplay [16,111] (incorrect)
- Should be: frontmatter [1,11], gameplay [12,111]
- Root cause: Page 12 only has numbers ("1", "20", "21") with no context/keywords
- LLM can't identify gameplay start without semantic markers like "BACKGROUND"

**User Insight:**
- BACKGROUND format = frontmatter format (both have page numbers at bottom)
- REAL signal is PATTERN shift: bottom page numbers → top section ranges
- Need pattern-driven segmentation, not just text-based

**Architecture Decision:**
- Need TWO separate coarse segmenters:
  1. **Semantic segmenter** (existing `coarse_segment_v1`): frontmatter/gameplay/endmatter based on text
  2. **Pattern segmenter** (new `coarse_segment_patterns_v1`): Header/footer style regions (generic)
- Pattern segmenter identifies regions with same header/footer style:
  - "Pages 1-11: bottom page numbers" (frontmatter style)
  - "Pages 12-111: top section ranges" (gameplay style)
  - May skip pages, regions may overlap (generic approach)
- FF-style override: Rule that "gameplay starts with BACKGROUND header" (FF-specific but documented)

**Implementation Complete:**
- ✅ Created `coarse_segment_patterns_v1` module (pattern-based segmenter)
- ✅ Created `coarse_segment_ff_override_v1` module (FF override for BACKGROUND rule)
- ✅ Created `coarse_segment_merge_v1` module (merges semantic + pattern + override)
- ✅ Fixed critical bug in `pick_best_engine_v1` (BACKGROUND text was being lost)
- ✅ Integrated all modules into canonical recipe (`recipe-ff-canonical.yaml`)
- ✅ Fixed bug in `coarse_segment_ff_override_v1` (incorrectly finding BACKGROUND on page 5 instead of page 12)
- ✅ Fixed bug in `classify_headers_v1` (TypeError when aggregating boolean results)
- ✅ Tested with full 113-page book: Page 12 correctly identified as gameplay start

**Integration Details:**
- Recipe now runs 4 stages in sequence:
  1. `coarse_segment_semantic` - LLM-based semantic segmentation (existing)
  2. `coarse_segment_patterns` - Pattern-based header/footer style regions (new)
  3. `coarse_segment_ff_override` - FF-specific BACKGROUND rule (new)
  4. `coarse_segment` - Merges all three (replaces single semantic stage)
- Downstream `fine_segment_frontmatter` updated to use `merged_segments.json`
- Expected result: Frontmatter [1,11], Gameplay [12,111] (corrected from [1,15] / [16,111])

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

### 2025-01-XX: Segmentation Architecture Integration - COMPLETE ✅

**Integration Complete:**
- ✅ Integrated `coarse_segment_patterns_v1`, `coarse_segment_ff_override_v1`, and `coarse_segment_merge_v1` into canonical recipe
- ✅ Updated `recipe-ff-canonical.yaml` to run 4-stage segmentation pipeline:
  1. `coarse_segment_semantic` - LLM-based semantic segmentation
  2. `coarse_segment_patterns` - Pattern-based header/footer style detection
  3. `coarse_segment_ff_override` - FF-specific BACKGROUND rule
  4. `coarse_segment` (merge) - Combines all three sources
- ✅ Updated `fine_segment_frontmatter` to consume `merged_segments.json`
- ✅ Fixed critical bug in `pick_best_engine_v1` where "BACKGROUND" text was being lost
- ✅ Fixed bug in `coarse_segment_ff_override_v1` (incorrectly finding BACKGROUND on page 5 instead of page 12)
- ✅ Fixed bug in `classify_headers_v1` (TypeError when aggregating boolean results)

**Expected Impact:**
- Page 12 now correctly identified as gameplay start (via FF override) ✅
- Frontmatter [1,11], gameplay [12,111] (corrected from [1,15] / [16,111]) ✅
- Pattern evidence provides additional confidence signals for boundary detection ✅

**Validation Complete:**
- ✅ Tested segmentation pipeline with full 113-page book
- ✅ Verified page 12 correctly identified as gameplay start (via FF override)
- ✅ Verified "BACKGROUND" preserved through pipeline (pick_best_engine_v1 fix)
- ✅ Verified frontmatter [1,11] and gameplay [12,111] boundaries correct
- ✅ All segmentation stages complete successfully
- ✅ Integration tests created (`tests/test_segmentation_pipeline_integration.py`) - all pass

**Impact:**
- **Story-scope impact:** Segmentation architecture prerequisite completed, enabling accurate page boundary detection for improved section detection
- **Pipeline-scope impact:** Coarse segmentation now correctly identifies gameplay start page, reducing false positives from frontmatter misclassification
- **Evidence:** 
  - Full 113-page book tested: Frontmatter [1,11], Gameplay [12,111], Endmatter [112,113]
  - FF override correctly finds BACKGROUND on page 12 (not page 5 TOC entry)
  - Integration tests pass: `tests/test_segmentation_pipeline_integration.py`
- **Next:** Continue with Priority 1: Investigate 23 missing sections from boundary detection

### 20251216-0900 — Enhanced Page Number Classification Implementation

- **Implemented**: Pattern-based page number and running header classification in `elements_content_type_v1`
  - Added `get_abstract_position()` function to generalize position analysis (vertical_align, horizontal_align)
  - Added `NumericElementInfo` dataclass to track numeric elements with their positions and segments
  - Implemented `detect_sequential_page_numbers()` - highest priority pattern detection (0.99 confidence)
  - Implemented `detect_other_header_footer_patterns()` - running headers (0.90) and consistent footers (0.85)
  - Removed numeric-only skip in repetition analysis (line 778) - now includes numeric text for pattern detection
  - Added coarse segments loading (optional) for segment-aware pattern analysis
  - Added pattern-based classification overrides that apply after initial heuristics
  - Added `--patterns-out` parameter and debug artifact generation (`element_patterns.jsonl`)
  - Updated `module.yaml` and recipe to include new parameters
  - Status: IMPLEMENTED - Ready for testing

### 20251216-0815 — Enhanced Page Number Classification Requirement

- **Requirement**: Improve `elements_content_type_v1` to better classify page numbers and running headers
  - Problem: Page numbers at margins are sometimes misclassified as Section-headers
  - Current logic: Only checks y-position when layout data exists, skips numeric text in repetition analysis
  - Solution: Add cross-page pattern analysis for numeric elements at margins
  - Plan documented in "Requirements for Improvement" section above
  - Status: PENDING - Added to story requirements

### 20251216-0730 — Critical Bugs Identified
- **Bug 1: Content Type Classifier False Positives**
  - Page numbers (e.g., "12", "13" on page 8) incorrectly classified as Section-headers
  - These are PAGE NUMBERS/REFERENCES, not section numbers
  - Root cause: Layout data missing (`layout: {}`) so upstream classifier can't use y-position checks
  - **Fix Applied**: Added validation in `detect_boundaries_code_first_v1` to treat classification as SIGNAL, not guarantee
    - Reject if layout y >= 0.92 when available (bottom = page footer)
    - Note: Removed exact match check (section_num == page) - sections CAN legitimately be on pages with same number (e.g., section 21 on page 21)
    - Note: Did NOT add first/last element checks - too FF-specific (frontmatter has centered bottom numbers, gameplay has ranges in corners)
  - **Status**: PARTIALLY FIXED - layout check added when data available, but page numbers without layout data still need other filters (frontmatter, context, sequential validation)
  
- **Bug 2: Frontmatter Filtering Order**
  - Frontmatter filtering happens AFTER duplicate resolution
  - Duplicate resolution might choose frontmatter instance (page 8) over valid instance (page 20)
  - Sequential validation then filters out frontmatter, but valid instance is already lost
  - **Fix Applied**: 
    1. Find section 1 using fit score (best consecutive match) instead of first instance
    2. Filter frontmatter BEFORE duplicate resolution (after finding section 1's page)
  - **Status**: FIXED - tested and verified page 7 correctly identified as best section 1 (fit_score=2 with consecutive [1,2])

### 20251216-0630 — Missing Sections Investigation (CORRECTED)
- **Initial Analysis Was WRONG**: Assumed sections could appear out of order (section 13 on page 8, section 3 on page 17)
- **Reality**: Sections ARE 100% properly ordered - cannot have section 13 before section 3
- **Actual Issue**: "13" on page 8 is a PAGE NUMBER, not a section number
- **Root Cause**: Two separate bugs:
  1. Content type classifier incorrectly identifies page numbers as Section-headers
  2. Frontmatter filtering happens too late in the pipeline (after duplicate resolution)

### 20251216-0630 — Missing Sections Investigation
- **Investigated 6 random missing sections:** 3, 4, 7, 11, 63, 80, 393
- **Findings:**
  - **Section 7, 11, 393:** Found in `elements_core_typed.jsonl` as Section-header, present in initial candidates (909 candidates, 397 unique sections), but MISSING from final boundaries (377 found)
  - **Root cause:** These sections are being filtered out by validation stages (page-level clustering, duplicate resolution, or sequential validation)
  - **Section 3, 4:** Not classified as Section-header (only appear in text as "3.", "4.")
  - **Section 63:** Correctly classified as Page-footer (page number, not section header)
  - **Section 80:** Not a real section header (only appears as "1.80" decimal)
- **Bug found:** `detect_boundaries_code_first_v1` uses `elem.get('element_id')` but schema uses `'id'` - fixed but didn't resolve the issue
- **Next:** Debug which filtering stage rejects sections 7, 11, 393

### 20251215-2145 — Integration Audit: Story 068 Modules Status
- **Audit Results:**
  - ✅ **`inject_missing_headers_v1`**: INTEGRATED (added in Story 068 commit)
  - ✅ **`validate_choice_completeness_v1`**: INTEGRATED (added in Story 068 commit)
  - ❌ **`detect_boundaries_code_first_v1`**: NOT INTEGRATED until now (Story 073)
    - Commit message claimed "Integrated new modules" but recipe still used `detect_gameplay_numbers_v1`
    - Just now integrated in Story 073 (20251215-2130)
  - ❌ **`extract_choices_v1`**: NOT INTEGRATED until now (Story 073)
    - Commit message didn't claim integration, but module was built and tested
    - Just now integrated in Story 073 (20251215-2130)
- **Other modules found:**
  - ⚠️ **`fine_segment_gameplay_v1`**: NOT INTEGRATED (appears to be legacy/superseded by `detect_boundaries_code_first_v1`)
    - Created earlier (before Story 068)
    - Has similar functionality but different approach
    - Appears to have been replaced, not abandoned
- **Conclusion:** Story 068 commit message was misleading. Only 2 of 4 modules were actually integrated. The 2 most critical modules (`detect_boundaries_code_first_v1` and `extract_choices_v1`) were built, tested to 99.5% coverage, but left unintegrated until Story 073.

---

## Story Completion Summary

**What Was Accomplished**:
- ✅ Multi-stage segmentation architecture implemented (semantic + pattern + FF override + merge)
- ✅ Page 12 correctly identified as gameplay start (via FF override)
- ✅ Frontmatter/gameplay boundaries corrected: [1,11] / [12,111] (was [1,15] / [16,111])
- ✅ Critical bugs fixed: pick_best_engine_v1 data loss, coarse_segment_ff_override_v1 page detection, classify_headers_v1 TypeError
- ✅ Diagnostic tool created: `scripts/trace_section_pipeline.py`
- ✅ Integration tests created: `tests/test_segmentation_pipeline_integration.py`
- ✅ All modules integrated into canonical recipe

**What Remains** (moved to Story-074):
- 23 sections missing from boundaries (investigation needed)
- 31 sections missing from portions (investigation needed)
- 19 sections requiring stubs in gamebook (investigation needed)
- 100% section coverage goal (400/400 sections)

**See Story-074**: Missing Sections Investigation — Complete 100% Coverage

---

## Expected Outcomes (Story-073 Scope - ACHIEVED)

**Success Metrics** (Story-073 scope):
- ✅ Segmentation architecture: Complete (4-stage pipeline)
- ✅ Page boundary detection: Correct (Frontmatter [1,11], Gameplay [12,111])
- ✅ Integration: All modules working together
- ✅ Diagnostic tooling: Trace script available for investigation
- ✅ Testing: Integration tests pass

**Quality Metrics** (Story-073 scope):
- ✅ No false positives in segmentation (correct boundaries)
- ✅ Critical bugs fixed (data loss, page detection, type errors)
- ✅ Frontmatter correctly identified

**Deliverables** (Story-073 scope):
- ✅ Diagnostic tool for section tracing (`scripts/trace_section_pipeline.py`)
- ✅ Integration tests (`tests/test_segmentation_pipeline_integration.py`)
- ✅ Updated pipeline with segmentation architecture
- ⏭️ 100% coverage goal moved to Story-074

