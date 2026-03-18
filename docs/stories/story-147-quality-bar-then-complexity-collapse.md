# Story 147 — Quality Bar Then Complexity Collapse

**Priority**: High
**Status**: Done
**Ideal Refs**: Requirement #3 (Extract), Requirement #6 (Validate), Fidelity to the source, Transparency over magic, Graduate, don't accumulate
**Spec Refs**: `docs/spec.md` intro (compromises get deleted when resolved), spec:2.1 C1, spec:3.1 C3, spec:5.1 C7
**Decision Refs**: `docs/build-map.md`, `docs/spec.md`, `docs/ideal.md`, Story 145 work log, Story 146 work log, `docs/decisions/adr-001-source-aware-consistency-strategy/adr.md`
**Depends On**: Story 145, Story 146

## Goal

Turn the project instinct into an explicit operating rule: first push an active converter or repair seam to an acceptable manual-review quality bar, then open a simplification / complexity-collapse pass instead of indefinitely stacking more workaround logic. The story should place that mandate in the build map's operating-system layer, define what "acceptable quality" means in codex-forge terms, and use the Onward genealogy table path after Story 146 as the first concrete candidate for a collapse roadmap back toward the Ideal's simpler execution model.

## Acceptance Criteria

- [x] `docs/build-map.md` has an explicit cross-cutting operating rule under `Project Operating System` that says quality comes first, but once a converter reaches an acceptable reviewed bar the next planned step is simplification / complexity collapse rather than another unbounded layer of repair logic
- [x] The build-map rule defines an inspectable acceptable-quality bar in project terms: real `driver.py` validation, artifacts in `output/runs/`, manual inspection on the known hard cases, and no known reviewed defects in the active slice
- [x] The build map names the first tracked candidate for this rule, using the Onward scanned genealogy table path after Story 146 / `story146-onward-build-stitch-r5`, and records at least a first-pass inventory of likely collapse targets or simplification questions
- [x] The story and `docs/stories.md` make this mandate discoverable to future triage / align passes as a cross-cutting project direction rather than an Onward-only note
- [x] The story explicitly distinguishes "codify the mandate and candidate inventory" from "actually simplify the pipeline", so future implementation work can be scoped cleanly

## Out of Scope

- Deleting or refactoring existing rescue / rerun / build stages yet
- Claiming any compromise is already eliminated
- Rewriting `docs/spec.md` or the Ideal beyond what the current documents already say
- Reprioritizing unrelated input-format gaps such as born-digital PDF or handwriting intake

## Approach Evaluation

- **Simplification baseline**: There is no single-call model shortcut here; this is a cross-cutting workflow / roadmap clarification problem grounded in existing evidence, not a fuzzy generation problem.
- **AI-only**: An LLM could draft the mandate text or candidate inventory, but the authoritative output still has to be deterministic project docs tied to real runs and stories.
- **Hybrid**: Use AI to synthesize current workaround layers and collapse candidates from Story 146 / build-map evidence, then lock the result into docs with explicit human-verifiable references. This is the leading candidate because it keeps the rule grounded in actual artifacts.
- **Pure code**: Not applicable except for doc scaffolding and index updates.
- **Repo constraints / prior decisions**: `docs/spec.md` already says compromises are temporary and should be deleted when the detection signal says they are no longer needed; Story 145 made `docs/build-map.md` the human-readable project map; ADR-001 explicitly frames document-consistency planning as a compromise that should collapse away once stronger extraction makes it unnecessary.
- **Existing patterns to reuse**: `docs/build-map.md` Compromise Progress sections, Story 145's build-map convergence pattern, Story 146's work log and validated runs, and the existing `Next Actions` section for surfacing cross-cutting priorities.
- **Eval**: The deciding check is whether a future reader can open the build map and find: the mandate, the quality bar definition, the first candidate system, and the linked story. Validation is manual doc inspection plus link/index correctness rather than a model benchmark.

## Tasks

- [x] Add a `Project Operating System` subsection in `docs/build-map.md` that codifies the quality-bar-then-collapse rule and defines the acceptable-quality gate
- [x] Record the first tracked candidate in the build map using the Onward genealogy table path after Story 146, including the evidence run and first-pass collapse questions / likely deletion targets
- [x] Make the mandate discoverable in `docs/stories.md` and this story file so future triage / align passes can treat it as project direction rather than a buried work-log note
- [x] Decide whether the build map should also surface a reusable "collapse candidate" slot for other systems once they hit the same bar, and document that decision
- [x] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [x] Run required checks for touched scope:
  - [x] Docs/index hygiene: `git diff --check`
  - [x] Verify story numbering, story index row, and build-map references resolve correctly
  - [x] If implementation expands beyond docs into executable behavior, run the relevant `make test` / `make lint` / `driver.py` checks then (`N/A`; docs-only implementation)
- [x] If evals or goldens changed: update `docs/evals/registry.yaml` only if the implementation creates or changes a formal detection signal (`N/A`; no eval or golden changes)
- [x] Search all docs and update any related to what we touched
- [x] Verify Central Tenets:
  - [x] T0 — Traceability: the mandate points to real runs / stories instead of vague simplification aspirations
  - [x] T1 — AI-First: no code-heavy solution is invented for what is fundamentally a project-direction clarification
  - [x] T2 — Eval Before Build: the mandate is grounded in measured quality evidence, not intuition alone
  - [x] T3 — Fidelity: the rule preserves "quality first" instead of allowing premature simplification to reintroduce extraction defects
  - [x] T4 — Modular: simplification targets are named as collapse candidates, not hidden in ad hoc edits
  - [x] T5 — Inspect Artifacts: the first candidate is backed by manually reviewed artifacts, not just green logs

## Workflow Gates

- [x] Build complete: implementation finished, required checks run, and summary shared
- [x] Validation complete or explicitly skipped by user
- [x] Story marked done via `/mark-story-done` validation rerun

## Architectural Fit

- **Owning module / area**: `docs/build-map.md` under `Project Operating System`, with the story backlog as the execution surface
- **Data contracts / schemas**: No schema changes expected; this is documentation / roadmap work unless the eventual build opens a new machine-readable collapse-candidate inventory
- **File sizes**: `docs/build-map.md` is 380 lines, `docs/stories.md` is 170 lines, `docs/stories/story-147-quality-bar-then-complexity-collapse.md` is 96 lines; no size risk
- **Decision context**: Reviewed `docs/ideal.md`, `docs/spec.md`, `docs/build-map.md`, ADR-001, Story 145 context, and Story 146 evidence. No separate ADR currently owns this cross-cutting workflow rule; the build map is the right human-readable home unless future implementation reveals a harder-to-reverse governance decision.

## Files to Modify

- `docs/build-map.md` — add the quality-first then collapse mandate and first candidate placement (380 lines)
- `docs/stories.md` — add Story 147 index row (170 lines)
- `docs/stories/story-147-quality-bar-then-complexity-collapse.md` — flesh out the pending story (96 lines)

## Redundancy / Removal Targets

- Implicit "simplify later" guidance that currently lives only in story work logs
- Ad hoc future collapse decisions that would otherwise be invisible to build-map triage

## Notes

This is intentionally more than an Onward follow-up. The build-map mandate should apply to any compromise-bearing system: reach reviewed quality first, then deliberately collapse the workaround stack toward the Ideal's simpler shape instead of treating every successful workaround as permanent architecture.

## Plan

### Exploration Findings

- Story 147 is aligned with the Ideal and ADR-001. It closes a real execution-ideal gap by turning "simplify later" into an inspectable, evidence-backed collapse roadmap instead of letting workaround layers accumulate invisibly.
- Relevant decision docs reviewed: `docs/decisions/adr-001-source-aware-consistency-strategy/adr.md`, Story 145, and Story 146. No separate ADR currently owns this cross-cutting workflow rule; the build map remains the right home unless implementation reveals a harder-to-reverse governance change.
- The current repo baseline already satisfies part of the story:
  - `docs/build-map.md` already has the cross-cutting operating rule
  - the acceptable-quality bar is already defined there
  - the first tracked candidate is already named with evidence run `story146-onward-build-stitch-r5`
  - Story 147 is already discoverable in `docs/stories.md` and `docs/build-map.md` Next Actions
- The real remaining gap is narrower and more concrete than the original stub implied: the build map still lacks an explicit first-pass inventory of the active workaround stack for the Onward seam, and it does not yet record whether future collapse candidates should use a reusable mini-template or some other pattern.
- Active workaround stack identified during exploration of the current Onward seam:
  - story-scoped validation recipe `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml`
  - planner-aware rerun adapter `modules/adapter/rerun_onward_genealogy_consistency_v1/`
  - page-level deterministic normalization in `modules/adapter/table_rescue_onward_tables_v1/`
  - build-stage genealogy stitching and subgroup-row normalization in `modules/build/build_chapter_html_v1/`
- Files likely to change: this story file, `docs/build-map.md`, and `docs/stories.md`.
- Files at risk: `docs/build-map.md` can easily drift into vague strategy language or accidentally overclaim that C7 is already resolved; Story 146 evidence references must stay precise; `docs/stories.md` needs to remain status-consistent.
- Patterns to follow: Story 145's docs-first build-map convergence and Story 146's evidence-first work-log discipline.

### Eval / Baseline

- Deterministic success metric: a 6-point docs/readback checklist
  1. Operating rule present
  2. Acceptable-quality bar present
  3. Evidence-backed first candidate named
  4. Explicit first-pass collapse inventory present
  5. Discoverability in story index / build-map next actions
  6. Reusable future-candidate pattern decision documented
- Current baseline: `4/6` criteria are already present. Missing items are the explicit collapse inventory and the reusable-pattern decision.
- Approach comparison:
  - **AI-only**: draft the inventory from story logs alone. Fastest, but too likely to blur or invent the actual code seams.
  - **Hybrid**: inspect the docs plus the live recipe/modules behind Story 146, then write a grounded inventory and reusable-pattern decision. Recommended.
  - **Pure code**: not applicable beyond grep/readback verification.

### Recommended Implementation Shape

- Update the existing build-map operating-rule block with a compact `Collapse Candidate` mini-template for the first candidate only:
  - seam + evidence run
  - active workaround stack
  - candidate deletion / merge targets
  - proof needed before simplification
  - explicit non-goal: this does not claim the compromise is deleted
- Record the reusable-pattern decision in prose: do **not** add a standalone empty cross-project section yet. Reuse the same mini-template when another seam clears the quality bar. That keeps the build map browsable while still making the pattern explicit.
- Keep Story 147 docs-only. The next actual code simplification should be a separate follow-up story once the inventory is explicit.

### Task Plan

#### Task 1 — Normalize the story baseline and active state (`S`)

- **Files:** `docs/stories/story-147-quality-bar-then-complexity-collapse.md`, `docs/stories.md`
- **Change:** mark the story `In Progress`, record the corrected baseline, and make the remaining work explicit as inventory + reusable-pattern decision rather than re-adding the mandate text that already exists
- **Impact / risk:** without this, the story still reads like greenfield work and the eventual diff will look arbitrary
- **Done when:** the story file and index reflect the active build state and corrected remaining scope

#### Task 2 — Add the first-pass collapse inventory to the build map (`M`)

- **Files:** `docs/build-map.md`
- **Change:** under `Planning Infrastructure` / `Operating Rule`, add an explicit Onward collapse-candidate inventory naming the real layers introduced across Story 146's rerun / rescue / build seam
- **Impact / risk:** the main risk is overstating deletion readiness or burying the inventory inside too much prose
- **Done when:** a reader can open the build map and see real deletion / merge targets plus the evidence still needed before simplification

#### Task 3 — Record the reusable future-candidate pattern decision (`S`)

- **Files:** `docs/build-map.md`, `docs/stories/story-147-quality-bar-then-complexity-collapse.md`
- **Change:** explicitly decide whether to add a reusable collapse-candidate slot now; recommended answer is "use the same mini-template when another candidate exists, but do not add an empty section yet"
- **Impact / risk:** premature templating bloats the build map, but leaving the decision implicit forces future triage passes to rediscover the pattern
- **Done when:** the decision is explicit and future stories know how to surface the next candidate

#### Task 4 — Verify the docs/readback bundle before closure (`S`)

- **Files:** `docs/build-map.md`, `docs/stories/story-147-quality-bar-then-complexity-collapse.md`, `docs/stories.md`
- **Change:** run `git diff --check` and manual readback against the 6-point checklist; only mark the story `Done` if the inventory and reusable-pattern decision are both genuinely present
- **Impact / risk:** the story could otherwise be closed just because the mandate already exists, even though the actual collapse roadmap does not
- **Done when:** the checklist reaches `6/6` and the closeout can point to exact doc locations

### Scope Adjustments Folded Into This Build

- Scope correction, not expansion: the mandate itself is already implemented, so this build focuses on the missing collapse roadmap and reusable-pattern decision.
- No code simplification, schema change, or C7-deletion claim is part of Story 147.

### Human-Approval Blockers

- No new dependency is expected.
- No schema or pipeline change is expected.
- Main decision to confirm before implementation:
  - **Recommended:** keep Story 147 docs-only and treat the next actual code simplification as a follow-up story once the inventory is explicit.
  - **Not recommended:** start deleting / merging Onward modules inside Story 147.
- Relative effort: `S`

### Done Criteria

- Story 147 is done only when the build map explicitly names the Onward workaround stack and candidate deletion / merge targets, the reusable-pattern decision is documented, the docs/readback checklist is `6/6`, and the story remains clearly separated from any actual pipeline simplification follow-up.

## Work Log

20260316-1110 — story created: promoted the user's "quality first, then simplify" direction into a pending cross-cutting story instead of burying it in Story 146 notes; evidence is `docs/spec.md`'s compromise-deletion rule, Story 145's build-map convergence, and Story 146's manually accepted `story146-onward-build-stitch-r5` baseline; next step is to place the mandate explicitly in `docs/build-map.md` under `Project Operating System`
20260316-1123 — mandate placed: added the operating rule to `docs/build-map.md` under `Project Operating System`, named the Onward genealogy scanned-table path as the first tracked collapse candidate, surfaced "Build Story 147" in `Next Actions`, and added the story row to `docs/stories.md`; evidence is the new build-map subsection plus the Story 147 index row; next step is `/build-story 147` when we want to turn the mandate into a concrete collapse roadmap
20260318-0711 — build-story exploration: promoted Story 147 to active work after verifying it was fully specified and still the top next action; reviewed `docs/ideal.md`, `docs/spec.md`, `docs/build-map.md`, ADR-001, Story 145, Story 146, the live Story 146 validation recipe, and the current Onward rerun/rescue/build modules; confirmed the mandate, acceptable-quality bar, first candidate, and discoverability are already landed (`4/6` baseline criteria satisfied), so the real remaining work is to document the active workaround stack plus candidate deletion / merge targets and to decide whether future collapse candidates should use a reusable mini-template; files likely to change are `docs/build-map.md`, `docs/stories/story-147-quality-bar-then-complexity-collapse.md`, and `docs/stories.md`; main risk is overstating that C7 is resolved instead of documenting a collapse roadmap; next step is the written approval-gate plan before any implementation edits beyond story tracking
20260318-0718 — docs implementation and closeout: expanded `docs/build-map.md` so the Onward candidate now records the evidence run, active workaround stack, candidate deletion / merge targets, proof needed before simplification, explicit non-goal, and reusable-pattern decision; replaced the stale build-map next action "Build Story 147" with the actual follow-up to create the Onward collapse implementation story; verified `git diff --check` passes and manually re-read the touched docs against the story's 6-point checklist (`6/6`: rule present, acceptable-quality bar present, candidate named, collapse inventory present, discoverability preserved via `docs/stories.md` + build-map cross-reference, reusable future-candidate pattern decision documented); no new dependency, schema change, or eval update was required; next step is to create the Onward scanned-genealogy collapse implementation story from the documented inventory rather than adding more opportunistic repair logic to Story 147
20260318-0825 — mark-story-done validation rerun: re-ran the required close-out checks in this worktree with `python -m pytest tests/` and `python -m ruff check modules/ tests/`; both passed (`619 passed, 6 skipped`; Ruff clean); re-checked Story 147 against the shipped docs-only slice in `docs/build-map.md`, `docs/stories.md`, and this story file; dependencies Story 145 and Story 146 remain `Done`, all task / acceptance-criteria / tenet checkboxes remain satisfied, no pipeline-module or eval-registry changes were required, and the close-out now matches the standard `/mark-story-done` path rather than the earlier equivalent manual closeout wording
