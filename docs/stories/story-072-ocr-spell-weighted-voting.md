# Story: OCR Spell-Weighted Voting Enhancement

**Status**: To Do
**Created**: 2025-12-19
**Parent Story**: story-070 (OCR Split Refinement - COMPLETE)
**Related Stories**: story-063 (OCR Ensemble Three-Engine Voting - DONE), story-069 (PDF Text Extraction Engine - DONE)

---

## Goal

Enhance the OCR ensemble voting algorithm to use per-engine spell quality as a tiebreaker. Currently spell checking (`spell_garble_metrics()`) is only used for post-fusion quality diagnostics and escalation triggers. It's NOT used during engine voting, which is a missed opportunity for quality improvement.

**Expected Impact**: 1-2% quality improvement with minimal risk and performance cost.

---

## Success Criteria

- [ ] **Per-engine spell metrics computed**: Dictionary quality calculated for each engine before voting
- [ ] **Integrated into voting**: Spell quality used as tiebreaker in fusion cascade
- [ ] **Quality improvement measured**: 1-2% reduction in disagreement score on test pages
- [ ] **No performance degradation**: Spell metrics add < 5ms per page
- [ ] **Handles digit confusion**: Test cases with "t0", "1S7" correctly resolved to "to", "157"
- [ ] **Handles common typos**: Test cases with "Tum", "skilI" correctly resolved to "Turn", "skill"

---

## Context

**Current Implementation**:
- Spell checking (`spell_garble_metrics()`) exists in `modules/common/text_quality.py`
- Used only for post-fusion diagnostics and escalation triggers
- NOT used during engine voting/fusion decisions
- Existing wordlist includes Fighting Fantasy terms (STAMINA, SKILL, etc.)

**Opportunity**:
- Use per-engine dictionary quality as a voting weight/tiebreaker
- Prefer engines with better spelling (fewer OOV words, fewer digit confusions)
- Low-hanging fruit: spell metrics already exist, just need to pass to fusion

**Related Work**:
- Story-063: OCR Ensemble Three-Engine Voting (established fusion algorithm)
- Story-069: PDF Text Extraction Engine (documented fusion algorithm)
- Story-070: OCR Split Refinement (where this was originally scoped)

---

## Tasks

### Task 1: Compute Per-Engine Spell Metrics

- [ ] **After outlier detection**, compute `spell_garble_metrics()` for each non-outlier engine
- [ ] Store per-engine quality scores: `oov_ratio`, `char_confusion_score`, `combined_quality`
- [ ] Pass `engine_quality` dict to fusion functions
- [ ] Only compute for engines with sufficient text (`total_words >= 10`)

**Key Files**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Add spell metrics computation (lines ~2615-2670)

### Task 2: Integrate into Voting Cascade

- [ ] Modify `_choose_fused_line()` to accept `engine_quality` parameter (lines ~1956-2049)
- [ ] Use spell quality as **tiebreaker** when confidence scores are close (< 0.1 difference)
- [ ] Weight conservatively: 70% confidence, 30% spell quality
- [ ] Only apply when `total_words >= 10` (skip short pages/headers)

**Key Files**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Modify `_choose_fused_line()` (lines ~1956-2049)

### Task 3: Character-Level Fusion Enhancement

- [ ] Modify `fuse_characters()` for dictionary-aware fusion (lines ~1619-1714)
- [ ] When fusing "Turn" vs "Tum", check if candidate is in dictionary
- [ ] Prefer dictionary words at character decision points
- [ ] Example: 'r' vs 'm' → check if "Turn" in vocab → prefer 'r'

**Key Files**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Modify `fuse_characters()` (lines ~1619-1714)

### Task 4: Testing & Validation

- [ ] Test on pages with known digit confusion ("Turn t0 157" → "Turn to 157")
- [ ] Test on pages with common OCR typos ("Tum to" → "Turn to")
- [ ] Measure quality improvement: expect 1-2% reduction in disagreement score
- [ ] Verify no performance degradation (spell metrics are fast ~1ms)
- [ ] Run regression tests to ensure no regressions

---

## Expected Benefits

- **Better tiebreaking**: When confidence scores are ambiguous, spell quality breaks ties
- **Automatic digit confusion detection**: Handles l↔1, o↔0, s↔5 substitutions
- **Reduced character fusion errors**: Prefers "Turn" over "Tum" when dictionary-aware
- **1-2% quality improvement**: Measurable improvement with minimal risk
- **Low performance cost**: ~3-4ms per page (negligible compared to OCR time)

---

## Implementation Notes

**Key Files to Modify**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`:
  - Add per-engine spell metrics computation (lines ~2615-2670)
  - Modify `_choose_fused_line()` to use spell quality (lines ~1956-2049)
  - Modify `fuse_characters()` for dictionary-aware fusion (lines ~1619-1714)
- `modules/common/text_quality.py`: Already has `spell_garble_metrics()` - no changes needed

**Approach**:
1. Compute spell metrics for each engine after outlier detection
2. Pass engine quality scores to fusion functions
3. Use as conservative tiebreaker (70% confidence, 30% spell quality)
4. Add dictionary-aware character fusion for common OCR errors

**Testing Strategy**:
- Unit tests for spell metrics computation
- Integration tests on known OCR error patterns
- Regression tests to ensure no quality degradation
- Performance benchmarks to verify < 5ms overhead

---

## Tradeoffs

- **Performance**: Small cost (~3-4ms per page) for 3-4 extra calls to `spell_garble_metrics()`
- **False positives**: Proper nouns (Zanbar, Deathtrap) may trigger OOV warnings → mitigated by using OOV ratio threshold
- **Weighting**: May need tuning of confidence vs spell quality weighting (start conservative: 70/30)

---

## Work Log

### 2025-12-19 — Story Created
- **Context**: Extracted from Story-070 Priority 6 (Spell-Weighted Voting Enhancement)
- **Rationale**: Spell-weighted voting is unrelated to page splitting, deserves its own story
- **Status**: Ready to implement
- **Next**: Implement per-engine spell metrics computation and integrate into voting cascade

---

## References

- `docs/ocr-ensemble-fusion-algorithm.md`: Fusion algorithm details
- `modules/common/text_quality.py`: `spell_garble_metrics()` implementation
- Story-063: OCR Ensemble Three-Engine Voting (fusion algorithm)
- Story-069: PDF Text Extraction Engine (fusion documentation)

