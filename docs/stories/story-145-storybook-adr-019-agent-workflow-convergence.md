# Story 145 — Storybook ADR-019 Agent Workflow Convergence

**Priority**: High
**Status**: Done
**Ideal Refs**: Requirement #6 (Validate), Transparency over Magic, Graduate, Don't Accumulate
**Spec Refs**: Active Compromises C1-C7 (detection + deletion workflow), especially the Detection / When it resolves clauses and Compromise-Level Preferences
**Decision Refs**: Storybook ADR-019 migration guide (sibling `storybook` repo), `docs/scout/scout-004-dossier-triage-skills.md`, `docs/scout/scout-006-storybook-adr-skills.md`, `docs/scout/scout-007-storybook-adr-followups.md`, `docs/runbooks/adr-creation.md`, `docs/runbooks/deep-research.md`
**Depends On**: None

## Goal

Converge codex-forge's agent-management surface with Storybook's post-ADR-019 workflow, but adapt it to codex-forge's actual scope instead of cargo-culting Storybook's structure. The main work is to normalize a currently drifted state: `reflect` is still the live command, `align/` exists only as an empty stub, `verify-eval` still exists separately, the Storybook-style `/triage` orchestration has not been adopted, and codex-forge still lacks the central `docs/build-map.md` surface that should tie systems, dependencies, story coverage, and compromise progress together. This story should leave one coherent skill/doc/wrapper surface, create and fill a codex-forge-specific build map, and make any intentional deferrals unmistakable.

## Acceptance Criteria

- [x] `docs/build-map.md` exists and is filled with codex-forge-specific system structure, dependency order, story coverage, and compromise progress sourced from current repo docs rather than copied verbatim from Storybook
- [x] `docs/build-map.md` has been content-reviewed after drafting: system summaries, dependencies, story coverage boxes, ADR refs, compromise progress, latest eval data, and optimize/eliminate notes all match codex-forge's current state
- [x] The capability / graduation / gap-tracking content currently owned by `docs/format-registry.md` is subsumed into `docs/build-map.md` in a way that keeps the build map browsable and coherent
- [x] Active guidance that currently points at `docs/format-registry.md` is retargeted to `docs/build-map.md` or the relevant build-map section, and `docs/format-registry.md` is removed once nothing active depends on it
- [x] `.agents/skills/align/SKILL.md` exists as the canonical advisory/alignment skill, live `/reflect` guidance is removed from active docs and wrappers, and `align` treats `docs/build-map.md` as a first-class methodology input
- [x] `.agents/skills/improve-eval/SKILL.md` absorbs the failure-classification / golden-verification workflow now split into `/verify-eval`, and the standalone `.agents/skills/verify-eval/` skill plus `.gemini/commands/verify-eval.toml` are removed
- [x] Codex-forge adopted the full triage convergence shape in this story: `/triage` plus its required leaf skills/wrappers landed, with full-sweep mode read-only and leaf ownership preserved
- [x] `AGENTS.md`, relevant runbooks, relevant skill docs, the story template, and build-map-aware skills now describe the post-migration workflow rather than the pre-migration command set
- [x] `docs/evals/registry.yaml` now documents the derived triage taxonomy in header comments without adding a new schema field
- [x] `scripts/sync-agent-skills.sh`, `scripts/sync-agent-skills.sh --check`, and `make skills-check` pass after the migration
- [x] Verification greps show no active `/reflect` or standalone `verify-eval` guidance remaining, and active build-map references point at `docs/build-map.md` rather than a missing or Storybook-specific surface

## Out of Scope

- Changing pipeline modules, recipes, schemas, or run artifacts in `output/runs/`
- Rewriting historical CHANGELOG entries, completed story work logs, or scout notes solely to remove legacy command names
- Migrating Dossier- or CineForge-specific management surfaces that do not exist in codex-forge
- Rewriting historical story work-log references to `docs/format-registry.md` when they are only evidence of past work rather than active guidance

## Migration Matrix

| Workstream | Storybook end state | Codex-forge current state | Adaptation required |
|---|---|---|---|
| Advisory impact skill | `align` is the canonical post-change methodology sweep | Live `reflect` skill and wrapper still exist; `.agents/skills/align/` exists only as an empty directory; active `/reflect` refs remain in `create-adr`, `adr-creation.md`, `deep-research.md`, and `docs/decisions/README.md` | Populate `align`, retire `reflect`, rename/regenerate wrappers, and make `align` use `docs/build-map.md` as a first-class input |
| Eval failure classification | `improve-eval` owns classification / verification; `verify-eval` is gone | `verify-eval` still exists separately; `improve-eval` still tells users to invoke `/verify-eval`; live refs remain in the create-story skill/template and eval runbooks | Fold failure classification into `improve-eval`, delete the separate skill and wrapper, and sweep all active references |
| Build-map convergence tracking | Storybook uses `docs/build-map.md` as a core methodology surface | Codex-forge has neither `build-map.md` nor `feature-map.md`; adjacent structure lives in `docs/spec.md`, `docs/format-registry.md`, `docs/stories.md`, and scattered runbooks/scouts | Create `docs/build-map.md` from scratch, using Storybook's structure as the template but codex-forge's docs as the source data |
| Build-map source ownership | Storybook absorbed some adjacent capability-tracking docs into the build map | Codex-forge already has `docs/format-registry.md` covering format capability, graduation status, and prioritized gaps, with active references in `AGENTS.md`, `format-gap-analysis`, and `reflect` | Subsumed fully: migrate the live content into `docs/build-map.md`, update active references, and remove `docs/format-registry.md` once the build map becomes the source of truth |
| Triage architecture | `/triage` orchestrates read-only full sweeps across leaf skills | Codex-forge has `triage-inbox` and `triage-stories`, but no `/triage`, no `triage-evals`, and no Gemini wrappers for them | Decide whether to adopt `/triage` now or document a deliberate defer; if adopted, preserve leaf ownership and keep full-sweep mode read-only |
| Eval-registry prioritization taxonomy | Registry header documents eval classes for triage/rerun prioritization | `docs/evals/registry.yaml` documents `type`, score fields, and `retry_when`, but not the Storybook class taxonomy | Add the taxonomy if it materially supports triage-evals / convergence tracking; otherwise document why it is not needed here |
| Skill creation scaffolding | `create-cross-cli-skill` enforces the alignment-check rule | Local `create-cross-cli-skill` already has Rule 2 for the alignment blockquote | Verify parity; only change if Storybook's newer wording adds missing nuance |
| Wrapper and orientation sync | Storybook docs and wrappers all point at the canonical commands and the build map | No `.gemini/commands/align.toml`; no `.gemini/commands/triage.toml`; stale `reflect.toml` and `verify-eval.toml` still exist; live docs still point at old commands and there is no local build-map surface to reference | Regenerate wrappers, re-read AGENTS/runbooks/templates after migration, and update active guidance to point at `docs/build-map.md` where appropriate |

## Approach Evaluation

- **Simplification baseline**: Start with a strict adopt/adapt/skip pass against the Storybook ADR-019 migration guide before editing anything. Current repo evidence already shows the important gaps: empty `.agents/skills/align/`, live `/reflect` refs, a separate `/verify-eval`, no `/triage`, and no build-map surface.
- **AI-only**: Bulk-copy Storybook skills and docs, then rename a few paths. Fastest to type, but high risk because Storybook assumes `build-map.md`, triage-evals infrastructure, and a different repo surface.
- **Hybrid**: Use Storybook's `build-map`, `align`, `triage`, and `improve-eval` as reference targets, but apply them through codex-forge-specific diffs driven by grep/readback evidence. This is the likely winning path because the work is mostly doc/skill convergence with one new central doc assembled from existing local sources.
- **Pure code**: Manual rename/merge of local skills, wrappers, and runbooks without consulting Storybook. Safe for plumbing, but weaker on behavior parity and likely to miss the triage-orchestration shape or failure-classification details.
- **Repo constraints / prior decisions**: Scout 006 and Scout 007 previously skipped Storybook-only `feature-map` / `build-map` surfaces, but this story intentionally re-opens that decision based on current user direction. Agent-tooling changes must still pass `make skills-check`, and the build map should be filled from codex-forge's real docs rather than invented structure.
- **Existing patterns to reuse**: Existing `triage-inbox` and `triage-stories` leaf skills, `scripts/sync-agent-skills.sh`, the current `create-cross-cli-skill` Rule 2 alignment block, the Storybook reference `build-map` / `align` / `triage` / `improve-eval` skills, and codex-forge's current `docs/format-registry.md` as source material to be absorbed into the new build map.
- **Eval**: No model eval is needed. Success is distinguished by grep-based drift detection, wrapper sync, `make skills-check`, and manual readback of the post-migration skill surface.

## Tasks

- [x] Baseline the migration against current repo state and the Storybook ADR-019 reference surface before editing local files
- [x] Create and manually review `docs/build-map.md`, then absorb the former human-readable format registry into it
- [x] Refresh `tests/fixtures/formats/_coverage-matrix.json` so the machine-readable coverage inventory matches the new build map and current eval/provenance truth
- [x] Retarget active guidance from the removed format-registry surface to `docs/build-map.md`, then delete `docs/format-registry.md`
- [x] Replace `reflect` with `align` across skills, runbooks, docs, and generated Gemini wrappers
- [x] Merge the standalone eval-verification workflow into `improve-eval`, remove `verify-eval`, and retarget future story scaffolding to the merged flow
- [x] Adopt the full `/triage` architecture now: add `/triage` and `/triage-evals`, update `/triage-inbox` for `scan` mode, and make `/triage-stories` build-map aware
- [x] Update AGENTS, create-adr, create-cross-cli-skill, create-story, format-gap-analysis, and registry taxonomy comments to match the converged workflow
- [x] Sync generated Gemini wrappers and verify the new `align`, `triage`, and `triage-evals` wrappers exist while `reflect` / `verify-eval` wrappers are removed
- [x] Run required checks for touched scope: `scripts/sync-agent-skills.sh`, `scripts/sync-agent-skills.sh --check`, `make skills-check`, `make lint`, and `make test`
- [x] Verify migration greps and classify remaining hits as historical-only where appropriate; no active guidance in AGENTS, build-map, runbooks, decisions, or skills still points at `reflect`, standalone `verify-eval`, `format-registry`, or worktree-local paths
- [x] Search related docs and update all live surfaces touched by the migration
- [x] Verify Central Tenets:
  - [x] T0 — Traceability preserved; no pipeline artifact contract or provenance surface was loosened
  - [x] T1 — AI-First respected; this was a workflow/doc/skill convergence task, not a place to replace AI reasoning with code
  - [x] T2 — Eval Before Build respected; the story used grep/readback and existing eval signals as the verification baseline instead of inventing new logic blindly
  - [x] T3 — Fidelity preserved; no pipeline content path was changed and no source-preservation guarantees were weakened
  - [x] T4 — Modular preserved; the change converged reusable skills/wrappers rather than adding product-specific one-offs
  - [x] T5 — Inspect Artifacts satisfied by manual readback of `docs/build-map.md`, the refreshed coverage matrix, and generated Gemini wrappers

## Workflow Gates

- [x] Build complete: migration workstreams are applied, required checks are run, and the post-migration command surface is summarized in the work log
- [x] Validation complete in this build-story pass
- [x] Story marked done via manual closeout in this build-story pass

## Architectural Fit

- **Owning module / area**: `.agents/skills/`, `.gemini/commands/`, `AGENTS.md`, `docs/build-map.md`, `docs/runbooks/`, and `docs/evals/registry.yaml`
- **Data contracts / schemas**: No pipeline schema changes are expected. The real contracts here are skill names, generated Gemini wrappers, and the human-facing workflow documented in AGENTS/runbooks/templates.
- **File sizes**: Largest likely touches are `docs/evals/registry.yaml` (436 lines), `AGENTS.md` (398), `docs/runbooks/deep-research.md` (163), `docs/runbooks/adr-creation.md` (156), `.agents/skills/verify-eval/SKILL.md` (152), `.agents/skills/improve-eval/SKILL.md` (124), `.agents/skills/format-gap-analysis/SKILL.md` (122), and `.agents/skills/reflect/SKILL.md` (116). `docs/build-map.md` will be a new file and should stay intentionally browsable, not a dumping ground.
- **Decision context**: Reviewed the Storybook ADR-019 migration guide and Storybook `docs/build-map.md` plus local Scouts 004, 006, and 007 and `docs/format-registry.md`. No codex-forge ADR specifically defines the `/triage` orchestration shape yet; if build work exposes a hard-to-reverse workflow decision, create or update an ADR instead of burying it in skill text.

## Files to Modify

- `AGENTS.md` — update the documented skill/workflow surface if command names or triage architecture change (398 lines)
- `docs/build-map.md` — create the codex-forge build map and fill it with system structure + compromise progress (new file)
- `docs/format-registry.md` — remove after its live content is absorbed into `docs/build-map.md` (140 lines)
- `tests/fixtures/formats/_coverage-matrix.json` — refresh machine-readable coverage to match the new build map and current eval/provenance truth (157 lines)
- `.agents/skills/align/SKILL.md` — populate the currently empty directory with the canonical alignment skill (new file)
- `.agents/skills/reflect/SKILL.md` — remove after migration to `align` completes (116 lines)
- `.agents/skills/format-gap-analysis/SKILL.md` — retarget active references from `docs/format-registry.md` to `docs/build-map.md` (107 lines)
- `.agents/skills/improve-eval/SKILL.md` — absorb the standalone verification/classification workflow (124 lines)
- `.agents/skills/verify-eval/SKILL.md` — remove after the merge (152 lines)
- `.agents/skills/triage/SKILL.md` — add the orchestrator if this story adopts the full triage architecture (new file)
- `.agents/skills/triage-evals/SKILL.md` — add the eval leaf if this story adopts it (new file)
- `.agents/skills/triage-inbox/SKILL.md` — add orchestration-safe read-only behavior if needed (66 lines)
- `.agents/skills/triage-stories/SKILL.md` — add codex-forge-specific convergence scoring / routing language if needed (67 lines)
- `.agents/skills/create-story/SKILL.md` — replace `/verify-eval` references in the story-creation guidance (89 lines)
- `.agents/skills/create-story/templates/story.md` — replace `/verify-eval` in the default checklist text (88 lines)
- `.agents/skills/create-adr/SKILL.md` — route post-decision follow-up to `/align` instead of `/reflect` (79 lines)
- `.agents/skills/create-cross-cli-skill/SKILL.md` — verify parity with Storybook's alignment-check rule and adjust only if needed (40 lines)
- `.gemini/commands/reflect.toml` — remove/rename as part of the `align` migration (8 lines)
- `.gemini/commands/align.toml` — generated wrapper after sync
- `.gemini/commands/verify-eval.toml` — remove after merge (8 lines)
- `.gemini/commands/improve-eval.toml` — regenerated wrapper after the merge (8 lines)
- `.gemini/commands/triage.toml` — generated wrapper after triage adoption
- `.gemini/commands/triage-evals.toml` — generated wrapper after triage adoption
- `docs/runbooks/adr-creation.md` — update post-decision guidance to `/align` (156 lines)
- `docs/runbooks/deep-research.md` — update follow-up guidance to `/align` (163 lines)
- `docs/runbooks/golden-build.md` — migrate live eval-verification guidance to the merged `/improve-eval` flow (52 lines)
- `docs/runbooks/crop-eval-workflow.md` — migrate live eval-verification guidance to the merged `/improve-eval` flow (58 lines)
- `docs/decisions/README.md` — update the post-ADR follow-up command reference (37 lines)
- `docs/evals/registry.yaml` — add eval-class taxonomy comments if the adopted workflow benefits from them (436 lines)

## Redundancy / Removal Targets

- `.agents/skills/reflect/` and `.gemini/commands/reflect.toml`
- `.agents/skills/verify-eval/` and `.gemini/commands/verify-eval.toml`
- The empty `.agents/skills/align/` stub directory state
- Any stale "codex-forge has no build-map" guidance in active docs or skill text
- `docs/format-registry.md` once its live content is subsumed into `docs/build-map.md`
- Any duplicated system/progress tracking that should live in `docs/build-map.md` rather than being re-explained elsewhere
- Any duplicate failure-classification guidance that survives in both `improve-eval` and runbooks
- Any active `/reflect` or `/verify-eval` references left outside historical story/scout context

## Notes

### Verification Greps

- `rg -l 'verify-eval' .agents/ docs AGENTS.md -g'*.md'`
- `rg -l '/reflect' .agents/ docs AGENTS.md -g'*.md'`
- `rg -l 'feature-map\\.md|build-map\\.md' .agents/ docs AGENTS.md -g'*.md'`
- `rg -n '/Users/.+/.codex/worktrees/' .agents/ docs -g'*.md'`

### Resolved Decisions

- `docs/build-map.md` became the single human-readable convergence surface and now owns the former format-registry content.
- Codex-forge adopted the full Storybook-style `/triage` + leaf architecture in this story, with read-only full-sweep orchestration.
- `docs/evals/registry.yaml` keeps its coarse `type` field; the triage taxonomy is documented in header comments instead of adding a new stored field.
- No new ADR was required; this stayed within skill/runbook/build-map convergence rather than introducing a hard-to-reverse product architecture decision.

## Plan

### Baseline / Success Metric

- Use a structural verification bundle rather than a model-quality eval. This story is docs/skill/workflow convergence, not pipeline behavior.
- Current baseline:
  - `docs/build-map.md`: missing
  - `.agents/skills/align/`: empty directory, no `SKILL.md`
  - active `/reflect` guidance hits: `8`
  - active `verify-eval` guidance hits: `8`
  - active `docs/format-registry.md` guidance hits: `6`
  - `.gemini/commands/align.toml`: missing
  - `.gemini/commands/triage.toml`: missing
  - `scripts/sync-agent-skills.sh --check`: passes
  - `make skills-check`: passes
- "Done" for this story means the same bundle shows the drift is resolved, not just that files were edited.

### Task 1 — Create `docs/build-map.md` and absorb `docs/format-registry.md` (`M`)

- **Files**: `docs/build-map.md` (new), `docs/format-registry.md` (remove), `AGENTS.md`, `.agents/skills/format-gap-analysis/SKILL.md`, and any build-map-aware advisory skills.
- **Order**:
  1. Draft a dependency-ordered build-map skeleton from `docs/spec.md`, `docs/stories.md`, `docs/evals/registry.yaml`, and the current format registry.
  2. Define codex-forge system buckets so the absorbed format-coverage material has a natural home instead of becoming an appendix dump.
  3. Populate each compromise-carrying system with `Optimize` / `Eliminate` progress using current eval IDs, latest scores/dates, and retry conditions when available.
  4. Migrate the format registry's capability tables, known gaps, graduation criteria, and next-action content into the right build-map sections.
  5. Re-read the document and remove duplicated or stale statements before deleting `docs/format-registry.md`.
- **Impact / risk**:
  - Highest content risk in the story: the build map can easily become bloated or contradictory if the absorbed registry content is pasted rather than reorganized.
  - No schema or pipeline-runtime risk.
- **Done looks like**:
  - `docs/build-map.md` stands alone as the canonical map of systems, compromises, format coverage, and graduation state.
  - No active doc/skill depends on `docs/format-registry.md`.

### Task 2 — Replace `reflect` with `align` (`S`)

- **Files**: `.agents/skills/align/SKILL.md` (new), `.agents/skills/reflect/SKILL.md` (remove), `.agents/skills/create-adr/SKILL.md`, `docs/runbooks/adr-creation.md`, `docs/runbooks/deep-research.md`, `docs/decisions/README.md`, generated Gemini wrappers.
- **Order**:
  1. Adapt Storybook's `align` skill to codex-forge's methodology graph and new local build map.
  2. Update all active `/reflect` guidance to `/align`.
  3. Regenerate wrappers so `align.toml` exists before removing `reflect.toml`.
- **Impact / risk**:
  - Low code risk, moderate workflow risk if stale docs or wrappers remain.
  - No local ADR directly constrains this rename; `docs/decisions/adr-001-source-aware-consistency-strategy/adr.md` is unrelated to agent workflow convergence.
- **Done looks like**:
  - Active `/reflect` guidance is gone.
  - `align` is the canonical advisory skill and reads `docs/build-map.md`.

### Task 3 — Merge `verify-eval` into `improve-eval` (`S`)

- **Files**: `.agents/skills/improve-eval/SKILL.md`, `.agents/skills/verify-eval/SKILL.md` (remove), `.agents/skills/create-story/SKILL.md`, `.agents/skills/create-story/templates/story.md`, `docs/runbooks/golden-build.md`, `docs/runbooks/crop-eval-workflow.md`, generated Gemini wrappers.
- **Order**:
  1. Fold mismatch classification and golden/test-correction guidance into `improve-eval`.
  2. Replace active `/verify-eval` references in story scaffolding and runbooks.
  3. Remove the standalone skill and wrapper.
- **Impact / risk**:
  - Main risk is losing the "raw scores are meaningless; classify mismatches" discipline while simplifying the skill surface.
  - No benchmark reruns are needed during planning; this is workflow consolidation.
- **Done looks like**:
  - Active `verify-eval` guidance is gone.
  - `improve-eval` still explicitly preserves mismatch-classification rigor.

### Task 4 — Adopt `/triage` now (`M`, approved)

- **Files if adopted now**: `.agents/skills/triage/SKILL.md` (new), `.agents/skills/triage-evals/SKILL.md` (new), `.agents/skills/triage-inbox/SKILL.md`, `.agents/skills/triage-stories/SKILL.md`, generated Gemini wrappers, possibly `AGENTS.md`.
- **Chosen path**:
  - **Option A — Land `/triage` now**: complete the Storybook-style orchestration in this story, including the read-only full-sweep meta-skill and an eval leaf.
- **Approval**:
  - User approved the full migration, including `/triage`, so the larger workflow convergence shipped in one pass.
- **Done looks like**:
  - If adopted: `/triage` exists as an orchestrator only, leaf ownership is preserved, and full-sweep mode is read-only.
  - If deferred: the story explicitly records the defer and leaves no ambiguous half-migration language.

### Task 5 — Registry / scaffolding / final verification (`S`)

- **Files**: `docs/evals/registry.yaml`, `AGENTS.md`, `.agents/skills/create-cross-cli-skill/SKILL.md`, `scripts/sync-agent-skills.sh` outputs, and any docs that still reference superseded surfaces.
- **Order**:
  1. Decide whether the Storybook eval-class taxonomy materially helps codex-forge once the new skill/build-map surface is in place.
  2. Re-run sync, wrapper checks, and grep verification.
  3. Update the story checklist/work log with exact evidence.
- **Impact / risk**:
  - Low implementation risk.
  - The main failure mode is thinking the migration is done while active guidance still points at removed docs/skills.
- **Done looks like**:
  - Verification commands pass.
  - Remaining grep hits are historical-only and explicitly called out as such.

### Scope Adjustments Found During Exploration

- **Folded into this story**:
  - Retarget `.agents/skills/format-gap-analysis/SKILL.md` from `docs/format-registry.md` to `docs/build-map.md`.
  - Use the active-guidance grep bundle, not repo-wide grep counts, as the primary verification metric.
- **Potential larger follow-up**:
  - `/triage` orchestration remains the only part that could reasonably be split out if you want to keep this migration tighter.

### Human-Approval Blockers

- Resolved: the user approved the full migration, including `/triage`, before implementation started.

## Work Log

### 20260315-1653 — story creation: drafted a codex-forge-specific ADR-019 convergence plan

- **Result:** Created Story 145 as a Pending migration plan with a repo-specific comparison matrix and explicit workstreams for `reflect` -> `align`, `verify-eval` merge, triage convergence, and wrapper/doc sync.
- **Evidence:** Manual readback of the Storybook migration guide plus local grep/readback of codex-forge showed live `/reflect` references, a separate `/verify-eval`, no `.gemini/commands/align.toml`, no `.gemini/commands/triage.toml`, no `docs/build-map.md`, and an empty `.agents/skills/align/` directory.
- **Next:** Run `/build-story` to choose the exact triage-convergence scope and then execute the migration with sync/grep verification.

### 20260315-1657 — scope update: build-map promoted from skip to deliverable

- **Result:** Updated Story 145 so `docs/build-map.md` is now an explicit migration deliverable rather than an intentional codex-forge skip.
- **Evidence:** User direction overrode the earlier "skip build-map" assumption. Manual readback of Storybook's `docs/build-map.md` and codex-forge's `docs/format-registry.md` showed a viable adaptation path: create the build map from local system/compromise/capability docs instead of treating Storybook's structure as product-specific.
- **Next:** Build the story with a concrete plan for `docs/build-map.md`, including its ownership boundary versus `docs/format-registry.md`.

### 20260315-1703 — scope update: format registry now treated as an absorption target

- **Result:** Updated Story 145 so `docs/format-registry.md` is no longer treated as a possible sibling surface. The story now assumes its live content will be subsumed into `docs/build-map.md` and the old file will be removed after retargeting active references.
- **Evidence:** Repo grep found active `docs/format-registry.md` dependencies in `AGENTS.md`, `.agents/skills/format-gap-analysis/SKILL.md`, and `.agents/skills/reflect/SKILL.md`, so leaving the ownership boundary ambiguous would create avoidable drift.
- **Next:** Build the story with a concrete section plan for absorbed format coverage/gap/graduation content inside `docs/build-map.md`, then retarget the live references during implementation.

### 20260315-1707 — exploration: migration surface confirmed, no local ADR blocks the work

- **Result:** Promoted the story into active planning after tracing the real migration surface and reducing the verification problem to active guidance rather than historical references.
- **Files that will change:** `AGENTS.md`; `docs/build-map.md` (new); `docs/format-registry.md` (remove); `.agents/skills/align/SKILL.md` (new); `.agents/skills/reflect/SKILL.md`; `.agents/skills/improve-eval/SKILL.md`; `.agents/skills/verify-eval/SKILL.md`; `.agents/skills/format-gap-analysis/SKILL.md`; `.agents/skills/create-story/SKILL.md`; `.agents/skills/create-story/templates/story.md`; `.agents/skills/create-adr/SKILL.md`; `docs/runbooks/adr-creation.md`; `docs/runbooks/deep-research.md`; `docs/runbooks/golden-build.md`; `docs/runbooks/crop-eval-workflow.md`; `docs/decisions/README.md`; generated `.gemini/commands/*.toml`; optionally triage skills if that scope is approved.
- **Files at risk:** `scripts/sync-agent-skills.sh` outputs and every generated Gemini wrapper, because wrapper generation only sees real `SKILL.md` files; the empty `.agents/skills/align/` directory is currently ignored and therefore does not create `align.toml`.
- **ADRs / decision docs consulted:** `docs/decisions/README.md` and `docs/decisions/adr-001-source-aware-consistency-strategy/adr.md`. No local ADR directly constrains build-map / skill-surface convergence; ADR-001 is about document-consistency extraction strategy, not agent workflow.
- **Patterns to follow:** Canonical skill definitions live in `.agents/skills/`; Gemini wrappers are generated, not hand-maintained; Storybook's `build-map`, `align`, `triage`, and merged `improve-eval` are the reference implementation shapes; active guidance should be measured separately from historical story/scout mentions.
- **Surprises found:** `scripts/sync-agent-skills.sh --check` and `make skills-check` already pass on the pre-migration repo; active guidance counts are much smaller than raw repo grep counts (`8` `/reflect`, `8` `verify-eval`, `6` `format-registry`); and the empty `align/` stub means the repo is already in a partial migration state rather than a clean pre-migration state.
- **Next:** Present the implementation plan and get approval on whether `/triage` is included in this story or deferred.

### 20260315-1742 — implementation: build-map landed, registry absorbed, and live guidance retargeted

- **Impact**
  - **Story-scope impact:** Closed the largest structural gap in the migration by creating `docs/build-map.md`, absorbing the former format-registry content, and removing the last active dependencies on that deleted surface.
  - **Pipeline-scope impact:** The repo now has one browsable human-readable source of truth for system ownership, compromise progress, input coverage, graduation criteria, and prioritized format gaps. The machine-readable coverage matrix was refreshed so build-map and coverage inventory agree on crop/provenance status.
  - **Evidence:** Manual readback of `docs/build-map.md`; manual readback of `tests/fixtures/formats/_coverage-matrix.json`; active `format-registry` grep against AGENTS/build-map/runbooks/decisions/skills returned no hits.
  - **Next:** Land the skill/wrapper convergence so the docs and command surface stop disagreeing.

### 20260315-1751 — implementation: align, triage, and merged eval workflow replaced the drifted skill surface

- **Impact**
  - **Story-scope impact:** Completed the command-surface migration: `align` replaced `reflect`, `improve-eval` absorbed the standalone verification flow, `/triage` plus `/triage-evals` landed, and the supporting leaf skills/runbooks/templates now point at the converged workflow.
  - **Pipeline-scope impact:** The agent operating system is now internally coherent. Future sessions can use build-map-aware advisory sweeps and full triage sweeps without landing in a half-migrated wrapper/doc state.
  - **Evidence:** Manual readback of `.agents/skills/align/SKILL.md`, `.agents/skills/triage/SKILL.md`, `.agents/skills/triage-evals/SKILL.md`, and `.agents/skills/improve-eval/SKILL.md`; generated wrapper readback of `.gemini/commands/align.toml`, `.gemini/commands/triage.toml`, and `.gemini/commands/triage-evals.toml`.
  - **Next:** Run sync, lint, tests, and grep verification before closing the story.

### 20260315-1808 — verification: wrapper sync, repo checks, and migration greps all passed

- **Impact**
  - **Story-scope impact:** Verified the migration end to end. The build-map/doc/skill/wrapper surface is consistent, generated wrappers are present, and the retired command names no longer appear in active guidance.
  - **Pipeline-scope impact:** Repo-level confidence stayed intact: `make lint` stayed clean, the full pytest suite passed (`599 passed, 5 skipped`), and no active AGENTS/build-map/runbook/decision/skill surface still points at deleted skills or worktree-local paths.
  - **Evidence:** `./scripts/sync-agent-skills.sh`; `./scripts/sync-agent-skills.sh --check`; `make skills-check`; `make lint`; `make test`; targeted greps showing `verify-eval`, `/reflect`, `format-registry`, and worktree-path hits are absent from active guidance surfaces and only remain in historical story/scout evidence where expected.
  - **Next:** Close the story as Done and leave any remaining historical reference cleanup for future non-migration hygiene work, since it is out of scope here.

### 20260315-1818 — closure: mark-story-done validation passed and changelog recorded

- **Impact**
  - **Story-scope impact:** Completed the formal story-closeout requirements: Story 145 now has a completion note, matching `Done` status in the index, and a dedicated changelog entry.
  - **Pipeline-scope impact:** No pipeline behavior changed at closure time; this step only made the delivered migration auditable in the project’s normal release and story-tracking surfaces.
  - **Evidence:** `make test`; `make lint`; `make skills-check`; [CHANGELOG.md](/Users/cam/Documents/Projects/codex-forge/CHANGELOG.md) entry `2026-03-15-03`; [docs/stories.md](/Users/cam/Documents/Projects/codex-forge/docs/stories.md) row `145 = Done`.
  - **Next:** Land the validated diff to `main` with `.codex/` excluded as unrelated local state.
