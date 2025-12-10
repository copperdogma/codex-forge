# Story: Apple Vision OCR (VNRecognizeTextRequest) Adapter

**Status**: Open  
**Created**: 2025-12-06  

## Goal
Add a native macOS OCR path using `VNRecognizeTextRequest` (Vision framework) and integrate it as a third engine in the OCR ensemble to improve recall/quality on Apple Silicon.

## Success Criteria
- [ ] A new extract module (e.g., `extract_ocr_apple_v1`) that runs VNRecognizeTextRequest on page images/PDF pages and emits `pagelines_v1` or compatible IR.
- [ ] OCR ensemble updated to accept the Apple engine as an optional third source and to include it in consensus scoring.
- [ ] Recipes/docs include instructions to enable the Apple OCR path on macOS; non-mac platforms gracefully skip/disable it.
- [ ] Validation on Deathtrap Dungeon shows improved boundary/header recall versus current ensemble without Vision.

## Tasks
- [ ] Spike a minimal VNRecognizeTextRequest runner (Python + ctypes/pyobjc or Swift CLI) that outputs plain text per page.
- [ ] Define module `extract_ocr_apple_v1` that wraps the runner and writes `pagelines_v1` (including per-line coords/confidence if available).
- [ ] Extend `extract_ocr_ensemble_v1` to accept the Apple engine flag and merge its outputs into consensus (weights/tie-breaks documented).
- [ ] Update recipes/settings to optionally enable the Apple engine on macOS; ensure safe no-op on other platforms.
- [ ] Validate on Deathtrap Dungeon: run ensemble with and without Apple OCR, compare section/header counts; record improvements in story log.
- [ ] Document usage and platform caveats in README/story.

## Work Log
### 20251206-1830 — Story created
- **Result:** Captured scope to add macOS Vision OCR as third ensemble engine.
- **Next:** Spike VNRecognizeTextRequest runner and decide packaging (pyobjc vs Swift CLI).
### 20251206-1915 — Swift helper + modules added
- **Result:** Implemented `extract_ocr_apple_v1` (macOS-only) that compiles a Swift `VNRecognizeTextRequest` helper and emits `pagelines_v1`. Added `apple_helper.swift` and wired `extract_ocr_ensemble_v1` to accept `apple` in `--engines`, building the helper once and merging Apple text into consensus. README updated with ARM/Vision notes.
- **Notes:** Helper renders PDF pages via PDFKit thumbnails; outputs bbox-normalized lines. Requires Xcode CLTs (`swiftc`) and macOS. Not yet validated in ensemble run due to time.
- **Next:** Run ensemble with `--engines tesseract easyocr apple` on ARM hi_res, compare header/section recall vs without apple; add fallback handling for helper build failures.
