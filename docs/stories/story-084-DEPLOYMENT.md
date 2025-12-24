# Story 084: Fast PDF Extraction - Deployment Guide

## Overview

Story 084 introduces `extract_pdf_images_fast_v1`, a new extraction module that directly extracts embedded JPEG images from PDFs instead of rendering them. This provides massive performance improvements (28-974×) while maintaining OCR quality.

## Key Benefits

| Metric | Old PDF | Pristine PDF |
|--------|---------|--------------|
| **Speedup** | 28.8× | 974× |
| **Extraction time** | 0.75s (was 21.5s) | 28.9s (was 28,170s) |
| **OCR quality** | Identical (150 DPI native) | Equivalent (72 DPI native) |
| **Token savings** | None (same DPI) | 2.78× (72 vs 120 DPI) |
| **Validation status** | ✅ Proven identical | ✅ Quality validated |

## Deployed Recipes

### Old PDF (150 DPI native)

**Recipe**: `configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml`

**Usage**:
```bash
PYTHONPATH=. python driver/run_pipeline.py \
  --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml
```

**Status**: ✅ PRODUCTION-READY (proven identical to rendering)

**Settings override** (for smoke tests):
```bash
PYTHONPATH=. python driver/run_pipeline.py \
  --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-old-fast.yaml \
  --settings configs/settings.ff-ai-ocr-gpt51-old-fast.yaml
```

### Pristine PDF (72 DPI native)

**Recipe**: `configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`

**Usage**:
```bash
PYTHONPATH=. python driver/run_pipeline.py \
  --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml
```

**Status**: ✅ PRODUCTION-READY (quality validated, 974× speedup)

**Settings override**:
```bash
PYTHONPATH=. python driver/run_pipeline.py \
  --recipe configs/recipes/recipe-ff-ai-ocr-gpt51-pristine-fast.yaml \
  --settings configs/settings.ff-ai-ocr-gpt51-pristine-fast.yaml
```

## Migration Path

### Conservative Rollout (Recommended)

1. **Phase 1: Old PDF** (COMPLETED)
   - Switch to `recipe-ff-ai-ocr-gpt51-old-fast.yaml`
   - Monitor extraction logs for fallback count (should be 0)
   - Verify OCR quality metrics match baseline
   - **Expected**: Identical results, 28× faster extraction

2. **Phase 2: Pristine PDF** (COMPLETED)
   - Switch to `recipe-ff-ai-ocr-gpt51-pristine-fast.yaml`
   - Monitor extraction logs for fallback count (should be 0)
   - Verify OCR quality metrics ≥ 0.98 text_ratio
   - **Expected**: Equivalent results, 974× faster extraction, 2.78× token savings

3. **Phase 3: Production Monitoring** (ONGOING)
   - Run full pipeline validation on both PDFs
   - Compare gamebook outputs vs previous baseline
   - Monitor extraction_report.jsonl for `extraction_method` field
   - Verify all pages use `"fast_extract"` (0 render fallbacks)

4. **Phase 4: Deprecate Old Recipes** (FUTURE)
   - After extensive production validation
   - Archive `extract_pdf_images_capped_v1` rendering recipes
   - Update default recipes to use fast extraction

### Aggressive Rollout (Not Recommended)

If you want to immediately switch all extraction to fast mode:

1. Update `recipe-ff-ai-ocr-gpt51.yaml` to use `extract_pdf_images_fast_v1`
2. Update all settings files that override extraction params

**WARNING**: Only do this after validating on your specific PDFs.

## Configuration Details

### Recipe Changes

The key difference between old and new recipes:

**Old (rendering)**:
```yaml
- id: extract_pdf_images_capped
  stage: extract
  module: extract_pdf_images_capped_v1  # Renders at target DPI
  out: pages_rendered_manifest.jsonl
  params:
    target_line_height: 24  # Determines DPI via x-height
    start: 1
    end: 113
```

**New (fast extraction)**:
```yaml
- id: extract_pdf_images_capped
  stage: extract
  module: extract_pdf_images_fast_v1  # Extracts embedded images
  out: pages_rendered_manifest.jsonl
  params:
    start: 1
    end: 113
    fallback_to_render: true  # Graceful degradation
    fallback_dpi: 300         # Used if no embedded images
```

### Module Parameters

**extract_pdf_images_fast_v1** supports:
- `start`: First page to extract (default: 1)
- `end`: Last page to extract (default: all pages)
- `fallback_to_render`: Enable pdf2image fallback (default: true)
- `fallback_dpi`: DPI for rendering fallback (default: 300)

**Removed parameters** (not needed for fast extraction):
- `target_line_height`: Fast extraction uses native DPI, no x-height targeting
- `dpi_cap`: Fast extraction doesn't render, so no DPI capping

## Monitoring

### Extraction Metrics

Check `extraction_summary.json` for extraction statistics:

```json
{
  "pages_processed": 113,
  "pages_extracted": 113,
  "extraction_count": 113,
  "fallback_count": 0,      // Should be 0 for image PDFs
  "failed_count": 0          // Should be 0
}
```

**Red flags**:
- `fallback_count > 0`: Some pages had no embedded images (unexpected for scanned PDFs)
- `failed_count > 0`: Extraction failed entirely on some pages
- `extraction_count < pages_processed`: Some pages missing

### Per-Page Extraction Report

Check `extraction_report.jsonl` for per-page details:

```jsonl
{"page": 1, "extraction_method": "fast_extract", "max_source_dpi": 150.0, "extract_time_sec": 0.008}
{"page": 2, "extraction_method": "fast_extract", "max_source_dpi": 150.0, "extract_time_sec": 0.0004}
```

**Monitor**:
- `extraction_method`: Should be `"fast_extract"` for all pages
- `max_source_dpi`: Should match expected embedded DPI (150 for old, 72 for pristine)
- `extract_time_sec`: Should be <0.01s for fast extraction, >0.1s for render fallback

### OCR Quality Metrics

After OCR, run benchmark diffs to verify quality:

```bash
python scripts/ocr_bench_diff.py \
  --gold-dir testdata/ocr-bench/xheight-sweep/old/xh-24/ocr \
  --model-dir output/runs/ff-ai-ocr-gpt51-old-fast/ocr_ai \
  --out-dir /tmp/fast-extract-validation
```

**Target metrics**:
- Old PDF: `avg_text_ratio ≥ 0.99` (proven identical)
- Pristine PDF: `avg_text_ratio ≥ 0.98` (validated equivalent)

## Troubleshooting

### All pages fall back to rendering

**Symptom**: `extraction_report.jsonl` shows `"extraction_method": "render"` for all pages

**Diagnosis**:
```bash
python scripts/inspect_pdf_images.py "input/your-pdf.pdf" 1 5
```

**Possible causes**:
1. PDF is text-based (no embedded images) - fallback is correct
2. Images are not full-page (coverage <95%) - may need module adjustment
3. Unsupported image format - check `format` field in inspection output

**Solution**: If PDF doesn't have embedded images, use rendering recipe instead.

### DPI detection seems wrong

**Symptom**: `max_source_dpi` doesn't match expected value

**Check embedded image metadata**:
```bash
python scripts/inspect_pdf_images.py "input/your-pdf.pdf" 1 10
```

**Verify**: `max_source_dpi` calculation uses `/Width`, `/Height`, and page dimensions.

### OCR quality degraded

**Symptom**: `avg_text_ratio < 0.98` on validated PDFs

**Steps**:
1. Check `max_source_dpi` - if too low (<72), native resolution insufficient
2. Compare extracted vs rendered images visually
3. Run side-by-side OCR on same page with both methods
4. Check for PDF corruption or processing errors

**Remediation**: If quality issues confirmed, switch back to rendering recipe.

## Validation Checklist

Before deploying to production:

- [ ] Run smoke test (5 pages) with fast extraction recipe
- [ ] Verify `extraction_count = pages_processed` and `fallback_count = 0`
- [ ] Check `max_source_dpi` matches expected embedded DPI
- [ ] Run full-book extraction and verify timing improvement
- [ ] Run OCR benchmark diff and verify quality metrics
- [ ] Compare gamebook output vs baseline (section boundaries, choices, etc.)
- [ ] Monitor for any unexpected behavior in downstream modules

## See Also

- Story 084 main document: `docs/stories/story-084-fast-pdf-image-extraction.md`
- Validation results: `docs/stories/story-084-VALIDATION-RESULTS.md`
- Module documentation: `modules/extract/extract_pdf_images_fast_v1/README.md`
