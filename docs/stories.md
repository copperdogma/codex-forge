# Project Stories — codex-forge

## Recommended Order (next up)
- 031 Fighting Fantasy output refinement — fix quality and correctness issues in FF output modules.
- 030 Fighting Fantasy Engine format export — retarget FF recipe to the engine schema while keeping provenance/images.
- DONE: 016 Driver DAG & schema compatibility — unlocks arbitrary workflows, coarse+fine branches, safer schema wiring.
- DONE: 017 Module UX polish (params & outputs) — catches bad configs early; allows custom outputs for varied runs.
- DONE: 018 Enrichment & alternate modules — delivers gameplay semantics and demonstrates swap breadth.
- DONE: 019 Pipeline visibility dashboard — live stage/state view + artifact inspection for ops.
- DONE: 006 Enrichment pass (choices/combat/items/endings) — core value for gamebooks; builds on 018 modules.
- DONE: 007 Turn-to validator — sanity for CYOA cross-refs once enriched data exists.
- DONE: 022 Pipeline instrumentation (timing & cost) — measure LLM/local time and API spend; add estimates.
- DONE: 023 Consolidate section target adapters — simplify map/backfill into one guard.
- DONE: 010 Coarse+fine portionizer & continuation merge — improves coverage quality for long spans.
- DONE: 008 Image cropper/mapper — map images to portions; leverage source_images.
- DONE: 012 Automation wrapper (driver snapshots) — run configs + snapshot for reproducibility.
- DONE: 013 Cost/perf benchmarking — tune presets after instrumentation lands.
- 021 Dashboard UI polish (highlighting & pane) — follow-up UI tweaks after visibility foundation.
- 025 Module pruning & registry hygiene — audit/remove redundant modules and mark experimental variants.
- 011 AI planner to assemble pipelines — optional; depends on stabilized modules/recipes.
- ~~020 Module encapsulation & shared common~~

This index tracks stories in `/docs/stories/` for the codex-forge pipeline.

## Story List
| Story ID | Title | Priority | Status | Link |
|----------|-------|----------|---------|------|
| 001 | Establish run layout & manifests | High | Done | /docs/stories/story-001-run-layout-and-manifest.md |
| 002 | Page cleaning module (multimodal) | High | Done | /docs/stories/story-002-page-cleaning.md |
| 003 | Portionization with priors & overlaps | High | Done | /docs/stories/story-003-portionization-priors.md |
| 004 | Consensus/dedupe/normalize/resolve pipeline | High | Done | /docs/stories/story-004-consensus-resolve.md |
| 005 | Final assembly (portions_final_raw.json) | High | Done | /docs/stories/story-005-final-assembly.md |
| 006 | Enrichment pass (choices/combat/items/endings) | High | Done | /docs/stories/story-006-enrichment.md |
| 007 | Turn-to validator (CYOA cross-refs) | Medium | Done | /docs/stories/story-007-turn-validator.md |
| 008 | Image cropper/mapper | Medium | Done | /docs/stories/story-008-image-cropper.md |
| 009 | Layout-preserving extractor | Medium | To Do | /docs/stories/story-009-layout-preserve.md |
| 010 | Coarse+fine portionizer & continuation merge | Medium | Done | /docs/stories/story-010-coarse-fine-merge.md |
| 011 | AI planner to assemble pipelines | Medium | To Do | /docs/stories/story-011-ai-planner.md |
| 012 | Automation wrapper (single driver + config snapshots) | Medium | Done | /docs/stories/story-012-driver-automation.md |
| 013 | Cost/perf benchmarking and presets | Low | Done | /docs/stories/story-013-cost-perf.md |
| 015 | Modular pipeline & module registry | High | Done | /docs/stories/story-015-modular-pipeline.md |
| 016 | Driver DAG & schema compatibility | High | Done | /docs/stories/story-016-driver-dag-schema.md |
| 017 | Module UX polish (params & outputs) | Medium | Done | /docs/stories/story-017-module-ux.md |
| 018 | Enrichment & alt modules | High | Done | /docs/stories/story-018-enrichment-alt-mods.md |
| 019 | Pipeline visibility dashboard | Medium | Done | /docs/stories/story-019-pipeline-visibility.md |
| 020 | Module encapsulation & shared common | Medium | Done | /docs/stories/story-020-module-encapsulation.md |
| 021 | Dashboard UI polish (highlighting & pane) | Medium | In Progress | /docs/stories/story-021-dashboard-ui-polish.md |
| 022 | Pipeline instrumentation (timing & cost) | High | Done | /docs/stories/story-022-instrumentation.md |
| 023 | Consolidate section target adapters | Medium | Done | /docs/stories/story-023-section-target-guard.md |
| 024 | Image cropper follow-up | Medium | To Do | /docs/stories/story-024-image-cropper-followup.md |
| 025 | Module pruning & registry hygiene | Medium | Done | /docs/stories/story-025-module-prune.md |
| 026 | Onward to the Unknown — Arthur L'Heureux pilot | Medium | To Do | /docs/stories/story-026-onward-unknown-arthur-lheureux.md |
| 027 | Contact-sheet intake for automatic book type planning | Medium | Done | /docs/stories/story-027-contact-sheet-auto-intake.md |
| 030 | Fighting Fantasy Engine format export | High | Done | /docs/stories/story-030-ff-engine-format.md |
| 031 | Fighting Fantasy output refinement | High | In Progress | /docs/stories/story-031-ff-output-refinement.md |
| 032 | Unstructured intake & Document IR adoption | Medium | Done | /docs/stories/story-032-unstructured-intake-and-document-ir-adoption.md |
| 033 | ARM64-native pipeline environment & performance | Medium | Done | /docs/stories/story-033-arm64-pipeline-conversion.md |
| 034 | FF Unstructured follow-ups (elements, helpers, graph quality) | High | To Do | /docs/stories/story-034-ff-unstructured-followups.md |
| 099 | Remove dev-only backcompat disclaimer | Low | To Do | /docs/stories/story-099-remove-dev-backcompat-note.md |

## Notes
- Status “Done” reflects current working state in codex-forge. “To Do” items are planned next steps aligned with `docs/requirements.md` and `snapshot.md`.
- Use existing files in `/docs/stories/` as templates for structure when creating these story documents.
