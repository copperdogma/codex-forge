# Scout 006 — storybook-adr-skills

**Source:** /Users/cam/Documents/Projects/Storybook/storybook
**Scouted:** 2026-03-14
**Scope:** ADR skill package only — identify Storybook's ADR workflow surface, adapt the minimal working parts to codex-forge, and install them
**Previous:** Scout 003 (storybook-patterns, 2026-03-10)
**Status:** Complete

## Findings

1. **`create-adr` skill package is self-contained and high leverage** — HIGH value
   What: Storybook's dedicated ADR surface is a single `create-adr` skill backed by one bootstrap script and three templates. It creates a new ADR directory with a stub, research prompt, and synthesis file.
   Us: codex-forge has no ADR creation skill today.
   Recommendation: Adopt inline, but adapt it to codex-forge's docs layout instead of copying Storybook's assumptions verbatim.

2. **Storybook's ADR runbook is useful, but too Storybook-specific as-is** — HIGH value
   What: `docs/runbooks/adr-creation.md` defines lifecycle, statuses, discussion flow, and an integration checklist. It assumes `setup.md`, `feature-map.md`, `docs/decisions/`, and a broader ADR system.
   Us: codex-forge currently has `docs/inbox.md`, stories, specs, scouts, and runbooks, but no `setup.md` or `feature-map.md`.
   Recommendation: Adopt inline after adapting the integration checklist to codex-forge (`Decision Refs`, AGENTS, runbooks, spec/ideal/requirements).

3. **Minimal ADR scaffolding is enough to start** — MEDIUM value
   What: Storybook's package does not require a large platform to be useful; the bootstrap script can create the directory structure on demand.
   Us: codex-forge does not need a full "decision system" upfront to benefit from ADRs. A `docs/decisions/` convention plus a runbook is enough.
   Recommendation: Adopt inline with a lightweight `docs/decisions/README.md`.

4. **Making all existing skills ADR-aware is a separate, larger pass** — MEDIUM value
   What: In Storybook, many skills check `docs/decisions/` while planning, validating, and landing work.
   Us: codex-forge intentionally absorbed ADR intent into generalized decision-check language earlier instead of inventing empty ADR scaffolding.
   Recommendation: Adopt inline now that codex-forge has ADR scaffolding.

## Approved

- [x] 1. `create-adr` skill package — **Adopted inline.** Added a codex-forge-adapted `.agents/skills/create-adr/` with `SKILL.md`, `scripts/start-adr.sh`, and ADR bootstrap templates.
- [x] 2. ADR lifecycle runbook — **Adopted inline.** Added `docs/runbooks/adr-creation.md` adapted to codex-forge's current docs surface and workflow.
- [x] 3. Minimal ADR scaffolding — **Adopted inline.** Added `docs/decisions/README.md` and synced the new skill into Gemini wrappers.
- [x] 4. ADR-aware skill surface — **Adopted inline.** Updated the relevant codex-forge skills and story scaffolding to consult `docs/decisions/`, cite ADRs in `Decision Refs`, and route inbox items into ADRs when appropriate.

## Verification

- `bash -n .agents/skills/create-adr/scripts/start-adr.sh` — bootstrap script syntax is valid
- `scripts/sync-agent-skills.sh` — regenerated wrappers including `.gemini/commands/create-adr.toml`
- `scripts/sync-agent-skills.sh --check` — passed (`18` skills, `18` Gemini wrappers)
- `make skills-check` — passed
- Manual readback: `.agents/skills/create-adr/SKILL.md`, `.agents/skills/create-adr/templates/adr.md`, `docs/runbooks/adr-creation.md`, and `docs/decisions/README.md`
- Manual readback: ADR-aware updates in `.agents/skills/build-story/SKILL.md`, `.agents/skills/check-in-diff/SKILL.md`, `.agents/skills/create-story/SKILL.md`, `.agents/skills/mark-story-done/SKILL.md`, `.agents/skills/triage-inbox/SKILL.md`, `.agents/skills/codebase-improvement-scout/SKILL.md`, `.agents/skills/validate/SKILL.md`, `AGENTS.md`, and `.agents/skills/create-story/templates/story.md`

## Skipped / Rejected
