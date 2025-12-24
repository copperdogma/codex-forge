# Project Stories — codex-forge

## Recommended Order (next up)
Guiding priorities: **development stability first**, then **quality definitions**, followed by **core gameplay enrichment**. Finish Fighting Fantasy to 100% "game-ready" status before scaling optimizations or starting the genealogy pilot.

1. DONE: **053 — Pipeline Smoke Test (Static Sample, No External Calls)**: Essential for developer productivity and CI stability; catches integration breakages without incurring API costs.
3. **095 — Combat and Enemy Extraction**: High-value enrichment; parses enemy stat blocks and outcomes critical for the game engine's primary mechanic.
4. **094 — Inventory Parsing and Extraction**: Core enrichment for tracking item gains, losses, and conditional possession logic in the engine.
5. **088 — Choice Parsing Enhancements (HTML + Linking)**: Improves structural HTML quality and link recall before scaling to the full library.
6. **066 — FF Pipeline Accel + Accuracy Guardrails**: Optimizes the now-stable GPT-5.1 pipeline for speed and cost efficiency without risking regressions.
7. **084 — Fast PDF Image Extraction (Embedded Streams)**: Technical optimization to significantly reduce slow and expensive PDF rasterization time.
8. **087 — Retire Legacy OCR-Only Recipe**: Housekeeping to reduce maintenance overhead and prevent accidental use of superseded OCR-ensemble paths.
9. **075 — Booktype Text Cleanup Adapter (Downstream Normalization)**: Refines final text fidelity via deterministic tools and lexicon-guided normalization.
10. **080 — Central Escalation Cache (Premium OCR Overlay)**: Architectural cleanup to eliminate redundant vision calls and unify page-level provenance.
13. **024 — Image cropper follow-up**: Improves quality of extracted illustrations and diagrams via more advanced detector backends.
14. **011 — AI planner to assemble pipelines**: Facilitates easier configuration for diverse book types via agentic goal-to-recipe matching.
15. **038 — Agentic Pipeline Coordinator**: Fundamental shift toward autonomous quality monitoring, sanity checking, and self-healing artifacts.
2. **083 — Game-Ready Validation Checklist**: Establishes the formal quality bar for "authoritative" artifacts before declaring the FF phase complete.
11. **009 — Layout-preserving extractor**: Prerequisite capability for handling non-narrative (tabular/complex) book layouts in the next phase.
12. **026 — Onward to the Unknown — Arthur L'Heureux pilot**: First end-to-end testbed for genealogy/complex layouts; depends on 009.
16. **099 — Remove dev-only backcompat disclaimer**: Final milestone marking the entire pipeline as stable and production-ready.



This index tracks stories in `/docs/stories/` for the codex-forge pipeline.

## Story List
| Story ID | Title | Priority | Status | Link |
|----------|-------|----------|---------|------|
|| 001 | Establish run layout & manifests | High | Done | /docs/stories/story-001-run-layout-and-manifest.md |
|| 002 | Page cleaning module (multimodal) | High | Done | /docs/stories/story-002-page-cleaning.md |
|| 003 | Portionization with priors & overlaps | High | Done | /docs/stories/story-003-portionization-priors.md |
|| 004 | Consensus/dedupe/normalize/resolve pipeline | High | Done | /docs/stories/story-004-consensus-resolve.md |
|| 005 | Final assembly (portions_final_raw.json) | High | Done | /docs/stories/story-005-final-assembly.md |
|| 006 | Enrichment pass (choices/combat/items/endings) | High | Done | /docs/stories/story-006-enrichment.md |
|| 007 | Turn-to validator (CYOA cross-refs) | Medium | Done | /docs/stories/story-007-turn-validator.md |
|| 008 | Image cropper/mapper | Medium | Done | /docs/stories/story-008-image-cropper.md |
|| 009 | Layout-preserving extractor | Medium | To Do | /docs/stories/story-009-layout-preserve.md |
|| 010 | Coarse+fine portionizer & continuation merge | Medium | Done | /docs/stories/story-010-coarse-fine-merge.md |
|| 011 | AI planner to assemble pipelines | Medium | To Do | /docs/stories/story-011-ai-planner.md |
|| 012 | Automation wrapper (single driver + config snapshots) | Medium | Done | /docs/stories/story-012-driver-automation.md |
|| 013 | Cost/perf benchmarking and presets | Low | Done | /docs/stories/story-013-cost-perf.md |
|| 015 | Modular pipeline & module registry | High | Done | /docs/stories/story-015-modular-pipeline.md |
|| 016 | Driver DAG & schema compatibility | High | Done | /docs/stories/story-016-driver-dag-schema.md |
|| 017 | Module UX polish (params & outputs) | Medium | Done | /docs/stories/story-017-module-ux.md |
|| 018 | Enrichment & alt modules | High | Done | /docs/stories/story-018-enrichment-alt-mods.md |
|| 019 | Pipeline visibility dashboard | Medium | Done | /docs/stories/story-019-pipeline-visibility.md |
|| 020 | Module encapsulation & shared common | Medium | Done | /docs/stories/story-020-module-encapsulation.md |
|| 021 | Dashboard UI polish (highlighting & pane) | Medium | In Progress | /docs/stories/story-021-dashboard-ui-polish.md |
|| 022 | Pipeline instrumentation (timing & cost) | High | Done | /docs/stories/story-022-instrumentation.md |
|| 023 | Consolidate section target adapters | Medium | Done | /docs/stories/story-023-section-target-guard.md |
|| 024 | Image cropper follow-up | Medium | To Do | /docs/stories/story-024-image-cropper-followup.md |
|| 025 | Module pruning & registry hygiene | Medium | Done | /docs/stories/story-025-module-prune.md |
|| 026 | Onward to the Unknown — Arthur L'Heureux pilot | Medium | To Do | /docs/stories/story-026-onward-unknown-arthur-lheureux.md |
|| 027 | Contact-sheet intake for automatic book type planning | Medium | Done | /docs/stories/story-027-contact-sheet-auto-intake.md |
|| 028 | Market Discovery for codex-forge | Medium | In Progress | /docs/stories/story-028-market-discovery.md |
|| 029 | Audit model lineup vs latest OpenAI sheets | Medium | Obsolete | /docs/stories/story-029-model-audit-openai.md |
|| 030 | Fighting Fantasy Engine format export | High | Done | /docs/stories/story-030-ff-engine-format.md |
|| 031 | Fighting Fantasy output refinement | High | Done | /docs/stories/story-031-ff-output-refinement.md |
|| 032 | Unstructured intake & Document IR adoption | Medium | Done | /docs/stories/story-032-unstructured-intake-and-document-ir-adoption.md |
|| 033 | ARM64-native pipeline environment & perforecipe-pagelines-repair-choices.yamlrmance | Medium | Done | /docs/stories/story-033-arm64-pipeline-conversion.md |
|| 034 | FF Unstructured follow-ups (elements, helpers, graph quality) | High | Done | /docs/stories/story-034-ff-unstructured-followups.md |
|| 035 | Fighting Fantasy Pipeline Optimization | High | Done | /docs/stories/story-035-ff-pipeline-optimization.md |
|| 036 | FF OCR Recovery & Text Repair | High | Done | /docs/stories/story-036-ff-ocr-recovery-and-text-repair.md |
|| 037 | FF OCR Ensemble with BetterOCR | High | Done | /docs/stories/story-037-ocr-ensemble-with-betterocr.md |
|| 038 | Agentic Pipeline Coordinator | Medium | To Do | /docs/stories/story-038-agentic-pipeline-coordinator.md |
|| 050 | FF Ending Detection Verification | Medium | Done | /docs/stories/story-050-ff-ending-detection.md |
|| 051 | Text Quality Evaluation & Repair | High | Done | /docs/stories/story-051-text-quality-eval.md |
|| 052 | Evaluate Apple Vision OCR Integration | Medium | Done | /docs/stories/story-052-apple-ocr-integration.md |
|| 053 | Pipeline Smoke Test (Static Sample, No External Calls) | High | Done | /docs/stories/story-053-smoke-test-pipeline.md |
|| 054 | Canonical FF Recipe Consolidation | High | Done | /docs/stories/story-054-canonical-ff-recipe.md |
|| 056 | Validation Forensics Automation | High | Done | /docs/stories/story-056-validation-forensics.md |
|| 057 | OCR Quality & Column Detection Improvements | High | Done | /docs/stories/story-057-ocr-quality-column-detection.md |
|| 058 | Post-OCR Text Quality & Error Correction | High | Done | /docs/stories/story-058-post-ocr-text-quality.md |
|| 059 | Section Detection & Boundary Improvements | High | Done | /docs/stories/story-059-section-detection-boundaries.md |
|| 060 | Pipeline Regression Testing Suite | High | Done | /docs/stories/story-060-pipeline-regression-testing.md |
|| 061 | OCR Ensemble Fusion Improvements | High | Done | /docs/stories/story-061-ocr-ensemble-fusion.md |
|| 062 | OCR Content Type Detection Module | Medium | Done | /docs/stories/story-062-ocr-content-type-detection.md |
|| 063 | OCR Ensemble Three-Engine Voting | High | Done | /docs/stories/story-063-ocr-ensemble-three-engine.md |
|| 064 | Apple Vision OCR (VNRecognizeTextRequest) Adapter | Medium | Done | /docs/stories/story-064-apple-vision-ocr.md |
|| 065 | Stabilize EasyOCR as a Third OCR Engine | High | Done | /docs/stories/story-065-easyocr-reliability.md |
|| 066 | FF Pipeline Accel + Accuracy Guardrails | High | To Do | /docs/stories/story-066-ff-pipeline-accel-accuracy.md |
|| 067 | GPU Acceleration for OCR Pipeline | High | Done | /docs/stories/story-067-gpu-acceleration-ocr.md |
|| 068 | Fighting Fantasy Boundary Detection Improvements | High | Done | /docs/stories/story-068-ff-boundary-detection.md |
|| 069 | PDF Text Extraction Engine for OCR Ensemble | Medium | Done | /docs/stories/story-069-pdf-text-extraction-engine.md |
|| 070 | OCR Split Refinement — Zero Bad Slices | High | Done | /docs/stories/story-070-ocr-split-refinement.md |
|| 071 | Output Artifact Organization | Medium | Done | /docs/stories/story-071-output-artifact-organization.md |
|| 072 | OCR Spell-Weighted Voting Enhancement | Medium | Obsolete | /docs/stories/story-072-ocr-spell-weighted-voting.md |
|| 073 | 100% Section Detection — Segmentation Architecture | High | Done | /docs/stories/story-073-100-percent-section-detection.md |
|| 074 | Missing Sections Investigation — Complete 100% Coverage | High | Done | /docs/stories/story-074-missing-sections-investigation.md |
|| 075 | Booktype Text Cleanup Adapter (Downstream Normalization) | Medium | To Do | /docs/stories/story-075-booktype-text-cleanup-adapter.md |
|| 076 | AI Vision Engine Evaluation — Best Value for Pipeline | Medium | Done | /docs/stories/story-076-ai-vision-engine-evaluation.md |
|| 077 | AI OCR Radical Simplification — Challenging the Escalation Assumption | High | Done | /docs/stories/story-077-ai-ocr-simplification.md |
|| 078 | Boundary Ordering Guard + Targeted Escalation | High | Done | /docs/stories/story-078-boundary-ordering-escalation.md |
|| 079 | Sequential Page Numbering Refactor — Dual-Field Provenance | High | Done | /docs/stories/story-079-page-numbering-refactor.md |
|| 080 | Central Escalation Cache (Premium OCR Overlay) | High | To Do | /docs/stories/story-080-central-escalation-cache.md |
|| 081 | GPT‑5.1 AI‑First OCR Pipeline (HTML‑First) | High | Done | /docs/stories/story-081-ai-ocr-gpt51-pipeline.md |
|| 082 | Large-Image PDF Cost Optimization | High | Done | /docs/stories/story-082-large-image-pdf-cost-optimization.md |
|| 083 | Game-Ready Validation Checklist | High | To Do | /docs/stories/story-083-game-ready-validation-checklist.md |
|| 084 | Fast PDF Image Extraction (Embedded Streams) | Medium | To Do | /docs/stories/story-084-fast-pdf-image-extraction.md |
|| 085 | Table Rescue OCR Pass | High | Done | /docs/stories/story-085-table-rescue-ocr.md |
|| 086 | Preserve HTML Through Final Gamebook | High | Done | /docs/stories/story-086-preserve-html-final-output.md |
|| 087 | Retire Legacy OCR-Only Recipe | Medium | To Do | /docs/stories/story-087-retire-legacy-ocr-recipe.md |
|| 088 | Choice Parsing Enhancements | High | To Do | /docs/stories/story-088-choice-parsing-enhancements.md |
|| 089 | Pristine Book Parity (Missing Sections + Robustness) | High | Done | /docs/stories/story-089-pristine-book-parity.md |
|| 090 | Run Summary UX (Missing Sections + Stage Metrics) | Medium | Done | /docs/stories/story-090-run-summary-and-missing-section-signal.md |
|| 091 | Orphaned Section Mitigation | High | Done | /docs/stories/story-091-orphaned-section-mitigation.md |
|| 092 | HTML Presentation Cleanup | High | Done | /docs/stories/story-092-html-presentation-cleanup.md |
|| 093 | Coarse Portionizer Endmatter Filter | High | Done | /docs/stories/story-093-coarse-portionizer-endmatter-filter.md |
|| 094 | Inventory Parsing and Extraction | High | To Do | /docs/stories/story-094-inventory-parsing.md |
|| 095 | Combat and Enemy Extraction | High | Done | /docs/stories/story-095-combat-enemy-extraction.md |
|| 096 | Stat Check Extraction (Skill, Luck, and Dice Rolls) | High | To Do | /docs/stories/story-096-stat-check-extraction.md |
|| 097 | Stat Modification Extraction (Skill, Stamina, Luck Changes) | High | To Do | /docs/stories/story-097-stat-modification-extraction.md |
|| 099 | Remove dev-only backcompat disclaimer | Low | To Do | /docs/stories/story-099-remove-dev-backcompat-note.md |

## Notes
- Status "Done" reflects current working state in codex-forge. "To Do" items are planned next steps aligned with `docs/requirements.md` and `snapshot.md`.
- Use existing files in `/docs/stories/` as templates for structure when creating these story documents.
