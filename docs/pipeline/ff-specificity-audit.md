# FF-Specificity Audit (Pipeline Reuse)

**Date:** 2025-12-18  
**Goal:** Identify Fighting Fantasy (FF) / gamebook-specific logic in the pipeline and propose how to push specialization downstream so the OCR intake stack stays broadly reusable.

## Definitions

**Generic:** Works across most book types without assuming gamebook mechanics, section numbering, or FF vocabulary.

**Gamebook/CYOA-generic:** Assumes “navigational graph” text patterns (e.g., *turn to N*), numbered sections, or mechanics-like formatting, but not FF-specific terminology.

**FF-specific:** Assumes Fighting Fantasy conventions (e.g., sections 1–400, BACKGROUND start rule, SKILL/STAMINA/LUCK sheets, FF engine schema).

## Current Canonical FF DAG (high level)

From `configs/recipes/recipe-ff-canonical.yaml`:

1) `extract_ocr_ensemble_v1` (intake OCR + voting)
2) `easyocr_guard_v1`
3) `pick_best_engine_v1`
4) `inject_missing_headers_v1`
5) `ocr_escalate_gpt4v_v1` → `merge_ocr_escalated_v1`
6) `reconstruct_text_v1`
7) `pagelines_to_elements_v1`
8) `elements_content_type_v1`
9) FF-oriented segmentation + boundary stack
10) `portionize_ai_extract_v1` / `extract_choices_v1`
11) `build_ff_engine_v1` + validators

## Specificity Inventory (modules)

### OCR / Intake area (should be generic)

**`modules/extract/extract_ocr_ensemble_v1`**
- **Current specialization:** includes a gamebook navigation phrase repair:
  - `repair_turn_to_phrases(...)`: repairs `turn/tum (to|t0|tO) <number>` to canonical `Turn to <N>`.
- **Current status:** now **opt-in** via `enable_navigation_phrase_repair` (default off) so the OCR module can remain generic by default.
- **Classification:** **Gamebook/CYOA-generic** logic embedded inside OCR (not ideal).
- **Why it exists:** fixes correctness when only one engine supplies the line (no alternate candidate for “spell-weighted voting”).
- **Reuse risk:** non-gamebook prose could legitimately contain “tum”; and other domains may want to preserve literal OCR text.

**Recommendation:** keep OCR fusion/spell-weight tiebreaking generic, but migrate navigation normalization downstream (see “Proposed Moves”).

### Post-OCR adapters (acceptable place for gamebook/FF assumptions)

**`modules/adapter/pick_best_engine_v1`**
- Uses `is_section_header()` to preserve standalone numeric headers when choosing a canonical engine view.
- **Classification:** **Gamebook/CYOA-generic**, with FF defaults (range assumptions appear in comments).
- **Recommendation:** keep here; it’s already downstream from OCR and “header preservation” is a structural requirement for numbered-section books.

**`modules/adapter/inject_missing_headers_v1`**
- Injects missing numeric section headers; defaults to `1–400` (FF) but is parameterized via `min_value/max_value`.
- **Classification:** **FF-specific by default, but parameterizable to Gamebook-generic**.
- **Recommendation:** keep as an adapter (not OCR), but consider renaming/reframing as “inject_numeric_headers_v1” and making range mandatory (no FF default) for reuse.

**`modules/adapter/reconstruct_text_v1`**
- Contains stats table detection keyed on `SKILL/STAMINA`, and “section header” heuristics for numeric-only lines.
- **Classification:** mixed:
  - section header detection: **Gamebook/CYOA-generic**
  - SKILL/STAMINA table handling: **FF-specific**
- **Recommendation:** split the FF stat-table logic into an FF-only adapter (or gate it behind a knob) so non-FF pipelines don’t pick up these heuristics.

**`modules/adapter/elements_content_type_v1`**
- Tags FF combat stat blocks and sheet labels (SKILL/STAMINA/LUCK) and uses an FF-ish whitelist by default.
- **Classification:** **FF-specific**, though the “content typing” concept is generic.
- **Recommendation:** keep the module, but make FF-specific detectors opt-in via a `profile: ff` vs `profile: generic` config.

### Portionize / structure stack (FF-specific by design)

**`modules/portionize/coarse_segment_ff_override_v1`**, **`macro_locate_ff_v1`**, **`detect_gameplay_numbers_v1`**, etc.
- Explicit FF rules (e.g., BACKGROUND start, 1–400 order).
- **Classification:** **FF-specific**.
- **Recommendation:** correct to keep these downstream.

### Extraction / enrichment / validation (FF/gamebook specific, should remain downstream)

**`modules/extract/extract_choices_v1`**
- Primary logic is “turn to X” pattern matching, with FF range defaults (1–400).
- **Classification:** **Gamebook/CYOA-generic** with FF defaults.
- **Recommendation:** this is the best home for tolerant parsing (`tum`, `t0`, digit confusions) instead of OCR. It’s where we care about the graph edges.

**`modules/portionize/portionize_ai_extract_v1`**
- Prompt explicitly says Fighting Fantasy; uses “Turn to” and SKILL/STAMINA patterns.
- **Classification:** **FF-specific**.
- **Recommendation:** update prompt or preprocessing to tolerate OCR variants if we migrate normalization out of OCR.

**`modules/export/build_ff_engine_v1`**, **`modules/validate/validate_ff_engine_node_v1`**
- FF engine schema.
- **Classification:** **FF-specific** (correct).

## Proposed Moves (push specialization downstream)

### 1) Move “Turn to <N>” normalization out of OCR

**Goal:** keep `extract_ocr_ensemble_v1` generic (OCR + fusion), and put navigation normalization closer to the consumers:
- choice extraction
- AI gameplay extraction
- choice completeness validation

**Options:**

**A. Best option (minimal surface area): add tolerant parsing in `extract_choices_v1`**
- Expand regex to accept:
  - `tum` as `turn` (only when followed by `to <digits>`)
  - `t0/tO` as `to` (only when followed by `<digits>`)
  - normalize target digits using a conservative digit-confusion map
- Pros: no text mutation; directly improves the engine graph; cheap.
- Cons: doesn’t improve raw text readability for LLM stages unless they also tolerate variants.

**B. Add a dedicated adapter module `normalize_navigation_phrases_v1`**
- Runs on section text (not OCR pages) and records structured provenance of edits.
- Place it:
  - **before** `portionize_ai_extract_v1` (so the LLM sees clean “Turn to” phrasing), and/or
  - **before** `extract_choices_v1` (if it uses raw_text).
- Pros: keeps OCR generic and improves downstream text for both deterministic + LLM consumers.
- Cons: introduces a new module/stage; must be recipe-scoped to gamebooks.

### 2) Make `reconstruct_text_v1` “profiled”

Split or gate FF-only heuristics:
- Keep generic paragraph reconstruction + numeric header detection always on.
- Gate SKILL/STAMINA table detection under `profile: ff` (or a boolean knob).

### 3) Make content typing generic with FF detectors opt-in

`elements_content_type_v1` already has a conceptual separation (content type + subtypes). Make FF detectors opt-in:
- `profile: generic` (no FF stat/sheet heuristics)
- `profile: ff` (enable combat_stats/form_field heuristics)

## Proposed Updated DAG (FF recipe)

Keep the canonical FF recipe mostly unchanged, but *conceptually* move navigation normalization downstream:

- Keep: `extract_ocr_ensemble_v1` (OCR fusion + spell-weighted voting)
- Keep: `pick_best_engine_v1`, `inject_missing_headers_v1` (they’re structural for numbered-section books)
- Add (new): `normalize_navigation_phrases_v1` **after** section text is assembled (closest to extraction/choices)
- Update: `extract_choices_v1` to be tolerant to OCR variants even if the normalization adapter is disabled

This keeps performance (regex-based) and accuracy (graph edges) while isolating “Turn to <N>” semantics from generic OCR.

## Notes / Open Questions

- Some current adapters (e.g., `inject_missing_headers_v1`) implicitly assume FF section range defaults. For reuse, those should be explicitly parameterized (mandatory range) or wrapped in FF recipes only.
- If we want OCR-stage normalization for performance/coverage, decouple it from spell-weighted voting behind a dedicated knob so non-gamebook recipes can disable it cleanly.
