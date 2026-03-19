# Story 154 — Dossier `doc-web` Semantic HTML Handoff

**Priority**: High
**Status**: Pending
**Ideal Refs**: Requirement #6 (Validate), Requirement #7 (Export), Dossier-ready output, Traceability is the Product
**Spec Refs**: spec:6 (Validation, Provenance & Export), spec:7 (Graduation & Dossier Handoff)
**Decision Refs**: `docs/decisions/adr-002-doc-web-runtime-boundary/adr.md`, Story 152, Story 153
**Depends On**: Story 152, Story 153

## Goal

Publish the exact handoff contract that Dossier will consume from `doc-web`. ADR-002 settled the architectural direction, but Dossier still needs a concrete compatibility target: what files `doc-web` outputs, what Dossier pins/version-checks, what provenance fields are mandatory for citation, and what fixture or contract-test pack proves compatibility. This story should turn that into a handoff package rather than leaving "Dossier will consume it" as a vague future promise.

## Acceptance Criteria

- [ ] A Dossier-facing handoff contract is documented, including expected `doc-web` bundle files, required manifest/provenance fields, versioning expectations, and compatibility-test expectations.
- [ ] The story identifies the exact fixture/golden pack that should be used for Dossier-side contract testing once the Dossier work begins.
- [ ] The handoff contract clearly distinguishes responsibilities:
  - codex-forge R&D
  - `doc-web` runtime
  - Dossier consumer
- [ ] The story names the first concrete Dossier-side follow-up needed to support `--target semantic_html` or equivalent stop-point behavior.

## Out of Scope

- Implementing Dossier code inside this repo
- Building the standalone `doc-web` repo itself
- Visual website theming or polish
- Reworking upstream codex-forge extraction unless the Dossier contract exposes a hard blocker

## Approach Evaluation

- **Simplification baseline**: First ask whether Dossier can consume the accepted `doc-web` bundle with a thin compatibility layer and pinned bundle contract, rather than requiring a bespoke ingestion path immediately.
- **AI-only**: An LLM can draft the handoff contract, but it cannot choose the right mandatory fields without the real `doc-web` bundle contract from Story 152 and seam assumptions from Story 153.
- **Hybrid**: Use the accepted ADR direction plus the bundle contract to synthesize a Dossier-facing contract package and compatibility-test plan. This is the leading candidate.
- **Pure code**: Start changing Dossier blindly before the handoff contract exists. Fastest locally, but it guarantees churn and rework.
- **Repo constraints / prior decisions**: ADR-002 already settled that Dossier consumes `doc-web` via tagged SemVer releases and contract tests, not by pulling codex-forge directly.
- **Existing patterns to reuse**: Story 152 contract outputs, Story 153 seam extraction notes, current Onward structural website outputs, and codex-forge's golden-build discipline.
- **Eval**: The deciding evidence is whether the proposed handoff contract is specific enough that a Dossier implementer could build the consumer without asking basic questions about files, fields, or versioning.

## Tasks

- [ ] Define the Dossier-facing `doc-web` handoff package:
  - bundle files
  - manifest expectations
  - provenance expectations
  - versioning expectations
- [ ] Define the first Dossier compatibility-test pack:
  - fixture inputs
  - expected bundle outputs
  - failure modes that should block upgrades
- [ ] Identify the first Dossier-side implementation slice required to consume `doc-web`
- [ ] Publish the handoff artifact where future Dossier work can reference it directly
- [ ] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [ ] Run required checks for touched scope:
  - [ ] If this remains docs-only, verify the referenced bundle/provenance fixtures and paths manually
  - [ ] If codex-forge code changes while tightening the handoff artifact, run `make test` and `make lint`
  - [ ] If pipeline behavior changes, clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and inspect the handoff bundle manually
  - [ ] If agent tooling changed: `make skills-check`
- [ ] If evals or goldens changed materially: run `/improve-eval` and update `docs/evals/registry.yaml`
- [ ] Search all docs and update any related to what we touched
- [ ] Verify Central Tenets:
  - [ ] T0 — Traceability: Dossier handoff preserves the provenance needed for exact citation and open-original behavior
  - [ ] T1 — AI-First: do not introduce unnecessary bespoke Dossier transforms if `doc-web` can own the clean contract directly
  - [ ] T2 — Eval Before Build: validate the handoff package against real bundle fixtures before external integration
  - [ ] T3 — Fidelity: handoff contract does not erase structure or location data for convenience
  - [ ] T4 — Modular: keep codex-forge, `doc-web`, and Dossier responsibilities explicit
  - [ ] T5 — Inspect Artifacts: manually inspect the fixture bundles and provenance maps used for handoff

## Workflow Gates

- [ ] Build complete: implementation finished, required checks run, and summary shared
- [ ] Validation complete or explicitly skipped by user
- [ ] Story marked done via `/mark-story-done`

## Architectural Fit

- **Owning module / area**: Handoff and contract-doc layer in codex-forge, with Dossier implementation deferred to the downstream repo.
- **Data contracts / schemas**: This story consumes the Story 152 contract and should not invent a parallel schema.
- **File sizes**: `README.md` is 72 lines, `docs/spec.md` is 194 lines, and `docs/build-map.md` is 457 lines. Prefer a dedicated handoff doc or note instead of bloating those files further.
- **Decision context**: ADR-002 is the authority. Story 152 defines the contract; Story 153 defines the extraction seam. This story should not reopen either decision.

## Files to Modify

- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/stories/story-154-dossier-doc-web-semantic-html-handoff.md — keep the handoff story current
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/notes/standalone-dossier-intake-runtime-plan.md — update the migration plan with the Dossier handoff package once defined
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/decisions/adr-002-doc-web-runtime-boundary/adr.md — only if the handoff contract reveals a true architectural change
- /Users/cam/.codex/worktrees/cdb6/codex-forge/README.md — only if the handoff expectations require a higher-level repo-role clarification (72 lines)

## Redundancy / Removal Targets

- Any vague doc text that says "Dossier will consume `doc-web`" without naming the expected bundle contract
- Any future ad hoc handoff notes that are not tied back to the accepted ADR and these stories

## Notes

- This story is still owned in codex-forge because the boundary needs to be published before the Dossier repo starts implementation.
- The Dossier-side code story should be created in Dossier after this handoff package exists.

## Plan

Pending — `/build-story` should decide whether this handoff should live as a dedicated note, a Dossier-consumer contract doc, or both.

## Work Log

20260318-2337 — story created: captured the Dossier-facing follow-up implied by ADR-002. The architecture is settled, but Dossier still needs a precise handoff package before anyone starts coding against the future `doc-web` runtime.
