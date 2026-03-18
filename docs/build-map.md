# Build Map

> Central dashboard for system progress. Organized by category matching
> `spec.md` (spec:1–spec:9). Each category tracks: product need, tech need,
> substrate status, story coverage, and compromise phase.
>
> See `docs/spec.md` for compromise definitions and `docs/evals/registry.yaml`
> for current eval signals. Converged with Storybook ADR-019 via Story 145;
> reorganized to ADR-021 category/phase structure via Story 148.

## How to Read This Map

- **Product need** — what the category delivers to the user
- **Tech need** — what architectural substrate must exist in code
- **Substrate** — `exists` / `partial` / `missing` / `unplanned`
- **Phase** — `climb` (below target) / `hold` (at target) / `converge` (deletion gate passes)

---

## 1. Intake & Format Routing                                            `spec:1`

**Product need:** Accept source material in multiple formats and route it into the right pipeline.
**Tech need:** Format detection, manifest normalization, recipe selection, contact-sheet routing.
**Substrate:** partial

**Story coverage:** [x] complete
**Spec:** spec:1 (spec:1.1)
**ADR Refs:** None yet
**Absorbs:** Intake & Format Routing (old 1)

### Compromise Progress

- **C2: Format-Specific Conversion Recipes** (AI capability) — **climb**
  - Current: User selects a YAML recipe. Lightweight routing helpers (contact sheets, manifest-based intake) reduce ambiguity.
  - Target: Auto-detect replaces manual recipe selection for 10 diverse documents.
  - Eval: `auto-book-type-detection` — no scores recorded. **no eval.** Retry when: `new-approach` (contact sheet + VLM classification).

---

## 2. OCR & Text Extraction                                              `spec:2`

**Product need:** Turn scanned pages and page images into faithful text/HTML.
**Tech need:** AI-first OCR, targeted downstream rescue for hard layouts, artifact reuse workflows.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:2 (spec:2.1, spec:2.2)
**ADR Refs:** None yet
**Absorbs:** OCR & Text Extraction (old 2)

### Compromise Progress

- **C1: Multi-Stage OCR Pipeline** (AI capability) — **climb**
  - Current: AI-first OCR as default, targeted rescue/rerun loops for failures. Strong signals from Stories 127, 131, 140, 144.
  - Target: Single-model OCR of a 400-page mixed-format book at ≥99% character accuracy, layout preserved, <$2 total cost.
  - Eval: No dedicated compromise-detection eval. Closest: `ocr-model-genealogy` at `character_accuracy = 0.97` (2026-02-20, target 0.99), `onward-table-fidelity` at `structure_preservation = 0.969` (2026-03-11, target 0.95). **FAIL** on deletion gate. Retry when: `new-subject-model` or `architecture-change`.

- **C6: Expensive OCR for Quality** (Economics) — **hold**
  - Current: GPT-5.1 AI OCR at ~$0.01/page. Artifact reuse workflows minimize re-runs. Story 134 validated 2048px downsampling as safe default.
  - Target: Current-quality OCR below $0.001/page sustained.
  - Eval: No deletion eval recorded. Trigger is economic, not model-quality. **hold** — acceptable cost, waiting on market.

---

## 3. Layout & Structure Understanding                                   `spec:3`

**Product need:** Detect boundaries, headings, tables, multi-column structure, and layout cues.
**Tech need:** Deterministic detectors, VLM escalation, section splitting, boundary ordering.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:3 (spec:3.1)
**ADR Refs:** None yet
**Absorbs:** Layout & Structure Understanding (old 3)

### Compromise Progress

- **C3: Heuristic + AI Layout Detection** (AI capability) — **climb**
  - Current: Deterministic detectors for cheap/stable cases, AI escalation for ambiguity. System still depends on heuristics for stability and cost.
  - Target: VLM-only layout detection at 100% accuracy on a diverse 5-document benchmark with no heuristic fallbacks.
  - Eval: No dedicated deletion eval recorded. **no eval.** Retry when: layout benchmark exists or new subject model makes VLM-first credible.

---

## 4. Illustration Extraction                                            `spec:4`

**Product need:** Detect illustrations, crop them cleanly, exclude text, preserve source relationship.
**Tech need:** VLM crop detection, validator models, OCR-driven text trimming, retry logic.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:4 (spec:4.1, spec:4.2)
**ADR Refs:** None yet
**Absorbs:** Illustration Extraction (old 4)

### Compromise Progress

- **C4: Two-Stage Image Crop Detection** (AI capability) — **climb**
  - Current: Detector + validator architecture with retry-on-count-mismatch. Story 133 improved quality/cost with Gemini 3 Flash conservative-count prompt.
  - Target: Single-model crop detection ≥0.95 overall, ≥0.95 pass rate.
  - Eval: `single-model-crop-detection` — `overall = 0.856`, `pass_rate = 0.77` (2026-01-25). **FAIL.** Retry when: `new-subject-model`.

- **C5: Layout Text Trim Heuristics for Crops** (AI capability) — **climb**
  - Current: OCR-driven text trimming, conservative and inspectable.
  - Target: VLM crop detection excludes all non-illustration content on a 50-page benchmark.
  - Eval: No dedicated text-exclusion eval. Closest: `image-crop-extraction` at `overall = 0.900`, `pass_rate = 0.923` (2026-03-11, target 0.95). **FAIL.** Retry when: `new-subject-model` or dedicated text-exclusion benchmark.

---

## 5. Document Consistency Planning                                      `spec:5`

**Product need:** Ensure repeated structures render consistently across a whole document.
**Tech need:** Pattern discovery, consistency plan emission, plan-aware selective reruns, conformance reporting.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:5 (spec:5.1)
**ADR Refs:** ADR-001 (source-aware consistency strategy)
**Absorbs:** Document Consistency Planning (old 5)

### Compromise Progress

- **C7: Page-Scope Extraction with Document-Level Consistency Planning** (AI capability + cost) — **climb**
  - Current: Document-level planning explicit and inspectable. Plan-aware reruns instead of hidden normalization. Stories 141-146 established the pattern.
  - Target: On 3+ repeated-structure documents, one-pass extractor produces internally consistent structures without planning layer.
  - Eval: `onward-document-consistency-planning` at `missed_manual_format_coverage = 1.0` (2026-03-15) — proves planning layer works, not yet deletable. **FAIL** on deletion gate. Retry when: `new-approach` (second repeated-structure document) or `architecture-change`.

---

## 6. Validation, Provenance & Export                                    `spec:6`

**Product need:** Prove output is correct and Dossier-ready with full traceability.
**Tech need:** Schema validation, provenance stamping, run health, export formatting.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:6
**ADR Refs:** None yet
**Absorbs:** Validation, Provenance & Export (old 6)

No active compromises. Obligations flow from Non-Negotiable Design Principles #1-4.

Provenance completeness for verified scanned/image pipelines is `1.0` after
Story 132's envelope fixes. Validation and run health remain active cross-cutting
responsibilities.

---

## 7. Graduation & Dossier Handoff                                      `spec:7`

**Product need:** Migrate mature converters into Dossier so codex-forge stays lean.
**Tech need:** Graduation criteria, Dossier intake surface readiness, fixture breadth.
**Substrate:** missing

**Story coverage:** [ ] stories needed
**Spec:** spec:7
**ADR Refs:** None yet
**Absorbs:** Graduation & Dossier Handoff (old 7)

No active product compromises. Obligations flow from Non-Negotiable Design
Principle #5 (Graduate to Dossier) and the Mission. `0` formats graduated today.

---

## 8. AI Harnesses & Tooling                                            `spec:8`

**Product need:** (execution category — no direct user-facing product need)
**Tech need:** Eval framework, prompt engineering, pipeline orchestration, schema validation, artifact inspection.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:8 (B1–B6)
**ADR Refs:** None yet
**Absorbs:** Project Operating System (old 8) — AI/tooling half

### Compromise Progress

Build-process compromises tracked in `spec:8`:

| ID | Process Element | Phase | Notes |
|---|---|---|---|
| B1 | Eval framework (promptfoo) | hold | Working; used actively for quality and deletion gates |
| B2 | Prompt engineering | hold | Prompts are stable for current pipelines |
| B3 | Pipeline orchestration (driver.py) | hold | Mature; handles recipes, stages, artifact management |
| B4 | Schema stamping & validation | hold | Working; catches structural drift |
| B5 | Manual artifact inspection | climb | Still required for every story completion |
| B6 | Escalation loops & retry caps | climb | Active in OCR, crop detection, consistency planning |

---

## 9. Planning Infrastructure                                           `spec:9`

**Product need:** (execution category — no direct user-facing product need)
**Tech need:** Stories, ADRs, build map, triage skills, runbooks.
**Substrate:** exists

**Story coverage:** [x] complete
**Spec:** spec:9 (B7–B10)
**ADR Refs:** None yet
**Absorbs:** Project Operating System (old 8) — planning half

### Compromise Progress

Build-process compromises tracked in `spec:9`:

| ID | Process Element | Phase | Notes |
|---|---|---|---|
| B7 | Story/backlog system | hold | Working; 148 stories tracked |
| B8 | Build map & phase tracking | hold | This document; reorganized per ADR-021 |
| B9 | ADR process | hold | 1 accepted ADR; process established |
| B10 | YAML recipe configuration | climb | Overlaps with C2; manual config still required |

### Operating Rule — Quality First, Then Complexity Collapse

When an active converter or repair seam is still failing manual review, the next
job is to raise quality with the smallest coherent changes needed to clear that
bar. Once the reviewed output is acceptable, the next planned step should not
be another unbounded layer of workaround logic by default. It should be a
**complexity collapse** pass: inventory the active workaround stack, name the
deletion / merge targets, and define the evidence needed to simplify without
reopening the quality gap.

**Acceptable-quality bar:** a real `driver.py` validation run, artifacts in
`output/runs/`, manual inspection on the known hard cases, and no known
reviewed defects in the active slice. At that point remaining work should look
like semantic cleanup, broader fixture coverage, or deliberate architecture
simplification, not emergency structural repair.

**First tracked candidate:** the Onward scanned genealogy table path after Story
146 and run `story146-onward-build-stitch-r5`. That seam now has manually
accepted reviewed outputs on the previously failing table-continuity and
row-shape cases, so the next strategic step is a collapse / simplification
story rather than another opportunistic repair layer. See Story 147.

**Evidence run:** `story146-onward-build-stitch-r5`

**Story 149 result:** first collapse step landed. The maintained regression
path is now `configs/recipes/onward-genealogy-build-regression.yaml`, and the
retained shared genealogy HTML stitching logic now lives in
`modules/common/onward_genealogy_html.py` instead of being reused through
private build/rerun cross-imports.

**Current state:** `climb` on the full canonical Onward output, `hold` on the
reviewed table-continuity / row-shape slice, and not yet `converge`. The seam
has a reviewed trusted slice and a maintained regression path, but the full
Onward output is not yet blessed end-to-end and the workaround stack still
survives.

**Current blessed evidence run:** `story149-onward-build-regression-r1` is now
recorded `known_good` for scope `onward_genealogy_reviewed_html_slice`; generic
`html` remains `partial` until broader value-level verification is refreshed.
The committed reviewed slice for this baseline now lives under
`benchmarks/golden/onward/reviewed_html_slice/story149-onward-build-regression-r1/`.

**Active workaround stack:**
- `plan_onward_document_consistency_v1` plus its `pattern_inventory`,
  `consistency_plan`, and `conformance_report` sidecars still define the
  document-local policy for this recipe.
- `rerun_onward_genealogy_consistency_v1` turns planner / validator signals into
  bounded source-aware rereads.
- `table_rescue_onward_tables_v1` still carries page-level deterministic
  normalization that can beat or replace a weak OCR rerun on some genealogy
  pages.
- `modules/common/onward_genealogy_html.py` now owns the retained deterministic
  genealogy HTML stitching and row-shape normalization that both build and
  rerun still need.
- `build_chapter_html_v1 --merge_contiguous_genealogy_tables` is now narrowed to
  chapter-local continuity assembly that calls the shared helper instead of
  privately owning that normalization logic.
- `configs/recipes/onward-genealogy-build-regression.yaml` is the smaller
  permanent build/validate regression bundle for this seam; the old Story 146
  proof recipe is historical evidence only, not a maintained second operating
  path.

**Candidate deletion / merge targets:**
- Collapse planner-guided rerun targeting and late build-stage repair into
  fewer layers once one upstream seam can preserve subgroup rows, table
  continuity, and row shape by default.
- Delete or narrow deterministic normalization that only exists to compensate
  for weak upstream extraction once the stronger seam proves stable on the
  reviewed hard cases.
- Keep the permanent regression bundle small and evidence-backed; do not promote
  the historical Story 146 proof recipe back into the maintained operating path
  unless the smaller guardrail stops covering the reviewed slice.

**Proof needed before simplification:**
- A real `driver.py` run on the maintained Onward path or a clearly proposed
  replacement path, not only the story-scoped validation recipe.
- Manual review on the previously failing chapters covered by
  `story146-onward-build-stitch-r5`.
- No reopened fragmentation, subgroup-row, or row-shape defects in the reviewed
  slice.
- A file-level mapping showing which late repair step becomes redundant, which
  step absorbs any still-necessary logic, and why provenance / inspectability
  stay intact.

**Non-goal:** this does not claim that C7, C1, or C3 are resolved. It is the
inspectable roadmap for deciding what can be deleted or merged next.

**Tracking model:** this build-map section is the high-level dashboard for the
Onward seam: plan, current phase, trusted slice, and next simplification move.
The detailed operational truth lives elsewhere:
- `output/run_assessments.jsonl` is the trust ledger for blessed runs and
  scopes (`known_good`, `partial`, `unsafe`, `superseded`).
- `output/run_health.jsonl` and `output/run_manifest.jsonl` track reuse safety,
  provenance, and exact run discovery.
- `benchmarks/golden/onward/` holds the committed Onward golden slices used by
  evals and spot-checked regression work today.
- `docs/runbooks/golden-build.md` defines how those goldens are created and
  maintained.
- Long-term direction: these scoped trusted slices should accumulate toward one
  canonical 100%-correct Onward baseline, but until that exists the registry
  and committed goldens describe which parts of that baseline are actually
  verified.

**Reusable pattern:** when another seam clears the acceptable-quality bar, reuse
this same mini-template: evidence run, active workaround stack, candidate
deletion / merge targets, and proof needed before simplification. Do not add an
empty dedicated section until a second candidate exists.

---

## Input Coverage

> Cross-cutting section spanning multiple categories. Machine-readable source:
> `tests/fixtures/formats/_coverage-matrix.json`

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
- **Root cause:** C4 (spec:4.1) and C5 (spec:4.2) still hold. Single-stage crop detection is not good
  enough to remove validator + trim heuristics.
- **Fix category:** Model-selection / compromise-detection.
- **Status:** Still open; blocked on better single-model performance or a
  stronger benchmark signal.

### Gap 2 — Born-digital PDF native text extraction

- **Current signal:** No pipeline, no fixture, no eval.
- **Root cause:** Intake (spec:1) still assumes scanned/OCR-first processing.
- **Fix category:** New intake module.
- **Status:** High-value missing capability.

### Gap 3 — Office document intake (DOCX/XLSX/PPTX)

- **Current signal:** No pipeline family exists for office documents.
- **Root cause:** Intake coverage (spec:1) is still heavily skewed toward PDFs and image
  directories.
- **Fix category:** New intake modules / routing.
- **Status:** High-value missing capability, especially for Storybook-adjacent
  uploads.

### Gap 4 — Handwritten document transcription

- **Current signal:** No tested handwriting path exists.
- **Root cause:** No fixture set and no dedicated VLM transcription flow.
- **Fix category:** New intake/extraction path (spec:1, spec:2).
- **Status:** High-value missing capability for personal archives.

### Gap 5 — Fixture breadth and graduation confidence

- **Current signal:** Passing formats still rely on very few fixtures, and no
  format meets the "3 diverse fixtures" graduation bar (spec:7) yet.
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

A converter is ready to graduate to Dossier (spec:7) when:

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
