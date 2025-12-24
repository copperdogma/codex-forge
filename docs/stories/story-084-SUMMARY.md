# Story 084: Fast PDF Image Extraction - Summary

## TL;DR

**Finding:** Both PDFs can use fast extraction for **massive speedups** (28× to 974×) AND **cost savings** (2.78× fewer AI tokens for pristine). Old PDF is guaranteed identical quality. Pristine PDF needs OCR quality validation, but upscaling at 120 DPI is wasteful - native 72 DPI should perform equally well or better.

## CRITICAL INSIGHT (20251224)

**Story-082's upscaling is wasteful:** Rendering pristine PDF at 120 DPI when source is embedded at 72 DPI is upscaling via interpolation. Upscaling adds ZERO OCR information, just bigger pixels that cost 2.78× more AI tokens. Native extraction at 72 DPI is both faster (974×) AND cheaper without quality loss.

## Investigation Results

### Old PDF (`06 deathtrap dungeon.pdf`)
- **Embedded DPI:** 150
- **Target OCR DPI:** 150
- **Speedup:** 28.8× faster (0.0066s vs 0.1904s per page)
- **Quality:** **IDENTICAL** to rendering
- **Recommendation:** ✅ **Use fast extraction** (no downside)

### Pristine PDF (`deathtrapdungeon00ian_jn9_1 - from internet archive.pdf`)
- **Embedded DPI:** 72 (native resolution)
- **Current Render DPI:** 120 (**wasteful upscaling from 72 DPI source**)
- **Speedup:** 974× faster (0.0042s vs 4.0922s per page)
- **Cost savings:** 2.78× fewer AI tokens (native 72 DPI vs upscaled 120 DPI)
- **Quality:** Upscaling adds zero OCR information; native should be equivalent or better
- **Recommendation:** ⚠️ **MUST validate OCR quality** - but native extraction expected to pass (upscaling doesn't help OCR)

## Implementation Plan

### Phase 1: Investigation (✅ COMPLETED)
- Confirmed both PDFs have full-page embedded JPEGs
- Prototyped fast extraction using pypdf
- Identified upscaling waste in current approach
- Documented 974× speedup + 2.78× cost savings

### Phase 2: Quality Validation (🚨 CRITICAL - BLOCKING)

**MUST PASS before any implementation. Zero tolerance for quality degradation.**

#### Test 2.1: Old PDF Baseline
- Extract all benchmark pages at native 150 DPI
- Run full OCR benchmark
- **Pass criteria:** text_ratio ≥ 0.999 (virtually identical)
- **Expected:** PASS (native = render DPI, guaranteed identical)

#### Test 2.2: Pristine PDF Validation
- Extract all 9 mapped benchmark pages at native 72 DPI
- Run full OCR benchmark with table rescue
- **Pass criteria:** avg_text_ratio ≥ 0.98779 (current xh-24 baseline)
- **Expected:** PASS (native preserves JPEG quality, upscaling doesn't help)

#### Test 2.3: Edge Case Testing
- Table-heavy pages (061, 067, 091, 100, 190)
- Maps and diagrams
- Low-contrast pages
- **Pass criteria:** No new failures vs baseline

See `docs/stories/story-084-VALIDATION-PLAN.md` for detailed test procedures.

### Phase 3: Implementation (⏸️ BLOCKED until Phase 2 passes)
- Create `extract_pdf_images_fast_v1` module
- Add feature flag (default: off)
- Add fallback for non-image PDFs
- Document decision logic

### Phase 4: Deployment (Conservative rollout)
- Enable for old PDF first (proven safe)
- Enable for pristine PDF only if validation passes
- Monitor production metrics
- Remove rendering paths only after extensive validation

## Scripts Created

1. **`scripts/inspect_pdf_images.py`** - Analyze PDF XObject structure and embedded image metadata
2. **`scripts/extract_pdf_images_fast.py`** - Fast extraction prototype using pypdf
3. **`scripts/benchmark_pdf_extraction.py`** - Performance comparison (fast vs render)
4. **`scripts/compare_extraction_quality.py`** - Quality comparison (dimensions, DPI)

## Decision Framework (UPDATED 20251224)

**Core principle:** NEVER upscale for AI OCR - adds zero information, wastes tokens.

```python
if has_embedded_full_page_images:
    # Fast extraction at native resolution
    extract_at_native_resolution()

    # Only downsample if x-height TOO HIGH (>30px)
    if x_height > MAX_TARGET_X_HEIGHT:
        downsample_to_target()

    # NEVER upscale if x-height too low
    # (source doesn't have higher res data)
else:
    # No embedded images (composite/vector PDF)
    # Render at minimum viable DPI
    render_at_minimum_viable_dpi()
```

**Quality validation is MANDATORY:**
- Any change MUST maintain or improve OCR quality
- Run full benchmarks, not just samples
- Require avg_text_ratio ≥ current baseline
- Test edge cases: tables, maps, low-contrast
- Conservative rollout with feature flag

## Next Steps

1. ✅ **Investigation complete** - both PDFs viable for fast extraction
2. 🚨 **BLOCKING: OCR quality validation** (Phase 2) - MUST pass before implementation
   - Old PDF: Run benchmark at native 150 DPI (expect identical)
   - Pristine PDF: Run benchmark at native 72 DPI (expect ≥ 0.98779 text_ratio)
   - Edge cases: Tables, maps, diagrams
   - Statistical validation across full benchmark set
3. ⏸️ **Implement module** (Phase 3) - blocked until validation passes
4. ⏸️ **Add configuration** (Phase 3) - feature flag, conservative rollout
5. ⏸️ **Document usage** (Phase 4) - only after production validation

## Critical Quality Requirement

**Zero tolerance for OCR degradation.** Cost savings are NOT worth even 1% quality loss. Phase 2 validation is MANDATORY before any implementation.

## References

- **Story document:** `docs/stories/story-084-fast-pdf-image-extraction.md`
- **Related:** story-082 (DPI optimization), story-081 (GPT-5.1 OCR pipeline)
- **Benchmark data:** `/tmp/cf-fast-extract-old/extract_report.json`, `/tmp/cf-fast-extract-pristine/extract_report.json`
