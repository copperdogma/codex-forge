# Project Stories — codex-forge

## Recommended Order (next up)
- DONE: 016 Driver DAG & schema compatibility — unlocks arbitrary workflows, coarse+fine branches, safer schema wiring.
- 020 Module encapsulation & shared common
- 017 Module UX polish (params & outputs) — catches bad configs early; allows custom outputs for varied runs.
- 018 Enrichment & alternate modules — delivers gameplay semantics and demonstrates swap breadth.
- 019 Pipeline visibility dashboard — live stage/state view + artifact inspection for ops.
- 006 Enrichment pass (choices/combat/items/endings) — core value for gamebooks; builds on 018 modules.
- 007 Turn-to validator — sanity for CYOA cross-refs once enriched data exists.
- 008 Image cropper/mapper — maps images to portions; leverage existing source_images.
- 010 Coarse+fine portionizer & continuation merge — complements DAG work; improves coverage quality.
- 012 Automation wrapper (driver snapshots) — operational convenience after DAG/UX solid.
- 013 Cost/perf benchmarking — tune presets after pipeline variants stabilize.
- 014 Docs & onboarding — clean handoff after structural changes settle.

This index tracks stories in `/docs/stories/` for the codex-forge pipeline.

## Story List
| Story ID | Title | Priority | Status | Link |
|----------|-------|----------|---------|------|
| 001 | Establish run layout & manifests | High | Done | /docs/stories/story-001-run-layout-and-manifest.md |
| 002 | Page cleaning module (multimodal) | High | Done | /docs/stories/story-002-page-cleaning.md |
| 003 | Portionization with priors & overlaps | High | Done | /docs/stories/story-003-portionization-priors.md |
| 004 | Consensus/dedupe/normalize/resolve pipeline | High | Done | /docs/stories/story-004-consensus-resolve.md |
| 005 | Final assembly (portions_final_raw.json) | High | Done | /docs/stories/story-005-final-assembly.md |
| 006 | Enrichment pass (choices/combat/items/endings) | High | To Do | /docs/stories/story-006-enrichment.md |
| 007 | Turn-to validator (CYOA cross-refs) | Medium | To Do | /docs/stories/story-007-turn-validator.md |
| 008 | Image cropper/mapper | Medium | To Do | /docs/stories/story-008-image-cropper.md |
| 009 | Layout-preserving extractor | Medium | To Do | /docs/stories/story-009-layout-preserve.md |
| 010 | Coarse+fine portionizer & continuation merge | Medium | To Do | /docs/stories/story-010-coarse-fine-merge.md |
| 011 | AI planner to assemble pipelines | Medium | To Do | /docs/stories/story-011-ai-planner.md |
| 012 | Automation wrapper (single driver + config snapshots) | Medium | To Do | /docs/stories/story-012-driver-automation.md |
| 013 | Cost/perf benchmarking and presets | Low | To Do | /docs/stories/story-013-cost-perf.md |
| 014 | Layout of docs & developer onboarding | Low | To Do | /docs/stories/story-014-docs-onboarding.md |
| 015 | Modular pipeline & module registry | High | Done | /docs/stories/story-015-modular-pipeline.md |
| 016 | Driver DAG & schema compatibility | High | Done | /docs/stories/story-016-driver-dag-schema.md |
| 017 | Module UX polish (params & outputs) | Medium | To Do | /docs/stories/story-017-module-ux.md |
| 018 | Enrichment & alt modules | High | To Do | /docs/stories/story-018-enrichment-alt-mods.md |
| 019 | Pipeline visibility dashboard | Medium | In Progress | /docs/stories/story-019-pipeline-visibility.md |
| 020 | Module encapsulation & shared common | Medium | To Do | /docs/stories/story-020-module-encapsulation.md |

## Notes
- Status “Done” reflects current working state in codex-forge. “To Do” items are planned next steps aligned with `docs/requirements.md` and `snapshot.md`.
- Use existing files in `/docs/stories/` as templates for structure when creating these story documents.
