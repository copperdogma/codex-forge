# Story: X-Height Measurement and Target Investigation

**Status**: To Do  
**Created**: 2025-12-24  
**Priority**: High  
**Parent Stories**: story-082 (Large-Image PDF Cost Optimization), story-084 (Fast PDF Image Extraction)

---

## Goal

Investigate and resolve two critical issues with x-height measurement and target selection:

1. **X-height measurement accuracy**: The system reports x-height values that don't match manual measurements in image editing software (e.g., Photoshop), suggesting the measurement algorithm may be incorrect.
2. **Optimal x-height target**: Re-evaluate whether 24px is the correct target, given that native 14px x-height appears to produce excellent OCR results.

---

## Context

### Related Stories

- **story-082**: Established the 24px x-height target through an OCR quality sweep across multiple x-height values (16/20/24/28px). Found that xh-24 provided good quality for both old and pristine PDFs, with text ratios of 0.9923 (old) and 0.9878 (pristine).
- **story-084**: Implemented fast PDF image extraction with x-height normalization. Simplified the normalization logic to measure native pixel x-height (removing DPI normalization complexity).

### Current Behavior

- **Old PDF** (150 DPI source): System reports observed=16.0px, target=24px, scale=1.0 (no resize)
- **Pristine PDF** (72 DPI source): System reports observed=14.5px, target=24px, scale=1.0 (no resize)
- **Manual measurement** (pristine PDF): User measures 47px x-height in Photoshop, which is ~3.2× larger than system's 14.5px measurement

### Problem Statement

1. **Measurement discrepancy**: System's x-height measurement (14.5px) doesn't match manual measurement (47px) for pristine PDF. This suggests:
   - The `_estimate_line_height_px` algorithm may be measuring something other than true x-height
   - The algorithm may be incorrectly normalizing or processing the measurement
   - There may be a bug in how the measurement is calculated or reported

2. **Target validation**: The 24px target was determined in story-082, but:
   - Old PDF has native 14px x-height and produces excellent OCR quality
   - Pristine PDF has native ~14px x-height (per system) or ~47px (per manual measurement)
   - If native 14px works well, why target 24px? This may be unnecessarily large.

---

## Success Criteria

- [ ] **Measurement accuracy**: System's x-height measurement matches manual measurements within reasonable tolerance (±10%)
- [ ] **Algorithm verification**: `_estimate_line_height_px` algorithm is verified to measure true x-height (height of lowercase letters like 'x', 'a', 'e')
- [ ] **Target re-evaluation**: Determine optimal x-height target through empirical testing:
  - Test OCR quality at multiple x-heights (12px, 14px, 16px, 20px, 24px, 28px)
  - Compare quality metrics (text ratio, HTML ratio) across targets
  - Identify minimum x-height that maintains acceptable quality
- [ ] **Documentation**: Document findings with evidence (measurement comparisons, OCR quality metrics, cost implications)
- [ ] **Implementation**: Update x-height target if a lower value is found to be optimal

---

## Tasks

### Phase 1: Measurement Investigation
- [ ] **Manual measurement baseline**: Measure x-height manually in Photoshop/ImageJ for sample pages from both PDFs
  - Old PDF: Measure 3-5 representative pages
  - Pristine PDF: Measure 3-5 representative pages
  - Document measurement method (which letter, how measured)
- [ ] **Algorithm analysis**: Review `_estimate_line_height_px` implementation to understand what it's actually measuring
  - Check if it measures line height (ascender to descender) vs x-height (baseline to midline)
  - Verify normalization logic (if any)
  - Check for bugs in the measurement calculation
- [ ] **Comparison**: Compare system measurements vs manual measurements
  - Identify discrepancies
  - Determine root cause (algorithm issue, normalization bug, or measurement method difference)
- [ ] **Fix or document**: Either fix the algorithm to match manual measurements, or document why the difference exists and is acceptable

### Phase 2: Target Re-evaluation
- [ ] **Baseline quality**: Establish baseline OCR quality at native x-heights
  - Old PDF @ native 14px (or measured value)
  - Pristine PDF @ native 14px or 47px (depending on measurement resolution)
- [ ] **Quality sweep**: Run OCR quality tests across multiple x-height targets
  - Test targets: 12px, 14px, 16px, 18px, 20px, 24px, 28px
  - Use same benchmark pages as story-082
  - Measure: text ratio, HTML ratio, cost per page
- [ ] **Analysis**: Determine optimal x-height target
  - Find minimum x-height that maintains quality threshold (e.g., text ratio ≥ 0.98)
  - Consider cost implications (larger x-height = more tokens)
  - Document trade-offs
- [ ] **Recommendation**: Propose new target (if different from 24px) with justification

### Phase 3: Implementation
- [ ] **Update target**: Update `target_line_height` default if new optimal value is found
- [ ] **Update recipes**: Update recipes to use new target (if changed)
- [ ] **Update documentation**: Update story-082 and story-084 with findings
- [ ] **Validation**: Run full pipeline with new target and verify quality maintained

---

## Investigation Plan

### Measurement Method Comparison

**Manual measurement (Photoshop)**:
- Select a lowercase letter (e.g., 'w', 'x', 'a')
- Measure height from baseline to midline (x-height)
- Record in pixels

**System measurement (`_estimate_line_height_px`)**:
- Converts image to grayscale
- Thresholds to find ink pixels
- Analyzes row-wise ink density
- Finds runs of rows with consistent ink density
- Returns median run length

**Hypothesis**: The system may be measuring line height (full line including ascenders/descenders) rather than x-height (baseline to midline of lowercase letters).

### Target Re-evaluation Plan

1. **Establish native baselines**:
   - Old PDF: Measure actual native x-height (manual + system)
   - Pristine PDF: Measure actual native x-height (manual + system)
   - Run OCR on native images to establish baseline quality

2. **Sweep x-height targets**:
   - Use `scripts/ocr_bench_xheight_sweep.py` or similar
   - Test 12px, 14px, 16px, 18px, 20px, 24px, 28px
   - Use same 9-page benchmark set from story-082
   - Measure text ratio, HTML ratio, token usage

3. **Analysis**:
   - Plot quality vs x-height
   - Identify quality threshold (e.g., text ratio ≥ 0.98)
   - Find minimum x-height that meets threshold
   - Consider cost (tokens scale with image size)

---

## Expected Outcomes

1. **Measurement accuracy**: System measurements will match manual measurements, or we'll understand and document why they differ
2. **Optimal target**: We'll identify the minimum x-height that maintains OCR quality, potentially lower than 24px
3. **Cost savings**: If optimal target is < 24px, we'll reduce OCR costs by processing smaller images
4. **Documentation**: Clear understanding of what x-height means and how to measure it correctly

---

## Work Log

### 2025-12-24 — Story created
- **Result**: Story created to investigate x-height measurement discrepancy and target validation
- **Context**: User discovered that pristine PDF manual measurement (47px) doesn't match system measurement (14.5px), and questions whether 24px target is optimal given that native 14px works well
- **Next**: Begin Phase 1 investigation (measurement accuracy)

---

## References

- **story-082**: Large-Image PDF Cost Optimization — established 24px target through x-height sweep
- **story-084**: Fast PDF Image Extraction — implemented x-height normalization with simplified pixel-based logic
- **Measurement algorithm**: `modules/extract/extract_pdf_images_fast_v1/main.py::_estimate_line_height_px`
- **OCR bench script**: `scripts/ocr_bench_xheight_sweep.py`
- **Benchmark data**: `testdata/ocr-bench/xheight-sweep/`

