# Story 140 — Onward Targeted Genealogy Table Rescue Fidelity

**Priority**: High
**Status**: Pending
**Ideal Refs**: Requirement #3 (Extract), Requirement #6 (Validate), Fidelity to Source
**Spec Refs**: C1 (Multi-Stage OCR Pipeline), C3 (Heuristic + AI Layout Detection), C6 (Expensive OCR for Quality)
**Decision Refs**: Story 128 work log, Story 131 eval results, Story 138 residual review evidence; none found after search in `docs/runbooks/`, `docs/scout/`, or `docs/notes/`
**Depends On**: Story 138, Story 131

## Goal

Fix the remaining within-table fidelity failures that still appear after Story 138's chapter-boundary work. The problem is no longer whole-table ownership; it is upstream table rescue quality on a small suspect-page set where family subheaders, child rows, or root table rows are still malformed before final HTML build. This story should improve those pages upstream without reopening the now-fixed chapter-splitting behavior.

## Acceptance Criteria

- [ ] In the current verification run, the reviewed Arthur tail table in `chapter-010.html` no longer ends with heading-only family stubs; family headings such as `RICHARD'S FAMILY`, `PAUL'S FAMILY`, and `VIVIAN'S FAMILY` retain their child rows in final HTML
- [ ] In the current verification run, the reviewed Roseanna and Emilie within-table regressions are structurally faithful in final HTML: Roseanna's tail is not left as loose/scattered paragraph data, and Emilie's table keeps the root heading plus reviewed family-table structure and summary counts without the current corruption
- [ ] The repair happens upstream of chapter build (targeted rescue and/or continuation repair), preserves provenance, and does not reintroduce the cross-family or same-family chapter-splitting regressions fixed in Story 138
- [ ] A fresh `driver.py` run is manually inspected for `chapter-010.html`, `chapter-018.html`, `chapter-020.html`, and adjacent chapter boundaries, with artifact paths and concrete sample data recorded in the work log

## Out of Scope

- Chapter ownership, stale-span carry-back, or TOC-boundary logic already addressed by Story 138
- Image placement, swapped captions, or frontmatter logo/seal issues
- Broad typography normalization across prose pages
- Hand-editing generated artifacts outside the pipeline
- Generalizing a new table architecture beyond a bounded suspect-page rescue/repair loop for this Onward converter

## Approach Evaluation

The problem is no longer "which chapter owns this table." The current evidence says a few rescued source pages are still structurally wrong before `build_chapter_html_v1` runs. The right story is therefore an upstream rescue-quality story with bounded scope and explicit validation against the existing reviewed pages.

- **Simplification baseline**: Targeted one-page re-rescue already has evidence. `gpt-4.1` materially improved Arthur source page `35` / printed page `26`, partially improved Emilie source pages `97-98` / printed pages `88-89`, and produced a mixed result on Roseanna source page `89` / printed page `80`. `gpt-5` rescue is now API-compatible but still produced blank output on Roseanna in the current experiment.
- **AI-only**: Reuse `table_rescue_onward_tables_v1` to re-rescue only the flagged suspect pages with the strongest model/prompt combination that actually improves structure. This is cheap relative to full OCR because the page set is tiny.
- **Hybrid**: Use deterministic detection or an explicit suspect-page allowlist to select pages, run targeted AI rescue, then apply conservative existing post-processing such as BOY/GIRL splitting and continuation-row repair. This is the leading candidate because it keeps the change upstream and bounded.
- **Pure code**: Paragraph-to-table reconstruction from scrambled lines is possible but risky. Current evidence from Roseanna shows the text order itself is noisy, so a code-only parser is likely to overfit unless rescue output first recovers line structure.
- **Repo constraints / prior decisions**: Reuse OCR artifacts instead of re-running expensive upstream OCR (`C6`). Keep the fix upstream of `build_chapter_html_v1` unless new evidence forces otherwise. Do not hardcode family names or page IDs into generic builder logic. Story 131 proved eval success on golden pages, but current manual review shows that score did not cover all real-run pages.
- **Existing patterns to reuse**: `modules/adapter/table_rescue_onward_tables_v1/main.py`, `modules/adapter/table_fix_continuations_v1/main.py`, `benchmarks/tasks/onward-table-fidelity.yaml`, Story 131's eval loop, and Story 138's reused-artifact driver validation pattern.
- **Eval**: The gate is reviewed-page fidelity in a real run plus, if practical, promoting the newly identified suspect pages into targeted regression/eval coverage. A candidate approach passes only if the final HTML improves the reviewed Arthur / Roseanna / Emilie table spans without reopening boundary regressions.

## Tasks

- [ ] Establish the precise baseline on the current suspect pages (`page_number` `35`, `89`, `97`, `98`, plus any newly justified additions): compare upstream rescued HTML, continuation-fixed HTML, and final chapter HTML; classify each failure as model-wrong, post-processing-wrong, or ambiguous
- [ ] Measure the simplest targeted rescue baseline with the existing Onward rescue module on the suspect pages using current viable models/prompts; record which pages improve, regress, or return unusable output
- [ ] Implement the highest-leverage bounded fix upstream of build:
  - likely in `table_rescue_onward_tables_v1`
  - only use `table_fix_continuations_v1` if rescue output is structurally close and only needs conservative cleanup
- [ ] Add focused regression coverage for the chosen fix, and promote the reviewed suspect pages into eval coverage if that is the cleanest guardrail
- [ ] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [ ] Run required checks for touched scope:
  - [ ] Focused tests for touched modules
  - [ ] Repo-wide Python checks: `python -m pytest tests/`
  - [ ] Repo-wide lint: `python -m ruff check modules/ tests/`
  - [ ] If pipeline behavior changed: clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and manually inspect sample HTML/JSONL data
- [ ] If evals or goldens changed: run `/verify-eval` and update `docs/evals/registry.yaml`
- [ ] Search all docs and update any related to what we touched
- [ ] Verify Central Tenets:
  - [ ] T0 — Traceability: every output traces to source page, OCR engine, confidence, processing step
  - [ ] T1 — AI-First: didn't write code for a problem AI solves better
  - [ ] T2 — Eval Before Build: measured SOTA before building complex logic
  - [ ] T3 — Fidelity: source content preserved faithfully, no silent losses
  - [ ] T4 — Modular: new recipe not new code; no hardcoded book assumptions
  - [ ] T5 — Inspect Artifacts: visually verified outputs, not just checked logs

## Workflow Gates

- [ ] Build complete: implementation finished, required checks run, and summary shared
- [ ] Validation complete or explicitly skipped by user
- [ ] Story marked done via `/mark-story-done`

## Architectural Fit

- **Owning module / area**: Upstream Onward table rescue in the adapter layer. `build_chapter_html_v1` should remain stable unless fresh evidence shows a new downstream ownership bug.
- **Data contracts / schemas**: Likely no schema change if the story only improves `html` payloads and existing rescue metadata. If new rescue provenance fields need to survive stamping, they must be added to `schemas.py` first.
- **File sizes**: `modules/adapter/table_rescue_onward_tables_v1/main.py` is 558 lines and already over the 500-line threshold; keep changes tight and consider extracting helpers if the logic grows. `modules/adapter/table_fix_continuations_v1/main.py` is 177 lines. `benchmarks/tasks/onward-table-fidelity.yaml` is 61 lines. `docs/evals/registry.yaml` is 366 lines. `tests/test_table_rescue_onward_tables_v1.py` is 63 lines. `tests/test_build_chapter_html.py` is 867 lines, so prefer a new focused rescue regression file over further growth there.
- **Decision context**: Reviewed `docs/ideal.md`, Story 128, Story 131, and Story 138 evidence. No directly applicable runbook, scout, or notes decision doc was found for this exact suspect-page rescue problem.

## Files to Modify

- `modules/adapter/table_rescue_onward_tables_v1/main.py` — targeted suspect-page rescue selection, prompt/model handling, and bounded post-rescue cleanup (558 lines)
- `modules/adapter/table_fix_continuations_v1/main.py` — only if rescued rows are structurally close and need conservative continuation repair (177 lines)
- `tests/test_table_rescue_onward_tables_v1.py` — module-level rescue request/repair coverage (63 lines)
- `tests/test_onward_targeted_table_rescue.py` — new focused regression coverage for suspect-page HTML patterns (new file)
- `benchmarks/tasks/onward-table-fidelity.yaml` — add suspect-page coverage if the story formalizes these pages into the benchmark set (61 lines)
- `docs/evals/registry.yaml` — record new eval/baseline attempts if benchmark coverage expands (366 lines)
- `docs/stories/story-138-onward-genealogy-table-continuation-and-header-regressions.md` — cross-reference the split if implementation changes the handoff point (301 lines)

## Redundancy / Removal Targets

- No repo removal target is known yet
- Do not fossilize the local `/tmp/story138-*-rerescue-*` recipe and artifact experiments into the repo; either formalize a reusable workflow or keep them ephemeral

## Notes

- Current reviewed evidence:
  - `story138-onward-stale-span-validate-r2` is the cleanest baseline for the fixed chapter-boundary behavior
  - `story138-onward-stale-span-validate-r3` should not be treated as the preferred baseline because the one-page Roseanna rescue introduced a worse within-table regression there
  - `story138-onward-stale-span-validate-r4` shows targeted `gpt-4.1` re-rescue can materially improve Arthur page `26`, but Emilie pages `88-89` remain mixed and Roseanna is still unresolved
- The story should optimize for a bounded reviewed-page set first. If a generic suspect-page detector emerges cleanly during implementation, that can be absorbed; otherwise prefer explicit reviewed-page targeting within the Onward converter rather than pretending the problem is solved generically.

## Plan

To be written during `/build-story` after the eval-first exploration on the current suspect pages.

## Work Log

20260313-1539 — story created: split residual within-table rescue fidelity out of Story 138 by user request, using current review evidence from `story138-onward-stale-span-validate-r2` / `r3` / `r4`; next step is `/build-story` to choose the bounded upstream rescue approach with evidence
