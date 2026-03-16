---
name: align
description: Check alignment of the methodology graph after a change — Ideal, ADRs, Spec, Build Map, Stories, Evals — and propose corrections
user-invocable: true
---

# /align [what-changed | ADR-NNN]

> Alignment check: Before choosing an approach, verify it aligns with `docs/ideal.md` and relevant decision records in `docs/decisions/`. If this work touches a known compromise in `docs/spec.md`, respect its limitation type and evolution path. If none apply, say so explicitly.

Check the methodology graph for misalignment after a change. This is read-only
and advisory.

## When To Use

Use this after changes that may ripple across core project guidance:

- an ADR is accepted or materially redirected
- `docs/ideal.md`, `docs/spec.md`, or `docs/requirements.md` changes
- `docs/build-map.md` changes
- an eval newly passes and may delete a compromise
- a story reveals a new repo-level lesson
- a new model, tool, or external constraint may invalidate current guidance

## Read First

1. `docs/ideal.md`
2. `docs/spec.md`
3. `docs/build-map.md`
4. `docs/requirements.md`
5. `docs/stories.md` plus directly affected story files
6. relevant ADRs under `docs/decisions/`
7. `docs/evals/registry.yaml`
8. `AGENTS.md` if workflow or guardrails may be affected

## What To Check

### Ideal
- did this reveal a new ideal that is not explicit yet?
- did it sharpen an existing central tenet or requirement?

### Spec / Requirements
- does this add, remove, or change a compromise?
- does it change a detection mechanism or evolution path?
- should any existing compromise now be re-evaluated?

### Build Map
- does this change system scope, dependency order, or compromise progress?
- does input coverage, graduation tracking, or known-gap prioritization need to move?

### Stories
- are any Draft, Pending, or In Progress stories affected?
- did any Done stories become stale or mis-scoped?
- should a new story likely exist? Flag it; do not create it.

### Evals
- should any evals be rerun, added, or retired?
- does a compromise now lack a meaningful deletion signal?

### ADRs / Runbooks / Guardrails
- does this contradict an ADR?
- should an existing ADR or runbook be updated?
- does `AGENTS.md` need stronger or different guidance?

## Report Format

```markdown
## Align — {what changed}

### Ideal
- {impact or "Aligned"}

### Spec / Requirements
- {impact or "Aligned"}

### Build Map
- {impact or "Aligned"}

### Stories
- {story IDs and why}

### Evals
- {rerun / add / remove guidance}

### ADRs / Runbooks / AGENTS
- {affected guidance or "Aligned"}

### Recommended Actions
- [ ] {specific action in priority order}
```

## Guardrails

- Read the actual docs; do not reason from memory.
- Keep the report short and actionable.
- If there is no meaningful downstream impact, say so explicitly.
- Do not silently create stories, ADRs, or evals while using this skill.
