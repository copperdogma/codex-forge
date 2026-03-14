# Story 141 — Onward Genealogy Table Consistency Pass

**Priority**: High
**Status**: In Progress
**Ideal Refs**: Requirement #3 (Extract), Requirement #5 (Structure), Requirement #6 (Validate), Fidelity to Source, Dossier-ready output
**Spec Refs**: C1 (Multi-Stage OCR Pipeline), C2 (Format-Specific Conversion Recipes), C3 (Heuristic + AI Layout Detection), C6 (Expensive OCR for Quality)
**Decision Refs**: `docs/runbooks/golden-build.md`, `docs/scout/scout-003-storybook-patterns.md`, Story 140 work log and `story140-onward-targeted-rescue-r19` review evidence; none found after search in `docs/notes/`
**Depends On**: Story 140

## Goal

Add a separate, recipe-scoped consistency pass for the Onward genealogy converter so same-schema genealogy content inside a chapter normalizes to one canonical HTML structure even when upstream OCR/rescue pages disagree. This story explicitly locks in Story 140's page-rescue gains and treats consistency as a new layer: infer the dominant genealogy schema for a contiguous run, normalize compatible fragments to it, preserve provenance, and make the output easier for downstream consumers such as Storybook to understand without guessing.

## Acceptance Criteria

- [ ] In a fresh verification run, reviewed chapters [chapter-009.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-009.html), [chapter-010.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-010.html), [chapter-013.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-013.html), [chapter-014.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-014.html), and [chapter-015.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-015.html) no longer mix incompatible genealogy table representations within the same chapter when the underlying schema is the same
- [ ] The reviewed inconsistent chapters normalize to a canonical genealogy structure: `NAME / BORN / MARRIED / SPOUSE / BOY / GIRL / DIED`, family/context headings are full-width internal section rows instead of fused concatenations or unlabeled mini-tables, and totals remain separate summary tables
- [ ] The implementation is explicitly AI-first: before adding complex new code, the story measures whether a single strong AI normalization call can repair a whole genealogy chapter or contiguous page run; any deterministic logic that remains is justified as orchestration, validation, or rendering glue
- [ ] The consistency pass is recipe-scoped, preserves access to the original page-level HTML/provenance, and does not silently erase real source distinctions when the document genuinely uses different structures
- [ ] A fresh `driver.py` validation run is manually inspected with concrete evidence recorded for the reviewed chapters plus at least one non-regression chapter, and any new goldens/evals added for the consistency behavior are hand-verified and recorded

## Out of Scope

- A generic "all weird tables in any PDF" engine
- Replacing the HTML-first target with a CSV-only or row-IR product path
- Reopening Story 140's targeted rescue scope unless a shared helper extraction is required
- Hand-editing generated HTML outside the pipeline
- Image placement/caption work unrelated to genealogy table consistency
- Auto-normalizing genuinely different source structures into one format without evidence that they are semantically the same

## Approach Evaluation

Story 140 proved that local page rescue can recover missing data, but the remaining failures in `r19` are chapter-level inconsistency failures: different pages in the same genealogy run choose different table structures, heading ownership, and `BOY/GIRL` encodings. The next story should therefore evaluate chapter/run-level normalization rather than keep patching isolated pages.

- **Simplification baseline**: Do not assume more heuristics are needed. First measure whether a single top-tier AI call can take a whole reviewed chapter or contiguous genealogy page run plus the current HTML and produce a more consistent canonical HTML structure. Remember that this repo has access to brilliant AI API calls; use that capability before defaulting to more brittle parsing code.
- **AI-only**: A chapter-level or contiguous-run-level normalization call could infer the dominant schema, relocate context/family headings, split `BOY/GIRL`, and emit coherent HTML directly. This may already solve most of the issue on a bounded reviewed set at acceptable cost.
- **Hybrid**: Code detects contiguous same-schema genealogy runs and preserves provenance; AI resolves semantic normalization decisions for headings, column structure, and merge boundaries; deterministic code renders/validates the normalized structure and rejects regressions. This is the leading candidate if the one-shot baseline is good but not perfectly reliable.
- **Pure code**: A structural canonicalizer can merge same-schema fragments and split obvious `BOY/GIRL` cases, but fused hierarchy text and heading ownership are semantic problems. Pure code is likely to overfit unless AI has already recovered the intended hierarchy.
- **Repo constraints / prior decisions**: Reuse OCR artifacts and narrow reruns because OCR is expensive (`C6`). Keep the change recipe-scoped for the Onward converter (`C2`). Do not hardcode family names or page IDs into generic pipeline code. Story 140 is now the stable baseline and should not be silently mutated into a broader experiment.
- **Existing patterns to reuse**: `modules/adapter/table_rescue_onward_tables_v1/main.py`, `modules/build/build_chapter_html_v1/main.py`, existing genealogy merge/split helpers, `benchmarks/tasks/ocr-genealogy-tables.yaml`, `benchmarks/tasks/onward-table-fidelity.yaml`, and the hand-verified golden workflow in `docs/runbooks/golden-build.md`
- **Eval**: The distinguishing test is chapter-level consistency on the reviewed `r19` problem chapters. A candidate approach passes only if it removes fused headings such as `Arthur’s Great Grandchildren Agnes’ Grandchildren LAWRENCE’S FAMILY`, removes `BOY/GIRL` headers on the reviewed same-schema tables, preserves Story 140's recovered data, and keeps Alma as a non-regression case.

## Tasks

- [ ] Establish the exact inconsistency baseline on the reviewed `r19` chapters and their upstream page HTML: classify each issue as page-level inconsistency, build-level inconsistency, or genuine source variation
- [ ] Measure the simplest strong-model baseline on a bounded set of chapters or contiguous page runs before writing new normalization logic; record whether a single AI normalization pass already produces acceptable canonical HTML
- [ ] Choose and implement the smallest recipe-scoped consistency architecture that solves the reviewed chapters:
  - [ ] likely a new genealogy consistency stage or helper rather than further growth inside existing 1400-line modules
  - [ ] preserve original HTML/provenance and log normalization decisions so regressions are inspectable
  - [ ] normalize same-schema runs without flattening genuinely distinct structures
- [ ] Add focused regression coverage and, if needed, new hand-verified goldens/evals for the reviewed consistency patterns
- [ ] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [ ] Run required checks for touched scope:
  - [ ] Focused tests for touched modules/helpers
  - [ ] Repo-wide Python checks: `python -m pytest tests/`
  - [ ] Repo-wide lint: `python -m ruff check modules/ tests/`
  - [ ] If pipeline behavior changed: clear stale `*.pyc`, run through `driver.py` with artifact reuse where appropriate, verify artifacts in `output/runs/`, and manually inspect reviewed HTML/JSONL data
- [ ] If evals or goldens changed: run `/verify-eval` and update `docs/evals/registry.yaml`
- [ ] Search all docs and update any related to what we touched
- [ ] Verify Central Tenets:
  - [ ] T0 — Traceability: every output traces to source page, OCR engine, confidence, processing step
  - [ ] T1 — AI-First: didn't write code for a problem AI solves better
  - [ ] T2 — Eval Before Build: measured SOTA before building complex logic
  - [ ] T3 — Fidelity: source content preserved faithfully, no silent losses
  - [ ] T4 — Modular: new recipe or recipe-scoped stage, not hidden book-specific branching in generic code
  - [ ] T5 — Inspect Artifacts: visually verified outputs, not just checked logs

## Workflow Gates

- [ ] Build complete: implementation finished, required checks run, and summary shared
- [ ] Validation complete or explicitly skipped by user
- [ ] Story marked done via `/mark-story-done`

## Architectural Fit

- **Owning module / area**: Likely a new recipe-scoped genealogy consistency module or narrowly extracted helper placed between page-level rescue and final chapter build. The exact seam should be selected during `/build-story` after the strong-model baseline, not assumed now.
- **Data contracts / schemas**: A new adapter stage can likely stay on `page_html_v1` with no schema change if original access is preserved through the prior artifact chain plus a companion report JSONL. Only add schema fields if in-row normalization metadata must survive stamping.
- **File sizes**: `modules/adapter/table_rescue_onward_tables_v1/main.py` is 1400 lines, `modules/build/build_chapter_html_v1/main.py` is 1383 lines, and `tests/test_build_chapter_html.py` is 1054 lines. This story should prefer a new focused module/test file over piling more special cases into already oversized files.
- **Decision context**: Reviewed `docs/ideal.md`, `docs/spec.md`, `docs/runbooks/golden-build.md`, `docs/scout/scout-003-storybook-patterns.md`, Story 140 work log, and the live `story140-onward-targeted-rescue-r19` chapter/page artifacts. No directly relevant decision doc was found in `docs/notes/`.

## Files to Modify

- `modules/adapter/genealogy_table_consistency_v1/module.yaml` — likely new recipe-scoped consistency stage if the chosen seam warrants a dedicated module (new file)
- `modules/adapter/genealogy_table_consistency_v1/main.py` — likely new AI-first consistency pass for contiguous genealogy runs (new file)
- `configs/recipes/recipe-onward-images-html-mvp.yaml` — wire the chosen consistency stage/policy into the Onward recipe (178 lines)
- `modules/build/build_chapter_html_v1/main.py` — only if final build must consume a normalized artifact or provide a narrow fallback hook (1383 lines)
- `modules/adapter/table_rescue_onward_tables_v1/main.py` — only if helper extraction is needed; avoid further growth if a new stage is cleaner (1400 lines)
- `tests/test_genealogy_table_consistency_v1.py` — focused regression coverage for chapter/run normalization (new file)
- `tests/test_build_chapter_html.py` — only minimal additions if build behavior changes (1054 lines)
- `benchmarks/tasks/ocr-genealogy-tables.yaml` — extend page-level regression coverage if normalization changes what "good" looks like for reviewed pages
- `benchmarks/tasks/onward-table-fidelity.yaml` — add chapter-level or chapter-adjacent coverage if new hand-verified goldens are created
- `benchmarks/golden/ocr-genealogy/` and `benchmarks/golden/onward/` — new hand-verified goldens only if needed to guard this behavior
- `docs/evals/registry.yaml` — record any new eval coverage or benchmark targets (366 lines)
- `docs/stories/story-141-onward-genealogy-table-consistency-pass.md` — build/implementation work log

## Redundancy / Removal Targets

- Ad hoc genealogy merge/split behavior inside `build_chapter_html_v1` that exists only to paper over chapter-level inconsistency and becomes redundant once a dedicated consistency pass owns that responsibility
- Any helper code inside `table_rescue_onward_tables_v1` that is really chapter-level normalization rather than page-level rescue
- Temporary experiment prompts/scripts for one-off consistency trials, if a stable recipe/module path replaces them

## Notes

- Manual review evidence driving this story:
  - [chapter-009.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-009.html) is the current non-regression reference and was reviewed as "perfect"
  - [chapter-010.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-010.html) is good early, then drops out of the canonical table shape and returns with multiple inconsistent tables
  - [chapter-013.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-013.html), [chapter-014.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-014.html), and [chapter-015.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-015.html) still show fused headings, non-spanning family headers, and combined `BOY/GIRL`
  - The same inconsistency is already visible upstream in [pages_html_onward_tables_fixed.jsonl](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/01_load_artifact_v1/pages_html_onward_tables_fixed.jsonl), so the story should not assume this is only a final build problem
- Strong AI-first reminder for `/build-story`: you have brilliant AI API calls available. Use them. Do not jump straight to another layer of BeautifulSoup/regex heuristics if a bounded strong-model normalization pass can already infer the right chapter-level structure.
- Consistency is the main product goal for this slice, but fidelity still matters. If the source truly uses different structures in one chapter, the pass must preserve that distinction or surface ambiguity rather than silently flatten it.
- Handoff notes for the next agent:
  - Do not assume this is mainly a final `build_chapter_html_v1` problem. The same inconsistency is already visible upstream in [pages_html_onward_tables_fixed.jsonl](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/01_load_artifact_v1/pages_html_onward_tables_fixed.jsonl).
  - Specific upstream examples already observed in `r19`:
    - page `30`: one table, still uses `BOY/GIRL`, and embeds `ARTHUR'S FAMILY` as an internal row
    - page `32`: fused contextual heading inside table header, e.g. `Joe's Grandchildren / MARIE'S FAMILY`
    - page `40`: same-schema genealogy table still uses `BOY/GIRL` and family-heading rows inside the table
    - page `41`: contextual hierarchy already flattened into a heading before the table, e.g. `Leonidas' Great Great Grandchildren / Alma's Great Grandchildren / Dolly's Grandchildren / SHARON'S FAMILY`
    - page `43`: already fragmented into many separate tables before final build
    - page `45`: heading + table + totals split already exists upstream
  - Current built-HTML failure signatures to keep in mind:
    - [chapter-010.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-010.html): good early, then falls back into fragmented/headerless mini-tables and fused headings like `Arthur’s Great Grandchildren Agnes’ Grandchildren LAWRENCE’S FAMILY`
    - [chapter-013.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-013.html): second table is effectively a fused heading block and still carries `BOY/GIRL`
    - [chapter-014.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-014.html): still uses `BOY/GIRL` and has non-spanning/fused family headings
    - [chapter-015.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-015.html): still uses `BOY/GIRL`; `REAL'S FAMILY` appears as an isolated mini-table heading
  - Protect the wins from Story 140 while experimenting: [chapter-018.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-018.html) and [chapter-020.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-020.html) are the minimum non-regression set, with [chapter-009.html](/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-009.html) as the continuity-quality reference.
  - Best first move remains the same: try a bounded top-tier model on a whole reviewed chapter or contiguous page run, using current HTML as context, before writing more deterministic normalization code.

## Plan

### Exploration Findings

- The live `r19` review baseline confirms this is a chapter/run-consistency problem, not just a final-build presentation issue. The same incompatible structures already exist upstream in `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/01_load_artifact_v1/pages_html_onward_tables_fixed.jsonl`.
- Current reviewed chapter baseline on `story140-onward-targeted-rescue-r19`:
  - `chapter-009.html` is the non-regression reference: `1` canonical split-header genealogy table plus `1` separate summary table.
  - `chapter-010.html` still mixes `20` tables total (`15` split-header, `5` headerless fragments) and retains fused heading text like `Arthur’s Great Grandchildren Agnes’ Grandchildren LAWRENCE’S FAMILY`.
  - `chapter-013.html` still has a second genealogy table carrying `BOY/GIRL` and fused heading ownership.
  - `chapter-014.html` is the clearest open failure: `15` tables total, `3` combined-header genealogy tables, `12` headerless fragments, and `11` external family headings.
  - `chapter-015.html` still has `2` combined-header genealogy tables, `1` headerless fragment, and isolated family-heading mini-tables such as `REAL'S FAMILY`.
- Representative upstream page-level inconsistency is already visible before chapter build:
  - page `30`: one combined-header table with `ARTHUR'S FAMILY` embedded as an internal row.
  - page `32`: contextual heading fused inside `<thead>`, e.g. `Joe’s Grandchildren / MARIE’S FAMILY`.
  - page `40`: same-schema table with a heading-only first `<thead>` row plus `BOY/GIRL`.
  - page `41`: multiline external context heading before a combined-header table.
  - page `43`: repeated heading + headerless mini-table fragments.
  - page `45`: heading + table + separate totals split already exists upstream.
- Existing code already contains two partial normalization layers:
  - `table_rescue_onward_tables_v1` normalizes page-local table structure, splits `BOY/GIRL`, and promotes some contextual headings.
  - `build_chapter_html_v1` merges contiguous genealogy heading/table runs during final build.
- Neither layer owns whole-run normalization, and both files are already oversized. Exploration therefore favors a new adapter stage over adding more special cases to the rescue or builder modules.
- Validation can stay cheap: `r19` is already a `load_artifact_v1` resume recipe (`load_pages` + `load_portions` + `load_crops` + `build_chapters`), so a fresh verification run can reuse OCR/rescue artifacts and insert one new stage between `load_pages` and `build_chapters`.

### Ideal Alignment Gate

- This story closes a direct Ideal gap: same-schema genealogy content is still not exporting as one faithful, inspectable structure.
- The evidence points toward an AI-first solution, not more heuristic growth. A strong one-shot normalizer already repairs the structural shape better than the current layered deterministic fixes.
- No new product compromise is required if deterministic code stays limited to run detection, acceptance/validation, provenance logging, and narrow rendering cleanup.

### Eval / Baseline

- Distinguishing eval for this story: reviewed chapter-level consistency on `chapter-010.html`, `chapter-013.html`, `chapter-014.html`, and `chapter-015.html`, plus non-regression on `chapter-009.html` and at least one of `chapter-018.html` / `chapter-020.html`.
- Current code baseline:
  - `chapter-014.html`: `15` tables, `0` subgroup rows, `11` external family headings, `1` summary table.
  - `chapter-015.html`: `4` tables, `0` subgroup rows, combined `BOY/GIRL` headers still present.
  - `chapter-010.html`: mixed compatible structures remain in the same chapter despite Story 140 page rescue gains.
- AI-first bounded trials:
  - `gpt-4.1` one-shot over pages `40-41` (`/tmp/story141_ai_baseline_pages40_41_gpt41.html`) normalized two incompatible source shapes into `1` canonical `NAME/BORN/MARRIED/SPOUSE/BOY/GIRL/DIED` table with `22` subgroup rows and no external family headings. This proves a single strong call can repair the core pattern on a bounded contiguous run.
  - `gpt-4.1` one-shot over pages `40-45` (`/tmp/story141_ai_baseline_pages40_45_gpt41.html`) removed `BOY/GIRL` headers and external family headings, but still emitted `14` tables. Better than baseline, not canonical enough.
  - `gpt-5` one-shot over full `chapter-014.html` (`/tmp/story141_ai_baseline_ch14.html`) was materially stronger: it collapsed `15` mixed tables down to `2` tables total (`1` main genealogy table + `1` separate summary table), split `BOY/GIRL`, emitted `31` subgroup rows, and removed all external family headings.
- AI baseline conclusion: a single top-tier AI normalization pass is strong enough to be the primary normalization engine for this story, but deterministic glue is still required for run detection, provenance preservation, acceptance/rejection, and cleanup of residual fused multi-line subgroup rows.

### Implementation Plan

#### Task 1 — Add a New `genealogy_table_consistency_v1` Adapter Stage

- Files: `modules/adapter/genealogy_table_consistency_v1/main.py`, `modules/adapter/genealogy_table_consistency_v1/module.yaml`, `configs/recipes/recipe-onward-images-html-mvp.yaml`
- Change:
  - Create a recipe-scoped adapter over `page_html_v1` that groups consecutive compatible genealogy pages into candidate normalization runs.
  - Feed each run's current HTML to a strong model, defaulting to `gpt-5`, and ask for canonical run-level HTML with split `BOY/GIRL`, internal subgroup rows, and separate totals.
  - Keep the previous stage artifact as the source-of-truth fallback. The new stage writes a fresh `page_html_v1` artifact plus a companion report JSONL that records run membership, source page numbers, model/request metadata, decision reasons, and candidate-vs-input quality signals.
- Risk:
  - Over-grouping could flatten genuinely distinct source structures.
  - A run-level model call could return prettier HTML that silently loses content unless acceptance is strict.
- Done when:
  - The stage produces page HTML that `build_chapter_html_v1` can consume directly, while the report makes every normalization decision inspectable and traceable to source pages.

#### Task 2 — Keep Deterministic Logic Thin and Auditable

- Files: primarily `modules/adapter/genealogy_table_consistency_v1/main.py`; only extract tiny shared helpers if duplication is clearly worse
- Change:
  - Implement generic run-detection and acceptance checks only: canonical header presence, summary-table preservation, reduced heading/table fragmentation, retention of family labels and totals, and rejection of regressions such as combined `BOY/GIRL` or dropped rows.
  - If AI output still fuses multiple context lines inside one subgroup row via `<br>`, add a narrow post-AI rendering cleanup to split that row into multiple full-width subgroup rows without changing textual content.
  - Do not add family-name or page-number logic, and do not grow `table_rescue_onward_tables_v1` into a second chapter-level normalization layer unless a tiny shared helper extraction is clearly cleaner.
- Risk:
  - Acceptance logic that is too permissive could silently erase distinctions.
  - Cleanup logic that is too aggressive could rewrite semantics rather than presentation.
- Done when:
  - The stage only applies AI output when structure materially improves without losing source content, and residual fused-heading cleanup is fixture-backed and conservative.

#### Task 3 — Minimize Build Coupling

- Files: `configs/recipes/recipe-onward-images-html-mvp.yaml`, possibly minimal changes in `modules/build/build_chapter_html_v1/main.py` and `tests/test_build_chapter_html.py`
- Change:
  - Insert the new stage after `table_fix_continuations` in the full Onward recipe and after `load_pages` in the reused-artifact validation recipe.
  - Keep `merge_contiguous_genealogy_tables` enabled initially unless validation proves it now causes double-processing or becomes redundant. Prefer making it a harmless no-op on already-normalized runs rather than widening builder-specific logic.
- Risk:
  - Builder-side merging could re-fragment or double-merge already normalized output.
- Done when:
  - A fresh resumed driver run consumes the new stage output cleanly and does not regress Story 140's reviewed non-regression chapters.

#### Task 4 — Add Focused Regression Coverage Before Benchmark Expansion

- Files: `tests/test_genealogy_table_consistency_v1.py`, optionally minimal additions to `tests/test_build_chapter_html.py`
- Change:
  - Add fixture-backed tests for the reviewed patterns: combined-header pages like `40/41`, fragmented runs like `43/45`, and a chapter-level consistency case modeled on `chapter-014.html`.
  - Add acceptance tests that explicitly guard summary-table preservation, run rejection on content loss, and narrow `<br>` subgroup splitting if that cleanup lands.
  - Only add new promptfoo goldens/evals if the final stage output stabilizes enough that hand-verified chapter/run goldens are worth the maintenance cost.
- Risk:
  - Expanding promptfoo too early will create churn before the normalization contract is stable.
- Done when:
  - Current `r19` inconsistency signatures fail the focused fixtures, and the new stage makes them pass without builder regressions.

#### Task 5 — Driver Validation and Manual Inspection

- Files: run-local resume recipe/config under `output/runs/`, story work log, and any touched docs
- Change:
  - Clear stale `*.pyc`, run through `driver.py` from the new stage using reused artifacts, and inspect the resulting HTML/JSONL artifacts.
  - Manually verify `chapter-009.html`, `chapter-010.html`, `chapter-013.html`, `chapter-014.html`, `chapter-015.html`, plus at least one non-regression chapter from `chapter-018.html` / `chapter-020.html`.
  - Record specific artifact paths and sample rows/headings verified.
- Done when:
  - The reviewed chapters no longer mix compatible genealogy structures, totals remain separate, and the non-regression set still looks correct by manual inspection.

### Scope Adjustment

- Small coherent scope expansion absorbed: the new adapter stage should emit a companion report JSONL even if no schema change is required. That report is the cleanest way to preserve inspectable normalization decisions without bloating `page_html_v1`.
- Small coherent scope expansion absorbed: the cheapest trustworthy validation path is a reused-artifact resume recipe, because the shared Onward output root lives outside this worktree and `r19` already proves the `load_artifact_v1` path.
- Small coherent scope contraction absorbed: promptfoo/golden expansion is not the default first guardrail. Focused fixture tests plus manual driver inspection are the lower-risk path until the normalization output stabilizes.

### Human Approval Gate

- No new dependencies are expected.
- Recommended default model for the new stage: `gpt-5`. The measured `gpt-4.1` baselines are promising on very small runs but materially weaker on a six-page slice.
- Main risks to watch:
  - run detection that over-merges genuinely different source structures;
  - acceptance logic that allows silent content loss;
  - builder double-processing already-normalized HTML;
  - latency/cost if run chunking is too coarse.
- Success is falsified if a fresh driver validation run still leaves mixed compatible genealogy table shapes in `chapter-010.html` / `chapter-013.html` / `chapter-014.html` / `chapter-015.html`, or if `chapter-009.html`, `chapter-018.html`, or `chapter-020.html` regress.

## Work Log

20260314-1058 — story created: split chapter-level genealogy consistency normalization out of Story 140 after manual review of `story140-onward-targeted-rescue-r19` showed that page rescue recovered data but not chapter-wide structural consistency; next step is `/build-story` to evaluate AI-first normalization against the reviewed Arthur/Paul/George/Joe chapters
20260314-1511 — exploration + AI-first baseline grounded Story 141 in the live `r19` artifacts and selected a new adapter-stage seam
- **Result:** Verified that the reviewed inconsistency is already present upstream in `pages_html_onward_tables_fixed.jsonl`, quantified the current chapter-level failure signatures, and measured bounded one-shot AI normalization on both contiguous page runs and a full problematic chapter. The strongest measured baseline (`gpt-5` on `chapter-014.html`) already collapses the mixed structure into one canonical genealogy table plus a separate summary table, so the story should center an AI normalization stage with thin deterministic validation rather than more builder heuristics.
- **Impact:**
  - **Story-scope impact:** The implementation path is now materially clearer. This is not a good candidate for adding more special cases to `table_rescue_onward_tables_v1` or `build_chapter_html_v1`; a new `genealogy_table_consistency_v1` adapter stage is the clean seam.
  - **Pipeline-scope impact:** The baseline proves a strong model can normalize same-schema runs across page boundaries. `gpt-4.1` fixed the core two-page pattern (`40-41`) but was weaker on the six-page run (`40-45`), while `gpt-5` normalized the full reviewed `chapter-014.html` from `15` mixed tables down to `2` tables with split `BOY/GIRL`, `31` subgroup rows, and a separate totals table.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/01_load_artifact_v1/pages_html_onward_tables_fixed.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-010.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story140-onward-targeted-rescue-r19/output/html/chapter-014.html`, `/tmp/story141_ai_baseline_pages40_41_gpt41.html`, `/tmp/story141_ai_baseline_pages40_45_gpt41.html`, `/tmp/story141_ai_baseline_ch14.html`
  - **Next:** After approval, implement `genealogy_table_consistency_v1`, wire it into the Onward recipe/resume path, and validate through `driver.py` with artifact reuse. Success is falsified if the reviewed chapters still mix compatible table shapes or if `chapter-009.html` / `chapter-018.html` / `chapter-020.html` regress.
