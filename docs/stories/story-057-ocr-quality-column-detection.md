# Story: OCR Quality & Column Detection Improvements

**Status**: Open  
**Created**: 2025-12-09  
**Parent Story**: story-054 (canonical recipe - COMPLETE)

## Goal
Improve OCR quality by fixing column detection issues, enhancing quality checks, and preventing fragmented text output. Address specific issues identified in artifact analysis where column detection incorrectly splits pages or fails to detect fragmentation.

## Success Criteria
- [ ] Column quality check correctly rejects bad column splits (e.g., page 008L fragmentation)
- [ ] Adventure Sheet forms are detected and handled appropriately (no column splitting)
- [ ] Fragmentation detection flags pages with >30% very short lines
- [ ] Column detection thresholds prevent false positives on single-column pages
- [ ] Quality checks catch fragmentation even when OCR engines agree

## Context

**Issues Identified** (from artifact analysis - see `docs/artifact-issues-analysis.md`):

1. **Page 008L - Column Fragmentation**
   - Column mode produced severely fragmented text: "1-6. This sequenc score of either ° fighting has been"
   - Quality check (`check_column_split_quality`) failed to detect fragmentation
   - Thresholds too lenient; fragmentation_score=0.27 but column mode still used

2. **Page 011R - Adventure Sheet Column Fragmentation**
   - Adventure Sheet form was split into columns, causing garbled text
   - Text completely garbled: "MONSTER ENCOI", "Cif = Shal) =", "Stanpitiwd ="
   - Average line length: 3.89 characters (extremely short)
   - Forms should not be split into columns

3. **Page 018L - Incorrect Column Detection** (already partially fixed)
   - Page has NO columns but was incorrectly split
   - Fixed in previous work, but quality checks need improvement

**Root Causes**:
- Column detection heuristics too sensitive
- Quality check doesn't detect sentence fragmentation across boundaries
- No special handling for form-like pages (grids, boxes, tables)
- Fragmentation detection exists but thresholds may be too lenient

## Tasks

### High Priority

- [ ] **Fix Column Quality Check for Page 008L**
  - **Issue**: Column mode produced severely fragmented text ("1-6. This sequenc score of either ° fighting has been")
  - **Root Cause**: Quality check (`check_column_split_quality`) failed to detect fragmentation; thresholds too lenient
  - **Mitigations**:
    - Add sentence boundary detection - if sentences are split across column boundaries, reject the split
    - Lower `fragmentation_ratio_threshold` from 0.05 to 0.02 for column mode
    - Post-column validation: use LLM to validate if text makes semantic sense
    - Re-OCR fallback: if column mode produces fragmented text, automatically re-OCR as single column

- [ ] **Detect and Handle Adventure Sheet Forms**
  - **Issue**: Page 011R (Adventure Sheet) was split into columns, causing garbled text ("MONSTER ENCOI", "Cif = Shal) =")
  - **Root Cause**: Column detection incorrectly identified form structure as columns; no special handling for forms
  - **Mitigations**:
    - Form detection: detect form-like pages (high density of short lines, boxes, "=" patterns, repeated structure)
    - Disable column mode for forms: if form detected, force single-column OCR
    - Form-aware OCR settings: use `--psm 6` (uniform block) or `--psm 11` (sparse text)
    - Layout preservation: for forms, preserve spatial relationships rather than trying to reconstruct prose
    - Post-processing: forms may need different reconstruction logic (preserve structure vs. merge lines)
    - Consider skipping forms: if forms are not needed for gameplay, skip them entirely

- [ ] **Add Fragmentation Detection to Quality Assessment**
  - Count lines with < 5 characters (very short lines)
  - Flag pages with >30% very short lines as fragmented
  - Add missing word detection (low word count per sentence)
  - Flag pages for escalation even when engines agree but text is fragmented
  - **Note**: Fragmentation detection already exists (`fragmentation_score`) but may need threshold adjustments

- [ ] **Improve Column Detection Logic** (partially done)
  - Let Apple OCR detect columns naturally (spread pages can still have columns on each side) ✅ DONE
  - Improve `infer_columns_from_lines` to be less sensitive (higher gap threshold) ✅ DONE
  - Add column detection quality check: if split fragments words, reject it ✅ DONE
  - Verify column splits don't break words across boundaries ✅ DONE
  - **Remaining**: Improve quality check to catch sentence fragmentation (see page 008L issue)

- [ ] **Add Column Splitting Quality Check** (partially done)
  - Detect when column splits fragment words ✅ DONE
  - Check for incomplete sentences at column boundaries ✅ DONE
  - Reject column mode if quality is poor, fall back to single-column OCR ✅ DONE
  - **Remaining**: Add sentence boundary detection to catch cases like page 008L

### Medium Priority

- [ ] **Improve Apple OCR Usage in Column Mode**
  - Investigate why Apple OCR lines are filtered out in column mode
  - Fix bbox matching for column filtering
  - Use Apple OCR if it has more complete text than Tesseract

- [ ] **Column Split Confidence Reporting**
  - Per-page metrics (gap size, lines/col, reason)
  - Flag low-confidence splits
  - Retain both full-page and per-column OCR when unsure

- [ ] **Layout-Aware Fusion**
  - Vote within columns; do not mix across columns when aligning
  - Ensure column boundaries are respected in fusion

## Related Work

**Previous Improvements** (from story-054):
- ✅ Column detection implemented with projection-based guard
- ✅ Column quality check added (`check_column_split_quality`)
- ✅ Fragmentation score added to quality metrics
- ✅ Column spans recorded in page metadata
- ✅ Page 018L issue fixed (no longer incorrectly split)

**Research Completed**:
- See `docs/ocr-post-processing-research.md` for SOTA techniques
- See `docs/ocr-issues-analysis.md` for detailed analysis
- See `docs/column-detection-issue-018.md` for page 018L analysis
- See `docs/artifact-issues-analysis.md` for comprehensive artifact analysis

## Work Log

### 2025-12-09 — Story created from story-054
- **Context**: Story-054 (canonical recipe) is complete. OCR quality and column detection improvements were identified as separate domain concerns.
- **Action**: Extracted OCR quality & column detection tasks from story-054 into this focused story.
- **Scope**: Focus on column detection quality checks, form detection, and fragmentation detection improvements.
- **Next**: Implement sentence boundary detection in column quality check, add form detection, adjust fragmentation thresholds.

