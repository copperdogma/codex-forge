# Story 141 — Onward Genealogy Table Consistency Pass

**Priority**: High
**Status**: Pending
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
- **Data contracts / schemas**: If the pass emits new normalized HTML artifacts or normalization-decision metadata across stages, add the fields to `schemas.py` before relying on them. If the work stays inside final build only, schema impact may be avoidable.
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

Pending `/build-story`. The first gate is to measure the one-shot strong-model normalization baseline before deciding whether this becomes a dedicated new stage, a builder-owned pass, or a hybrid helper.

## Work Log

20260314-1058 — story created: split chapter-level genealogy consistency normalization out of Story 140 after manual review of `story140-onward-targeted-rescue-r19` showed that page rescue recovered data but not chapter-wide structural consistency; next step is `/build-story` to evaluate AI-first normalization against the reviewed Arthur/Paul/George/Joe chapters
