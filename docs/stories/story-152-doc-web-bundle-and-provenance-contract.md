# Story 152 — `doc-web` Bundle and Provenance Contract

**Priority**: High
**Status**: Pending
**Ideal Refs**: Requirement #5 (Structure), Requirement #6 (Validate), Requirement #7 (Export), Traceability is the Product, Dossier-ready output
**Spec Refs**: spec:6 (Validation, Provenance & Export), spec:7 (Graduation & Dossier Handoff)
**Decision Refs**: `docs/decisions/adr-002-doc-web-runtime-boundary/adr.md`, `docs/notes/standalone-dossier-intake-runtime-plan.md`, `README.md`, `docs/spec.md`
**Depends On**: Story 151

## Goal

Define the first formal `doc-web` bundle contract so the runtime boundary stops being implicit. The current Onward HTML output proves that codex-forge can emit a structural website, but the final contract is still too loose: `chapter_html_manifest_v1` is not formalized in `schemas.py`, and provenance is too coarse for Dossier's citation requirement. This story should define the bundle layout, manifest schema, provenance sidecar schema, and the default paragraph-level block contract that later extraction and Dossier integration work can implement against.

## Acceptance Criteria

- [ ] A build-ready contract document or schema package defines the first `doc-web` bundle layout, including reading order, chapter/page files, assets, and machine-readable manifests.
- [ ] A provenance contract is defined for paragraph-level default blocks, including stable block IDs and the minimum required source mapping fields needed for Dossier citation/open-original behavior.
- [ ] The current codex-forge output surfaces are mapped clearly into `kept`, `renamed`, `superseded`, or `missing` relative to the new `doc-web` contract, including the fate of `chapter_html_manifest_v1`.
- [ ] At least one real Onward output slice or fixture is identified as the initial golden example for validating the contract.

## Out of Scope

- Extracting code into a new `doc-web` repo
- Dossier implementation work
- Themed website presentation, editorial polish, or publish UX
- Reworking unrelated OCR or genealogy extraction logic unless contract gaps demand it

## Approach Evaluation

- **Simplification baseline**: First inspect whether the current Onward HTML plus manifest already satisfy most of the contract with only schema formalization and a provenance sidecar addition. If so, prefer formalizing the existing shape over inventing a fresh bundle unnecessarily.
- **AI-only**: An LLM can draft candidate schema names and field groupings, but it cannot decide the contract responsibly without checking the real emitted artifacts and current schema stamping behavior.
- **Hybrid**: Inspect the current outputs and schemas, then use AI to synthesize the cleanest bundle/provenance contract with explicit migration notes. This is the leading candidate because the work is part artifact analysis and part contract design.
- **Pure code**: Define schemas directly in `schemas.py` without first writing down the contract and mapping current fields to their future names. Fastest path to code, but risks baking in a sloppy first contract.
- **Repo constraints / prior decisions**: ADR-002 already settled the boundary: structural website bundle, block-level provenance, paragraph-level default citation unit, and no codex-forge-as-runtime dependency. The new contract must support tagged release pins and downstream contract tests.
- **Existing patterns to reuse**: `modules/build/build_chapter_html_v1`, current `chapters_manifest.jsonl` output, `schemas.py`, `UnstructuredElement` provenance patterns, and the extraction inventory in `docs/notes/standalone-dossier-intake-runtime-plan.md`.
- **Eval**: The deciding evidence is whether a real Onward output slice can be losslessly described by the proposed bundle/provenance schema without hand-waving missing fields or relying on chapter-only provenance.

## Tasks

- [ ] Inspect the current HTML output bundle and list the exact fields/files that already align with the accepted `doc-web` contract.
- [ ] Define the first `doc-web` bundle schema:
  - bundle layout
  - manifest fields
  - reading-order/navigation representation
  - assets expectations
- [ ] Define the first provenance schema:
  - paragraph-level default blocks
  - stable block ID format
  - required source reference fields
  - optional location/confidence fields
- [ ] Decide what happens to current codex-forge surfaces:
  - `chapter_html_manifest_v1`
  - inline nav
  - any inline provenance or page-range fields
- [ ] Select or create the first golden fixture set for validating the contract in later `doc-web` and Dossier work
- [ ] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [ ] Run required checks for touched scope:
  - [ ] If this remains docs/schema-only, verify referenced output artifacts and schema mappings manually
  - [ ] If `schemas.py` changes, run `make test` and `make lint`
  - [ ] If pipeline behavior changes, clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and manually inspect the resulting bundle
  - [ ] If agent tooling changed: `make skills-check`
- [ ] If evals or goldens changed materially: run `/improve-eval` and update `docs/evals/registry.yaml`
- [ ] Search all docs and update any related to what we touched
- [ ] Verify Central Tenets:
  - [ ] T0 — Traceability: contract carries enough provenance for Dossier citation and open-original behavior
  - [ ] T1 — AI-First: formalize the smallest contract that matches real outputs instead of overbuilding a speculative schema
  - [ ] T2 — Eval Before Build: validate the contract against real emitted artifacts before freezing it
  - [ ] T3 — Fidelity: no required source-location signal is dropped for convenience
  - [ ] T4 — Modular: contract is generic enough for `doc-web`, not Onward-only
  - [ ] T5 — Inspect Artifacts: manually inspect real HTML and manifest outputs while designing the contract

## Workflow Gates

- [ ] Build complete: implementation finished, required checks run, and summary shared
- [ ] Validation complete or explicitly skipped by user
- [ ] Story marked done via `/mark-story-done`

## Architectural Fit

- **Owning module / area**: Contract/schema layer first, with `modules/build/build_chapter_html_v1` as the primary current-output reference.
- **Data contracts / schemas**: This story likely introduces new bundle/provenance schema classes and may deprecate or supersede the implicit `chapter_html_manifest_v1` shape.
- **File sizes**: `schemas.py` is 964 lines and `modules/build/build_chapter_html_v1/main.py` is 1345 lines, so keep contract work carefully scoped and avoid deep logic edits unless they are clearly required.
- **Decision context**: ADR-002 is the authoritative boundary decision. The extraction-plan note and Story 151 provide the local migration context.

## Files to Modify

- /Users/cam/.codex/worktrees/cdb6/codex-forge/schemas.py — add or formalize `doc-web` bundle/provenance schema classes if implementation starts here (964 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/modules/build/build_chapter_html_v1/main.py — current output reference; only touch if schema or output gaps require it (1345 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/decisions/adr-002-doc-web-runtime-boundary/adr.md — record any settled contract details that become architectural decisions
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/notes/standalone-dossier-intake-runtime-plan.md — update extraction inventory with the final contract mapping
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/stories/story-152-doc-web-bundle-and-provenance-contract.md — keep the story current as the contract decisions land

## Redundancy / Removal Targets

- Implicit use of `chapter_html_manifest_v1` as an undocumented final contract
- Any future docs that describe `doc-web` as "just HTML" without the manifest/provenance bundle
- Any stale note that keeps provenance at chapter-only granularity after this contract lands

## Notes

- Default first citation unit: paragraph-level block provenance, not sentence-level by default.
- Navigation is part of the structural contract, not an optional presentation flourish.
- Favor sidecar provenance for heavy fields and keep inline HTML provenance hooks light.
- Canonical owner note: the accepted `doc-web` contract was frozen in `/Users/cam/.codex/worktrees/e66a/doc-web/docs/stories/story-152-doc-web-bundle-and-provenance-contract.md` and `/Users/cam/.codex/worktrees/e66a/doc-web/docs/doc-web-bundle-contract.md`. This local `codex-forge` file remains a planning mirror for seam-adoption context and is not the dependency gate for closing Story 153.

## Plan

Pending — `/build-story` should decide whether to implement schema classes inside codex-forge first or freeze the contract in docs and extract directly into the future `doc-web` repo.

## Work Log

20260318-2337 — story created: captured the first implementation slice implied by ADR-002. The contract is the next hard dependency because extraction and Dossier integration both need a stable bundle/provenance shape before code can move safely.
