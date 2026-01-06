# Crop Illustrations from OCR Bounding Boxes

Crops illustrations from source images using bounding boxes detected by vision models during OCR.

## Overview

This module works downstream from `ocr_ai_gpt51_v1` (or other vision-based OCR modules) that detect illustrations and provide bounding box coordinates. It:

1. Reads OCR output containing illustration metadata (`illustrations` field with `bbox` and `alt`)
2. Crops each illustration from the source image using the bounding box coordinates
3. Optionally generates transparent PNG versions for B&W artwork (for rendering on custom backgrounds)
4. Outputs cropped images and a manifest with provenance metadata

## Inputs

- **ocr_manifest**: OCR JSONL file (`page_html_v1` schema) with `illustrations` field containing:
  - `alt`: Description of the illustration
  - `bbox`: Bounding box with `{x, y, width, height}` in pixels

## Outputs

- **illustration_manifest.jsonl**: Manifest with cropped illustration metadata
- **images/**: Directory containing cropped PNG files

## Parameters

- `--transparency`: Generate alpha-channel versions for B&W images (default: false)
- `--threshold`: White threshold for transparency (0-255, default: 230)

## Usage

```bash
python modules/extract/crop_illustrations_from_ocr_v1/main.py \
  --ocr-manifest output/ocr/pages_html.jsonl \
  --output-dir output/illustrations \
  --transparency \
  --threshold 230
```

## Output Schema

### illustration_manifest.jsonl (illustration_v1)

```json
{
  "schema_version": "illustration_v1",
  "module_id": "crop_illustrations_from_ocr_v1",
  "run_id": "...",
  "created_at": "2026-01-04T15:00:00Z",
  "source_image": "input/images/img-005.jpg",
  "source_page": 2,
  "filename": "page-002-000.png",
  "filename_alpha": "page-002-000-alpha.png",
  "has_transparency": true,
  "alt": "Cover illustration showing a large monstrous creature emerging from water",
  "bbox": {
    "x": 120,
    "y": 250,
    "x1": 920,
    "y1": 1350,
    "width": 800,
    "height": 1100
  }
}
```

## Transparency Processing

For B&W illustrations, the transparency feature:
- Converts grayscale to alpha channel (dark = opaque, white = transparent)
- Provides smooth anti-aliased edges
- Forces near-white pixels (above threshold) to fully transparent to avoid fringing
- Enables rendering on custom backgrounds (cream, parchment, etc.) instead of white

## Integration

Typical pipeline flow:
1. **OCR**: `ocr_ai_gpt51_v1` detects illustrations and adds bounding boxes to HTML output
2. **Crop**: `crop_illustrations_from_ocr_v1` extracts cropped images
3. **Associate**: Section association module maps illustrations to gamebook sections
4. **Build**: Build stage populates `images[]` arrays in gamebook.json

## Advantages

- **No false positives**: Vision model semantically distinguishes artwork from text
- **Accurate bounding boxes**: Vision model understands page layout
- **Alt text included**: Accessibility descriptions from OCR
- **No additional cost**: Reuses bounding boxes from existing OCR process
