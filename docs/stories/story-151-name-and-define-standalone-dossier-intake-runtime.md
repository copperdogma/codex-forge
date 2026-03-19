# Story 151 — Define `doc-web` as the Standalone Dossier Intake Runtime

**Priority**: High
**Status**: Pending
**Ideal Refs**: Requirement #5 (Structure), Requirement #6 (Validate), Requirement #7 (Export), Traceability is the Product, Dossier-ready output, Graduate, don't accumulate
**Spec Refs**: spec:5.1 C7 (Page-Scope Extraction with Document-Level Consistency Planning), spec:6 (Validation, Provenance & Export), spec:7 (Graduation & Dossier Handoff)
**Decision Refs**: `README.md`, `docs/ideal.md`, `docs/spec.md`, `docs/build-map.md`, `docs/pipeline/ff-specificity-audit.md`, `docs/decisions/adr-002-doc-web-runtime-boundary/adr.md`
**Depends On**: None

## Goal

Codex-forge is no longer the right place to grow a polished website layer, but the current Onward HTML path has clarified what the reusable runtime really is: a provenance-first semantic HTML bundle with minimal machine-useful navigation, not just "plain HTML." This story defines `doc-web` as the extracted runtime that Dossier should consume and records the migration boundary so future work stops oscillating between "pull in codex-forge" and "rewrite it in Dossier." The result should be a build-ready decision package covering repo boundary, artifact contract, provenance requirements, release model, and the follow-up implementation slices needed to replace codex-forge's current role.

## Acceptance Criteria

- [ ] A new ADR or equivalent decision record names `doc-web` as the extracted runtime, explains why it should be a separate runtime repo instead of `codex-forge`-as-dependency or a direct one-off Dossier port, and lists the rename/update surfaces that follow from that choice.
- [ ] The current codex-forge surface is inventoried into `migrate as-is`, `refactor before migrate`, `leave behind`, and `archive only`, with exact modules, schemas, recipes, fixtures, and docs called out.
- [ ] The output contract is specified precisely enough for Dossier and Storybook citation needs: semantic HTML bundle, minimal TOC/prev-next navigation, stable DOM or block IDs, document/chapter manifests, and block-level provenance back to the original uploaded artifact page and source element.
- [ ] The Dossier integration contract is specified: dependency/versioning model, HTML-only stop point, and how downstream consumers resolve citations back to the original artifact.
- [ ] Concrete follow-up implementation slices are identified for:
  - runtime repo bootstrap/extraction
  - provenance contract upgrades that the current `chapter_html_manifest_v1` does not yet cover
  - Dossier integration
  - separate website-builder consumer

## Out of Scope

- Implementing the new runtime repo
- Moving code into Dossier or changing Dossier code directly
- Building the polished Onward website
- Reopening settled Onward extraction-quality work unless current artifacts prove the contract itself is insufficient
- Legal or trademark clearance for the final product name beyond choosing a practical working name and shortlist

## Approach Evaluation

- **Simplification baseline**: First prove whether the current Onward semantic HTML output plus manifest already satisfy Dossier's needs with only a thin adapter. If the existing bundle already carries enough navigation and provenance, the "new runtime" may just be a packaging and contract extraction exercise, not a format redesign.
- **AI-only**: A single LLM pass can draft a keep/drop inventory and generate candidate names, but it cannot authoritatively choose the runtime boundary without checking real modules, schemas, recipes, and output artifacts. Useful for synthesis, insufficient as sole evidence.
- **Hybrid**: Inspect the current reusable path and artifact surfaces, then use AI to synthesize the runtime boundary, naming shortlist, and migration plan. This is the leading candidate because the decision is architectural and evidence-heavy, not a pure coding exercise.
- **Pure code**: Either pull `codex-forge` into Dossier wholesale or immediately fork/copy code into a new repo without defining the contract first. Fastest mechanically, but likely to drag along FF-specific baggage or freeze the wrong provenance boundary.
- **Repo constraints / prior decisions**: `README.md` now states that codex-forge stops at semantic HTML and that the Dossier stop-point should be "ingest to semantic HTML" before downstream semantic processing. `docs/spec.md` and `docs/build-map.md` already frame graduation into Dossier as the mission, while `docs/pipeline/ff-specificity-audit.md` shows which logic is clearly generic versus FF-specific and should not be carried forward blindly. No existing ADR currently defines the extracted runtime boundary or name.
- **Existing patterns to reuse**: `schemas.py` (`UnstructuredElement`, `CodexMetadata`), `modules/build/build_chapter_html_v1`, `configs/recipes/recipe-onward-images-html-mvp.yaml`, `docs/pipeline/ff-specificity-audit.md`, and the recent docs changes that reclassified in-repo website generation out of scope.
- **Eval**: The deciding evidence is a concrete module and artifact inventory plus manual inspection of the current Onward HTML and manifest outputs to determine whether the existing contract already carries enough machine-useful navigation and whether provenance is still too coarse for Storybook-style citations. No promptfoo eval is expected for this planning story.

## Tasks

- [ ] Create the missing ADR for the standalone runtime boundary:
  - separate repo vs direct Dossier ownership vs `codex-forge` dependency
  - what stays in-scope for the runtime contract
  - what stays out of scope
  - release/update model
- [ ] Document the chosen runtime name (`doc-web`):
  - record why the name fits the scope better than the alternatives considered
  - identify rename/update surfaces inside codex-forge docs
  - note any obvious collision or packaging checks to confirm before implementation
- [ ] Inspect the current semantic HTML outputs and manifests and define the Dossier-facing bundle contract:
  - semantic HTML files
  - minimal TOC and prev/next navigation
  - stable block IDs
  - document/chapter manifests
  - block-level provenance requirements back to the original artifact
- [ ] Produce the extraction inventory for the current repo:
  - migrate as-is
  - refactor before migrate
  - leave behind
  - archive only
- [ ] Define the Dossier integration surface:
  - versioning and release flow
  - dependency mechanism
  - `semantic_html` stop-point contract
  - citation/open-original expectations
- [ ] Split follow-up implementation work into coherent next stories or milestones so the migration does not happen as an unbounded repo fork
- [ ] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [ ] Run required checks for touched scope:
  - [ ] If this remains docs/ADR-only, verify story index consistency, markdown links, and that the referenced artifact paths actually exist
  - [ ] If code prototypes or schema changes are introduced while scoping the runtime, run `make test` and `make lint`
  - [ ] If pipeline behavior changes during scope expansion, clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and manually inspect the semantic HTML plus provenance outputs
  - [ ] If agent tooling changed: `make skills-check`
- [ ] If evals or goldens changed materially while defining the contract, run `/improve-eval` and update `docs/evals/registry.yaml`
- [ ] Search all docs and update any related to what we touched
- [ ] Verify Central Tenets:
  - [ ] T0 — Traceability: the new runtime contract preserves source artifact, page, and element-level provenance instead of collapsing to chapter-only metadata
  - [ ] T1 — AI-First: prefer proving current HTML output usefulness before inventing extra deterministic layers
  - [ ] T2 — Eval Before Build: compare repo-boundary options and artifact sufficiency before moving code
  - [ ] T3 — Fidelity: keep semantic structure and machine-useful nav without smuggling in presentation-only website concerns
  - [ ] T4 — Modular: extract the reusable intake path without dragging along FF/gamebook or story-system baggage
  - [ ] T5 — Inspect Artifacts: inspect real HTML and manifest artifacts, not just module descriptions

## Workflow Gates

- [ ] Build complete: implementation finished, required checks run, and summary shared
- [ ] Validation complete or explicitly skipped by user
- [ ] Story marked done via `/mark-story-done`

## Architectural Fit

- **Owning module / area**: This is primarily a docs/decision-layer story. The owning surfaces are `README.md`, `docs/spec.md`, `docs/build-map.md`, `docs/pipeline/ff-specificity-audit.md`, and a new ADR or planning note. The main runtime references to inspect are `schemas.py`, `modules/build/build_chapter_html_v1`, and `configs/recipes/recipe-onward-images-html-mvp.yaml`.
- **Data contracts / schemas**: The story should decide whether the current `chapter_html_manifest_v1` is sufficient or whether the extracted runtime needs a stricter `document_manifest` and `provenance_map` contract with block-level references. Any cross-artifact fields approved for implementation later must be added to `schemas.py` before code emits them.
- **File sizes**: `README.md` is 72 lines, `docs/spec.md` is 194 lines, `docs/build-map.md` is 457 lines, and `docs/pipeline/ff-specificity-audit.md` is 144 lines. The likely ADR and planning note are new files. This story should stay docs-sized; if implementation pressure starts touching large runtime files directly, split a follow-up.
- **Decision context**: Reviewed `docs/ideal.md`, `README.md`, `docs/spec.md`, `docs/build-map.md`, and `docs/pipeline/ff-specificity-audit.md`. No prior ADR defining the extracted runtime boundary or naming was found in `docs/decisions/`, which is why this story should create one before implementation begins.

## Files to Modify

- /Users/cam/.codex/worktrees/cdb6/codex-forge/README.md — codify the named standalone runtime and its handoff relationship to codex-forge and Dossier (72 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/spec.md — tighten the semantic HTML/provenance handoff language if the story finds current wording too loose (194 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/build-map.md — add the named graduation target and any clarified handoff expectations (457 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/pipeline/ff-specificity-audit.md — use the existing audit to anchor the migrate/refactor/leave-behind inventory (144 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/decisions/adr-002-doc-web-runtime-boundary/adr.md — accepted ADR for the name and repo boundary
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/notes/standalone-dossier-intake-runtime-plan.md — new extraction inventory and follow-up migration plan (new file)

## Redundancy / Removal Targets

- Any lingering documentation that implies the next codex-forge milestone is an in-repo website builder
- Any assumption that Dossier should depend directly on the whole `codex-forge` repo
- Any future "plain HTML" wording that omits minimal navigation and provenance from the reusable contract
- Long-term: codex-forge runtime docs that become redundant once the extracted runtime repo becomes the source of truth

## Notes

- Final runtime name selected by user: `doc-web`.
- The name implies the runtime outputs a structural, navigable document website, not merely isolated HTML fragments. The ADR still needs to lock the exact boundary between structural website output and later presentation polish.
- The current `build_chapter_html_v1` nav shell is not automatically "presentation-only." Minimal TOC and prev/next links may be part of the semantic runtime contract if they materially help Dossier reason across document pages or chapters.
- The likely risk surface is provenance granularity. The existing manifest appears chapter-oriented; Storybook-style click-through citations may require block-level or DOM-node-level provenance sidecars instead of only `source_pages`.

## Plan

Pending — `/build-story` should first decide whether the extracted runtime can extend the current HTML bundle and manifest with a stricter provenance sidecar, or whether the contract needs a new bundle schema from scratch. The implementation order should be: ADR and name, artifact inspection, extraction inventory, Dossier integration surface, then follow-up implementation slices.

## Work Log

20260318-2246 — story created: captured the priority pivot away from an in-repo website builder toward a named standalone Dossier intake runtime with semantic HTML, minimal navigation, and provenance as the contract. Evidence: `README.md` now states codex-forge stops at semantic HTML, `modules/build/build_chapter_html_v1` already emits nav and chapter-manifest fields, and no ADR currently defines the extracted runtime boundary or name. Next step: `/build-story` should create the ADR, choose the working name, inspect current HTML/manifest artifacts, and classify migrate vs refactor vs leave-behind surfaces.
20260318-2255 — naming decision captured: user selected `doc-web` as the final runtime name. Updated the story title, goal, acceptance criteria, and notes so the forthcoming ADR treats naming as settled and focuses on boundary, contract, and migration decisions.
20260318-2300 — ADR cross-link added: created `docs/decisions/adr-002-doc-web-runtime-boundary/adr.md` plus the ADR-local research prompt and linked Story 151 to that decision path. Next step: run the ADR research pass, then use the result to decide repo ownership, bundle contract, and migration slices.
20260318-2308 — research scaffolding prepared: added ADR-local provider report stubs (`openai`, `gemini`, `opus`, `xai`) and wired the synthesis file to those sources. This reduces setup friction for the next step, which is the actual multi-provider research pass on ownership model, bundle contract, provenance granularity, and Dossier integration.
20260318-2329 — multi-provider synthesis landed: xAI and Opus manual reports plus OpenAI and Gemini automated runs now converge on the same core direction. `doc-web` should be a standalone runtime, not a `codex-forge` dependency; its contract should be a structural website bundle with stronger block-level provenance; and extraction should start with the bundle-emission seam rather than a big-bang repo move. The remaining practical decision is packaging intensity on day one, with the synthesis recommending tagged SemVer releases plus contract tests before adding private registry infrastructure.
20260318-2337 — direction accepted and propagated: user approved the synthesized direction, ADR-002 moved to `ACCEPTED`, core docs now name `doc-web` as the graduation target, the extraction inventory note was added, and follow-up stories 152-154 were created. Remaining work is implementation and handoff, not architecture.
