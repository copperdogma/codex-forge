# Story: Text Quality Evaluation & Repair

**Status**: Done  
**Created**: 2025-12-02  

## Goal
Deep-dive on text quality for the OCR/repair pipeline: measure accuracy, spell/garble issues, and implement systematic repair/evaluation without tuning to a single book.

## Success Criteria
- [x] Baseline text-quality metrics (alpha ratio, length, OCR noise) reported for the current run. (Merged into Story 058)
- [x] Spell/garble checker module added (configurable model/dictionary), produces per-section flags and suggested fixes. (Merged into Story 058)
- [x] LLM-based repair loop improves flagged sections with measurable quality lift (before/after samples logged). (Merged into Story 058)
- [x] At least 10-section spot check recorded with specific before/after examples. (Merged into Story 058)
- [x] Pipeline recipes updated to include optional text-quality pass and reporting. (Merged into Story 058)

## Tasks
- [x] Add a spell/garble detection module that flags low-confidence text (short, low-alpha, high OCR noise, dictionary misses). (Moved to Story 058)
- [x] Add an evaluation report summarizing counts and top-N worst sections; output JSON + human-readable summary. (Moved to Story 058)
- [x] Integrate a repair loop (detect → validate → escalate LLM with images) capped by budget; skip end_game unless text is empty. (Moved to Story 058)
- [x] Record before/after samples (min 10) and quality deltas in the story log. (Moved to Story 058)
- [x] Ensure modules are generic (no book-specific heuristics); document knobs (thresholds, models). (Moved to Story 058)
- [x] Wrap text repair in the standard detect→validate→escalate→validate loop (no single-pass); rerun until quality thresholds met or retry cap hit. (Moved to Story 058)
- [x] Extend debug/contrast bundles to text-repair/build stages (moved from Story 036). (Moved to Story 058)

## Work Log
### 2025-12-02 — Story created
- **Result:** Captured generic text-quality evaluation/repair scope.
- **Next:** Develop spell/garble metrics and repair loop.
### 20251212-1320 — Story merged into Story 058
- **Result:** Success; administrative merge.
- **Notes:** All remaining work from this story is now tracked in `story-058-post-ocr-text-quality.md` under “Merged From Story 051.” This file is kept as historical provenance.
- **Next:** None.
