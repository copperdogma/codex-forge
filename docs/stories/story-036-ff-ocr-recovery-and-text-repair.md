# Story: Fighting Fantasy OCR Recovery & Text Repair

**Status**: Open  
**Created**: 2025-11-30  
**Parent Story**: story-035 (partial success)

---

## Goal

Achieve near-complete section recall and readable text by recovering OCR-missed headers and repairing garbled sections, then validating the full Fighting Fantasy gamebook output.

## Success Criteria

- [ ] Missing sections reduced to <5 (from 18 currently).
- [ ] No-text sections reduced to <50 (from 163 currently).
- [ ] Choices missing reduced below 30 (from 65 currently).
- [ ] Validation passes on full range 1–400.
- [ ] Spot-check shows removed numeric clutter, readable text, and recovered headers for prior gaps (e.g., 11, 127, 273, 300, 314, 337, 393).

## Tasks

### OCR/Header Recovery
- [ ] Resolve OpenMP SHM/permission issue blocking intake so full pipeline can re-run cleanly.
- [ ] Re-OCR or GPT-vision header hunt on gap spans covering missing IDs: 10–12, 123–129, 225–234, 270–274, 279–282, 299–304, 309–320, 334–343, 345–349, 349–352, 353–358, 392–395.
- [ ] Insert recovered headers as boundaries (low-confidence is fine) and re-run extraction.

### Text/Garble Repair
- [ ] Implement typo/garble repair module post-cleanup: flag low-alpha/short/garbled sections; prefer re-read from OCR or multimodal LLM with “do not invent” prompt.
- [ ] Repair known bad sections (44, 277, 381) and a sample of other no-text sections; ensure choices/targets unchanged.

### Validation & Quality
- [ ] Rerun full pipeline with recovered boundaries + repair module; run cleanup; build; validate.
- [ ] Compare before/after metrics (missing/no-text/no-choice) and sample readability; document examples.

### Documentation/Recipes
- [ ] Add or update recipe to include recovery + repair stages; document knobs (model, max_elements, image use).

---

## Artifacts for Reference

- Best current boundaries: `/tmp/section_boundaries_backfilled_llm.jsonl`
- Best current portions (cleaned): `/tmp/portions_enriched_backfilled_llm_clean.jsonl`
- Best current gamebook: `/tmp/gamebook_backfilled_llm.json`
- Latest validation: `/tmp/validation_backfilled_llm.json` (18 missing, 163 no-text, 65 no-choice)

---

## Work Log

### 2025-11-30 — Story created / handoff from story-035
- **Result:** New story to finish OCR recovery and text repair; inherits baseline with 18 missing sections and many no-text portions.
- **Next:** Fix intake SHM issue, then target gap spans for headers and build typo/garble repair module.
