# Story: OCR Ensemble Three-Engine Voting

**Status**: Open
**Created**: 2025-12-10
**Parent Story**: story-061 (OCR Ensemble Fusion - DONE)
**Depends On**: story-055 (EasyOCR Reliability)

## Goal

Complete the OCR ensemble fusion improvements by enabling EasyOCR as a third engine and implementing three-engine voting. This story contains work deferred from story-061 that requires story-055 to be completed first.

## Background

Story-061 implemented significant improvements to OCR fusion:
- Removed document-level Apple OCR discard (R1)
- Character-level voting within lines (R2)
- Levenshtein distance outlier detection (R4)
- Confidence-weighted selection for Apple Vision (R5 partial)
- Inline GPT-4V escalation for critical failures (R6)
- Form page threshold improvements (Task 5.1)
- Two-column fragment filtering (Task 5.2)

However, EasyOCR integration was blocked by a numpy version conflict (numpy 2.x vs 1.x required by easyocr). This story completes the remaining work once story-055 resolves EasyOCR reliability issues.

## Requirements

### R1: Enable EasyOCR as Third Engine (from story-061 R3)

**Problem**: EasyOCR fails on full runs due to numpy version conflict and initialization issues.

**Prerequisites**: story-055 must resolve EasyOCR installation/reliability issues.

**Solution**: Once EasyOCR is stable, enable it in the OCR ensemble:

1. Force language to `en` for all pages
2. Add warmup step before page loop
3. Retry with `download_enabled=True` on error

**Acceptance Criteria**:
- [ ] EasyOCR runs successfully on full book (113 pages)
- [ ] `engines_raw` includes `easyocr` text for ≥95% of pages
- [ ] Three-engine voting produces better results than two-engine

### R2: Implement Three-Engine Voting

**Problem**: Current fusion only handles Tesseract + Apple Vision. With EasyOCR enabled, need true 3-way voting.

**Solution**: Extend `align_and_vote()` and `fuse_characters()` to handle 3+ engines:

1. Use existing outlier detection to identify garbage engines
2. For character-level fusion, use majority voting across 3 engines
3. If 2 engines agree and 1 differs, use majority
4. If all 3 differ, use confidence weighting

**Acceptance Criteria**:
- [ ] `align_and_vote()` handles 3+ engine inputs
- [ ] `fuse_characters()` uses majority voting with 3 engines
- [ ] Outlier detection excludes garbage engines before voting
- [ ] Test coverage for 3-engine scenarios

### R3: Extract Tesseract Confidence (from story-061 R5)

**Problem**: Only Apple Vision confidence is used; Tesseract word-level confidence could improve fusion.

**Solution**: Extract confidence scores from Tesseract output:

1. Use `pytesseract.image_to_data()` with `output_type=Output.DICT`
2. Extract `conf` field for each word
3. Pass to fusion functions for weighted voting

**Acceptance Criteria**:
- [ ] Tesseract confidence extracted via `image_to_data()`
- [ ] Confidence passed to `align_and_vote()` as `primary_confidences`
- [ ] Both engine confidences used in character-level fusion

### R4: Test Inline Escalation on Real Data

**Problem**: Inline GPT-4V escalation was implemented but not tested on actual critical failure pages.

**Solution**: Run the OCR pipeline with `--inline-escalation` on pages known to have critical failures:

1. Identify pages with high corruption or disagreement from previous runs
2. Run with inline escalation enabled
3. Compare output quality before/after escalation
4. Document cost/quality tradeoffs

**Acceptance Criteria**:
- [ ] Test run with `--inline-escalation` on 5+ critical failure pages
- [ ] Quality comparison documented
- [ ] Cost per escalation tracked
- [ ] Recommendations for threshold tuning

## Tasks

### Phase 1: Enable EasyOCR (requires story-055)
- [ ] Verify EasyOCR installs and runs after story-055 fixes
- [ ] Add warmup/retry logic to OCR module
- [ ] Test on full book (113 pages)
- [ ] Update histogram to show EasyOCR contribution

### Phase 2: Three-Engine Voting
- [ ] Extend `align_and_vote()` for 3+ engines
- [ ] Implement majority voting in `fuse_characters()`
- [ ] Add tests for 3-engine scenarios
- [ ] Run regression test comparing 2-engine vs 3-engine

### Phase 3: Tesseract Confidence
- [ ] Extract confidence from Tesseract
- [ ] Pass to fusion functions
- [ ] Test confidence-weighted 3-engine voting

### Phase 4: Inline Escalation Testing
- [ ] Identify critical failure test pages
- [ ] Run with `--inline-escalation`
- [ ] Document results and recommendations

## Related Stories

- story-055-easyocr-reliability.md - **PREREQUISITE** - Must be completed first
- story-061-ocr-ensemble-fusion.md - Parent story (DONE)
- story-057-ocr-quality-column-detection.md - Original OCR quality story

## Work Log

### 2025-12-10 — Story created
- **Context**: Created to track work deferred from story-061 due to EasyOCR numpy conflict
- **Deferred items**: R3 (EasyOCR), 3-engine voting, Tesseract confidence, inline escalation testing
- **Blocking**: Requires story-055 (EasyOCR reliability) to be completed first
