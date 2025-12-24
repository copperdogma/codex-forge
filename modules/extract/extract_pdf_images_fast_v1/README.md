# extract_pdf_images_fast_v1

Fast PDF image extraction module that directly extracts embedded JPEG images from PDFs, bypassing the rendering pipeline when possible.

## Purpose

This module optimizes PDF image extraction by:
1. **Fast extraction**: Directly extracts embedded JPEG streams from PDF XObjects using pypdf
2. **DPI inspection**: Analyzes embedded image metadata to determine native resolution
3. **Smart fallback**: Falls back to pdf2image rendering if embedded images are unavailable
4. **Cost optimization**: Avoids wasteful upscaling that increases AI OCR token costs without quality benefits

## Key Insight

PDFs with embedded images (scanned books, image-based PDFs) contain JPEG data at a fixed native resolution. Rendering these PDFs at higher DPI values doesn't improve quality - it just interpolates pixels through upscaling, adding zero OCR information while increasing costs 2-3× due to larger image dimensions.

**Decision logic**: Extract embedded images at native resolution. Only render if no embedded images exist.

## When Fast Extraction is Used

Fast extraction succeeds when:
- PDF page contains embedded image XObjects (`/Subtype /Image`)
- At least one image covers ≥95% of page dimensions (full-page image)
- Image data can be successfully decoded (JPEG, JPEG2000, etc.)

Fast extraction is **skipped** (fallback to rendering) when:
- No embedded images found in XObject resources
- Images are too small (not full-page)
- Image extraction fails (corrupt data, unsupported format)

## Configuration

```yaml
extract_pdf_images_fast_v1:
  fallback_to_render: true    # Enable pdf2image fallback if extraction fails
  fallback_dpi: 300           # DPI to use for rendering fallback
```

### Settings

- `fallback_to_render` (default: `true`): If fast extraction fails, fall back to pdf2image rendering
- `fallback_dpi` (default: `300`): DPI value for rendering fallback

## Outputs

### 1. Extraction Summary (`extraction_summary.json`)

```json
{
  "pdf": "path/to/input.pdf",
  "start": 1,
  "end": 228,
  "pages_processed": 228,
  "pages_extracted": 228,
  "extraction_count": 228,
  "fallback_count": 0,
  "failed_count": 0,
  "fallback_enabled": true,
  "fallback_dpi": 300,
  "manifest": "path/to/pages_rendered_manifest.jsonl",
  "report": "path/to/extraction_report.jsonl"
}
```

### 2. Page Manifest (`pages_rendered_manifest.jsonl`)

Compatible with `split_pages_from_manifest_v1`:

```jsonl
{"schema": "page_image_v1", "pdf": "input.pdf", "page": 1, "image": "page-001.jpg", "width": 2546, "height": 4259}
{"schema": "page_image_v1", "pdf": "input.pdf", "page": 2, "image": "page-002.jpg", "width": 2493, "height": 4162}
```

### 3. Extraction Report (`extraction_report.jsonl`)

Per-page extraction metadata:

```jsonl
{"page": 1, "extraction_method": "fast_extract", "extract_time_sec": 0.0081, "max_source_dpi": 72.0, "name": "/I2", "width": 2546, "height": 4259, "is_full_page": true, "coverage_x": 1.0, "coverage_y": 1.0, "format": "JPEG", "mode": "RGB"}
{"page": 2, "extraction_method": "render", "extract_time_sec": 0.142, "max_source_dpi": null, "width": 2550, "height": 4250, "is_full_page": null, "coverage_x": null, "coverage_y": null, "format": "PNG", "mode": "RGB"}
```

**Fields**:
- `extraction_method`: `"fast_extract"` or `"render"`
- `max_source_dpi`: Native DPI of embedded image (null for rendered pages)
- `extract_time_sec`: Extraction time in seconds
- `is_full_page`: Whether extracted image covers ≥95% of page
- `coverage_x`, `coverage_y`: Image coverage ratio relative to page dimensions
- `format`: Image format (JPEG, PNG, etc.)
- `mode`: Color mode (RGB, L, etc.)

## Usage

### Standalone

```bash
PYTHONPATH=. python modules/extract/extract_pdf_images_fast_v1/main.py \
  --pdf "input/book.pdf" \
  --outdir /tmp/extraction \
  --start 1 \
  --end 100
```

### In Pipeline

Use with `split_pages_from_manifest_v1` for OCR pipeline:

```yaml
# Extract images (fast or render)
extract_pdf_images_fast_v1:
  fallback_to_render: true
  fallback_dpi: 300

# Split pages from manifest
split_pages_from_manifest_v1: {}

# OCR
extract_ocr_ai_v1:
  model: gpt-5.2
```

Pipeline flow:
1. `extract_pdf_images_fast_v1` → generates `pages_rendered_manifest.jsonl`
2. `split_pages_from_manifest_v1` → reads manifest, creates page images
3. `extract_ocr_ai_v1` → performs OCR on page images

## Performance

Benchmarked against pdf2image rendering:

| PDF Type | Native DPI | Fast Extract | Render | Speedup |
|----------|-----------|--------------|--------|---------|
| Old (150 DPI) | 150 | 0.0066s/page | 0.1904s/page | 28.8× |
| Pristine (72 DPI) | 72 | 0.0042s/page | 4.0922s/page | 974× |

For 228-page pristine PDF:
- Fast extraction: 28.9s total
- Rendering: ~15 minutes
- **Cost savings**: 2.78× fewer AI tokens (72 DPI vs upscaled 120 DPI)

## Validation

OCR quality validated against story-082 xh-24 baseline:
- Old PDF (150 DPI native): text_ratio 0.982 (1% diff from split variation, not resolution)
- Pristine PDF (72 DPI native): text_ratio 0.984 (0.4% diff, within measurement noise)

**Finding**: Story-082's xh-24 rendering was SOURCE-LIMITED to 72 DPI for pristine PDF. Attempting to render at 120 DPI was capped by `max_source_dpi`, providing zero quality benefit while increasing costs.

**Conclusion**: Fast extraction maintains OCR quality while eliminating wasteful upscaling.

## Troubleshooting

### All pages fall back to rendering

Check extraction report for `extraction_method`:
```bash
cat /tmp/extraction/extraction_report.jsonl | jq -r '.extraction_method' | sort | uniq -c
```

If all pages show `"render"`:
- PDF may not have embedded images (text-based PDF)
- Images may be in unsupported formats
- Images may not be full-page (coverage <95%)

### DPI seems wrong

Inspect embedded image metadata:
```bash
python scripts/inspect_pdf_images.py "input/book.pdf" 1 5
```

Check `max_source_dpi` in extraction report to see detected native resolution.

### Quality issues

If OCR quality degrades:
1. Check `max_source_dpi` - native resolution may be too low
2. Compare extracted image dimensions vs rendered
3. Run OCR benchmark diff to measure text_ratio
4. Consider enabling rendering for problematic pages

## See Also

- Story 084: Fast PDF Image Extraction (`docs/stories/story-084-fast-pdf-image-extraction.md`)
- Story 084 Validation Results (`docs/stories/story-084-VALIDATION-RESULTS.md`)
- Benchmark scripts: `scripts/benchmark_pdf_extraction.py`, `scripts/inspect_pdf_images.py`
