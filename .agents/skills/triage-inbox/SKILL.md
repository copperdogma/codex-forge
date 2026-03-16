---
name: triage-inbox
description: Scan or process inbox items into stories, research spikes, ADRs, or spec updates
user-invocable: true
---

# /triage-inbox [scan]

> Alignment check: Before choosing an approach, verify it aligns with `docs/ideal.md` and relevant decision records in `docs/decisions/`. If this work touches a known compromise in `docs/spec.md`, respect its limitation type and evolution path. If none apply, say so explicitly.

Canonical inbox triage leaf skill. Direct invocation is allowed, and
`/triage inbox` routes here.

## Modes

- **Processing mode** (`/triage-inbox` or `/triage inbox`)
  - interactive and action-taking
  - may create stories, ADRs, spec notes, or other artifacts
  - may delete processed items from `docs/inbox.md`
- **Scan mode** (`/triage-inbox scan` or `/triage inbox scan`)
  - read-only
  - used by the `/triage` orchestrator
  - produces a compact report and recommended next action, but does not edit files

## Steps

1. **Read inbox** — Load `docs/inbox.md`. Present all untriaged items as a
   numbered list with one-line summaries.

2. **Staleness sweep** — Before prioritizing, actively search for each item
   across the project to determine if it's already been handled. Inbox items
   often sit for weeks/months and get resolved through ADRs, spec updates, or
   stories without anyone cleaning them up.

   For every item, search:
   - `docs/decisions/` — is there an ADR that already addresses this?
   - `docs/spec.md` — is this already captured in the spec?
   - `docs/stories/` — is there already a story covering this?
   - `docs/build-map.md` — is this already mapped to a system?
   - recent git log — was this implemented recently?

   Classify each item:
   - **STALE** — already fully handled elsewhere
   - **PARTIALLY HANDLED** — some aspects addressed, but not all
   - **LIVE** — not yet addressed anywhere

3. **Prioritize live items**
   - Read `docs/stories.md` and recent git log to understand what's in flight
   - Group items by theme if natural clusters exist
   - Recommend a top 3-5 to process first
   - Flag obvious defer/discard candidates

4. **If scan mode, stop and report**

   Use this format:

   ```markdown
   ## Triage Inbox

   ### Live Items
   - {item}

   ### Stale / Already Handled
   - {item -> where it landed}

   ### Top Candidates
   - {item + short why}

   ### Recommended Action
   - {one next inbox action}

   ### Health Flags
   - {inbox growing / stale backlog / unresolved urgent item}
   ```

   In scan mode, never create artifacts and never edit `docs/inbox.md`.

5. **If processing mode, work items one at a time**
   After the user confirms the order, discuss each item:
   - does this move toward the Ideal or away from it?
   - if it serves a compromise, does the detection eval still fail?
   - if it touches an input, artifact, or channel, read the Input Coverage
     section of `docs/build-map.md` and identify the real stage gap
   - is this a signal that a compromise can be deleted?
   - what if we do not create a dedicated story?
   - is there already a natural home in an existing draft or pending story?

   Possible outcomes:
   - Fold into existing story
   - New story
   - Research spike
   - ADR
   - Spec update
   - Ideal update
   - Note on existing story
   - Scout expedition
   - Backlog/defer
   - Discard

6. **Create artifacts immediately in processing mode**
   For each decision, create the appropriate artifact before moving on.

7. **Delete processed inbox items in processing mode**
   Once an item lands in a story, spec, ADR, or is explicitly discarded, remove
   it from the inbox instead of archiving it there.

8. **Summarize**
   Quick summary of what was processed, what was deferred, and any follow-up
   actions.

## Handling Links and Resources

Inbox items are often just a URL pasted in a hurry.

When triaging a link-only or link-heavy item:

1. **Quick read** — fetch the content and understand what it is
2. **Summarize and assess**
   - what it is
   - why it matters here
   - value: HIGH / MEDIUM / LOW
3. **Recommend an action**
   - scout expedition
   - story/spike
   - spec update
   - note on existing story
   - defer
   - discard
4. **Wait for user** — do not auto-scout

## Guardrails

- Processing mode may modify files; scan mode may not
- Always discuss with the user before creating artifacts in processing mode
- Keep the inbox clean — every processed item should land somewhere or be discarded
- For link items: quick-read and recommend, do not auto-launch a full scout
- When used by `/triage`, prefer `scan` mode unless the user explicitly asked to process the inbox now
