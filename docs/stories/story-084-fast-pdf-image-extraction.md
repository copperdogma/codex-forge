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

---

## Success Criteria

- [ ] **PDF inspection**: Confirm whether the old and pristine PDFs contain full‑page embedded images.
- [ ] **Fast extraction path**: If embedded images exist, implement a quick‑rip method (no rasterization).
- [ ] **Fallback behavior**: If images are not extractable, cleanly fall back to standard render.
- [ ] **Evidence**: Record timings and file sizes for both methods (old vs pristine).

---

## Tasks

- [ ] Inspect PDFs for embedded image streams and page‑level coverage.
- [ ] Prototype extraction using a PDF library capable of raw image extraction.
- [ ] Compare extracted images vs rendered images (dimensions, quality, orientation).
- [ ] Define decision logic: when to use fast extract vs render.
- [ ] Document results and add pipeline/recipe knobs if needed.

---

## Work Log

### 20251222-1020 — Story created
- **Result:** Success.
- **Notes:** New requirement to investigate fast extraction of embedded page images to avoid expensive rasterization.
- **Next:** Inspect both PDFs for embedded full‑page image streams.
