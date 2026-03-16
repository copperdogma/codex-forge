---
name: create-adr
description: Create a new Architecture Decision Record with research scaffolding
user-invocable: true
---

# /create-adr <number> <short-name> "<title>"

Create a new ADR with proper structure and research scaffolding.

## Example

```text
/create-adr 001 normalization-framework "Normalization and Consistency Alignment Framework"
```

## Steps

1. **Run the bootstrap script**

   ```bash
   .agents/skills/create-adr/scripts/start-adr.sh <number> <short-name>
   ```

   This creates:
   - `docs/decisions/adr-NNN-<name>/adr.md`
   - `docs/decisions/adr-NNN-<name>/research/research-prompt.md`
   - `docs/decisions/adr-NNN-<name>/research/final-synthesis.md`

2. **Fill in the ADR file**
   - Title
   - Context
   - Ideal alignment
   - Options
   - Research needed
   - Dependencies and affected docs/stories

3. **Write the research prompt**
   - Copy the relevant context from the ADR
   - Break the research into concrete numbered questions
   - Make the prompt stand alone so any model can do useful research without extra repo context

4. **Prepare research execution**
   - Use `docs/runbooks/deep-research.md` when the ADR needs multi-provider external research
   - Prefer the repo's ADR research-file convention:
     - `research-prompt.md`
     - `openai-research-report.md`
     - `gemini-research-report.md`
     - `opus-research-stub.md`
     - `xai-research-stub.md`
     - `final-synthesis.md`

5. **Cross-link if needed**
   - If the ADR came from a story, add it to that story's `Decision Refs`
   - If it came from `docs/inbox.md`, either replace the inbox item with the ADR path or note the follow-up explicitly

6. **Plan for reuse**
   - If the decision is likely to establish a reusable workflow, evaluation method, or architecture heuristic, note that the accepted result must later be captured in a skill, runbook, or `AGENTS.md` update

7. **Show the created files** to the user for review

8. **After the ADR matures, run `/align`**
   - Once research or implementation changes the project direction, use `/align` to propagate implications across `docs/ideal.md`, `docs/spec.md`, `docs/build-map.md`, `docs/requirements.md`, stories, ADRs, and evals

## Guardrails

- Never overwrite an existing ADR directory
- ADR numbers are explicitly assigned, not auto-incremented
- Never commit or push without explicit user request
- The research prompt must stand alone
- Do not assume Storybook-specific docs or product surfaces exist here
- Do not assume deep-research CLI default filenames match codex-forge's ADR research naming convention
- Do not let recurring patterns live only inside one ADR; once the direction is accepted, distill it into reusable repo guidance

## Notes

- ADR numbers should stay sequential. Check existing `docs/decisions/adr-*` directories before assigning a number.
- See `docs/runbooks/adr-creation.md` for the lifecycle and integration checklist.
- See `docs/runbooks/deep-research.md` for the multi-provider research workflow.
