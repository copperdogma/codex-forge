---
name: improve-eval
description: Investigate eval failures, classify whether the prompt/pipeline or test/golden is wrong, improve the result, and record verified scores
user-invocable: true
---

# /improve-eval [eval-id] [--autonomous]

> Alignment check: Before choosing an approach, verify it aligns with `docs/ideal.md` and relevant decision records in `docs/decisions/`. If this work touches a known compromise in `docs/spec.md`, respect its limitation type and evolution path. If none apply, say so explicitly.

Structured improvement loop for a specific eval. This skill now absorbs the
former standalone verification workflow: raw scores are not final, and mismatches must
be classified before goldens or assertions are changed.

**Default behavior:** propose the best next eval and the likely approach, then
wait for user approval.
**Autonomous mode:** if the user says "pick and do it" or passes
`--autonomous`, choose the best candidate and execute without a second gate.

## Arguments

- **eval-id** (optional but strongly preferred): the `id` field from
  `docs/evals/registry.yaml` (for example, `image-crop-extraction`).
- **--autonomous**: skip the user-approval gate after planning.

## Phase 0 — Situational Awareness

1. **Record the worker model** — note which model is doing the improvement work.
2. **Read the registry** — load `docs/evals/registry.yaml`.
3. **Read current git state** — capture `git rev-parse --short HEAD`.
4. **Verify live model or pricing claims when they matter** — if a retry depends
   on `new-subject-model`, `cheaper-subject-model`, or `faster-subject-model`,
   confirm it with current official provider docs or a fresh web search before
   claiming the trigger is met.
5. **Read the relevant local runbook when applicable** — for example,
   `docs/runbooks/golden-build.md` or `docs/runbooks/crop-eval-workflow.md`.

## Phase 1 — Pick or Confirm the Candidate

6. **Handle focused mode if `eval-id` was provided** — find that eval entry.
   If it does not exist, list available eval IDs and stop.

7. **If no eval was provided, rank candidates** using this priority:
   - retry-ready failed attempts whose `retry_when` conditions are now met
   - stale scores measured far from current `HEAD`
   - largest gap to target
   - compromise-detection evals with no meaningful baseline yet

8. **Show current state**:
   - name, type, description
   - target metric(s) and threshold(s)
   - best recorded score(s) versus target
   - latency / cost if tracked
   - gap and likely failure dimension

9. **Check pass / no-action gate** — if the eval already passes all relevant
   target dimensions and there is no open latency/cost issue, report
   `No action needed` and stop.

10. **Check staleness** — if a score records `git_sha` and it differs
    materially from current `HEAD`, flag re-measurement before deep diagnosis.

11. **Present the ranked candidate list** if no eval was supplied. Wait for the
    user to pick unless `--autonomous` is active.

## Phase 2 — Study History and Inputs

12. **Read prior attempts** — for the selected eval, list each attempt with:
    date, approach, score before/after, status, and `retry_when`.

13. **Classify retry state**:
    - **Blocked** — a failed approach whose `retry_when` conditions are not met
    - **Retry-ready** — a failed approach whose `retry_when` conditions are now met
    - **Fresh** — an approach not yet tried

14. **Read the eval implementation surface** — config, scorer, prompt, golden,
    and any relevant module or recipe under test. Do not reason from registry
    metadata alone.

15. **Summarize the failure mode** — what is actually failing, and why does the
    current score still miss the target?

## Phase 3 — Plan the Attempt

16. **Propose 1-3 candidate approaches** that are either fresh or retry-ready.
    For each, state:
    - what would change
    - expected quality / cost / latency impact
    - risk level
    - why it is allowed under retry discipline

17. **Prompt-first rule** — before escalating to a bigger or costlier subject
    model, consider prompt / instruction / output-contract fixes first. If you
    skip prompt-first, explain why.

18. **User gate** — present the plan and wait for approval unless
    `--autonomous` is active.

## Phase 4 — Classify Failures Before Fixing Them

19. **Treat raw scores as provisional** — every failing case or mismatch needs a
    classification before you edit the prompt, scorer, or golden.

20. **Classify each failure at the top level**:
    - **prompt/pipeline-wrong** — the subject prompt, model choice, pipeline
      logic, or output formatting is the real problem
    - **test-wrong** — the scorer, rubric, or golden is wrong or incomplete
    - **ambiguous** — evidence is insufficient or reasonable interpretations differ

21. **If the failure looks test-related, do the former standalone verification pass inline**
    before changing the golden:
    - build a mismatch table
    - compare actual output to the source material
    - sub-classify each mismatch as:
      - **model-wrong**
      - **golden-wrong**
      - **ambiguous**

22. **Golden-change consultation rules**:
    - always ask the user before structural golden changes
    - always ask if fixes would change more than 5% of cases
    - minor factual corrections can proceed without a second round-trip

23. **Cost discipline for reruns**:
    - use cached subject-model outputs when only the scorer or golden changed
    - drop the expensive judge while iterating if deterministic checks are enough
    - filter to the relevant provider or cases when debugging one failure
    - reserve `--no-cache` for prompt changes or the final verification run

## Phase 5 — Execute

24. **Baseline measurement** — run the eval or scoped test to establish the
    before-state if the current score is stale or insufficiently trustworthy.

25. **Implement the approved changes** — prompt, code, scorer, golden, config,
    or model selection as appropriate.

26. **Re-measure** — rerun the eval with the right cache strategy and record the
    after-state.

27. **If goldens changed, produce verified scores** — explicitly report
    raw versus verified results after the golden/scorer correction.

## Phase 6 — Record

28. **Update `docs/evals/registry.yaml`**:
    - add or refresh the score entry with measured date and `git_sha`
    - append an attempt entry in the existing local style, including:
      `id`, `date`, `status`, `approach`, `score_before`, `score_after`,
      optional model notes, and `retry_when` if it failed

29. **Update the work log** — if this happened under a story, add the verified
    outcome there too, including mismatch classification when relevant.

## Phase 7 — Assess and Report

30. **Compare to target**:
    - if passing, state that explicitly
    - if still failing, show the remaining gap and whether the next step is
      another attempt, a blocked wait, or a new story

31. **Summarize**:
    - what was tried
    - what changed
    - score / latency / cost delta
    - whether any mismatches were `model-wrong`, `golden-wrong`, or `ambiguous`
    - what not to retry next time if this failed

## Guardrails

- Never retry a blocked approach.
- Always measure before and after.
- Do not change files before the approval gate unless `--autonomous` is active.
- Record failed attempts as carefully as successful ones.
- Do not skip mismatch classification when the eval uses a golden or rubric.
- The separate verification skill is retired; do the verification work inside this skill.
- Do not commit or push without explicit user request.
