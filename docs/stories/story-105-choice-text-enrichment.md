# Story: Choice Text Enrichment (Spec Only)

**Status**: Done  
**Created**: 2025-12-29  
**Priority**: Medium  
**Parent Story**: story-104 (Gamebook Output File Tweaks)

---

## Goal

Define a safe, generic approach for enriching `choiceText` in `gamebook.json` with human‑readable phrases derived from `presentation_html`, while preserving numeric fallback (e.g., “Turn to 298”).

---

## Motivation

Current `choiceText` entries are correct but minimally informative. Players benefit when choices read as actions (“Put it on your wrist”, “Set off north”), improving UX without altering game logic. This should be a **specification only** to guide a future implementation.

---

## Success Criteria

- [x] **Spec complete**: Document a generic algorithm to derive choice phrases from `presentation_html` without book‑specific rules.
- [x] **Safety rules**: Define confidence/guardrails to avoid incorrect or misleading choice text.
- [x] **Fallback preserved**: Always retain numeric fallback for low‑confidence extraction.
- [x] **Placement defined**: Identify where in the pipeline enrichment would occur (module/stage level) without implementing it.
- [x] **Examples captured**: Provide 3–5 concrete examples (including section 114) showing expected enriched output.

---

## Approach (Spec Only)

1. Survey representative gameplay sections for choice phrasing patterns.
2. Propose deterministic parsing heuristics to extract action phrases around inline anchors.
3. Define a confidence scoring rubric and fallback rules.
4. Identify insertion point(s) in pipeline (e.g., enrich stage vs. export adapter).
5. Document risks and non‑goals (no changes to section targets, no LLM dependency unless strictly optional).

---

## Tasks

- [x] Draft extraction heuristics for choice phrases from `presentation_html`.
- [x] Define confidence thresholds and fallback behavior.
- [x] Specify output format changes (if any) and schema implications.
- [x] Provide example before/after snippets for at least five sections.
- [x] Document where the enrichment would live in the pipeline.
- [x] Record risks, edge cases, and validation strategy.

---

## Spec: Choice Text Enrichment (Design Only)

### Core Idea
Derive a human‑readable action phrase for each choice directly from `presentation_html`, while **preserving the numeric fallback** (`Turn to NNN`) when extraction is ambiguous.

### Extraction Heuristics
1. Parse `presentation_html` into a lightweight DOM and keep inline anchors (`<a href="#NNN">`).
2. For each anchor, search the containing `<p>` for a nearby choice clause:
   - Preferred lead‑ins: `If you`, `If you wish`, `If you would rather`, `You may`, `You can`, `Will you`, `Do you`, `Try to`, `Decide to`.
   - Use sentence boundaries (`.`, `;`, `?`, `:`) to define clause scope.
3. Candidate phrase is the clause text **minus** numeric anchor text (`turn to 298` and the anchor number).
4. Normalize into a concise action:
   - Strip leading lead‑in text (`If you would rather`) to keep the verb phrase.
   - Title case or sentence case depending on UI preference.

### Confidence & Fallback Rules
- **High confidence** when:
  - Lead‑in token exists, and
  - Clause length is 3–12 words, and
  - Clause does not contain another numeric reference.
- **Medium confidence** when:
  - Lead‑in token missing but clause is short and imperative.
- **Low confidence** in all other cases.

**Fallback:** if confidence < 0.7, keep `choiceText = "Turn to NNN"`.

### Where It Lives (No Implementation)
Preferred: a **post‑build adapter** that reads `gamebook.json` and rewrites `navigationLinks[*].choiceText` based on `presentation_html`.
Alternate: extend `extract_choices_*` to emit enriched text early (but this risks desync if HTML is later repaired).

### Output Format
No schema changes required if we only overwrite `choiceText` and preserve numeric fallback.
Optional: include `choiceText_source` and `choiceText_confidence` in a future revision.

### Examples (Expected Output)
1) **Section 114**
   - Before: `Turn to 336`, `Turn to 298`
   - After: **“Put it on your wrist”**, **“Set off north again”**

2) **Section 357**
   - Before: `Turn to 255`, `Turn to 332`, `Turn to 180`
   - After: **“Run round the side of the pool”**, **“Throw a gem into its pool”**, **“Attack it with your sword”**

3) **Section 68**
   - Before: `Turn to 271`, `Turn to 30`, `Turn to 212`
   - After: **“Throw your shield over the pit and jump after it”**, **“Jump the pit”**, **“Climb down the rope”**

4) **Section 20**
   - Before: `Turn to 279`
   - After: **“Set off north again”** (single action)

5) **Section 142**
   - Before: `Turn to 338`
   - After: **“Walk over to the bodies”**

### Risks & Edge Cases
- Multiple anchors in a single sentence: split by anchor positions.
- Clauses that only say “Turn to 298.”: no action; fallback to numeric.
- Complex conditional chains (“if you have X, otherwise Y”): may need multiple anchors with different phrases.

### Validation Strategy
- Sample 20 gameplay sections and compare extracted phrases to human‑readable intent.
- Ensure no target numbers change, only `choiceText`.

---

## Work Log

### 20251229-0011 — Story created
- **Result**: Success; stubbed spec‑only story for choice text enrichment.
- **Notes**: Based on recent request to improve `choiceText` labels while preserving numeric fallbacks.
- **Next**: Draft spec and examples; no code changes yet.

### 20251229-1606 — Spec drafted and finalized
- **Result**: Success; completed design spec, examples, and safety rules.
- **Notes**: No code changes required; intended as a future enhancement blueprint.
- **Next**: If approved, implement as a post‑build adapter with confidence‑based fallback.
