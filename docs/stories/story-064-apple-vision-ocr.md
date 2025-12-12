# Story: Apple Vision OCR (VNRecognizeTextRequest) Adapter

**Status**: Done  
**Created**: 2025-12-06  

## Goal
Add a native macOS OCR path using `VNRecognizeTextRequest` (Vision framework) and integrate it as a third engine in the OCR ensemble to improve recall/quality on Apple Silicon.

## Success Criteria
- [x] A new extract module (e.g., `extract_ocr_apple_v1`) that runs VNRecognizeTextRequest on page images/PDF pages and emits `pagelines_v1` or compatible IR.
- [x] OCR ensemble updated to accept the Apple engine as an optional third source and to include it in consensus scoring.
- [x] Recipes/docs include instructions to enable the Apple OCR path on macOS; non-mac platforms gracefully skip/disable it.

## Tasks
- [x] Spike a minimal VNRecognizeTextRequest runner (Swift helper) that outputs page text/lines.
- [x] Define module `extract_ocr_apple_v1` that wraps the runner and writes `pagelines_v1` (with bbox/confidence).
- [x] Extend `extract_ocr_ensemble_v1` to accept the Apple engine flag and merge its outputs into consensus.
- [x] Update recipes/settings to optionally enable the Apple engine on macOS; ensure safe no-op on other platforms.
- [x] Document usage and platform caveats in README/story.
- [x] Add explicit fallback/diagnostics when Swift helper build or run fails (clear error artifact, no silent drops).
- [x] Add a minimal non-mac smoke/guard test to confirm Apple OCR path cleanly no-ops outside macOS.

## Work Log
### 20251206-1830 — Story created
- **Result:** Captured scope to add macOS Vision OCR as third ensemble engine.
- **Next:** Spike VNRecognizeTextRequest runner and decide packaging (pyobjc vs Swift CLI).
### 20251206-1915 — Swift helper + modules added
- **Result:** Implemented `extract_ocr_apple_v1` (macOS-only) that compiles a Swift `VNRecognizeTextRequest` helper and emits `pagelines_v1`. Added `apple_helper.swift` and wired `extract_ocr_ensemble_v1` to accept `apple` in `--engines`, building the helper once and merging Apple text into consensus. README updated with ARM/Vision notes.
- **Notes:** Helper renders PDF pages via PDFKit thumbnails; outputs bbox-normalized lines. Requires Xcode CLTs (`swiftc`) and macOS. Not yet validated in ensemble run due to time.
- **Next:** Run ensemble with `--engines tesseract easyocr apple` on ARM hi_res, compare header/section recall vs without apple; add fallback handling for helper build failures.
### 20251212-1045 — Checklist review and update
- **Result:** Success; Tasks section already present and mostly complete.
- **Notes:** Added two explicit remaining tasks from prior notes: robust Swift-helper failure handling and a non-mac no-op smoke/guard check.
- **Next:** Execute validation runs on Deathtrap Dungeon, then implement fallback/guard tasks if gaps surface.
### 20251212-1125 — Validation run (Deathtrap Dungeon pages 1–40)
- **Result:** Success; Apple Vision engine runs cleanly and materially improves numeric header recall on a representative subset.
- **Commands:**  
  - Baseline: `PYTHONPATH=. python modules/extract/extract_ocr_ensemble_v1/main.py --pdf "input/06 deathtrap dungeon.pdf" --outdir output/runs/validate-apple-baseline-20251212-p1-40 --start 1 --end 40 --dpi 300 --lang eng --engines tesseract easyocr --write-engine-dumps --run-id validate-apple-baseline-20251212-p1-40`  
  - With Apple: `PYTHONPATH=. python modules/extract/extract_ocr_ensemble_v1/main.py --pdf "input/06 deathtrap dungeon.pdf" --outdir output/runs/validate-apple-with-apple-20251212-p1-40 --start 1 --end 40 --dpi 300 --lang eng --engines tesseract easyocr apple --write-engine-dumps --run-id validate-apple-with-apple-20251212-p1-40`
- **Artifacts inspected:**  
  - `output/runs/validate-apple-baseline-20251212-p1-40/ocr_ensemble/pages_raw.jsonl`  
  - `output/runs/validate-apple-with-apple-20251212-p1-40/ocr_ensemble/pages_raw.jsonl`  
  - `output/runs/validate-apple-*/ocr_ensemble/ocr_quality_report.json`
- **Header recall proxy:** numeric-only line count rose from **102 → 331** on pages 1–40.  
  - Baseline missed many gameplay headers entirely (e.g., page 19 had none).  
  - With Apple, page 19 includes standalone `12` and `13` headers plus fused `12-13`; page 22 includes `23`, `24`, `25` and fused `23-26`; page 29 adds `55`. These are consistent with true section headers.
- **Quality metrics (avg over report entries):**  
  - Baseline: disagreement_score 0.714, quality_score 0.252, corruption_score 0.199, missing_content_score 0.180, disagree_rate 0.000.  
  - With Apple: disagreement_score 0.814, quality_score 0.244, corruption_score 0.008, missing_content_score 0.034, disagree_rate 0.159.  
  - Interpretation: Apple sharply reduces corruption/missing-content signals; higher disagreement is expected with a third engine.
- **Notes:**  
  - Baseline run logged one missing hi‑res image warning (`page-030L-hi.png`); pagelines output still complete for 40 pages.  
  - Swift helper emits a macOS 14 deprecation warning for `usesCPUOnly`; non-fatal but should be updated in follow-up.
- **Next:** Decide whether to run full-book confirmation; then implement remaining tasks (helper fallback/diagnostics, non‑mac no‑op guard, and Swift deprecation cleanup).
### 20251212-1215 — Implemented fallback/guards and fixed Swift helper
- **Result:** Success; Apple OCR now degrades gracefully when unavailable and helper compiles on macOS 14+ without warnings or errors.
- **Changes:**  
  - `modules/extract/extract_ocr_apple_v1/main.py`: platform guard (no‑op off macOS), build/run error artifacts (`error.json`), removed deprecated `usesCPUOnly` and invalid `results=nil`.  
  - `modules/extract/extract_ocr_ensemble_v1/main.py`: platform guard in `ensure_apple_helper`, run‑level `apple_errors.jsonl`, per‑page warnings instead of silent drops.  
  - `modules/extract/extract_ocr_ensemble_v1/apple_helper.swift`: removed deprecated `usesCPUOnly`.  
  - `scripts/tests/test_apple_ocr_noop.sh`: added non‑mac smoke/guard test.
- **Smoke:** Ran Apple module on `testdata/tbotb-mini.pdf` page 1; helper builds and outputs pagelines successfully. Sample text includes “To Be or Not To Be -- Mini FF Branch…”.
- **Notes:** Initial smoke failed due to Vision API change (cannot assign to `recogReq.results`); fixed by removing manual reset.
- **Next:** Optional: full‑book (1–113) Deathtrap confirmation to quantify end‑to‑end section coverage impact.
### 20251212-1225 — Requirement trimmed per user
- **Result:** Success; removed full‑book Deathtrap Dungeon validation requirement after subset evidence accepted.
- **Notes:** Pages 1–40 validation remains in log as sufficient proof of improvement.
- **Next:** Story can close once earlier Success Criteria items are checked off (module/ensemble/docs already implemented).
### 20251212-1235 — Marked story complete
- **Result:** Success; all Tasks and Success Criteria met, story status set to Done and index updated.
- **Next:** None.
### 20251212-0913 — Documented sandbox permission caveat (sysctl)
- **Result:** Success; clarified that Apple Vision OCR can fail under restricted/sandboxed execution with `sysctlbyname for kern.hv_vmm_present failed`, producing no `apple` text.
- **Notes:** Reproduced locally: helper fails in restricted mode, succeeds with full host permissions (`sysctl kern.hv_vmm_present: 0` and helper emits JSON).
- **Next:** If we want Apple Vision to work in sandboxed runners, create a dedicated story to (a) detect the restricted mode early and auto-disable `apple`, or (b) restructure execution so Vision calls run with the necessary permissions.
