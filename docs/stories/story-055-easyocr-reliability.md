# Story: Stabilize EasyOCR as a Third OCR Engine

**Status**: Open  
**Created**: 2025-12-08  

## Goal
Make easyocr a reliable third engine in the OCR ensemble (alongside tesseract and Apple Vision) for Fighting Fantasy pipelines, so all three contribute text on full-book runs (113 pages), not just short subsets.

## Success Criteria
- easyocr runs end-to-end on full Deathtrap Dungeon intake (113 pages) without per-page errors.
- `engines_raw` for the full run contains `easyocr` (non-empty text) for ≥ 95% of pages.
- `ocr_quality_report.json` lists easyocr as a contributing engine (not just errors) and disagreement reflects its presence.
- Vision escalation still works with easyocr in the mix (no regressions in coverage/quality).

## Background / Findings
- Historical “good” run `deathtrap-ocr-ensemble-gpt4v` was actually tesseract-only; easyocr never contributed.
- Subset (5 pages) now succeeds with tesseract + easyocr + apple after forcing easyocr lang to `en` and enabling model download.
- Full book (113 pages) still records `easyocr_error: ({'eng'}, 'is not supported')` on every page, despite the subset working.
- Apple Vision now works across all pages; GPT-4V escalation rewrites 40 pages; easyocr absence is the remaining gap.

## Tasks
- [ ] Instrument easyocr path to log model/language and first error message to a per-run debug file for full runs.
- [ ] Force easyocr language to `en` for full runs and confirm model download/caching is reused (no per-page init).
- [ ] Add a one-time reader warmup step (single dummy page) before the page loop to catch load errors early.
- [ ] Retry easyocr on error with `download_enabled=True` and alternate lang code (`en`, `en_legacy`) before giving up.
- [ ] Add a small “subset smoke” recipe (5 pages) that runs all three engines and fails if easyocr text is empty.
- [ ] Validate on a full intake run: confirm `engines_raw` includes easyocr text for ≥ 95% pages and update story with results.

## Work Log
### 20251208-?? — Story created
- **Context:** Full runs still lack easyocr text; subset works. Need to make easyocr reliable at full scale.
- **Next:** Add instrumentation/warmup/retry, then run full intake and check `engines_raw`/quality report.
