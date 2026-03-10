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
- `ideal_refs`: relevant ideal.md requirements this story serves
- `spec_refs`: relevant spec.md compromises this implements
- `depends_on`: story IDs this depends on (if any)
- `status`: Draft or Pending (default: Draft)
  - **Draft** — skeleton with goal/notes but placeholder ACs and tasks
  - **Pending** — fully detailed ACs, tasks, and files to modify

## Steps

1. **Run the bootstrap script:**

   ```bash
   .agents/skills/create-story/scripts/start-story.sh <slug> [priority]
   ```

   Creates `docs/stories/story-NNN-<slug>.md` from template with next available number.

2. **Fill in the story file** — Replace all placeholder text (`{...}`) with real content:
   - Title (replace the slug with human-readable title)
   - Goal, acceptance criteria, out of scope, tasks, files to modify
   - Spec refs and dependencies
   - Approach evaluation: candidate approaches (AI-only, hybrid, code) and what eval distinguishes them

3. **Ideal alignment check** — Before writing the story, read `docs/ideal.md`:
   - Does this story close an Ideal gap? → proceed
   - Does it move AWAY from the Ideal? → STOP, push back, recommend alternative
   - Does it only optimize a compromise without closing a gap? → flag as low-value, confirm with user
   - If introducing a new AI compromise: note whether a detection eval exists

4. **Update story index** — Add a row to the end of the table in `docs/stories.md`:
   `| NNN | Title | Priority | Draft | /docs/stories/story-NNN-slug.md |`
   Match the existing table format (check surrounding rows for pipe alignment).

5. **Verify** — Confirm file exists, numbering is consistent, stories.md row is correct.

## Conventions

- Every story must trace to an Ideal requirement or spec compromise. Stories without lineage are untraceable scope.
- Acceptance criteria must be testable and concrete.
- Always include the Approach Evaluation section — list candidates without pre-deciding. Approach selection happens during build-story's eval-first gate.
- **Simplification baseline gate**: Every story involving new logic must answer: "Can a single LLM call already do this?" If untested, first task = measure the baseline.
- "Files to Modify" is gold for AI agents — fill it in when known.
- Story IDs are identifiers, not sequence numbers. New stories get max+1. Never use letter suffixes.

## Guardrails

- Never overwrite an existing story file — the script will error
- Never commit or push without explicit user request
- Verify numbering is sequential — no gaps, no duplicates
