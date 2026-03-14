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

4. **Cross-link if needed**
   - If the ADR came from a story, add it to that story's `Decision Refs`
   - If it came from `docs/inbox.md`, either replace the inbox item with the ADR path or note the follow-up explicitly

5. **Show the created files** to the user for review

## Guardrails

- Never overwrite an existing ADR directory
- ADR numbers are explicitly assigned, not auto-incremented
- Never commit or push without explicit user request
- The research prompt must stand alone
- Do not assume Storybook-specific docs like `setup.md` or `feature-map.md` exist here

## Notes

- ADR numbers should stay sequential. Check existing `docs/decisions/adr-*` directories before assigning a number.
- See `docs/runbooks/adr-creation.md` for the lifecycle and integration checklist.
