---
name: codebase-improvement-scout
description: Periodically inspect the repo for high-value cleanup, draft improvement stories, and optionally apply narrow safe hygiene fixes.
user-invocable: true
---

# /codebase-improvement-scout [scope] [--create-story] [--autofix] [--autonomous]

> Decision check: If this task affects architecture, workflow, schemas, or cross-cutting agent behavior, read relevant ADRs in `docs/decisions/` plus supporting docs in `docs/runbooks/`, `docs/scout/`, and `docs/notes/` before choosing an approach. If none apply, say so explicitly.

Run a scheduled or on-demand repo-hygiene scan for codebase drift, AI-generated junk, and high-value cleanup opportunities.

Companion runbook: `docs/runbooks/codebase-improvement-scout.md`

## Default Behavior

- **Default mode** — report-only. Create a scan artifact, rank the best improvements, and recommend the next step.
- **`--create-story`** — create exactly one best-fit story for the highest-value non-mechanical improvement if no equivalent story already exists.
- **`--autofix`** — allow only narrow, behavior-preserving cleanup work on a side branch.
- **`--autonomous`** — if the user says "you choose and continue", continue through the next approved step without asking again.

This skill is a repo-hygiene scout, not a free-form refactoring bot. Prefer report plus story over speculative edits.

## Phase 0 — Bootstrap

1. **Create scan artifacts:**

```bash
.agents/skills/codebase-improvement-scout/scripts/start-scan.sh
```

This creates:
- `docs/reports/codebase-improvement/<timestamp>.md`
- `docs/reports/codebase-improvement/_state.yaml` if missing

2. **Record current state:**
   - `git status --short`
   - `git branch --show-current`
   - `git rev-parse --short HEAD`
   - If the worktree is dirty and the user did not explicitly authorize edits on top of it, stay in report-only mode.

3. **Read repo context:**
   - `AGENTS.md`
   - `docs/ideal.md`
   - `docs/spec.md`
   - relevant ADRs for likely hotspots
   - relevant runbooks, scout docs, and notes for likely hotspots
   - `docs/stories.md`
   - `docs/reports/codebase-improvement/_state.yaml` if it exists

## Phase 1 — Deterministic Discovery

Run the strongest available deterministic checks first. Verify tools exist before using them.

1. **Repo hygiene baseline:**
   - `make check-size` if available; otherwise `wc -l` on likely hotspots
   - `git log --since='30 days' --name-only --format='' | sed '/^$/d' | sort | uniq -c | sort -rn | head -50`
   - `rg -n "TODO|FIXME|XXX|HACK|TEMP|placeholder|stub" modules tests docs scripts benchmarks .agents AGENTS.md`

2. **Project-native quality checks:**
   - `make lint`
   - `make test`
   - `make skills-check`

3. **Optional narrow detectors if installed:**
   - duplication: `jscpd`
   - Python dead code: `vulture`
   - dependency drift: `deptry`

4. **Targeted reads:**
   - inspect the top hotspot files
   - inspect recent stories affecting those areas
   - check whether an apparent issue is already tracked or intentionally accepted

## Phase 2 — Triage and Classification

For each candidate finding, classify it as exactly one of:

- **Auto-fix**
  - mechanical
  - behavior-preserving
  - small blast radius
  - no architecture change
  - verifiable by existing checks
- **Story**
  - structural or architectural
  - likely to touch multiple files or layers
  - needs judgment, test design, or artifact inspection
  - better handled by the normal story workflow
- **Suppress**
  - intentional local convention
  - already reviewed and accepted
  - active work makes the signal misleading right now
- **Ignore**
  - cosmetic only
  - too low-value
  - low confidence

Rank findings by leverage, not raw issue count:
- hotspot score
- user-facing or pipeline impact
- maintenance drag
- confidence

Prefer the top 3-5 findings. Low-signal laundry lists are a failure.

## Phase 3 — Write the Scan Report

Fill the generated report with:
- run metadata and scope
- detectors used or unavailable
- top findings with classification
- one recommended next step
- story candidate or existing-story link
- suppressions or ignores with rationale

Also update `docs/reports/codebase-improvement/_state.yaml`:
- add newly suppressed findings
- record the run timestamp and top findings
- avoid re-raising recent suppressed items unless the evidence changed

## Phase 4 — Optional Story Creation

If `--create-story` is set or the user explicitly approves:

1. Search `docs/stories.md` and existing story files for overlap.
2. If an equivalent story already exists, link it in the report instead of creating a duplicate.
3. Otherwise create exactly one story for the highest-value non-mechanical improvement.
4. Default to `Draft` if the scope is still fuzzy; use `Pending` only when acceptance criteria and tasks are concrete.
5. Link the report in the story notes.

If the user also explicitly approves execution, continue using the normal chain:
- `/build-story`
- `/validate`
- `/mark-story-done`
- `/check-in-diff`

## Phase 5 — Optional Narrow Auto-Fix Lane

Only enter this phase when `--autofix` is set or the user explicitly approved safe cleanup edits.

1. Create a side branch before editing:
   - `git checkout -b codex/codebase-improvement-<timestamp>-<slug>`

2. Restrict changes to narrow safe classes:
   - remove unused imports
   - remove unused dependencies
   - delete provably dead files
   - collapse exact duplicate pure helpers with obvious replacements

3. Hard limits:
   - no more than 5 changed files per cleanup cluster
   - no new abstractions
   - no schema or API changes
   - no structural refactors
   - no pipeline behavior changes requiring new artifact semantics

4. Verification:
   - run the relevant native checks
   - if checks fail twice, revert that cleanup and downgrade it to a story

5. End with a concise summary and recommend `/check-in-diff` unless the user already approved later git steps.

## Guardrails

- Default to report-first, not code-first.
- Never run unconstrained "make the repo better" edits.
- Never re-litigate settled architecture if ADRs or other decision docs already answer the question.
- Never raise the same suppressed finding repeatedly without new evidence.
- Never do cosmetic-only churn.
- Never auto-fix structural or architectural issues.
- Never auto-edit on a dirty worktree unless the user explicitly approved that risk.
- Never commit or push without explicit user permission.
