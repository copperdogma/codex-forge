# Build Map — System Structure + Compromise Progress

> This file combines system structure, compromise convergence tracking, input
> coverage, and graduation readiness into one browsable map.
> It is the human-readable source of truth for what codex-forge currently owns,
> where active compromises still live, and which format gaps remain open.
> See `docs/spec.md` for compromise definitions and `docs/evals/registry.yaml`
> for current eval signals.
> Converged with Storybook ADR-019 via Story 145.

## How to Read Compromise Progress

Each system that carries a spec compromise has a **Compromise Progress**
subsection with two parts:

- **Optimize** — improve the current workaround while the limitation still
  exists
- **Eliminate** — track the signal that tells us the workaround can be deleted

Systems without active compromises still appear here so the whole repo stays
mapped in one place.

---

## 1. Intake & Format Routing
- [x] Stories cover this system

**Summary:** Accept source material in multiple formats, normalize it into a
pipeline-ready manifest, and route it into the right recipe/module chain.
Today this still depends on explicit recipes and format-specific intake paths.

**Spec Sections:** C2
**ADR Refs:** None yet
**Dependencies:** None

#### Compromise Progress

**C2 — Format-Specific Conversion Recipes** (Limitation: AI capability)
- **Optimize**: Keep the recipe surface explicit, expand input coverage one
  format family at a time, and use lightweight routing helpers such as contact
  sheets or manifest-based intake when they reduce operator ambiguity.
- **Eliminate**: Eval `auto-book-type-detection` — target: `accuracy = 1.0`
  across 10 diverse PDFs. Latest: no scores recorded. Retry when:
  `new-approach` (contact sheet + VLM classification). When it passes: manual
  recipe selection stops being the default operator step.

---

## 2. OCR & Text Extraction
- [x] Stories cover this system

**Summary:** Turn scanned pages and page images into faithful text/HTML.
Current best quality comes from AI-first OCR plus targeted downstream rescue for
hard layouts such as dense genealogy tables.

**Spec Sections:** C1, C6
**ADR Refs:** None yet
**Dependencies:** Intake & Format Routing

#### Compromise Progress

**C1 — Multi-Stage OCR Pipeline** (Limitation: AI capability)
- **Optimize**: Use AI-first OCR as the default, then apply targeted rescue or
  rerun loops only where the first pass demonstrably fails. Current strong
  signals come from Stories 127, 131, 140, and 144.
- **Eliminate**: No dedicated compromise-detection eval is recorded yet.
  Closest signals: `ocr-model-genealogy` at `character_accuracy = 0.97`
  (measured 2026-02-20, target `0.99`) and `onward-table-fidelity` at
  `structure_preservation = 0.969` (measured 2026-03-11, target `0.95` for that
  narrower benchmark). Retry when: `new-subject-model` or
  `architecture-change`. When it passes at mixed-format book scope: collapse
  the ensemble/escalation architecture into one extract pass.

**C6 — Expensive OCR for Quality** (Limitation: Economics)
- **Optimize**: Treat OCR as expensive and single-run, reuse artifacts
  downstream, and keep high-resolution reads only where they still pay for
  themselves. Story 134 validated 2048px downsampling as the safe default for
  the Onward OCR path.
- **Eliminate**: No deletion eval is recorded. The spec trigger is economic:
  current-quality OCR below `< $0.001/page`. When that threshold is sustained:
  remove the reuse-first workflows that exist mainly to avoid re-running OCR.

---

## 3. Layout & Structure Understanding
- [x] Stories cover this system

**Summary:** Detect boundaries, headings, tables, multi-column structure, and
other layout cues needed to turn raw OCR into coherent structured artifacts.
Today this remains a hybrid of deterministic code and AI escalation.

**Spec Sections:** C3
**ADR Refs:** None yet
**Dependencies:** OCR & Text Extraction

#### Compromise Progress

**C3 — Heuristic + AI Layout Detection** (Limitation: AI capability)
- **Optimize**: Keep deterministic detectors for cheap, stable cases and use AI
  escalation only where ambiguity is real. Existing stories already pushed a
  lot of the old brittle failure surface out of the way, but the system still
  depends on heuristics for stability and cost.
- **Eliminate**: No dedicated deletion eval is recorded yet. Target from
  `docs/spec.md`: VLM-only layout detection reaches `100%` accuracy on a
  diverse 5-document benchmark with no heuristic fallbacks. Latest: no scores
  recorded. Retry when: a layout benchmark exists or a new subject model makes
  a VLM-first path credible. When it passes: delete the pattern-matching
  fallbacks.

---

## 4. Illustration Extraction
- [x] Stories cover this system

**Summary:** Detect illustrations, crop them cleanly, keep text out of the
boxes, and preserve their relationship to the source document.

**Spec Sections:** C4, C5
**ADR Refs:** None yet
**Dependencies:** Intake & Format Routing, OCR & Text Extraction

#### Compromise Progress

**C4 — Two-Stage Image Crop Detection** (Limitation: AI capability)
- **Optimize**: Current best production path is still a detector + validator
  architecture with retry-on-count-mismatch. Story 133 improved the quality/cost
  balance substantially by moving to Gemini 3 Flash with a
  conservative-count prompt.
- **Eliminate**: Eval `single-model-crop-detection` — target:
  `overall >= 0.95`, `pass_rate >= 0.95`. Latest:
  `overall = 0.856`, `pass_rate = 0.77` (measured 2026-01-25). Retry when:
  `new-subject-model`. When it passes: remove the validator stage and count
  retry loop.

**C5 — Layout Text Trim Heuristics for Crops** (Limitation: AI capability)
- **Optimize**: Keep OCR-driven text trimming conservative and inspectable so it
  only removes obvious text contamination around otherwise-correct boxes.
- **Eliminate**: No dedicated text-exclusion deletion eval is recorded yet.
  Closest signal: `image-crop-extraction` at `overall = 0.900`,
  `pass_rate = 0.923` (measured 2026-03-11, target `0.95`). Retry when:
  `new-subject-model` or a dedicated text-exclusion benchmark exists. When it
  passes: delete `_trim_box_by_layout_text` and related cleanup heuristics.

---

## 5. Document Consistency Planning
- [x] Stories cover this system

**Summary:** Detect repeated structure drift across a document, emit explicit
policy artifacts (`pattern_inventory`, `consistency_plan`,
`conformance_report`), and use them to guide selective reruns or repair.

**Spec Sections:** C7
**ADR Refs:** ADR-001
**Dependencies:** OCR & Text Extraction, Layout & Structure Understanding

#### Compromise Progress

**C7 — Page-Scope Extraction with Document-Level Consistency Planning**
(Limitation: AI capability + cost)
- **Optimize**: Keep document-level planning explicit and inspectable, then use
  plan-aware reruns instead of hiding normalization policy inside prompts.
  Stories 141-144 established the current pattern.
- **Eliminate**: Closest signal is `onward-document-consistency-planning` with
  `missed_manual_format_coverage = 1.0` (measured 2026-03-15), but that eval
  proves the planning layer works; it does not yet prove the compromise is
  deletable. Retry when: `new-approach` (second repeated-structure document) or
  `architecture-change` (plan-guided reruns fully consume the planning layer).
  When the broader detection condition in `docs/spec.md` is met: remove the
  extra planning layer for that recipe.

---

## 6. Validation, Provenance & Export
- [x] Stories cover this system

**Summary:** Validate artifacts structurally and semantically, measure
provenance completeness, surface run health, and emit Dossier-ready output with
full traceability.

**Spec Sections:** Non-Negotiable Design Principles #1-4
**ADR Refs:** None yet
**Dependencies:** All upstream extraction systems

**Current health:** Provenance completeness for the verified scanned/image
pipelines is now `1.0` after Story 132's envelope fixes. Validation and run
health remain active cross-cutting responsibilities, not one-off stories.

---

## 7. Graduation & Dossier Handoff
- [ ] Stories cover this system

**Summary:** Mature converters should move into Dossier once they are stable,
well-measured, and no longer active R&D. This remains a mission-level system,
but it does not yet have explicit story coverage.

**Spec Sections:** Mission, Non-Negotiable Design Principle #5
**ADR Refs:** None yet
**Dependencies:** Intake & Format Routing, OCR & Text Extraction, Validation,
Provenance & Export

**Current state:** `0` formats are graduated today. The build map tracks which
ones are closest, but no explicit migration story has landed yet.

---

## 8. Project Operating System
- [x] Stories cover this system

**Summary:** Stories, ADRs, evals, skills, runbooks, and this build map form
the repo's operating system. This is where convergence work like Story 145
lives.

**Spec Sections:** None (cross-cutting workflow surface)
**ADR Refs:** None yet
**Dependencies:** None

---

## Input Coverage

This section absorbs the former human-readable format registry.

**Machine-readable source:** `tests/fixtures/formats/_coverage-matrix.json`

### Current Status

**6 formats passing** | **0 graduated** | **10 untested** | **16 total tracked**

### Passing

| Format | ID | Family | Current Pipeline | Text | Structure | Illustration | Provenance | Notes |
|---|---|---|---|---:|---:|---:|---:|---|
| Scanned PDF (prose) | `scanned-pdf-prose` | `scanned-pdf` | `extract_pdf_images_fast_v1 -> ocr_ai_gpt51_v1` | 0.97 | 0.95 | 0.900 | 1.00 | Primary scanned-PDF path. Illustration score uses the 2026-03-11 crop eval refresh; provenance uses Story 132 verification. |
| Scanned PDF (tables) | `scanned-pdf-tables` | `scanned-pdf` | `images -> ocr_ai_gpt51_v1 -> table_rescue_html_loop_v1` | 0.93 | 0.95 | 0.900 | 1.00 | Onward-style genealogy path. Structure quality comes from the 2026-03-11 table eval winner. |
| Image directory | `image-directory-scans` | `image-directory` | `images_dir_to_manifest_v1 -> ocr_ai_gpt51_v1` | 0.93 | 0.95 | 0.900 | 1.00 | Same source quality as the scanned-PDF image path once pages are extracted. |
| Plain text | `plain-text` | `plain-text` | `extract_text_v1` | 1.00 | - | - | - | Passthrough, no OCR. |
| Markdown | `markdown` | `markdown` | `extract_text_v1` | 1.00 | - | - | - | Passthrough. |
| HTML | `html-files` | `html` | `extract_text_v1` | 1.00 | - | - | - | Passthrough. |

### Has Fixture (pipeline not yet passing)

None currently.

### Untested

| Format | ID | Family | Complexity | Priority | Notes |
|---|---|---|---|---|---|
| Born-digital PDF | `born-digital-pdf` | `born-digital-pdf` | prose, tables, illustrations | High | Currently wastefully routed through OCR. Needs embedded-text extraction. |
| Word (.docx) | `docx` | `docx` | prose, tables, illustrations | High | Common Storybook/Dossier-adjacent upload format. |
| Excel (.xlsx) | `xlsx` | `xlsx` | tables | Medium | Structured family-history data often starts here. |
| PowerPoint (.pptx) | `pptx` | `pptx` | mixed-layout, illustrations | Low | Lower-frequency, but still plausible archive input. |
| EPUB | `epub` | `epub` | prose, illustrations | Medium | Zipped HTML + image intake remains unbuilt. |
| Email (.eml) | `email-eml` | `email` | prose | Medium | Personal correspondence import path still missing. |
| Email archive (.mbox) | `email-mbox` | `email` | prose | Medium | Bulk archive support still missing. |
| Web page | `web-page` | `web-page` | mixed-layout, illustrations | Medium | Online sources remain a routing/intake gap. |
| Handwritten notes | `handwritten-notes` | `handwritten` | handwritten, degraded | High | Valuable but still unproven VLM-transcription path. |
| Mixed archive | `mixed-archive` | `mixed-archive` | mixed | Low | Needs auto-routing plus multi-format unpacking. |

### Graduated

None yet.

## Accuracy Dimensions

- **Text Fidelity** — character-level accuracy versus source (target: `>= 0.99`)
- **Structure Preservation** — tables, columns, headers, lists (target: `>= 0.95`)
- **Illustration Extraction** — detection, cropping, and cataloging quality
  (target: `>= 0.95`)
- **Provenance Completeness** — every output traces to source page/location
  (target: `1.0`)

## Known Gaps (Prioritized)

### Gap 1 — Illustration crop quality on image-bearing formats

- **Current signal:** `image-crop-extraction` is at `0.900` overall against a
  `0.95` target, and the true deletion gate `single-model-crop-detection`
  remains at `0.856 / 0.77`.
- **Root cause:** C4 and C5 still hold. Single-stage crop detection is not good
  enough to remove validator + trim heuristics.
- **Fix category:** Model-selection / compromise-detection.
- **Status:** Still open; blocked on better single-model performance or a
  stronger benchmark signal.

### Gap 2 — Born-digital PDF native text extraction

- **Current signal:** No pipeline, no fixture, no eval.
- **Root cause:** Intake still assumes scanned/OCR-first processing.
- **Fix category:** New intake module.
- **Status:** High-value missing capability.

### Gap 3 — Office document intake (DOCX/XLSX/PPTX)

- **Current signal:** No pipeline family exists for office documents.
- **Root cause:** Intake coverage is still heavily skewed toward PDFs and image
  directories.
- **Fix category:** New intake modules / routing.
- **Status:** High-value missing capability, especially for Storybook-adjacent
  uploads.

### Gap 4 — Handwritten document transcription

- **Current signal:** No tested handwriting path exists.
- **Root cause:** No fixture set and no dedicated VLM transcription flow.
- **Fix category:** New intake/extraction path.
- **Status:** High-value missing capability for personal archives.

### Gap 5 — Fixture breadth and graduation confidence

- **Current signal:** Passing formats still rely on very few fixtures, and no
  format meets the "3 diverse fixtures" graduation bar yet.
- **Root cause:** Capability coverage grew faster than repeatable benchmark
  breadth.
- **Fix category:** Fixture expansion and rerun discipline.
- **Status:** Open cross-cutting quality gap.

## Resolved Gaps

### Resolved — Provenance completeness on verified scanned/image pipelines

- **Previous state:** provenance completeness was `0.984` (scanned-pdf-prose)
  and `0.956` (table/image paths).
- **Fix:** Story 132 stamped the missing envelope fields and verified the
  relevant pipeline path at `1.0`.
- **Resolved:** 2026-03-11 verification run `provenance-verify-132`.

### Resolved — Table structure preservation on dense genealogy tables

- **Previous state:** OCR/layout handling lost table shape on Onward-style
  content.
- **Fix:** Story 131 aligned the scorer, tuned the prompt, and selected the
  strongest subject model.
- **Resolved:** 2026-03-11 with `onward-table-fidelity = 0.969`.

## Graduation Criteria

A converter is ready to graduate to Dossier when:

1. Text fidelity is `>= 0.99` on all test fixtures for that format
2. Structure preservation is `>= 0.95` where structure matters
3. At least 3 diverse fixtures pass for that format family
4. The converter has been stable for 2+ stories without churn
5. Dossier has an intake surface ready to receive it

## Next Actions

1. Create the born-digital PDF intake story.
2. Create the DOCX intake story, then decide whether XLSX/PPTX should split or
   stay together.
3. Create the handwriting-transcription story.
4. Expand fixture breadth for already-passing formats so graduation decisions
   can be trusted.
5. Re-run stale capability measurements where the code changed but the benchmark
   signal did not.
