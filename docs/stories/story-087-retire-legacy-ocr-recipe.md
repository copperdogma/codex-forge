# Story: Retire Legacy OCR-Only Recipe

**Status**: To Do  
**Created**: 2025-12-22  
**Priority**: Medium  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline)

---

## Goal

Remove or deprecate legacy OCR‑ensemble recipes now superseded by the GPT‑5.1 HTML‑first pipeline.

---

## Motivation

The old OCR‑ensemble recipes are slower, less accurate, and no longer needed for active development. Keeping them as defaults risks accidental use and confusion.

---

## Success Criteria

- [ ] Legacy OCR‑only recipe(s) identified and documented as deprecated.
- [ ] New GPT‑5.1 pipeline is the default/recommended path in docs.
- [ ] Legacy recipes removed or clearly marked obsolete in `docs/stories.md`, README/AGENTS as needed.
- [ ] No pipeline depends on legacy recipes (or explicitly opts in for archival use).
- [ ] Optional: legacy recipes archived under `configs/recipes/legacy/` if we want to keep them for reference.

---

## Tasks

- [ ] Inventory legacy OCR recipes and where they’re referenced.
- [ ] Decide keep‑as‑archive vs remove; update docs accordingly.
- [ ] Update recommended order and references to use GPT‑5.1 pipeline.
- [ ] Validate no active workflow depends on legacy recipes.
- [ ] Log decisions and any file moves in work log.

---

## Work Log

### 20251222-2355 — Story created
- **Result:** Success.
- **Notes:** Added to track deprecating/removing legacy OCR‑only recipes in favor of GPT‑5.1 HTML‑first pipeline.
- **Next:** Inventory legacy recipes and doc references.
