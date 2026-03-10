# /format-gap-analysis [--format <id>] [--force-benchmark]

Diagnose format conversion quality gaps and prioritize what to build next.

This is a purely analytical skill. It reads existing data, diagnoses gaps, and proposes
stories. It never runs pipelines or modifies code.

## Arguments

- `--format <id>` — Focus on a single format from `_coverage-matrix.json` (e.g., `scanned-pdf-prose`)
- `--force-benchmark` — Run benchmarks before diagnosis (delegates to eval tools, does not run inline)

## Phase 1 — Data Currency Check

Before diagnosing, verify the data is fresh:

1. Read `tests/fixtures/formats/_coverage-matrix.json` — the machine-readable format inventory.
2. Read `docs/format-registry.md` — the human-readable status document.
3. For each format with `status: "passing"`:
   - Check `scores.measured` date. Flag if older than 30 days.
   - Check if pipeline recipe or intake module has changed since last measurement (git log on the recipe file).
4. For each format with `status: "has-fixture"`:
   - Verify the fixture path exists and is non-empty.
5. Report data currency status before proceeding.

If `--force-benchmark` is set, advise the user to run the relevant eval before continuing.

## Phase 2 — Diagnose

For each format (or the single `--format` target):

1. **Passing formats** — Check each accuracy dimension against targets:
   - `text_fidelity` target: ≥ 0.99
   - `structure_preservation` target: ≥ 0.95
   - `illustration_extraction` target: ≥ 0.95
   - `provenance_completeness` target: 1.0
   - Flag any dimension below target as a gap.
2. **Has-fixture formats** — Identify what's blocking the pipeline:
   - Missing intake module?
   - Missing recipe?
   - Pipeline errors?
3. **Untested formats** — Assess readiness:
   - Does a test fixture exist? If not, what would a good fixture look like?
   - Is there an existing module that could handle this format with minor changes?
   - What's the estimated effort to build a pipeline?

4. **Graduation check** — For passing formats, check if ALL graduation criteria are met
   (see `docs/format-registry.md` § Graduation Criteria). Flag candidates.

For each gap found, identify:
- **Root cause**: Why is the score low or the pipeline missing?
- **Fix category**: One of:
  - `golden-correction` — Test fixture or golden reference needs fixing
  - `pipeline-improvement` — Existing module needs enhancement
  - `new-intake-module` — New module needed for this format
  - `prompt-engineering` — Better prompts for existing AI calls
  - `model-selection` — Try a different/better model
  - `architecture-limitation` — Fundamental approach change needed

## Phase 3 — Categorize & Prioritize

Rank all gaps by ROI using:

```
priority_score = (score_lift × breadth) / effort
```

Where:
- `score_lift` — Expected improvement in the weakest dimension (0.0–1.0)
- `breadth` — How many formats benefit (1 = single format, 5+ = cross-cutting)
- `effort` — Estimated story points (1 = quick fix, 5 = multi-story arc)

Group into tiers:
- **Quick wins** — High lift, low effort, single story
- **Strategic investments** — High lift, medium effort, unlocks new format family
- **Long-term** — Architecture changes, model improvements, or blocked on external factors

## Phase 4 — Propose

For each prioritized gap:

1. Draft a story proposal (title, goal, key ACs) — do NOT create stories directly.
2. Map to existing gaps in `docs/format-registry.md` (update if new gaps found).
3. Check `docs/evals/registry.yaml` for relevant eval history.

## Phase 5 — Report

Present findings in this structure:

```
## Data Currency
- [status for each format checked]

## Gaps (Prioritized)

### 1. [Gap Title] — [format-id]
- **Current score:** X.XX → **Target:** Y.YY
- **Root cause:** ...
- **Fix category:** ...
- **Priority score:** Z.ZZ (lift × breadth / effort)
- **Proposed story:** `/create-story "Title" --priority P`

### 2. ...

## Graduation Candidates
- [Formats meeting all graduation criteria from docs/format-registry.md]

## Regressions
- [Any scores that dropped since last measurement]

## Recommendations
- [Top 3 actions ordered by ROI]
```

## Guardrails

- **Never run pipelines or benchmarks directly** — this is a diagnostic skill only.
- **Never auto-create stories** — present proposals for user decision.
- **Never conclude "AI can't do this"** from a cheap model's failure — check if SOTA was tried.
- **Always check data freshness** before diagnosing — stale scores lead to wrong priorities.
- **Treat every golden fixture as the 100% target** — don't lower the bar.
- **Cross-reference with `docs/evals/registry.yaml`** — don't propose work that's already been tried and blocked.
