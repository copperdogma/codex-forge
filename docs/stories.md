# Project Stories — codex-forge

## Recommended Order (next up)
Guiding priorities: **perfect OCR first**, then move downstream stage‑by‑stage. **Finish Fighting Fantasy to ~100% quality/coverage before starting Onward to the Unknown.**

1. **065 — Stabilize EasyOCR as a Third OCR Engine**  
   Finish full‑book EasyOCR coverage and performance on Deathtrap Dungeon. (Blocks true 3‑engine voting.)
2. **063 — OCR Ensemble Three‑Engine Voting**  
   Implement real 3‑way fusion + Tesseract confidences + inline escalation tuning once 065 is stable.
3. **062 — OCR Content Type Detection Module**  
   Tag OCR lines/elements with DocLayNet‑style content types to guide downstream routing and preserve layout intent.
4. **058 — Post‑OCR Text Quality & Error Correction**  
   Add generic spell/garble detection + repair loop so OCR output is readable even when engines agree on bad text.

5. **059 — Section Detection & Boundary Improvements**  
   Use improved OCR + content‑types to harden boundary/header detection for FF.
6. **035 — Fighting Fantasy Pipeline Optimization**  
   Drive missing/no‑text/no‑choice to targets using the new OCR + boundary stack.
7. **050 — FF Ending Detection Verification**  
   Verify ending/dead‑end classification quality on FF outputs (no book‑specific tuning).
8. **056 — Validation Forensics Automation (remaining items)**  
   Finish ending‑aware traces, boundary‑source reasoning, toggles/docs, optional HTML/CSV view.
9. **066 — FF Pipeline Accel + Accuracy Guardrails**  
   Only after 035 is Done; speed up clean/extract with hard regression guards.

10. **009 — Layout‑Preserving Extractor**  
    Build layout/table preservation needed for non‑FF books.
11. **026 — Onward to the Unknown pilot (Arthur L'Heureux)**  
    Run end‑to‑end with layout‑aware table handling once 009 lands.

Later / non‑blocking:
- 024 Image cropper follow‑up (image extraction quality)
- 053 Pipeline smoke test (static, no external calls)  
- 021 Dashboard UI polish
- 038 Agentic pipeline coordinator
- 011 AI planner to assemble pipelines
- 028 Market discovery, 029 Model audit, 099 Remove dev backcompat note

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
|| 029 | Audit model lineup vs latest OpenAI sheets | Medium | To Do | /docs/stories/story-029-model-audit-openai.md |
|| 030 | Fighting Fantasy Engine format export | High | Done | /docs/stories/story-030-ff-engine-format.md |
|| 031 | Fighting Fantasy output refinement | High | Done | /docs/stories/story-031-ff-output-refinement.md |
|| 032 | Unstructured intake & Document IR adoption | Medium | Done | /docs/stories/story-032-unstructured-intake-and-document-ir-adoption.md |
|| 033 | ARM64-native pipeline environment & perforecipe-pagelines-repair-choices.yamlrmance | Medium | Done | /docs/stories/story-033-arm64-pipeline-conversion.md |
|| 034 | FF Unstructured follow-ups (elements, helpers, graph quality) | High | Done | /docs/stories/story-034-ff-unstructured-followups.md |
|| 035 | Fighting Fantasy Pipeline Optimization | High | In Progress | /docs/stories/story-035-ff-pipeline-optimization.md |
|| 036 | FF OCR Recovery & Text Repair | High | Done | /docs/stories/story-036-ff-ocr-recovery-and-text-repair.md |
|| 037 | FF OCR Ensemble with BetterOCR | High | Done | /docs/stories/story-037-ocr-ensemble-with-betterocr.md |
|| 038 | Agentic Pipeline Coordinator | Medium | To Do | /docs/stories/story-038-agentic-pipeline-coordinator.md |
|| 050 | FF Ending Detection Verification | Medium | Open | /docs/stories/story-050-ff-ending-detection.md |
|| 051 | Text Quality Evaluation & Repair | High | Done | /docs/stories/story-051-text-quality-eval.md |
|| 052 | Evaluate Apple Vision OCR Integration | Medium | Done | /docs/stories/story-052-apple-ocr-integration.md |
|| 053 | Pipeline Smoke Test (Static Sample, No External Calls) | High | Open | /docs/stories/story-053-smoke-test-pipeline.md |
|| 054 | Canonical FF Recipe Consolidation | High | Done | /docs/stories/story-054-canonical-ff-recipe.md |
|| 056 | Validation Forensics Automation | High | To Do | /docs/stories/story-056-validation-forensics.md |
|| 057 | OCR Quality & Column Detection Improvements | High | Done | /docs/stories/story-057-ocr-quality-column-detection.md |
|| 058 | Post-OCR Text Quality & Error Correction | High | To Do | /docs/stories/story-058-post-ocr-text-quality.md |
|| 059 | Section Detection & Boundary Improvements | High | To Do | /docs/stories/story-059-section-detection-boundaries.md |
|| 060 | Pipeline Regression Testing Suite | High | Done | /docs/stories/story-060-pipeline-regression-testing.md |
|| 061 | OCR Ensemble Fusion Improvements | High | Done | /docs/stories/story-061-ocr-ensemble-fusion.md |
|| 062 | OCR Content Type Detection Module | Medium | Open | /docs/stories/story-062-ocr-content-type-detection.md |
|| 063 | OCR Ensemble Three-Engine Voting | High | Open | /docs/stories/story-063-ocr-ensemble-three-engine.md |
|| 064 | Apple Vision OCR (VNRecognizeTextRequest) Adapter | Medium | Done | /docs/stories/story-064-apple-vision-ocr.md |
|| 065 | Stabilize EasyOCR as a Third OCR Engine | High | Open | /docs/stories/story-065-easyocr-reliability.md |
|| 066 | FF Pipeline Accel + Accuracy Guardrails | High | To Do | /docs/stories/story-066-ff-pipeline-accel-accuracy.md |
|| 067 | GPU Acceleration for OCR Pipeline | High | Done | /docs/stories/story-067-gpu-acceleration-ocr.md |
|| 099 | Remove dev-only backcompat disclaimer | Low | To Do | /docs/stories/story-099-remove-dev-backcompat-note.md |

## Notes
- Status "Done" reflects current working state in codex-forge. "To Do" items are planned next steps aligned with `docs/requirements.md` and `snapshot.md`.
- Use existing files in `/docs/stories/` as templates for structure when creating these story documents.
