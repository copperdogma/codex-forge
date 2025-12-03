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
- [ ] Spike script that runs Apple OCR on a sample page set and produces pagelines JSON compatible with our index format.
- [ ] Comparative metrics on the sample: header recall, text alpha ratio, choice extraction impact vs. current ensemble.
- [ ] Recommendation (adopt / optional / drop) with tradeoffs (accuracy, latency, setup complexity).

## Tasks
- [ ] Identify the macOS APIs/CLI for Apple OCR (Vision framework / Live Text) and how to call from Python.
- [ ] Build a minimal runner that ingests images and outputs pagelines-like JSON (lines with text, page id, image path).
- [ ] Run on a representative subset (e.g., 10–20 pages with fused headers/garble) and compare to existing OCR outputs.
- [ ] Summarize metrics and propose how to integrate (optional engine slot in ensemble; divergence guard triggers, etc.).
- [ ] Keep integration optional and generic; no book-specific tuning.

## Work Log
- 2025-12-02 — Story created; scoped to evaluation of Apple OCR as a third engine; no changes to main pipeline yet.
