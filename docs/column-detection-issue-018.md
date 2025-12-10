# Column Detection Issue: Page 018L

## Problem

Page 018L (already split from spread) has NO columns, but column detection incorrectly found 2 columns, causing severe text fragmentation.

## Root Cause

1. **Apple OCR Not Run or Failed**: Apple OCR data not in `engines_raw` for page 018L
2. **Fallback to Image-Based Detection**: When Apple OCR fails, code falls back to `detect_column_splits(img_obj)`
3. **Over-Sensitive Detection**: `detect_column_splits` incorrectly detects 2 columns on a single-column page
4. **No Quality Check**: Column splits are accepted without checking if they fragment text

## Code Flow

```python
# Line 691-694: Try Apple OCR
apple_text, apple_lines, apple_cols, apple_lines_meta = call_apple(
    args.pdf, idx, args.lang, fast=False, helper_path=apple_helper, columns=True
)
col_spans = infer_columns_from_lines(apple_lines_meta) or apple_cols or []

# Line 699-701: Fallback to image-based detection
if not col_spans:
    col_spans = detect_column_splits(img_obj)  # ← This incorrectly finds 2 columns
col_spans = verify_columns_with_projection(img_obj, col_spans)
```

## Issues

1. **Apple OCR Told About Columns**: `columns=True` is passed even for spread pages (018L, 018R)
   - Spread pages are already split, so they shouldn't have columns
   - Apple OCR should detect columns on its own, not be told about them

2. **Image-Based Detection Too Sensitive**: `detect_column_splits` uses k-means on text pixels
   - For page 018L, some text might be slightly offset, creating false column split
   - No check if split actually makes sense (doesn't fragment words)

3. **No Quality Validation**: Column splits accepted without checking:
   - Do words get split across columns?
   - Are sentences incomplete at column boundaries?
   - Is the split actually improving OCR quality?

## Fixes Needed

1. **Let Apple OCR Detect Columns Naturally**
   - Apple OCR should detect columns on its own for all pages (spread and non-spread)
   - Spread pages (018L, 018R) can still have columns on each side
   - The `columns=True` parameter tells Apple to attempt column detection, which is fine
   - The real issue is the column detection algorithm being too sensitive

2. **Improve Column Detection Sensitivity**
   - Increase `min_gap` threshold in `infer_columns_from_lines` (currently 0.08)
   - Increase `min_spread` in `detect_column_splits` (currently 0.2)
   - Add more strict validation

3. **Add Column Split Quality Check**
   - After detecting columns, check if words are split across boundaries
   - Check for incomplete sentences at column boundaries
   - Reject column mode if quality is poor, fall back to single-column OCR

4. **Fix Apple OCR Usage**
   - Investigate why Apple OCR isn't running/failing for page 018L
   - Ensure Apple OCR data is saved to `engines_raw`
   - Use Apple OCR if it has better text than Tesseract

