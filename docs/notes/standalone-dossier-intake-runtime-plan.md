# `doc-web` Extraction Inventory and First-Cut Migration Plan

**Date:** 2026-03-18  
**Decision source:** `docs/decisions/adr-002-doc-web-runtime-boundary/adr.md`

This note records the current inventory for graduating codex-forge's mature
document-to-website runtime into `doc-web`.

## Accepted Boundary

- `codex-forge` remains the ingestion R&D lab.
- `doc-web` becomes the reusable structural-website runtime.
- Dossier consumes `doc-web` through a versioned contract.
- Presentation polish and publish-site theming stay outside both codex-forge
  and `doc-web`.

## First Extraction Slice

The first slice should prove the boundary with the smallest coherent seam:

- generic bundle contract (`manifest.json`, provenance sidecar, reading order)
- generic HTML or website emitter split from `build_chapter_html_v1`
- minimal golden fixtures validating the bundle and provenance contract

This is intentionally smaller than "move the whole pipeline."

## Migrate As-Is Candidates Later

These look broadly reusable and may later move into `doc-web` once the
bundle-emission seam is stable:

- `modules/extract/ocr_ai_gpt51_v1/`
- `modules/extract/crop_illustrations_guided_v1/`
- `modules/adapter/table_rescue_html_loop_v1/`
- `modules/transform/extract_page_numbers_html_v1/`
- `modules/adapter/table_fix_continuations_v1/`
- `modules/portionize/portionize_toc_html_v1/`

These are *not* the first extraction slice. They are later migration
candidates after the `doc-web` bundle contract is stable.

## Refactor Before Migrate

- `modules/build/build_chapter_html_v1/main.py`
  - currently mixes structural website output, embedded CSS, navigation, image
    publishing, and some document-specific output shaping
  - should be split into a generic bundle emitter plus optional presentation
    wrapper behavior
- `schemas.py`
  - currently lacks dedicated `chapter_html_manifest_v1` bundle schema classes
  - needs explicit `doc-web` bundle/provenance contract classes before the
    runtime boundary is trustworthy
- `configs/recipes/recipe-onward-images-html-mvp.yaml`
  - useful as evidence and fixture source, but not itself the runtime contract

## Leave Behind

These should remain in codex-forge, not move into `doc-web`:

- Fighting Fantasy/gamebook-specific extraction, enrichment, validation, and
  export logic
- story system, backlog docs, ADR scaffolding, and build-map/process overhead
- benchmark workspace, run registries, and research-only helper surfaces
- Onward-specific genealogy rescue and validation modules unless they are later
  generalized convincingly
- `driver.py` as the codex-forge R&D orchestrator

## Archive Only

Keep as cold storage or selective reference, not as runtime dependencies:

- full historical `output/runs/` evidence
- broad codex-forge golden slices beyond the minimal `doc-web` contract fixtures
- superseded R&D notes and legacy FF-oriented planning surfaces

## Follow-Up Stories

- Story 152 — `doc-web` bundle and provenance contract
- Story 153 — Extract `doc-web` bundle emitter
- Story 154 — Dossier `doc-web` semantic HTML handoff

## Open Questions

- whether `doc-web` v0 owns only bundle emission or also the first mature OCR
  and portionization stages
- how much provenance should be inline in HTML versus only in sidecars
- whether codex-forge eventually becomes fully archived or remains live as a
  narrow R&D fixture bank
