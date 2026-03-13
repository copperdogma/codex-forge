---
name: build-story
description: Execute a story from planning through implementation with work-log discipline
user-invocable: true
---

# /build-story [story-number]

Execute a development story end-to-end.

## Phase 1 — Explore (read-only, no file writes)

1. **Resolve story** — Read `docs/stories/story-{NNN}-*.md` (or resolve from `docs/stories.md`). Verify status is Pending or In Progress. If **Draft**, STOP — tell the user to promote it to Pending first (needs detailed ACs and tasks).
   - If status is Pending, update it to **In Progress** in both the story file and the corresponding row in `docs/stories.md`.

2. **Verify required sections** — Ensure the story has:
   - Goal
   - Acceptance Criteria (testable checkboxes)
   - Tasks (checkbox items)
   - Work Log
   If tasks are missing, add actionable items without discarding existing intent.

3. **Read context** — Read `docs/ideal.md`, then all spec refs, dependency stories, and referenced docs.

4. **Ideal Alignment Gate** — Before exploring code:
   - Does this story close an Ideal gap? → proceed
   - Does it move AWAY from the Ideal? → STOP, tell user to re-evaluate
   - Does it optimize a compromise without closing a gap? → flag as potentially low-value
   - If introducing a new AI compromise: note whether a detection eval exists or should be created

5. **Explore the codebase** — Don't just read what's listed. Trace the code:
   - Follow call graphs from entry points the story touches
   - Find every file that will change and every file that could break
   - Identify existing patterns and conventions to match
   - Note schema, config, or migration concerns

6. **Identify scope deltas** — If exploration reveals important work that is missing from the story but is necessary to actually solve the story's goal:
   - **Small, coherent delta** → expand the story automatically. Update the story's tasks/ACs/work log so the real scope is visible.
   - **Large delta** → do not silently absorb or silently split it out. Add it to the plan as a recommended scope expansion for user approval.
   - Prefer expanding the current story when the new work is tightly coupled, in the same subsystem, and reasonably achievable in the same implementation pass.
   - Prefer a follow-up story only when the new work is materially distinct, changes the story's goal, adds major blast radius, or would make validation unclear.
   - Do not optimize for human sprint sizing. Optimize for a coherent slice that an AI can implement and validate end-to-end.

7. **Record exploration findings** — Write a brief exploration entry in the work log:
   - Files that will change, files at risk, patterns to follow, surprises found

## Phase 2 — Plan (produces a written artifact)

8. **Eval-first approach gate** — Before planning implementation:
   - **What eval?** Identify or create a test that measures success. Even a minimal fixture + assertion counts.
   - **What's the baseline?** Run the eval against current code. Document the number.
   - **Candidate approaches?** For tasks involving reasoning/language/understanding: enumerate AI-only, hybrid, and pure code. If the story pre-decided an approach without evidence, challenge it.
   - **Test the simplest first.** Often a single LLM call. If it works, don't build code.
   - For pure orchestration/plumbing: code is obviously simpler — no comparison needed.

9. **Write the implementation plan** — Add a `## Plan` section to the story with:
   - For each task: which files change, what changes, in what order
   - Impact analysis: what tests are affected, what could break
   - Human-approval blockers (new dependencies, schema changes)
   - Any recommended scope adjustments discovered during exploration
   - If giving effort guidance, use relative effort only (`XS`, `S`, `M`, `L`, `XL` or equivalent), not hours/days
   - What "done" looks like for each task

10. **Human gate** — Present the plan to the user. Surface ambiguities and risks.
    - Small scope expansions already folded into the story should be called out explicitly.
    - Large scope expansions should be presented as a recommendation with rationale and relative effort.
    - **Do not write implementation code until approved.**

## Phase 3 — Implement

11. **Implement** — Work through tasks in order:
    - Mark task in progress in story file
    - Do the work
    - Run relevant tests after each change
    - Mark task complete with brief evidence

12. **Verification** — Run the project's validation:
    - `python -m pytest tests/` (all pass)
    - `python -m ruff check modules/ tests/` (clean)
    - If a pipeline module changed: run through `driver.py` and inspect artifacts
    - Review each acceptance criterion — is it met?

13. **Update docs** — Search all docs and update anything related to what was touched.

14. **Verify Central Tenets** — Check each tenet in the story:
    - T0 — Traceability: every output traces to source page, OCR engine, confidence, processing step?
    - T1 — AI-First: didn't write code for a problem AI solves better?
    - T2 — Eval Before Build: measured SOTA before building complex logic?
    - T3 — Fidelity: source content preserved faithfully?
    - T4 — Modular: new recipe not new code; no hardcoded book assumptions?
    - T5 — Inspect Artifacts: visually verified outputs?

15. **Update work log** — Add dated entry: what was done, decisions, evidence, blockers.

16. **Update status** — If all ACs met and checks pass, mark story Done. Update `docs/stories.md`.

## Work Log Format

```
YYYYMMDD-HHMM — action: result, evidence, next step
```

Entries should be verbose. Capture decisions, failures, solutions, and learnings. These are build artifacts — any future AI session should be able to pick up context from the log.

## Guardrails

- **Never write implementation code before the human gate (step 10)**
- When important adjacent work is required to actually satisfy the story, default to expanding the current story modestly instead of pretending it is out of scope
- For larger expansions, recommend the scope change explicitly before implementing
- Use relative effort estimates only; never present hours/days unless the user explicitly asks for calendar-style estimates
- Never skip acceptance criteria verification
- Never mark Done if any check fails
- Never mark Done without inspecting produced artifacts (not just checking logs)
- If evals were run: classify mismatches as **model-wrong**, **golden-wrong**, or **ambiguous**
- Never commit without explicit user request
- Always update the work log, even for partial progress
- If blocked, record the blocker and stop — don't guess
