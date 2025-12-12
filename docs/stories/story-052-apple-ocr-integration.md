# Story: Evaluate Apple Vision OCR Integration

**Status**: Open  
**Created**: 2025-12-02  

## Goal
Investigate adding Apple’s native OCR/vision stack as a third engine in the OCR ensemble to improve accuracy, especially on fused headers and garbled text, while keeping the pipeline generic.

## Questions to Answer
- Accuracy: Does Apple OCR reduce header/text errors vs. current GPT-4V + tesseract mix?
- Cost/latency: Is it fast enough for our pipeline budgets?
- Integration: How to invoke it locally (macOS), manage dependencies, and merge outputs with existing ensemble logic?

## Success Criteria
- [x] Spike script that runs Apple OCR on a sample page set and produces pagelines JSON compatible with our index format.
- [x] Comparative metrics on the sample: header recall, text alpha ratio, choice extraction impact vs. current ensemble.
- [x] Recommendation (adopt / optional / drop) with tradeoffs (accuracy, latency, setup complexity).

## Tasks
- [x] Identify the macOS APIs/CLI for Apple OCR (Vision framework / Live Text) and how to call from Python.
- [x] Build a minimal runner that ingests images and outputs pagelines-like JSON (lines with text, page id, image path).
- [x] Run on a representative subset (e.g., 10–20 pages with fused headers/garble) and compare to existing OCR outputs.
- [x] Summarize metrics and propose how to integrate (optional engine slot in ensemble; divergence guard triggers, etc.).
- [x] Keep integration optional and generic; no book-specific tuning.
- [ ] Close out evaluation by linking to implementation story (064) and marking status Done if no further follow‑ups are needed.

## Work Log
- 2025-12-02 — Story created; scoped to evaluation of Apple OCR as a third engine; no changes to main pipeline yet.
### 20251212-1245 — Evaluation completed via Story 064
- **Result:** Success; Apple Vision OCR was spiked, benchmarked on Deathtrap Dungeon pages 1–40, and adopted as an optional third ensemble engine.
- **Evidence:** See `docs/stories/story-064-apple-vision-ocr.md` for implementation details, metrics, and recipes.
- **Notes:** Success Criteria and original Tasks are now satisfied by the completed implementation; remaining action is administrative close‑out.
- **Next:** If no new evaluation questions, flip this story to Done and add cross‑link in stories index.
