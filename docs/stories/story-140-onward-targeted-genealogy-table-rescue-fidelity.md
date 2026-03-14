# Story 140 — Onward Targeted Genealogy Table Rescue Fidelity

**Priority**: High
**Status**: Done
**Ideal Refs**: Requirement #3 (Extract), Requirement #6 (Validate), Fidelity to Source
**Spec Refs**: C1 (Multi-Stage OCR Pipeline), C3 (Heuristic + AI Layout Detection), C6 (Expensive OCR for Quality)
**Decision Refs**: Story 128 work log, Story 131 eval results, Story 138 residual review evidence; none found after search in `docs/runbooks/`, `docs/scout/`, or `docs/notes/`
**Depends On**: Story 138, Story 131

## Goal

Fix the remaining within-table fidelity failures that still appear after Story 138's chapter-boundary work. The problem is no longer whole-table ownership; it is primarily upstream table rescue quality on a small suspect-page set where family subheaders, child rows, or root table rows are still malformed before final HTML build. This story should improve those reviewed pages without reopening the now-fixed chapter-splitting behavior, while allowing a narrow recipe-scoped build-stage fallback if real-run validation shows that final chapter HTML still fragments same-schema genealogy continuity.

## Acceptance Criteria

- [x] In the current verification run, the reviewed Arthur tail table in `chapter-010.html` no longer ends with heading-only family stubs; family headings such as `RICHARD'S FAMILY`, `PAUL'S FAMILY`, and `VIVIAN'S FAMILY` retain their child rows in final HTML
- [x] In the current verification run, the reviewed Roseanna and Emilie within-table regressions are structurally faithful in final HTML: Roseanna's tail is not left as loose/scattered paragraph data, and Emilie's table keeps the root heading plus reviewed family-table structure and summary counts without the current corruption
- [x] The shipped repair happens primarily upstream of chapter build (targeted rescue and/or continuation repair); any build-stage continuity fallback remains recipe-scoped, preserves provenance, and does not reintroduce the cross-family or same-family chapter-splitting regressions fixed in Story 138
- [x] A fresh `driver.py` run is manually inspected for `chapter-010.html`, `chapter-018.html`, `chapter-020.html`, and adjacent chapter boundaries, with artifact paths and concrete sample data recorded in the work log

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

- [x] Establish the precise baseline on the current suspect pages (`page_number` `35`, `89`, `97`, `98`, plus any newly justified additions): compare upstream rescued HTML, continuation-fixed HTML, and final chapter HTML; classify each failure as model-wrong, post-processing-wrong, or ambiguous
- [x] Measure the simplest targeted rescue baseline with the existing Onward rescue module on the suspect pages using current viable models/prompts; record which pages improve, regress, or return unusable output
- [x] Implement the highest-leverage bounded fix upstream of build:
  - [x] likely in `table_rescue_onward_tables_v1`
  - [x] only use `table_fix_continuations_v1` if rescue output is structurally close and only needs conservative cleanup
- [x] Add focused regression coverage for the chosen fix, and promote the reviewed suspect pages into eval coverage if that is the cleanest guardrail
- [x] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [x] Run required checks for touched scope:
  - [x] Focused tests for touched modules
  - [x] Repo-wide Python checks: `python -m pytest tests/`
  - [x] Repo-wide lint: `python -m ruff check modules/ tests/`
  - [x] If pipeline behavior changed: clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and manually inspect sample HTML/JSONL data
- [x] If evals or goldens changed: run `/verify-eval` and update `docs/evals/registry.yaml` (new hand-validated page goldens were added and scored directly against real artifacts; the registry now records the added page-golden coverage even though Story 140 did not run a fresh full promptfoo model sweep)
- [x] Search all docs and update any related to what we touched
- [x] Verify Central Tenets:
  - [x] T0 — Traceability: every output traces to source page, OCR engine, confidence, processing step
  - [x] T1 — AI-First: didn't write code for a problem AI solves better
  - [x] T2 — Eval Before Build: measured SOTA before building complex logic
  - [x] T3 — Fidelity: source content preserved faithfully, no silent losses
  - [x] T4 — Modular: new recipe not new code; no hardcoded book assumptions
  - [x] T5 — Inspect Artifacts: visually verified outputs, not just checked logs

## Workflow Gates

- [x] Build complete: implementation finished, required checks run, and summary shared
- [x] Validation complete or explicitly skipped by user
- [x] Story marked done via `/mark-story-done`

## Architectural Fit

- **Owning module / area**: Primarily upstream Onward table rescue in the adapter layer, with a recipe-scoped build merge now added after manual review showed that final chapter HTML could still fragment same-schema genealogy runs even when page-level rescue was acceptable.
- **Data contracts / schemas**: Likely no schema change if the story only improves `html` payloads and existing rescue metadata. If new rescue provenance fields need to survive stamping, they must be added to `schemas.py` first.
- **File sizes**: `modules/adapter/table_rescue_onward_tables_v1/main.py` is 558 lines and already over the 500-line threshold; keep changes tight and consider extracting helpers if the logic grows. `modules/adapter/table_fix_continuations_v1/main.py` is 177 lines. `benchmarks/tasks/onward-table-fidelity.yaml` is 61 lines. `docs/evals/registry.yaml` is 366 lines. `tests/test_table_rescue_onward_tables_v1.py` is 63 lines. `tests/test_build_chapter_html.py` is 867 lines, so prefer a new focused rescue regression file over further growth there.
- **Decision context**: Reviewed `docs/ideal.md`, Story 128, Story 131, and Story 138 evidence. No directly applicable runbook, scout, or notes decision doc was found for this exact suspect-page rescue problem.

## Files to Modify

- `modules/adapter/table_rescue_onward_tables_v1/main.py` — targeted suspect-page rescue selection, prompt/model handling, and bounded post-rescue cleanup (558 lines)
- `modules/adapter/table_rescue_onward_tables_v1/module.yaml` — expose any new recipe-facing rescue knobs cleanly if the module grows beyond the current fixed prompt/defaults
- `modules/adapter/table_fix_continuations_v1/main.py` — only if rescued rows are structurally close and need conservative continuation repair (177 lines)
- `configs/recipes/recipe-onward-images-html-mvp.yaml` — recipe-scoped suspect-page targeting and chosen rescue-model/prompt params for the Onward converter
- `modules/build/build_chapter_html_v1/main.py` — optional recipe-scoped final HTML merge for contiguous same-schema genealogy tables when chapter assembly still fragments reviewed outputs
- `modules/build/build_chapter_html_v1/module.yaml` — expose the build-stage genealogy merge as an explicit recipe knob
- `tests/test_table_rescue_onward_tables_v1.py` — module-level rescue request/repair coverage (63 lines)
- `tests/test_onward_targeted_table_rescue.py` — new focused regression coverage for suspect-page HTML patterns (new file)
- `tests/test_build_chapter_html.py` — build-stage genealogy merge regressions for flattened contextual headings and CLI wiring
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
- Remaining chapter-level consistency issues later confirmed in `story140-onward-targeted-rescue-r19` are intentionally split to `Story 141`, so Story 140 stays closed around the narrower shipped rescue + guarded continuity slice rather than silently expanding into a broader normalization story.

## Plan

### Exploration Findings

- Resolved the actual dependency files and evidence chain on disk: `story-128-onward-table-fidelity-verification.md`, `story-131-onward-table-structure-fidelity.md`, and `story-138-onward-genealogy-table-continuation-and-header-regressions.md`.
- The current review baseline is `story138-onward-stale-span-validate-r4`. `python tools/run_registry.py check-reuse --run-id story138-onward-stale-span-validate-r4 --scope html` reports `run_status="done"` with no fatal signals, but no recorded assessment yet, so the run is usable as evidence but not formally blessed for reuse.
- Arthur source `page_number=35` / printed `26` is already materially improved in `r4` upstream rescue and final HTML. `chapter-010.html` now contains `RICHARD'S FAMILY`, `PAUL'S FAMILY`, and `VIVIAN'S FAMILY` with child rows, so this page is now primarily a regression guard, not the main open defect.
- Roseanna source `page_number=89` / printed `80` is still wrong upstream in `r4`: `02_load_artifact_v1/pages_html_onward_tables.jsonl` has zero `<table>` elements, `05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl` is identical, and `chapter-018.html` still falls back to loose paragraph data after the first good table. This is model-wrong, not continuation-fix-wrong.
- Emilie source `page_number=97` / printed `88` is partially improved upstream in `r4`: the root heading/table is present, but the structure is still malformed before build. `table_fix_continuations_v1` only moves `Mar. 13, 1986` from the `Herve P.` row to the continuation row; it does not repair the larger table shape. This is model-wrong with one narrow post-processing repair already working.
- Emilie source `page_number=98` / printed `89` is still structurally wrong upstream in `r4`: the rescue output is fragmented into many small tables and heading paragraphs, continuation repair is byte-identical, and `chapter-020.html` keeps the root heading and summary counts but still shows corrupted family-table structure. This is model-wrong.
- Fresh standalone `gpt-4.1` rescue on suspect pages `35,89,97,98` reproduced the same overall ranking but not the exact earlier `r4` artifact. It materially improved only `1/4` pages, repeated the mixed Roseanna result, and still left Emilie structurally corrupt. Page `35` also drifted from the earlier better-looking rescue artifact, which means the current targeted retry path needs an acceptance guard instead of blindly trusting the latest model output.
- A bounded fresh `gpt-5` standalone sweep on the same page set did not finish with artifacts before being stopped, which is consistent with Story 138's recorded evidence that `gpt-5` produced unusable/blank Roseanna output in the current experiment lineage.
- The existing promptfoo eval does not cover Roseanna or Emilie. Promoting those pages into `benchmarks/tasks/onward-table-fidelity.yaml` would require new hand-validated goldens, so the lower-cost guardrail for this story is focused regression tests around rescue acceptance/scoring logic. Benchmark expansion remains optional if the output stabilizes cleanly.

### Ideal Alignment Gate

- This story closes a direct Ideal gap: the final HTML is still not faithfully preserving a small reviewed set of genealogy tables even after chapter ownership is fixed.
- The highest-leverage move still points upstream and AI-first: the evidence says the open defects are in rescued page HTML before chapter build, so more builder logic would move away from the Ideal.
- No new compromise is required if the targeted rescue path stays bounded, recipe-scoped, and provenance-preserving.

### Eval / Baseline

- Current verification baseline on `story138-onward-stale-span-validate-r4`: `1/3` reviewed final-HTML targets currently pass.
  - Arthur (`chapter-010.html`) = pass
  - Roseanna (`chapter-018.html`) = fail
  - Emilie (`chapter-020.html`) = fail
- Current suspect-page stage baseline in `r4`:
  - `page_number=35` = pass after prior targeted `gpt-4.1` re-rescue
  - `page_number=89` = fail upstream (`0` tables before and after continuation repair)
  - `page_number=97` = partial upstream recovery, still fail overall
  - `page_number=98` = fail upstream, unchanged by continuation repair
- Fresh standalone rescue baseline with the existing module:
  - `gpt-4.1` attempted `4/4` suspect pages and produced usable artifacts, but only `1/4` pages was materially improved enough to look promising; `3/4` remained unresolved or mixed
  - `gpt-5` did not produce a completed bounded artifact sweep before being stopped; treat it as non-viable until new evidence appears

### Implementation Plan

#### Task 1 — Harden targeted rescue in `table_rescue_onward_tables_v1`

- Files: `modules/adapter/table_rescue_onward_tables_v1/main.py`, `modules/adapter/table_rescue_onward_tables_v1/module.yaml`
- Change:
  - Add an explicit, recipe-scoped way to target the reviewed suspect pages in normal driver runs instead of relying on ad hoc `/tmp` experiments.
  - Extend the rescue prompt path so the model can see the current extracted HTML/text for the page alongside the image when doing a targeted retry. Right now the module sends only the image plus a fixed generic prompt, which leaves Roseanna and Emilie without any guidance from the already-extracted row fragments.
  - Add a conservative candidate-acceptance check that compares the rescued HTML against the existing page HTML and only replaces the page when structural signals improve. Candidate acceptance should be driven by generic signals such as: table/header presence, row count floor, retention of family-heading rows and summary rows, penalties for paragraph-only tails, and penalties for merged `BOY/GIRL` or slash-count artifacts.
- Risk:
  - An acceptance check that is too weak could approve prettier but less faithful HTML.
  - An acceptance check that is too strict could reject a candidate that is genuinely better but structurally different.
- Done when:
  - The chosen retry path can improve Roseanna/Emilie without regressing Arthur, and the module can reject fresh model drift that is worse than the current best artifact.

#### Task 2 — Only extend continuation repair if a narrow deterministic fix emerges

- File: `modules/adapter/table_fix_continuations_v1/main.py`
- Change:
  - Keep this file out of scope unless the targeted rescue output becomes structurally close and only needs conservative row-shift cleanup like the existing `DIED` move on page `97`.
  - If we touch it, the change must be generic and fixture-backed. Do not use family-name or page-number logic here.
- Risk:
  - This module is intentionally narrow; broadening it without strong evidence would re-create the downstream patching problem Story 140 is trying to avoid.
- Done when:
  - Either no change is needed, or a small deterministic cleanup is proven on a concrete failing fixture and leaves Roseanna/Emilie closer to source fidelity.

#### Task 3 — Add focused regression coverage instead of immediately expanding promptfoo

- Files: `tests/test_table_rescue_onward_tables_v1.py`, `tests/test_onward_targeted_table_rescue.py`
- Change:
  - Add unit coverage for any new prompt-building or candidate-acceptance helpers in `table_rescue_onward_tables_v1`.
  - Add fixture-backed regressions for the reviewed patterns:
    - Arthur-style heading-only tail should be treated as worse than the accepted `r4` structure.
    - Roseanna paragraph-only tail should not be accepted as a good rescue result.
    - Emilie fragmented multi-table/heading output should fail the acceptance guard unless structure materially improves.
    - Fresh-model drift should not overwrite a previously better rescue artifact.
- Risk:
  - If the acceptance logic stays too implicit, the tests will be hard to keep meaningful. Keep the scoring/check contract small and explicit.
- Done when:
  - The new tests fail on the current unsafe acceptance behavior and pass once the rescue decision path is locked down.

#### Task 4 — Wire the chosen rescue strategy into the Onward recipe and rerun from the rescue stage

- Files: `configs/recipes/recipe-onward-images-html-mvp.yaml`, resumed run-local recipe/config under `output/runs/`
- Change:
  - Put the chosen suspect-page targeting and rescue-model params into the actual Onward recipe so the fix ships as pipeline configuration, not a one-off shell command.
  - Reuse existing OCR/page-number artifacts and rerun from `onward_table_rescue` (or an equivalent `load_artifact_v1` resume recipe) through `table_fix_continuations` and `build_chapter_html_v1`.
  - Clear stale `*.pyc` before the rerun and manually inspect `chapter-010.html`, `chapter-018.html`, `chapter-020.html`, plus adjacent chapter boundaries.
- Risk:
  - A recipe-scoped suspect-page list can become silent tech debt if it is not documented and tested.
  - A re-rescue that improves Roseanna/Emilie could still reopen chapter-boundary regressions if the wrong upstream artifact set is loaded.
- Done when:
  - A fresh driver run produces improved upstream page HTML and improved final chapter HTML for the reviewed pages, while `chapter-017.html`/`chapter-019.html`/`chapter-021.html` still respect Story 138's ownership fixes.

#### Task 5 — Validation, docs, and optional eval registry updates

- Files: story docs, optional benchmark/eval files only if goldens actually change
- Change:
  - Run focused tests during implementation, then repo-wide `pytest` and `ruff`.
  - Update Story 140 and any touched docs with artifact paths and manual inspection evidence.
  - Only update `benchmarks/tasks/onward-table-fidelity.yaml` and `docs/evals/registry.yaml` if we actually create new reviewed goldens for Roseanna/Emilie.
- Done when:
  - The story has real driver evidence, manual artifact inspection, and no unrecorded gaps.

### Scope Adjustment

- Small coherent scope expansion absorbed: `configs/recipes/recipe-onward-images-html-mvp.yaml` and `modules/adapter/table_rescue_onward_tables_v1/module.yaml` need to be treated as first-class story files, because the likely fix must ship as recipe-scoped rescue policy rather than another hidden `/tmp` experiment.
- Small coherent scope contraction absorbed: promptfoo expansion is no longer the default guardrail for this slice. Until new hand-validated goldens exist, focused regression fixtures are the cleaner eval for Story 140.

### Human Approval Gate

- No new dependencies are anticipated.
- Avoid a schema change unless rescue provenance must survive in stamped page rows. Existing report artifacts may be sufficient.
- Main risks to watch:
  - model drift across identical targeted retries;
  - acceptance heuristics that are either too permissive or too strict;
  - fixing Roseanna/Emilie in a way that silently reopens Story 138 boundary behavior.
- Success is falsified if a fresh driver run still leaves Roseanna as loose paragraphs, leaves Emilie's family-table structure materially corrupt, or reintroduces cross-chapter table bleed.

## Work Log

20260313-1539 — story created: split residual within-table rescue fidelity out of Story 138 by user request, using current review evidence from `story138-onward-stale-span-validate-r2` / `r3` / `r4`; next step is `/build-story` to choose the bounded upstream rescue approach with evidence
20260313-1625 — exploration + eval baseline grounded the story in the live suspect-page artifacts and narrowed the likely fix to upstream targeted rescue acceptance
- **Result:** Verified the live failure chain on the actual `r4` artifacts, ran a fresh bounded `gpt-4.1` rescue sweep on suspect pages `35,89,97,98`, and confirmed that the open work is no longer chapter build or broad continuation repair. The problem is bounded upstream rescue quality plus lack of a guard against unstable targeted retries.
- **Impact:**
  - **Story-scope impact:** Arthur is now clearly a regression guard rather than the main blocker; Roseanna and Emilie remain the only reviewed failures that must be fixed to close the story.
  - **Pipeline-scope impact:** The evidence now says the pipeline needs a safer targeted rescue handoff, not more build-stage logic. `table_fix_continuations_v1` only contributes a narrow row shift on Emilie page `97`; it is not the right primary seam for Roseanna or page `98`.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/02_load_artifact_v1/pages_html_onward_tables.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/output/html/chapter-018.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/output/html/chapter-020.html`, `/tmp/story140-build-story-gpt41.jsonl`, `/tmp/story140-build-story-gpt41-report.jsonl`
  - **Next:** After approval, implement the targeted rescue acceptance path in `table_rescue_onward_tables_v1`, wire it into the Onward recipe, and rerun from the rescue stage through final HTML. Success is falsified if Roseanna remains paragraph-only or Emilie remains fragmented after the fresh driver validation run.
20260313-1648 — implemented targeted contextual rescue acceptance, validated through `driver.py`, and closed the reviewed within-table fidelity gap
- **Result:** Added context-aware targeted rescue plus candidate acceptance scoring to `table_rescue_onward_tables_v1`, wired the reviewed suspect-page policy into the Onward recipe, added focused regression tests, and validated a fresh real pipeline run `story140-onward-targeted-rescue-r1`.
- **Impact:**
  - **Story-scope impact:** The reviewed Arthur, Roseanna, and Emilie failures are now improved in the real build output without reopening Story 138's chapter-boundary fixes.
  - **Pipeline-scope impact:** The targeted rescue stage now refuses unstable regressions and only accepts structurally better rescue candidates. In the fresh driver run, `onward_table_rescue` attempted exactly `4` pages and finished with `0` unresolved pages.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/04_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/output/html/chapter-010.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/output/html/chapter-018.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/output/html/chapter-020.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/output/html/chapter-017.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/output/html/chapter-019.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r1/output/html/chapter-021.html`
  - **Next:** No immediate follow-up is required for this story. If later review wants stronger normalization of subfamily table captions or column labeling, that should be a separate fidelity-polish story rather than a reopen of the targeted rescue fix.
- **Evidence:**
  - Focused validation:
    - `python -m pytest tests/test_table_rescue_onward_tables_v1.py tests/test_onward_targeted_table_rescue.py -q` → `8 passed`
    - `python -m ruff check modules/adapter/table_rescue_onward_tables_v1/main.py tests/test_table_rescue_onward_tables_v1.py tests/test_onward_targeted_table_rescue.py` → clean
  - Fresh driver validation run:
    - `python driver.py --recipe /tmp/story140-onward-r1.yaml --run-id story140-onward-targeted-rescue-r1 --output-dir /Users/cam/Documents/Projects/codex-forge/output/runs`
    - `onward_table_rescue` summary: `attempted=4`, `unresolved=0`
  - Repo-wide checks:
    - `python -m pytest tests/ -q` → `564 passed, 6 skipped`
    - `python -m ruff check modules/ tests/` → clean
  - Manual artifact inspection:
    - `chapter-010.html` now keeps Arthur's tail families with child rows instead of heading-only stubs. Sample verified rows: `RICHARD'S FAMILY` → `Brent`, `Jeffery`; `PAUL'S FAMILY` → `Steven (adpt)`, `Richard (adpt)`, `Shane (adpt)`.
    - `chapter-018.html` no longer degrades the Roseanna tail into loose paragraph text. Sample verified structured rows: `PATRICIA'S FAMILY` → `Carrie Lynn`, `Lisa Marie`, `Aaron Judy`; `ELAINE'S FAMILY` → `David`; summary table preserved `TOTAL DESCENDANTS 56`, `LIVING 44`, `DECEASED 8`.
    - `chapter-020.html` keeps the Emilie root heading and structured family tables through the tail. Sample verified rows: root table `Emilie | June 8, 1898 | Sept. 22, 1922 | Patrick Nolin`; subfamily tables include `PAULETTE'S FAMILY` → `Tammy Lynn`, `Shane`; `EMILIENNE'S FAMILY` → `Gilles`, `Corine`, `Charlotte`, `Madelaine`, `Lloyd`; summary table preserved `TOTAL DESCENDANTS 83`, `LIVING 78`, `DECEASED 5`.
    - Adjacent boundary checks remain clean: `chapter-017.html` begins with Marie-Louise prose, `chapter-019.html` begins with Antoinette prose, and `chapter-021.html` begins with Wilfrid prose rather than prior-family table spill.
- **Central Tenets:**
  - **T0 Traceability:** Rescue decisions are logged via the stage artifact/report flow, and the final evidence is tied to explicit stage JSONL and HTML artifact paths.
  - **T1 AI-First:** The fix stays in targeted AI rescue, with deterministic code used only to reject structurally worse retries.
  - **T2 Eval Before Build:** Established the baseline on `r4`, ran a fresh standalone `gpt-4.1` sweep before implementation, then validated the new policy in a real driver run.
  - **T3 Fidelity:** The implementation improves structure without hand-editing artifacts and preserves reviewed child rows, family headings, and summary counts.
  - **T4 Modular:** The retry policy is recipe-scoped for the Onward converter and lives in the rescue adapter rather than new builder special cases.
  - **T5 Inspect Artifacts:** Manually inspected the final HTML and upstream JSONL artifacts above before closing the story.
20260313-1812 — direct golden regression follow-up clarified what Story 140 did and did not actually protect
- **Result:** Ran direct artifact-vs-golden regressions after the story close and found a real structural gap in the first implementation. Added deterministic inline-family-table splitting plus genealogy-column padding in `table_rescue_onward_tables_v1`, then revalidated across fresh driver runs `story140-onward-targeted-rescue-r2`, `r3`, and an experiment `r4`.
- **Impact:**
  - **Story-scope impact:** The Arthur page that Story 140 explicitly touched (`page_number=35`) now regresses correctly against the hand-verified golden: `page-035-golden.html` improved from `0.745` in the older Story 138 validation run to `0.794` in `story140-onward-targeted-rescue-r3`.
  - **Pipeline-scope impact:** The follow-up also exposed that the narrowed recipe-scoped retry set (`35,89,97,98`) does not cover earlier Arthur rescue pages `30` and `31`, so a whole-chapter Arthur golden can look worse even when page `35` improves. A bounded experiment that re-added `30,31` (`story140-onward-targeted-rescue-r4`) made page goldens `30/31/35` all pass, but the same run showed fresh model drift on un-goldened Roseanna/Emilie pages, so that broader retry set was not promoted.
 - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r3/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r3/output/html/chapter-010.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r4/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-030-golden.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-031-golden.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-035-golden.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/onward/arthur.html`
  - **Next:** Treat page-level Arthur goldens as the reliable non-regression check for the current targeted rescue policy. Roseanna/Emilie still require manual artifact inspection until hand-validated goldens exist, and any attempt to broaden the retry page set should be judged against both the Arthur goldens and the reviewed final HTML for chapters `018` and `020`.
20260313-1934 — manual Emilie review exposed a semantic hierarchy bug in page `97`, and the rescue post-processing now carries that hierarchy into the next family heading
- **Result:** The data rows and columns on Emilie were already materially correct, but page `97` was still semantically wrong because generational context lines such as `Emilie’s Great Grandchildren` / `Herve’s Grandchildren` were left as one-cell trailing rows in the previous family table. Added a bounded post-processing repair in `table_rescue_onward_tables_v1` that detects those trailing context rows and moves them into the next external family heading instead of leaving them attached to the prior table.
- **Impact:**
  - **Story-scope impact:** `chapter-020.html` now preserves the reviewed Emilie hierarchy more faithfully: `HERVE’S FAMILY` ends with only its child rows, and the next heading is emitted as `Emilie’s Great Grandchildren` / `Herve’s Grandchildren` / `ANNETTE’S FAMILY` before Annette’s child table.
  - **Pipeline-scope impact:** The fix stays upstream in rescue-page HTML and does not depend on chapter build heuristics. It also keeps the Arthur page-35 golden green after the follow-up changes.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r5/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r5/output/html/chapter-020.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/tests/test_table_rescue_onward_tables_v1.py`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-035-golden.html`
  - **Next:** Roseanna/Emilie still need hand-validated goldens if we want this hierarchy fidelity guarded automatically. Until then, use the Arthur page goldens plus manual HTML inspection on `chapter-018.html` / `chapter-020.html` as the validation gate for any rescue-policy changes.
20260313-2025 — safe single-table follow-up merged only repaired contextual runs, not all contextual genealogy tables
- **Result:** Tried a broader “merge contiguous contextual tables” repair and immediately caught a real regression: Arthur page `35` collapsed from a passing page golden to `0.272`. Narrowed the merge trigger so only headings explicitly repaired from trailing context rows can start a merge run. The final validated run is `story140-onward-targeted-rescue-r7`.
- **Impact:**
  - **Story-scope impact:** Emilie page `97` now keeps the intended context with the next subgroup inside a single table span: `EMILIE’S SECOND FAMILY` continues into subgroup rows `Emilie’s Grandchildren` / `HERVE’S FAMILY`, then `Emilie’s Great Grandchildren` / `Herve’s Grandchildren` / `ANNETTE’S FAMILY` before `David` and `Marie`.
  - **Pipeline-scope impact:** Arthur non-regression is preserved. `page-035-golden.html` returns to `PASS` at `0.794`, so the safe narrowing avoids reopening the earlier Arthur family-table split behavior.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r7/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r7/output/html/chapter-020.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-035-golden.html`
  - **Next:** Page `98` still emits multiple separate tables because there is no equally safe automatic merge signal there yet. The next clean step remains hand-validated goldens for `89/97/98`; once those exist, broader same-schema merge rules can be tested without risking silent Arthur regressions.
20260313-2215 — added hand-validated page goldens for Roseanna/Emilie and used them to score the current rescue artifacts against the canonical one-table standard
- **Result:** Added new page-level goldens for `Image088` / `page-089`, `Image096` / `page-097`, and `Image097` / `page-098` in `benchmarks/golden/ocr-genealogy/`, encoded as one continuous genealogy table per page with subgroup headings carried inside the table. Wired those pages into both OCR eval task lists and scored the actual `story140-onward-targeted-rescue-r7` artifacts directly with `table_structure_scorer.py`.
- **Impact:**
  - **Story-scope impact:** We now have automatic regression coverage on the exact Roseanna/Emilie pages that had only been guarded by manual review. That makes the remaining semantic gap explicit instead of inferred.
  - **Pipeline-scope impact:** The new goldens show mixed results. Roseanna page `89` now passes the canonical regression cleanly (`0.993` on `r7`, up from `0.000` on `story138-onward-stale-span-validate-r4`), which validates the structured-table rescue there. Emilie pages `97` and `98` still fail the canonical one-table standard on `r7` (`0.000` and `0.524` respectively), so the current safe merge logic still leaves real semantic fragmentation on Emilie even though the data is present.
  - **Evidence:** `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-089-golden.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-097-golden.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/ocr-genealogy/page-098-golden.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/tasks/ocr-genealogy-tables.yaml`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/tasks/ocr-genealogy-tables-gpt-only.yaml`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r7/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`
  - **Next:** Treat page `89` as now guarded and resolved. For Emilie, the highest-leverage next change is a safer generic merge rule that can collapse same-page split genealogy tables into one canonical table without reopening the Arthur regression; success is falsified if Arthur page `35` drops below its current golden pass or if page `97/98` still fail these new goldens after the merge change.
20260313-2258 — closed the reopened Emilie gap with a guarded deterministic fallback and revalidated the full shipped slice
- **Result:** Traced the apparent page-98 acceptance mismatch to a bad assumption in my own debugging: rejected rescue rows do not retain the OCR candidate in the stamped stage artifact, so reprocessing `raw_html` from a rejected row was reprocessing the original input, not the rejected OCR output. Turned that useful discovery into the actual fix: `table_rescue_onward_tables_v1` now runs the same bounded normalization on the existing page HTML, but only auto-applies it when it safely collapses a fragmented same-schema genealogy run into a single clean table. That let page `98` adopt the desired one-table Emilie continuation while leaving Arthur page `35` on the stronger OCR candidate path.
- **Impact:**
  - **Story-scope impact:** The reopened Roseanna/Emilie acceptance criterion is now actually closed. The final verified run `story140-onward-targeted-rescue-r13` passes the page goldens for Arthur `35`, Roseanna `89`, Emilie `97`, and Emilie `98`, and the built `chapter-020.html` keeps the reviewed Emilie hierarchy in final HTML.
  - **Pipeline-scope impact:** The rescue stage now has a safer three-way decision: keep the original page, adopt a narrowly eligible deterministic normalization of the original page, or accept a stronger OCR retry. This preserves the Arthur rescue win while recovering Emilie `98` even when the OCR retry is worse than the normalized existing page.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r13/table_rescue_onward_tables_v1/table_rescue_onward_report.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r13/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r13/output/html/chapter-020.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/tests/test_table_rescue_onward_tables_v1.py`, `/Users/cam/.codex/worktrees/4969/codex-forge/tests/test_onward_targeted_table_rescue.py`
  - **Next:** Story 140 is done. Any follow-up should be a new story if we want to generalize one-table continuity more broadly than this guarded same-page fallback.
20260313-2358 — manual Alma review reopened the story again, and the final fix is now a recipe-scoped chapter-build merge for contiguous genealogy tables
- **Result:** Manual review of `story140-onward-targeted-rescue-r13/output/html/chapter-009.html` showed the page-level rescue work was not enough: Alma still rendered as `34` small tables with fused headings such as `Alma’s Grandchildren BERTHA’S FAMILY`, which meant downstream consumers still could not trust the grouping. Added an optional `merge_contiguous_genealogy_tables` pass in `build_chapter_html_v1` that reuses the rescue HTML normalizer, then merges contiguous same-schema genealogy tables across the built chapter body and converts contextual heading runs into subgroup rows inside the preserved table.
- **Impact:**
  - **Story-scope impact:** The user-reported Alma failure is fixed in a real driver run. In `story140-onward-targeted-rescue-r18`, `chapter-009.html` drops from `34` tables to `2` (one main genealogy table plus the final totals table), and formerly fused subgroup labels are now split correctly as `BERTHA’S FAMILY`, `Bertha’s Grandchildren`, `PAUL’S FAMILY`, `Paul’s Grandchildren`, and `GABRIELLE’S FAMILY`. The Alma chapter golden improves from `0.657` on `r13` to `0.934` on `r18`.
  - **Pipeline-scope impact:** The merge stays recipe-scoped and downstream, so it does not disturb the already-validated rescue artifacts. Emilie remains structurally coherent in final HTML (`chapter-020.html` still preserves subgroup rows for `HERVE’S FAMILY`, `ANNETTE’S FAMILY`, `PAULETTE’S FAMILY`, `EMILIENNE’S FAMILY`, and `CORINE’S FAMILY` plus summary counts), and Arthur’s chapter golden improves slightly (`0.653` to `0.664`) without claiming full one-table continuity there.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r13/output/html/chapter-009.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r18/output/html/chapter-009.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r18/output/html/chapter-020.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r18/04_build_chapter_html_v1/chapters_manifest.jsonl`, `/Users/cam/.codex/worktrees/4969/codex-forge/benchmarks/golden/onward/alma.html`, `/Users/cam/.codex/worktrees/4969/codex-forge/tests/test_build_chapter_html.py`
  - **Next:** The immediate Alma inconsistency is resolved. If we want truly general chapter-level one-table continuity across all Onward families, Arthur remains the next falsifier and should be handled as a separate broader continuity story rather than silently folded into this targeted fix.
20260314-0009 — immediate follow-up fixed broken image attachments introduced by the new chapter-build merge validation path
- **Result:** Manual review caught that the new build-stage merge path was preserving genealogy structure but breaking images. Two issues were involved: the merge helper reused the rescue HTML normalizer on the full chapter body, which stripped `img src` and figure metadata, and the load-artifact validation recipe for `r18` copied the illustration manifest without its sibling `images/` directory. Fixed the code by restoring original figure/img attributes after the genealogy merge, added a regression in `tests/test_build_chapter_html.py`, and revalidated with a corrected load-artifact run `story140-onward-targeted-rescue-r19` that copies the crop image directory.
- **Impact:**
  - **Story-scope impact:** The latest validation artifact is now actually usable end-to-end. `chapter-009.html` in `r19` keeps the Alma genealogy continuity fix *and* the Henry/Alma anniversary image now resolves again at `images/page-022-000.jpg`.
  - **Pipeline-scope impact:** The build-stage genealogy merge no longer strips image attachments or figure metadata, so the Onward recipe can keep the chapter-level continuity improvement without regressing image fidelity. `chapter-020.html` also keeps working image attachments (`images/page-096-000.jpg`, `images/page-096-001.jpg`) alongside the previously reviewed Emilie hierarchy.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-009.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-020.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/images/page-022-000.jpg`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/03_load_artifact_v1/images`, `/Users/cam/.codex/worktrees/4969/codex-forge/tests/test_build_chapter_html.py`
  - **Next:** `r19` is the current good validation artifact. Any further continuity generalization should preserve images by default and use artifact-seeded recipes that copy sibling crop directories when validating from historical runs.
- **Evidence:**
  - Focused validation:
    - `python -m pytest tests/test_table_rescue_onward_tables_v1.py tests/test_onward_targeted_table_rescue.py -q` → `18 passed`
    - `python -m ruff check modules/adapter/table_rescue_onward_tables_v1/main.py tests/test_table_rescue_onward_tables_v1.py tests/test_onward_targeted_table_rescue.py` → clean
  - Fresh driver validation run:
    - `python driver.py --recipe /Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r7/snapshots/recipe.yaml --run-id story140-onward-targeted-rescue-r13 --output-dir /Users/cam/Documents/Projects/codex-forge/output/runs`
    - `onward_table_rescue` summary: `attempted=4`, `unresolved=0`
    - Rescue report confirms the intended guard behavior:
      - page `35`: normalized existing was eligible by score but not applied; OCR candidate accepted (`380 -> 2330`)
      - page `89`: normalized existing was eligible by score but not applied; OCR candidate accepted (`165 -> 425`)
      - page `97`: normalized existing was eligible by score but not applied; OCR candidate accepted (`485 -> 795`)
      - page `98`: normalized existing was eligible and applied (`555 -> 780`); OCR candidate rejected as worse (`555`)
  - Direct page-golden scoring against `table_structure_scorer.py` on `story140-onward-targeted-rescue-r13/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`:
    - `page-035-golden.html` → `0.794` `PASS`
    - `page-089-golden.html` → `0.993` `PASS`
    - `page-097-golden.html` → `0.849` `PASS`
    - `page-098-golden.html` → `0.861` `PASS`
  - Repo-wide checks:
    - `python -m pytest tests/ -q` → `580 passed, 6 skipped`
    - `python -m ruff check modules/ tests/` → clean
  - Build-stage validation run for the Alma follow-up:
    - `python driver.py --recipe /tmp/story140-r17-build.yaml --run-id story140-onward-targeted-rescue-r18 --output-dir /Users/cam/Documents/Projects/codex-forge/output/runs`
    - `build_chapters` summary: `Wrote 33 chapters to /Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r18/output/html`
    - `python driver.py --recipe /tmp/story140-r19-build.yaml --run-id story140-onward-targeted-rescue-r19 --output-dir /Users/cam/Documents/Projects/codex-forge/output/runs`
    - `build_chapters` summary: `Wrote 33 chapters to /Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html`
  - Manual artifact inspection:
    - `chapter-009.html` in `r19` keeps Alma as one main genealogy table plus the totals table, with subgroup rows including `MARY PAULE’S FAMILY`, `RONALD’S FAMILY`, `DARLENE’S FAMILY`, `BERTHA’S FAMILY`, `Bertha’s Grandchildren`, `PAUL’S FAMILY`, `Paul’s Grandchildren`, and `GABRIELLE’S FAMILY`, and the Henry/Alma figure now resolves with `src="images/page-022-000.jpg"`.
    - `chapter-020.html` in `r19` keeps the Emilie hierarchy inside the built HTML with subgroup headings `HERVE’S FAMILY`, `Herve’s Grandchildren`, `ANNETTE’S FAMILY`, `PAULETTE’S FAMILY`, `EMILIENNE’S FAMILY`, `Emilienne’s Grandchildren`, and `CORINE’S FAMILY`, and its two image attachments resolve at `images/page-096-000.jpg` and `images/page-096-001.jpg`.
    - Sample verified rows in `chapter-020.html`: `Herve P. | July 12, 1923 | Jan. 22, 1946 | Delores Lessard | 0 | 3`, `Annette | Nov. 4, 1946 | July 12, 1969 | Robert Hyde | 1 | 1`, `Paulette | July 12, 1953 | Mar. 20, 1971 | Richard Stebanuk | 1 | 1`, `Emilienne | Feb. 18, 1930 | , 1950 | Claude Cadrain | 2 | 3`, `Corine | Apr. 19, 1933 | Sept. 15, 1953 | Anthony Bertsch | 0 | 2`.
    - `chapter-020.html` still preserves the Emilie summary counts at the end: `TOTAL DESCENDANTS 83`, `LIVING 78`, `DECEASED 5`.
20260314-1208 — validation follow-up: rescoped Story 140 docs to match the shipped slice and recorded the page-golden coverage trail in the eval registry
- **Result:** Updated the story goal and acceptance/task wording so Story 140 now truthfully describes the shipped implementation as primarily upstream targeted rescue plus a narrow recipe-scoped build-stage continuity fallback, recorded the added `page-089` / `page-097` / `page-098` golden coverage in `docs/evals/registry.yaml`, and explicitly pointed broader chapter-consistency normalization to Story 141.
- **Impact:**
  - **Story-scope impact:** Story 140 can stay closed without pretending the later Alma/continuity fallback was still "upstream only," and the remaining `chapter-010` / `013` / `014` / `015` consistency work now has an explicit home in Story 141.
  - **Pipeline-scope impact:** No pipeline behavior changed; this is traceability/closure hygiene so the documented shipped slice matches the actual `r19` validation artifact and benchmark coverage added during the story.
  - **Evidence:** `/Users/cam/.codex/worktrees/4969/codex-forge/docs/stories/story-140-onward-targeted-genealogy-table-rescue-fidelity.md`, `/Users/cam/.codex/worktrees/4969/codex-forge/docs/evals/registry.yaml`, `/Users/cam/.codex/worktrees/4969/codex-forge/docs/stories/story-141-onward-genealogy-table-consistency-pass.md`
  - **Next:** Story 140 needs no more implementation. Continue any broader genealogy-table normalization in Story 141, starting with an AI-first consistency baseline on the reviewed `r19` chapters.
20260314-1237 — mark-story-done validation rerun: Story 140 closure reconfirmed on the current tree before check-in
- **Result:** Re-ran the required check suite on the current tree with the working repo interpreter, confirmed the branch is already based on `origin/main`, and verified a Python-based smoke run still completes successfully.
- **Impact:**
  - **Story-scope impact:** Story 140 is ready to stay closed; no remaining gaps belong to this story after the rescope, and broader chapter-level consistency remains intentionally split to Story 141.
  - **Pipeline-scope impact:** No new behavior changes were introduced after the rescope/registry edits; the validated code path is unchanged and still green.
  - **Evidence:** `python -m pytest tests/ -q` → `580 passed, 6 skipped`; `python -m ruff check modules/ tests/` → clean; `python driver.py --recipe configs/recipes/recipe-ff-smoke.yaml --run-id smoke-ff --output-dir output/runs --allow-run-id-reuse --force` → `Recipe complete.`; `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-010.html`; `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-018.html`; `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-020.html`
  - **Next:** Commit the current Story 140 + Story 141 handoff slice and land it onto `main`.
