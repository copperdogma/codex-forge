# Codex-Forge — Spec

> Every entry here exists because of a named limitation. When the limitation
> resolves, the compromise gets deleted and the system simplifies.
> See `docs/ideal.md` for what this system should be with zero limitations.
>
> **Organization:** Sections are organized by category (`spec:1` through `spec:9`),
> matching the build map structure. Each category may contain product constraints,
> build constraints, or both. Hierarchical section IDs (e.g., `spec:2.1`) provide
> stable cross-references across stories, ADRs, and the build map.

## Non-Negotiable Design Principles

These are not compromises — they are permanent architectural commitments:

1. **Traceability end-to-end** — Every output traces to source page, OCR engine, confidence score, and processing step.
2. **Modular pipeline** — YAML recipes compose modules. New document types = new recipes, not new code.
3. **Append-only artifacts** — Intermediate outputs preserved for audit. No silent overwrites.
4. **Validation is mandatory** — Every run ends with structural and semantic validation.
5. **Graduate to Dossier** — Proven converters migrate to Dossier. Codex-forge stays lean.

---

## spec:1 — Intake & Format Routing

> Product need: accept source material in any format and route it into the right pipeline.
> Tech substrate: format detection, manifest normalization, recipe selection.

### spec:1.1 — Format-Specific Conversion Recipes

### Constraints

**C2: Format-Specific Conversion Recipes** [AI capability → deletion]
*Ideal:* System auto-detects document format and configures itself. Zero user input.
*Compromise:* User selects a YAML recipe matching their document type.
*Limitation:* AI capability — reliable format detection and pipeline selection from raw input alone hasn't been proven across diverse document types.
*Detection:* Given 10 diverse documents with no metadata hints, system correctly identifies format and selects appropriate pipeline for all 10.
*Resolves:* Delete recipe selection. Auto-detect replaces manual choice.
*Preference:* Keep the recipe surface explicit, expand input coverage one format family at a time, and use lightweight routing helpers such as contact sheets or manifest-based intake when they reduce operator ambiguity.

---

## spec:2 — OCR & Text Extraction

> Product need: turn scanned pages and page images into faithful text/HTML.
> Tech substrate: OCR engines, AI extraction models, escalation loops, artifact reuse.

### spec:2.1 — Multi-Stage OCR Pipeline

### spec:2.2 — Expensive OCR for Quality

### Constraints

**C1: Multi-Stage OCR Pipeline** [AI capability → deletion]
*Ideal:* One AI call reads any page and returns perfect text with layout preserved.
*Compromise:* Multi-engine OCR pipeline with escalation (fast engine → stronger model on failures).
*Limitation:* AI capability — no single model reliably handles all page types (scanned, tables, multi-column, degraded) at acceptable cost.
*Detection:* Single-model OCR of a 400-page mixed-format book produces ≥99% character accuracy with layout preserved, at <$2 total cost.
*Resolves:* Delete OCR ensemble logic, escalation loops, engine voting. Collapse to single extract call.
*Preference:* Prefer code-first extraction for speed/cost; use AI only for flagged pages.

**C6: Expensive OCR for Quality** [Economics → evolution]
*Ideal:* OCR is instant and free with perfect quality.
*Compromise:* GPT-5.1 AI OCR at ~$0.01/page. Cost-conscious workflows reuse OCR artifacts rather than re-running.
*Limitation:* Economics — API calls cost money and take time.
*Detection:* Current-quality OCR below $0.001/page sustained.
*Resolves:* Remove cost-conservation and artifact-reuse workflows. Evolution path: cost decreases as models commoditize.
*Preference:* Treat OCR as expensive and single-run. Iterate downstream by reusing artifacts.

---

## spec:3 — Layout & Structure Understanding

> Product need: detect boundaries, headings, tables, multi-column structure, and layout cues.
> Tech substrate: heuristic detectors, VLM escalation, section splitting, boundary ordering.

### spec:3.1 — Heuristic + AI Layout Detection

### Constraints

**C3: Heuristic + AI Layout Detection** [AI capability → deletion]
*Ideal:* System understands document structure from content alone — sections, columns, tables, headers, illustrations.
*Compromise:* Code-first pattern matching with AI escalation for ambiguous layouts.
*Limitation:* AI capability — VLMs handle most cases but struggle with unusual layouts. Code heuristics are faster and cheaper for well-structured documents.
*Detection:* VLM-only layout detection achieves 100% accuracy on a diverse 5-document benchmark without any heuristic fallbacks.
*Resolves:* Delete pattern-matching heuristics. Collapse to single VLM call per page.

---

## spec:4 — Illustration Extraction

> Product need: detect illustrations, crop them cleanly, exclude text, preserve source relationship.
> Tech substrate: VLM crop detection, validator models, OCR-driven text trimming.

### spec:4.1 — Two-Stage Image Crop Detection

### spec:4.2 — Layout Text Trim Heuristics for Crops

### Constraints

**C4: Two-Stage Image Crop Detection** [AI capability → deletion]
*Ideal:* One call detects and crops every illustration perfectly.
*Compromise:* Detector model (Gemini 3 Pro) proposes bounding boxes → Validator model (Gemini 2.5 Flash) checks for text contamination → Auto-retry on count mismatch.
*Limitation:* AI capability — no single model reliably detects all illustrations AND avoids text contamination in one pass.
*Detection:* Single-model crop detection scores ≥0.95 on the image-crop-extraction eval with zero text contamination false positives. Current score: 0.856 (77% pass rate).
*Resolves:* Delete validator stage, retry logic. Single detect call.
*Preference:* Gemini 3 Pro is the current winning detector; Flash is the cheapest reliable validator.

**C5: Layout Text Trim Heuristics for Crops** [AI capability → deletion]
*Ideal:* Crop detection understands page layout and excludes text automatically.
*Compromise:* Post-detection heuristic trimming using OCR text coordinates.
*Limitation:* AI capability — VLM bounding boxes frequently absorb nearby text.
*Detection:* VLM crop detection produces bounding boxes that exclude all non-illustration content on a 50-page benchmark.
*Resolves:* Delete `_trim_box_by_layout_text` and related heuristics.

---

## spec:5 — Document Consistency Planning

> Product need: ensure repeated structures render consistently across a whole document.
> Tech substrate: pattern discovery, consistency plan emission, plan-aware selective reruns, conformance reporting.

### spec:5.1 — Page-Scope Extraction with Document-Level Consistency Planning

### Constraints

**C7: Page-Scope Extraction with Document-Level Consistency Planning** [AI capability + cost → deletion]
*Ideal:* One source-aware extraction pass emits faithful, globally consistent structure across a whole document, so repeated pattern families naturally render the same way everywhere.
*Compromise:* Extract page-level HTML first, then emit document-level `pattern_inventory`, `consistency_plan`, and `conformance_report` artifacts and use them to guide selective reruns or downstream repair.
*Limitation:* AI capability + cost — blind page-by-page extraction still produces representation drift, while full-document source-aware extraction is not yet the default cost/latency envelope for every recipe.
*Detection:* On at least 3 repeated-structure documents, the strongest practical one-pass extractor produces internally consistent repeated structures without needing a downstream consistency plan or selective reruns, while preserving provenance and manual-review quality.
*Resolves:* Delete the document-consistency planning layer for that recipe and collapse back to direct extraction plus final validation.
*Preference:* Keep consistency conventions explicit and inspectable. Emit document-local `pattern_inventory`, `consistency_plan`, and `conformance_report` artifacts instead of hiding normalization policy in prompts.

---

## spec:6 — Validation, Provenance & Export

> Product need: prove output is correct and Dossier-ready with full traceability.
> Tech substrate: schema validation, provenance stamping, run health, export formatting.

This category carries no active compromises. Its obligations flow from the
Non-Negotiable Design Principles (#1 Traceability, #2 Modular pipeline,
#3 Append-only artifacts, #4 Validation is mandatory).

---

## spec:7 — Graduation & Dossier Handoff

> Product need: graduate mature document-to-website conversion paths out of codex-forge so it stays lean and Dossier can consume them through a stable boundary.
> Tech substrate: graduation criteria, `doc-web` runtime boundary, Dossier intake surface readiness, fixture breadth.

This category carries no active product compromises. Its obligations flow from
Non-Negotiable Design Principle #5 (Graduate to Dossier) and the Mission in
`docs/ideal.md`.

Current accepted direction: when a mature path is still cleaner as a standalone
runtime than as a direct codex-forge dependency, graduate it first into
`doc-web`, then let Dossier consume `doc-web` through a versioned contract.

---

## spec:8 — AI Harnesses & Tooling

> These are execution compromises: process elements that exist because of
> AI's current limitations in building software.

| ID | Process Element | AI Limitation | Residual | Detection |
|---|---|---|---|---|
| B1 | Eval framework (promptfoo) | Can't self-assess output quality | Deletion | Reliable self-assessment on pipeline outputs |
| B2 | Prompt engineering | Calls need carefully designed prompts | Deletion | Models robust to naive prompts |
| B3 | Pipeline orchestration (driver.py) | Can't compose reliable multi-step pipelines from intent | Deletion | Single-call pipeline composition from document + intent |
| B4 | Schema stamping & validation | AI outputs need structural validation gates | Deletion | Outputs structurally guaranteed by the model |
| B5 | Manual artifact inspection | Can't reliably self-verify output quality | Deletion | Reliable self-verification with evidence |
| B6 | Escalation loops & retry caps | Single-pass extraction isn't reliable enough | Deletion | Single-pass reliability across all page types |

---

## spec:9 — Planning Infrastructure

> These are execution compromises: process elements that exist because of
> AI's current limitations in planning and sequencing work.

| ID | Process Element | AI Limitation | Residual | Detection |
|---|---|---|---|---|
| B7 | Story/backlog system | Can't autonomously scope, sequence, and validate work | Deletion | Autonomous project planning with self-correction |
| B8 | Build map & phase tracking | Can't maintain strategic awareness across sessions | Deletion | Persistent strategic reasoning across sessions |
| B9 | ADR process | Can't make and record hard-to-reverse decisions with full context | Deletion | Reliable autonomous architectural decision-making |
| B10 | YAML recipe configuration | Manual pipeline config; overlaps with C2 product compromise | Partial deletion | Auto-configuration eliminates manual recipe selection |

---

## Retired Compromises (from v1 book processing era)

These compromises existed when codex-forge was a book processing pipeline. They're preserved for reference but no longer actively tracked. The capabilities they addressed (game mechanic extraction, patching system) were specific to Fighting Fantasy processing and aren't part of the current intake R&D mission.

- **C5-old: Per-Module Enrichment Passes** — Separate extraction for each game mechanic type (choices, combat, inventory, stats). FF-specific.
- **C7-old: Patching System for Exceptional Books** — `*.patch.json` overrides for books that defy conventions. FF-specific.
