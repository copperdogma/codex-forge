---
name: triage-inbox
description: Process inbox items into stories, research spikes, ADRs, or spec updates
user-invocable: true
---

# /triage-inbox

> Decision check: If this task affects workflow, backlog structure, or cross-cutting project behavior, read relevant ADRs in `docs/decisions/` plus any supporting runbooks, scout docs, or notes before choosing an approach. If none apply, say so explicitly.

Go through accumulated inbox items together with the user.

## Steps

1. **Read inbox** — Load `docs/inbox.md`. List all untriaged items.

2. **Staleness sweep** — Before prioritizing, actively search for each item across the project to determine whether it already landed elsewhere.
   For each item, search:
   - `docs/decisions/` — is there already an ADR covering it?
   - `docs/spec.md` — is it already captured in the active spec?
   - `docs/stories/` and `docs/stories.md` — is there already a story covering it?
   - recent git history — was it implemented recently?

   Classify each item:
   - **STALE** — already handled elsewhere; recommend deletion with a one-line pointer
   - **PARTIALLY HANDLED** — some aspects are covered, but new substance remains
   - **LIVE** — not yet addressed anywhere

   Present stale items first as a batch for confirmation, then proceed with live items only.

3. **Prioritize** — Evaluate the live inbox against current project state:
   - Read `docs/stories.md` and `docs/ideal.md` for context
   - Group items by theme if natural clusters exist
   - Recommend a **top 3-5** to triage first with rationale
   - Flag items that are probably defer or discard candidates
   - Let the user adjust before proceeding

4. **For each item, discuss with the user:**
   - **What if we do nothing?** If the answer is "the user can solve it in 20 lines" or "nothing meaningful breaks", it may not deserve a story
   - Does this move toward the Ideal or away from it?
   - Is it a signal that a compromise in `docs/spec.md` can be deleted? If so, the first action may be re-running the detection eval, not creating a story
   - Does an existing story already have a natural home for it?
   - What should we do with it?
     - **Fold into existing story**
     - **New story**
     - **Research spike**
     - **ADR**
     - **Spec update**
     - **Ideal update**
     - **Discard**

5. **Create artifacts** — For each decision, create the appropriate artifact immediately.

6. **Delete from inbox** — Every processed item is removed from `docs/inbox.md`. The inbox is a processing queue, not an archive. If an item cannot be actioned yet, leave it only with a clear revisit trigger.

7. **Summarize** — Quick summary of what was processed and where each item landed.

## Guardrails

- Always discuss with the user before creating artifacts — don't auto-triage
- Batch-decide items with shared prerequisites or themes — don't force item-by-item
- Check existing draft stories before creating new ones — fold in when the fit is clean
- Prefer folding into existing stories over creating new backlog surface
- Check `docs/decisions/` before assuming an inbox item is still live
- The inbox should be empty or near-empty after triage
- If an item needs investigation before triaging, say so and move on
