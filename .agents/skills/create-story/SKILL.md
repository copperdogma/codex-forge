---
name: create-story
description: Scaffold a numbered story file and update the story index
user-invocable: true
---

# /create-story [title]

Create a new story in `docs/stories/` with consistent format.

## Inputs

- `title`: human-readable story title
- `slug`: kebab-case slug (derived from title if not provided)
- `priority`: High / Medium / Low (default: Medium)
- `ideal_refs`: ideal.md requirements this story serves
- `spec_refs`: relevant spec.md sections or compromise numbers
- `decision_refs`: relevant ADRs, runbooks, scout docs, notes, or other decision docs (or `None found after search`)
- `depends_on`: story IDs this depends on (if any)
- `status`: Draft or Pending (default: Draft)
  - **Draft** — skeleton with goal and notes but not ready to build
  - **Pending** — fully detailed ACs, tasks, workflow gates, and files to modify

## Steps

1. **Run the bootstrap script:**

   ```bash
   .agents/skills/create-story/scripts/start-story.sh <slug> [priority]
   ```

   This creates `docs/stories/story-NNN-<slug>.md` from the template with the next available number.

2. **Fill in the story file** — Replace all placeholder text (`{...}`) with real content:
   - Title (replace the slug with human-readable title)
   - Goal, acceptance criteria, out of scope, tasks, files to modify
   - Ideal refs, spec refs, decision refs, and dependencies
   - Approach evaluation: candidate approaches, repo constraints, existing patterns to reuse, and what eval distinguishes them
   - Workflow Gates
   - Redundancy or removal targets
   - Architectural Fit notes

3. **Ideal alignment check** — Before writing the story, read `docs/ideal.md`:
   - Does this story close an Ideal gap? → proceed
   - Does it move AWAY from the Ideal? → STOP, push back, recommend alternative
   - Does it only optimize a compromise without closing a gap? → flag as low-value, confirm with user
   - If introducing a new AI compromise: note whether a detection eval exists

4. **Update story index** — Add a row to the story table in `docs/stories.md`:
   `| NNN | Title | Priority | Draft | /docs/stories/story-NNN-slug.md |`
   Match the existing table format and nearby ordering conventions. Do not rewrite the entire index.

5. **Verify** — Confirm file exists, numbering is consistent, stories.md row is correct.

## Story Statuses

- **Draft** — Goal and notes exist, but acceptance criteria or tasks are still incomplete
- **Pending** — Fully detailed and ready for `/build-story`
- **In Progress** — Being built
- **Done** — Validated and closed
- **Blocked** — Waiting on dependency or decision

## Conventions

- Every story must trace to an Ideal requirement or spec compromise. Stories without lineage are untraceable scope.
- Acceptance criteria must be testable and concrete.
- Always include the Approach Evaluation section — list candidates without pre-deciding. Approach selection happens during `/build-story`.
- **Simplification baseline gate**: Every story involving new logic must answer: "Can a single LLM call already do this?" If untested, first task = measure the baseline.
- Search `docs/decisions/`, `docs/runbooks/`, `docs/scout/`, and `docs/notes/` for prior decisions or constraints while drafting. If none apply, say so explicitly.
- If the story raises a new unresolved architecture, workflow, or schema question, either cite the missing ADR need explicitly or recommend creating one before implementation starts.
- If the story changes pipeline, module, driver, schema, or recipe behavior, include a task for real `driver.py` verification and artifact inspection in `output/runs/`.
- If the story changes agent tooling or project instructions, include `make skills-check` in the task list.
- If the story will run evals, include a task to run `/verify-eval` and update `docs/evals/registry.yaml`.
- Always include the Workflow Gates section. These gates enforce the handoff chain: `/build-story` → `/validate` → `/mark-story-done`.
- If the story supersedes existing code or docs, name likely removal targets up front instead of silently accumulating parallel paths.
- "Files to Modify" is gold for AI agents — fill it in when known.
- Story IDs are identifiers, not sequence numbers. New stories get max+1. Never use letter suffixes.

## Work Log Entry Format

```
YYYYMMDD-HHMM — action: result, evidence, next step
```

## Guardrails

- Never overwrite an existing story file — the script will error
- Never commit or push without explicit user request
- Verify numbering is sequential — no gaps, no duplicates
