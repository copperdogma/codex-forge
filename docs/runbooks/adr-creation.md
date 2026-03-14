# Runbook: ADR Creation

Operational lifecycle for Architecture Decision Records in codex-forge.

Use an ADR when a decision affects architecture, workflow, schemas, cross-cutting module behavior, or a project-level constraint that future sessions should not relitigate from scratch.

## When To Create An ADR

- A technical choice affects multiple stories, modules, or stages
- The choice is hard to reverse and worth documenting
- The team is uncertain and needs research before deciding
- Future sessions are likely to ask "why did we choose this?"

Do not create ADRs for:

- small implementation details inside one story
- trivially reversible choices
- decisions already covered by an existing ADR

## Lifecycle

```text
Identified → Stub Created → Research Prompt Written → Research Run → Discussion → ACCEPTED
                                                                  ↘ REJECTED
                                                                  ↘ DEFERRED
                                                                  ↘ SUPERSEDED
```

Status values:

- `PENDING` — ADR exists, research still needed
- `RESEARCHING` — research is underway or summarized
- `DISCUSSING` — research exists and the decision is being finalized
- `ACCEPTED` — decision made and integration checklist complete
- `REJECTED` — explicitly decided against
- `DEFERRED` — not needed yet; record the trigger to reopen
- `SUPERSEDED` — replaced by a newer ADR

## Process

### 1. Identify The Decision

Capture the need in a story, `docs/inbox.md`, or ongoing planning notes.

### 2. Create The ADR Stub

Use `/create-adr`:

```text
/create-adr <number> <short-name> "<title>"
```

This creates:

- `docs/decisions/adr-NNN-name/adr.md`
- `docs/decisions/adr-NNN-name/research/research-prompt.md`
- `docs/decisions/adr-NNN-name/research/final-synthesis.md`

### 3. Fill In The Stub

Before research, write:

- Context
- Ideal alignment
- candidate options
- research questions
- repo constraints and dependencies

### 4. Run Research

The research method can vary. Use whatever is appropriate:

- `/scout` for repo or external pattern research
- direct model research across providers
- benchmark or spike results already in this repo

Research should answer the questions in `research/research-prompt.md` and leave enough evidence for later sessions to audit the choice.

### 5. Summarize And Discuss

Update the ADR:

- `Status: RESEARCHING` once research exists
- write `Research Summary`
- add discussion notes, disagreements, and corrections

When the direction is settled, change to `DISCUSSING` and record the final decisions with rationale.

### 6. Integrate The Decision

An ADR is not `ACCEPTED` until its integration checklist is done.

Typical integration targets in codex-forge:

- `docs/spec.md`, `docs/ideal.md`, or `docs/requirements.md`
- relevant story files, especially `Decision Refs` and task constraints
- `AGENTS.md` when the ADR changes workflow or agent guardrails
- relevant runbooks or scout docs
- other ADRs or decision records if cross-references are needed

### 7. Audit

Before marking `ACCEPTED`, reread the ADR decisions and verify each one is reflected in the correct artifact. The checklist is a prompt; the audit is the proof.

## Numbering

- Use sequential numbers: `ADR-001`, `ADR-002`, ...
- Check existing `docs/decisions/adr-*` directories before choosing a number
- Do not reuse numbers from superseded ADRs

## Directory Layout

```text
docs/decisions/
  adr-001-example/
    adr.md
    research/
      research-prompt.md
      final-synthesis.md
```

## Notes

- Keep the ADR focused on the decision, not the implementation diff
- Preserve the reasoning path, not just the final answer
- If a later ADR changes the decision, mark the old one `SUPERSEDED` and cross-link both
