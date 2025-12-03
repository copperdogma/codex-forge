# Story: Text Quality Evaluation & Repair

**Status**: Open  
**Created**: 2025-12-02  

## Goal
Deep-dive on text quality for the OCR/repair pipeline: measure accuracy, spell/garble issues, and implement systematic repair/evaluation without tuning to a single book.

## Success Criteria
- [ ] Baseline text-quality metrics (alpha ratio, length, OCR noise) reported for the current run.
- [ ] Spell/garble checker module added (configurable model/dictionary), produces per-section flags and suggested fixes.
- [ ] LLM-based repair loop improves flagged sections with measurable quality lift (before/after samples logged).
- [ ] At least 10-section spot check recorded with specific before/after examples.
- [ ] Pipeline recipes updated to include optional text-quality pass and reporting.

## Tasks
- [ ] Add a spell/garble detection module that flags low-confidence text (short, low-alpha, high OCR noise, dictionary misses).
- [ ] Add an evaluation report summarizing counts and top-N worst sections; output JSON + human-readable summary.
- [ ] Integrate a repair loop (detect → validate → escalate LLM with images) capped by budget; skip end_game unless text is empty.
- [ ] Record before/after samples (min 10) and quality deltas in the story log.
- [ ] Ensure modules are generic (no book-specific heuristics); document knobs (thresholds, models).
- [ ] Wrap text repair in the standard detect→validate→escalate→validate loop (no single-pass); rerun until quality thresholds met or retry cap hit.
- [ ] Extend debug/contrast bundles to text-repair/build stages (moved from Story 036).

## Work Log
- 2025-12-02 — Story created; scoped to generic text-quality evaluation and repair (no book-specific tuning).***
