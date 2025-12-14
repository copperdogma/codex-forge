# Story: OCR Split Refinement — Zero Bad Slices

**Status**: Open
**Created**: 2025-12-19
**Parent Story**: story-057 (OCR quality & column detection - COMPLETE)

---

## Goal

Refine the OCR page splitting process to ensure **ZERO images are sliced badly**. Currently, some pages have text or images cut off at the split boundary, causing downstream OCR quality issues and data loss.

**Current Problem**:
- Pages 021, 023, 025, 026, 071, 074, 076, 091 have bad splits where:
  - Text is cut off at the split boundary
  - Images are cut off at the split boundary
  - Both text and images are cut off

**Root Cause**:
- Global gutter position determined by sampling a few pages (`sample_spread_decision`) is applied to all pages
- Gutter position varies across pages (binding, scanning, page layout differences)
- No validation that content isn't cut off after splitting
- No per-page gutter detection or adjustment

**Target**: 100% accuracy — every split must preserve all content (text and images) with zero cutoffs.

---

## Success Criteria

### Split Refinement (Priorities 1-5)
- [ ] **Zero bad splits**: All pages split correctly with no text or images cut off
- [ ] **Per-page gutter detection**: Each page uses its own optimal gutter position (not global)
- [ ] **Content validation**: Automatic detection of cut-off text/images after splitting
- [ ] **Recovery mechanism**: Automatic re-splitting with adjusted gutter when cutoffs detected
- [ ] **Verified on problem pages**: Pages 021, 023, 025, 026, 071, 074, 076, 091 all split correctly
- [ ] **No regressions**: All previously-good splits remain good
- [ ] **Artifact inspection**: Manual verification of split quality on all pages

### Spell-Weighted Voting (Priority 6)
- [ ] **Per-engine spell metrics computed**: Dictionary quality calculated for each engine before voting
- [ ] **Integrated into voting**: Spell quality used as tiebreaker in fusion cascade
- [ ] **Quality improvement measured**: 1-2% reduction in disagreement score on test pages
- [ ] **No performance degradation**: Spell metrics add < 5ms per page
- [ ] **Handles digit confusion**: Test cases with "t0", "1S7" correctly resolved to "to", "157"
- [ ] **Handles common typos**: Test cases with "Tum", "skilI" correctly resolved to "Turn", "skill"

---

## Context

**Current Implementation** (from `modules/common/image_utils.py` and `modules/extract/extract_ocr_ensemble_v1/main.py`):

1. **Global Gutter Detection** (`sample_spread_decision`):
   - Samples 5 pages evenly across the book
   - Finds gutter position for each sample using brightness/contrast analysis
   - Uses median of confident samples as global gutter position (clamped to 0.4-0.6)
   - Applied to ALL pages regardless of page-specific variations

2. **Simple Split** (`split_spread_at_gutter`):
   - Crops image at fixed gutter position: `left = crop(0, 0, split_x, h)`, `right = crop(split_x, 0, w, h)`
   - No validation that content is preserved
   - No detection of cut-off text or images

3. **No Quality Checks**:
   - Split happens before OCR, so no text-based validation
   - No image analysis to detect cut-off content
   - Bad splits propagate downstream and cause OCR errors

**Problem Pages Identified**:
- 021: Text/image cut off
- 023: Text/image cut off
- 025: Text/image cut off
- 026: Text/image cut off
- 071: Text/image cut off
- 074: Text/image cut off
- 076: Text/image cut off
- 091: Text/image cut off

**Related Work**:
- Story-057: OCR quality & column detection (handles column splits, not spread splits)
- Story-054: Canonical recipe (established current OCR pipeline)
- `docs/column-detection-issue-018.md`: Similar issue with column detection (different problem)

---

## Tasks

### Priority 1: Per-Page Gutter Detection

- [ ] **Implement per-page gutter detection**:
  - [ ] Modify `extract_ocr_ensemble_v1/main.py` to call `find_gutter_position()` for each page
  - [ ] Use page-specific gutter instead of global `gutter_position` from `sample_spread_decision`
  - [ ] Keep global decision for `is_spread_book` (still sample-based)
  - [ ] Add confidence threshold: if page gutter confidence is too low, fall back to global or skip split

- [ ] **Improve gutter detection algorithm**:
  - [ ] Review `find_gutter_position()` in `modules/common/image_utils.py`
  - [ ] Add edge detection to find actual binding/crease (not just brightness)
  - [ ] Consider vertical projection of text density (gutter should have low text density)
  - [ ] Add validation that detected gutter is reasonable (not too close to edges)

- [ ] **Handle edge cases**:
  - [ ] Pages with no clear gutter (low contrast) → use global or conservative split
  - [ ] Pages with content crossing gutter → detect and adjust split position
  - [ ] Pages with images spanning gutter → detect and preserve full image

### Priority 2: Content Preservation Validation

- [ ] **Detect cut-off text**:
  - [ ] After splitting, run quick OCR pass on split boundary region (±50px)
  - [ ] Check for incomplete words or characters at edges
  - [ ] Flag if text appears to be cut mid-word or mid-sentence
  - [ ] Use text density analysis: boundary region should have low text density

- [ ] **Detect cut-off images**:
  - [ ] Analyze image edges for partial content (incomplete shapes, cut-off graphics)
  - [ ] Check for high edge gradients at split boundary (suggests cut-off content)
  - [ ] Use computer vision to detect incomplete objects at boundaries
  - [ ] Flag if images appear truncated

- [ ] **Validation function**:
  - [ ] Create `validate_split_quality(left_img, right_img, gutter_x)` function
  - [ ] Returns `(is_valid: bool, issues: List[str], confidence: float)`
  - [ ] Integrate into splitting pipeline to reject bad splits

### Priority 3: Adaptive Split Recovery

- [ ] **Automatic re-splitting**:
  - [ ] If validation fails, try alternative gutter positions (±5%, ±10% from detected)
  - [ ] Test multiple split positions and pick best (highest validation score)
  - [ ] Escalate to stronger detection if all attempts fail

- [ ] **Content-aware splitting**:
  - [ ] Detect text blocks and images before splitting
  - [ ] Ensure split doesn't bisect any text block or image
  - [ ] Adjust gutter position to fall in clear gap between content blocks
  - [ ] Prefer splitting in whitespace/gutter regions

- [ ] **Fallback strategies**:
  - [ ] If per-page detection fails → use global gutter
  - [ ] If global fails → use conservative center split (0.5)
  - [ ] If all splits fail validation → mark page for manual review or escalation
  - [ ] Log all failures with diagnostics for forensics

### Priority 4: Testing & Verification

- [ ] **Test on problem pages**:
  - [ ] Run improved splitting on pages 021, 023, 025, 026, 071, 074, 076, 091
  - [ ] Manually inspect split images to verify no cutoffs
  - [ ] Compare OCR output before/after to verify text completeness
  - [ ] Document improvements for each page

- [ ] **Regression testing**:
  - [ ] Run full pipeline on 20-page smoke test
  - [ ] Verify all previously-good splits remain good
  - [ ] Check for any new bad splits introduced
  - [ ] Compare OCR quality metrics (coverage, accuracy) before/after

- [ ] **Full book validation**:
  - [ ] Run on full Fighting Fantasy book
  - [ ] Spot-check 10-20 random pages for split quality
  - [ ] Verify zero bad splits across entire book
  - [ ] Document any remaining issues

### Priority 5: Diagnostics & Logging

- [ ] **Enhanced logging**:
  - [ ] Log per-page gutter position and confidence
  - [ ] Log validation results for each split
  - [ ] Log recovery attempts and outcomes
  - [ ] Store split diagnostics in artifact metadata

- [ ] **Forensics output**:
  - [ ] Generate split quality report (per-page scores, issues)
  - [ ] Create visualization of split positions across book
  - [ ] Flag pages needing manual review
  - [ ] Include in pipeline visibility dashboard

### Priority 6: Spell-Weighted Voting Enhancement

**Context**: Currently spell checking (`spell_garble_metrics()`) is only used for post-fusion quality diagnostics and escalation triggers. It's NOT used during engine voting, which is a missed opportunity for quality improvement.

**Opportunity**: Use per-engine dictionary quality as a voting weight/tiebreaker to prefer engines with better spelling (fewer OOV words, fewer digit confusions).

- [ ] **Compute per-engine spell metrics**:
  - [ ] After outlier detection, compute `spell_garble_metrics()` for each non-outlier engine
  - [ ] Store per-engine quality scores: `oov_ratio`, `char_confusion_score`, `combined_quality`
  - [ ] Pass `engine_quality` dict to fusion functions

- [ ] **Integrate into voting cascade**:
  - [ ] Modify `_choose_fused_line()` to accept `engine_quality` parameter
  - [ ] Use spell quality as **tiebreaker** when confidence scores are close (< 0.1 difference)
  - [ ] Weight conservatively: 70% confidence, 30% spell quality
  - [ ] Only apply when `total_words >= 10` (skip short pages/headers)

- [ ] **Character-level fusion enhancement**:
  - [ ] When fusing "Turn" vs "Tum", check if candidate is in dictionary
  - [ ] Prefer dictionary words at character decision points
  - [ ] Example: 'r' vs 'm' → check if "Turn" in vocab → prefer 'r'

- [ ] **Testing & validation**:
  - [ ] Test on pages with known digit confusion ("Turn t0 157" → "Turn to 157")
  - [ ] Test on pages with common OCR typos ("Tum to" → "Turn to")
  - [ ] Measure quality improvement: expect 1-2% reduction in disagreement score
  - [ ] Verify no performance degradation (spell metrics are fast ~1ms)

**Expected Benefits**:
- Better tiebreaking when confidence scores are ambiguous
- Automatic detection of digit confusion (l↔1, o↔0, s↔5)
- Reduced character fusion errors (prefer "Turn" over "Tum")
- 1-2% quality improvement with minimal risk

**Implementation Notes**:
- Spell metrics already computed in `modules/common/text_quality.py`
- Existing wordlist includes Fighting Fantasy terms (STAMINA, SKILL, etc.)
- No new dependencies required
- See `docs/ocr-ensemble-fusion-algorithm.md` for fusion algorithm details

**Tradeoffs**:
- Small performance cost: 3-4 extra calls to `spell_garble_metrics()` per page (~3-4ms total)
- False positives on proper nouns (Zanbar, Deathtrap) → mitigated by using OOV ratio threshold
- May need tuning of confidence vs spell quality weighting (start conservative: 70/30)

---

## Implementation Notes

**Key Files to Modify**:

*Split Refinement (Priorities 1-5)*:
- `modules/common/image_utils.py`: Improve `find_gutter_position()`, add validation
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Per-page detection, validation, recovery
- `schemas.py`: Add split quality metadata to page artifacts

*Spell-Weighted Voting (Priority 6)*:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Add per-engine spell metrics computation (lines ~2615-2670)
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Modify `_choose_fused_line()` to use spell quality (lines ~1956-2049)
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Modify `fuse_characters()` for dictionary-aware fusion (lines ~1619-1714)
- `modules/common/text_quality.py`: Already has `spell_garble_metrics()` - no changes needed

**Approach**:
1. Start with per-page gutter detection (simplest improvement)
2. Add validation to catch bad splits
3. Add recovery mechanism to fix detected issues
4. Iterate until zero bad splits achieved

**Testing Strategy**:
- Unit tests for gutter detection improvements
- Integration tests on problem pages
- Full pipeline regression tests
- Manual artifact inspection (mandatory per AGENTS.md)

---

## Work Log

### 2025-12-19 — Story created
- **Context**: User identified 8 pages with bad splits (021, 023, 025, 026, 071, 074, 076, 091) where text or images are cut off
- **Action**: Created story document to track refinement of OCR splitting process
- **Scope**: Focus on per-page gutter detection, content validation, and recovery mechanisms
- **Next**: Investigate current implementation and identify root causes for problem pages

### 2025-12-14 — Added Priority 6: Spell-Weighted Voting Enhancement
- **Context**: While documenting fusion algorithm (Story 069), discovered spell checking is only used for diagnostics, not voting
- **Opportunity**: Per-engine dictionary quality could improve voting accuracy (1-2% expected improvement)
- **Research**: Existing `spell_garble_metrics()` already detects OOV words, digit confusions, character swaps
- **Approach**: Use spell quality as conservative tiebreaker (70% confidence, 30% spell quality)
- **Benefits**: Better handling of digit confusion (t0→to), common typos (Tum→Turn), minimal risk
- **Implementation**: Low-hanging fruit - spell metrics already exist, just need to pass to fusion
- **Testing**: Focus on known OCR error patterns (digit substitution, single-char typos)
- **Next**: Implement per-engine spell metrics computation and integrate into voting cascade
