# Story: Fast PDF Image Extraction (Embedded Streams)

**Status**: To Do  
**Created**: 2025-12-22  
**Priority**: Medium  
**Related Stories**: story-082 (large-image cost optimization), story-081 (GPT-5.1 OCR pipeline)

---

## Goal

Determine whether input PDFs contain flat, embedded page images that can be extracted directly (fast “rip”) instead of full rasterization. If possible, add a fast extraction path; otherwise fall back to rendering.

---

## Motivation

Rasterizing high‑resolution PDFs is slow and expensive. If page images are embedded as single full‑page streams, we can extract them in seconds and reduce end‑to‑end runtime significantly.

**Related investigation:** story-082 established that embedded image DPI metadata can be misleading (pristine PDF reports 72 DPI max via XObject despite very large MediaBox). We should not trust DPI metadata alone and may need to re-extract specific pages at higher render DPI for better OCR, even if fast-rip is available. See `docs/stories/story-082-large-image-pdf-cost-optimization.md`.

---

## Success Criteria

- [ ] **PDF inspection**: Confirm whether the old and pristine PDFs contain full‑page embedded images.
- [ ] **Fast extraction path**: If embedded images exist, implement a quick‑rip method (no rasterization).
- [ ] **Fallback behavior**: If images are not extractable, cleanly fall back to standard render.
- [ ] **Evidence**: Record timings and file sizes for both methods (old vs pristine).
- [ ] **DPI metadata caution**: If fast extraction is used, document whether embedded image DPI looks trustworthy and when to re-render at higher DPI (e.g., 300) for selected pages/sections.

---

## Tasks

- [ ] Inspect PDFs for embedded image streams and page‑level coverage.
- [ ] Prototype extraction using a PDF library capable of raw image extraction.
- [ ] Compare extracted images vs rendered images (dimensions, quality, orientation).
- [ ] Define decision logic: when to use fast extract vs render.
- [ ] Document results and add pipeline/recipe knobs if needed.
- [ ] Add guidance for re-rendering selected pages at higher DPI (e.g., 300) when embedded DPI appears too low for OCR quality.

---

## Work Log

### 20251222-1020 — Story created
- **Result:** Success.
- **Notes:** New requirement to investigate fast extraction of embedded page images to avoid expensive rasterization.
- **Next:** Inspect both PDFs for embedded full‑page image streams.

### 20251222-2345 — Added DPI caveat and re-render guidance
- **Result:** Success.
- **Notes:** Linked story-082 findings: embedded image DPI can be misleading (pristine PDF XObject reported 72 DPI). Added requirement to document when to override fast extract with higher-DPI renders for OCR quality.
- **Next:** During fast-extract evaluation, record DPI metadata and determine when to re-render selected pages at higher DPI.
