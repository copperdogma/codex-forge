# Story: Central Escalation Cache (Premium OCR Overlay)

**Status**: To Do  
**Created**: 2025-12-18  
**Parent Stories**: story-078 (boundary ordering escalation), story-035 (FF pipeline optimization)  
**Related Stories**: story-068 (FF boundary detection), story-073 (segmentation architecture), story-074 (100% coverage)

---

## Goal

Introduce a **central, shared escalation cache** that produces **premium OCR overlays** (full text + section headers) for specific pages, and can be reused across boundary detection, extraction, and validation modules. This prevents duplicate vision calls and ensures consistent provenance.

---

## Rationale

Today, escalation is **module‑local**: each module uses its own `EscalationCache` and prompt, producing cache artifacts under that module’s output directory. This leads to:
- repeated escalations of the same pages by different modules,
- inconsistent prompts/outputs,
- fragmented provenance.

A central escalation cache makes sense if the escalation output is **generic premium OCR** that any module can consume.

---

## Success Criteria

- [ ] **Central cache artifact**: A shared `output/runs/<run_id>/escalation_cache/` directory with per‑page JSON overlays.
- [ ] **Generic prompt**: Vision escalation returns full text + section headers (no downstream feature extraction).
- [ ] **Module reuse**: At least two modules (boundary detection + extraction) consume the same cache without re‑calling vision.
- [ ] **No duplicate calls**: If a page exists in the central cache, no module re‑escalates it.
- [ ] **Provenance**: Cached overlays record `triggered_by`, `trigger_reason`, model, and timestamp.
- [ ] **Artifacts inspected**: Verified on a recent full run by inspecting cache overlays and downstream outputs.

---

## Tasks

### Priority 1: Central Cache Artifact
- [ ] Define central cache path: `output/runs/<run_id>/escalation_cache/page_XXX.json`.
- [ ] Implement shared loader/writer in `modules/common/escalation_cache.py`.
- [ ] Add a “cache overlay” schema (page, image_paths, model, sections, full_text, etc).

### Priority 2: Generic Vision Prompt
- [ ] Create a single prompt for premium OCR: **all text + all section headers**, no feature extraction.
- [ ] Ensure consistent output schema.

### Priority 3: Module Integration
- [ ] Update `detect_boundaries_code_first_v1` to use the central cache.
- [ ] Update `portionize_ai_extract_v1` (or its pre‑extract guard) to use the central cache.
- [ ] Ensure modules never call vision directly if central cache exists.

### Priority 4: Validation
- [ ] Run on the latest full FF run; verify cache hits and reduced vision calls.
- [ ] Confirm downstream outputs use cache text for escalated pages.
- [ ] Document results with artifact inspection.

---

## Work Log

### 20251218-1620 — Story created (central cache proposal)
- **Result:** Success; story scoped for a shared escalation cache and premium OCR overlay.
- **Notes:** This is an architectural improvement; keep Story‑078 focused on targeted ordering/span escalation.
- **Next:** Implement central cache path + generic prompt, then integrate with boundary detection and extraction.
