---
name: triage
description: Orchestrate the triage leaf skills and synthesize the highest-value next action
user-invocable: true
---

# /triage [stories|inbox|evals] [sub-arg]

> Alignment check: Before choosing an approach, verify it aligns with `docs/ideal.md` and relevant decision records in `docs/decisions/`. If this work touches a known compromise in `docs/spec.md`, respect its limitation type and evolution path. If none apply, say so explicitly.

`/triage` is the meta-skill. It does not own the backlog, inbox, or eval logic
itself. It routes to the leaf skills and, in full-sweep mode, synthesizes one
recommended next action.

## Routing

| Invocation | Behavior |
|---|---|
| `/triage` | Full-sweep orchestrator mode |
| `/triage stories` | Delegate to `/triage-stories` |
| `/triage stories 145` | Delegate to `/triage-stories 145` |
| `/triage inbox` | Delegate to `/triage-inbox` (processing mode) |
| `/triage inbox scan` | Delegate to `/triage-inbox scan` (read-only mode) |
| `/triage evals` | Delegate to `/triage-evals` |
| `/triage evals image-crop-extraction` | Delegate to `/triage-evals image-crop-extraction` |

When a scope is provided, hand off completely to the leaf skill. Do not
maintain duplicate logic here.

## Leaf Skills

- `/triage-stories` — backlog prioritization, readiness, dependency bottlenecks
- `/triage-inbox` — inbox scan or processing
- `/triage-evals` — eval health, rerun candidates, compromise deletion signals

## Full-Sweep Mode

When invoked with no scope:

1. **Read the shared frame**
   - `docs/ideal.md`
   - `docs/spec.md`
   - `docs/build-map.md`
   - relevant ADRs under `docs/decisions/`
   - recent `git log --oneline -20`

2. **Run leaf sweeps in parallel**
   - `/triage-stories`
   - `/triage-inbox scan`
   - `/triage-evals`

3. **Collect leaf reports**
   Each report should return:
   - one top recommendation
   - 1-3 supporting reasons
   - health flags / bottlenecks
   - whether the recommendation is read-only or action-taking

4. **Synthesize one cross-domain recommendation**
   Choose the next action with the strongest combined signal across:
   - Ideal alignment
   - blocking power / dependency leverage
   - compromise-elimination leverage
   - urgency / staleness
   - momentum from recent work
   - operator cost

5. **Return the compact report**

```markdown
## Triage

### Recommended Action
- {one next action}

### Why
- {2-3 strongest reasons}

### Runner-Ups
- {alternate action}
- {alternate action}

### Domain Notes
- Stories: {summary}
- Inbox: {summary}
- Evals: {summary}

### Health Flags
- {blocked story / stale inbox / stale eval / pending ADR}
```

## Guardrails

- Scoped invocations delegate; do not duplicate leaf logic here.
- Full-sweep mode is read-only.
- Use parallel leaf sweeps when feasible.
- Return one recommendation, not a vague list.
- Respect leaf-skill boundaries: `/triage inbox` may modify files; unscoped
  `/triage` may not.
