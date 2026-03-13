# Story 138 — Onward Genealogy Table Whole-Table Continuation and Header Regressions

**Priority**: High
**Status**: Done
**Ideal Refs**: Requirement #3 (Extract), Requirement #6 (Validate), Fidelity to Source
**Spec Refs**: C1 (OCR quality), C3 (layout detection)
**Depends On**: Story 131 (table structure fidelity), Story 129 (HTML output polish)

## Goal

Fix the reviewed Onward genealogy-table regressions that affect whole-table continuity in final HTML: family-table tails drifting into the next family’s chapter, same-family prose/table splits across adjacent chapters, and terminal summary rows or family headers getting detached because the table is no longer kept as one chapter-owned unit. Within-table OCR/rescue fidelity is explicitly split to Story 140.

## Acceptance Criteria

- [x] Reviewed genealogy tables stay attached to the correct family chapter in the current verification run; no reviewed chapter begins with the previous family’s leftover table rows
- [x] Reviewed genealogy tables include their own terminal rows and summary counts (`Total/Descendants/Living/Deceased`) instead of spilling those rows into the next family
- [x] Reviewed family table headers render correctly when the issue is chapter-boundary ownership, including separate `BOY` and `GIRL` columns and the missing `Antoine L'Heureux` family header
- [x] Manual verification of regenerated chapters confirms the reviewed Arthur/Josephine-Paul/Roseanna-Antoinette-Emilie/Pierre-Antoine table spans are self-contained at the chapter/whole-table level; remaining within-table OCR or rescue corruption is tracked in Story 140

## Out of Scope

- Missing prose pages or chapter-boundary defects
- Within-table OCR or rescue fidelity once the correct family table pages are attached together; split to Story 140
- Image placement, image attachment, or caption pairing issues
- New table golden-reference creation unrelated to the reviewed regressions

## Approach Evaluation

- **Simplification baseline**: Trace the reviewed failing tables through the existing rescued-table artifacts and compare them to final HTML. If the rows already exist upstream, fix the continuation or export stages instead of re-solving OCR.
- **AI-only**: Re-run only the flagged table pages through a stronger table rescue prompt/model. This is justified only if the table tails are actually missing from upstream rescued HTML.
- **Literal-row fallback**: If direct image-to-HTML rescue is still model-wrong on the reviewed pages, test a stricter "one visual line = one JSONL row" transcription pass on just the flagged spans, then assemble HTML deterministically. Treat this as a fallback tactic inside this story, not a new default pipeline architecture.
- **Hybrid**: Use deterministic tracing to find whether the problem is in rescue, continuation fixing, or export; apply targeted AI only to the pages whose table structure is genuinely unresolved.
- **Pure code**: If the reviewed summary rows exist upstream but are dropped or misaligned later, fix the post-processing/continuation logic deterministically.
- **Eval**: Reviewed-table fidelity is the gate: the cited headers and terminal count rows must appear in final HTML on the correct family chapter, with no cross-family leakage.

## Tasks

- [x] Trace the reviewed table-bleed defects through `table_rescue_onward_tables_v1`, `table_fix_continuations_v1`, chapter portionization, and final HTML to identify the exact failure stage
- [x] Diagnose whether each reviewed defect is model-wrong, post-processing-wrong, or export-wrong
- [x] If upstream rescue is still model-wrong on the reviewed spans, compare the current direct-HTML prompt against a literal-row JSONL stepping-stone prompt before adding more deterministic cleanup
- [x] Fix the highest-leverage root cause for the reviewed whole-table header and tail-row ownership regressions
- [x] Add regression coverage or eval coverage for the reviewed table tails and header alignment cases
- [x] Regenerate and manually verify the reviewed chapters for whole-table continuity/ownership
- [x] Run required checks:
  - [x] `python -m pytest tests/`
  - [x] `python -m ruff check modules/ tests/`
- [x] Search all docs and update any related to what we touched
- [x] Verify Central Tenets:
  - [x] T0 — Traceability: every output traces to source page, OCR engine, confidence, processing step
  - [x] T1 — AI-First: didn't write code for a problem AI solves better
  - [x] T2 — Eval Before Build: measured SOTA before building complex logic
  - [x] T3 — Fidelity: source content preserved faithfully, no silent losses
  - [x] T4 — Modular: new recipe not new code; no hardcoded book assumptions
  - [x] T5 — Inspect Artifacts: visually verified outputs, not just checked logs

## Files to Modify

- `modules/adapter/table_rescue_onward_tables_v1/main.py` — if the reviewed rows/headers are already wrong in rescue output
- `modules/adapter/table_fix_continuations_v1/main.py` — if reviewed tail rows disappear or shift during continuation repair
- `modules/build/build_chapter_html_v1/main.py` — if reviewed table tails exist upstream but are assigned to the wrong chapter during final HTML assembly
- `benchmarks/tasks/onward-table-fidelity.yaml` — if the reviewed regressions need to be promoted into eval coverage
- `tests/test_build_chapter_html.py` — extend existing chapter-build regression coverage for reviewed header/tail cases
- `tests/test_table_rescue_onward_tables_v1.py` — cover model-request compatibility for targeted rescue retries

## Notes

- Manual review defects feeding this story:
  - `chapter-009.html` in the original review — `BOY/GIRL` merged, `Died` header displaced
  - `chapter-011.html`, `chapter-026.html`, `chapter-027.html`, `chapter-028.html` in the original review — missing terminal genealogy-table rows or summary counts
  - `story137-onward-verify` round-2 review:
    - `chapter-009.html` tail rows incorrectly start `chapter-010.html`
    - `chapter-011.html` tail rows incorrectly start `chapter-012.html`
    - `chapter-012.html` tail rows incorrectly start `chapter-013.html`
    - `chapter-013.html` tail rows incorrectly start `chapter-014.html`
    - `chapter-014.html` tail rows incorrectly start `chapter-015.html`
    - `chapter-017.html` cuts off the last half of Emilie Nolin’s table into `chapter-018.html`
    - `chapter-018.html` loses the bottom total/living/deceased counts into the next family page
    - `chapter-021.html` cuts off Pierre L'Heureux’s table into `chapter-022.html`
    - `chapter-022.html` starts with the prior family’s tail and is missing the `Antoine L'Heureux` table header
  - `story139-onward-full127-composite-validate` review:
    - `chapter-010.html` ends with a genealogy-table tail that begins `chapter-011.html`
    - `chapter-013.html` ends with a genealogy-table tail that begins `chapter-014.html`
    - `chapter-014.html`, `chapter-016.html`, `chapter-018.html`, `chapter-020.html`, and `chapter-024.html` each lose the family genealogy table into the next chapter
    - `chapter-022.html` leaves the last quarter of the genealogy outside table structure
    - `chapter-025.html` is only the middle of the prior family’s genealogy and itself continues again on the next page
    - `chapter-026.html`, `chapter-028.html`, and `chapter-029.html` begin with the prior family’s leftover table rows
- Story 131 proved high benchmark fidelity on the golden tables. This story exists because real-run HTML still shows reviewed regressions that the benchmark set did not catch.

## Plan

### Exploration Findings

- The reviewed tail-row bleed is already present in the reused `story139-onward-full127-composite-validate` final HTML, but the offending rows still exist upstream in both `02_load_artifact_v1/pages_html_onward_tables.jsonl` and `05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`. This is not an OCR-loss problem on the reviewed pages.
- `table_fix_continuations_v1` is currently a narrow DIED-column repair. It does not change chapter ownership, and the reviewed boundary pages are materially identical before and after that stage for the spill cases inspected (`printed_page_number` 26, 48, 89, 90, 94, 103, 109).
- The dominant failure is in `build_chapter_html_v1::_refine_chapter_segments()`. When a TOC portion begins with one or more headless continuation pages and the first strong owner heading appears later, the function currently retitles the entire accumulated segment to that later heading instead of splitting at the heading page.
- Baseline diagnostic on the current verification run found 9 coarse portions with leading headless pages before the first strong owner heading: `Alma`, `Arthur`, `Leonidas`, `Josephine`, `Antoinette`, `Emilie`, `Wilfred`, `Pierre`, and `Antoine`. Eight of those are directly aligned with the reviewed cross-family spill pattern; the `Antoine` case is currently protected only because its later heading (`I WISH`) is not a known candidate title.
- Existing unit coverage in `tests/test_build_chapter_html.py` already exercises `_refine_chapter_segments()`, but one test (`test_retitles_stale_coarse_span_from_first_visible_owner`) currently codifies the buggy retitling behavior. This story should update that coverage instead of creating a separate standalone regression file.

### Ideal Alignment Gate

- This story closes a direct Ideal gap: the final HTML is not faithfully preserving genealogy-table ownership and terminal rows even though the upstream rescued HTML contains them.
- No new AI compromise is being introduced. The evidence so far says this is a deterministic ownership/export defect, so the highest-value move is to fix chapter assembly before considering new table-rescue prompts.

### Eval / Baseline

- Eval for this story: chapter-build regression coverage around `_refine_chapter_segments()` plus a resumed `driver.py` run from `build` using the reviewed Onward artifacts.
- Baseline on the current code: 9 coarse portions in the reviewed run accumulate leading headless pages and then retitle the whole segment to a later owner heading. Representative cases:
  - `Alma` (`18-25`) retitles the whole span to `ARTHUR L'HEUREUX` after the first owner heading appears on page 19.
  - `Arthur` (`26-36`) retitles the whole span to `LEONIDAS L'HEUREUX` after the first owner heading appears on page 29, dragging pages 26-28 into the wrong chapter.
  - `Pierre` (`103-108`) retitles the whole span to `ANTOINE L'HEUREUX` after the first owner heading appears on page 107, dragging pages 103-106 into the wrong chapter.
- Upstream baseline evidence checked:
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/02_load_artifact_v1/pages_html_onward_tables.jsonl`
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/06_build_chapter_html_v1/chapters_manifest.jsonl`

### Implementation Plan

#### Task 1 — Fix chapter-segmentation ownership in `build_chapter_html_v1`

- File: `modules/build/build_chapter_html_v1/main.py`
- Change:
  - Rework `_refine_chapter_segments()` and the surrounding build flow so that stale coarse TOC spans do not retroactively rename already-accumulated headless pages into the next owner chapter.
  - When a coarse span’s owner title has effectively already been emitted earlier, treat leading headless/continuation pages as carry-back content for the previous chapter until a new strong owner heading begins.
  - Keep the logic generic: use title relationships, heading strength, and stale-span detection rather than book-specific family names or page IDs.
  - Preserve the current guard against internal/subfamily headings such as `NOEL'S FAMILY`; allow late strong non-TOC headings only when the stale coarse span has already consumed its nominal owner earlier.
- Risk:
  - Over-splitting on legitimate within-chapter headings if the candidate-title checks are loosened too much.
  - Regressing prose chapter titles that intentionally retitle from a first-page owner heading.
- Done when:
  - The reviewed leading tail pages no longer get renamed into the next owner chapter in unit tests and in the resumed pipeline output.
  - Anonymous stale continuation spans merge backward instead of producing duplicate stray chapters when the surrounding structure signals that the owner was already emitted.

#### Task 2 — Update and extend regression coverage in the existing build test file

- File: `tests/test_build_chapter_html.py`
- Change:
  - Replace the stale test that expects retroactive retitling from a later owner heading.
  - Add regression cases for:
    - headless leading pages before a later owner heading (`Arthur` -> `Leonidas`, `Pierre` -> `Antoine`);
    - stale anonymous tail spans that should merge backward instead of producing duplicate chapters (`Roseanna` -> prior `Emilie`);
    - same-page splits only when the heading is a known candidate title;
    - no split/no retitle for non-candidate headings unless the coarse span is already stale (`I WISH`, subfamily headings).
- Risk:
  - None beyond needing to be explicit about the intended segmentation contract.
- Done when:
  - The regression tests fail on current behavior and pass with the fix.

#### Task 3 — Re-run the real pipeline from `build` and inspect reviewed HTML artifacts

- Files/artifacts:
  - run-local config or resumed `driver.py` command against `story139-onward-full127-composite-validate`
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/<run_id>/output/html/chapter-*.html`
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/<run_id>/06_build_chapter_html_v1/chapters_manifest.jsonl`
- Change:
  - Reuse the existing rescued-table artifact set and rerun from `build` (or from the earliest changed stage if the implementation needs it).
  - Manually inspect the reviewed Arthur / Josephine-Paul / Roseanna-Antoinette-Emilie / Pierre-Antoine spans in the regenerated HTML.
- Risk:
  - If build-only repair is insufficient, the remaining gap will likely be portionization policy rather than OCR rescue.
- Done when:
  - The reviewed terminal rows and summary counts stay with the correct family chapter and the missing `Antoine L'Heureux` family header is present in the right chapter.

#### Task 4 — Run required checks and update docs/work log

- Files:
  - `docs/stories/story-138-onward-genealogy-table-continuation-and-header-regressions.md`
  - `docs/stories.md`
  - any touched docs if the segmentation contract or validation evidence changes
- Change:
  - Run targeted tests during implementation, then `python -m pytest tests/` and `python -m ruff check modules/ tests/`.
  - Record artifact paths and manual inspection evidence in the work log.
- Done when:
  - Story work log, status, and tenet checklist reflect the validated result.

### Scope Adjustment

- Small coherent scope adjustment absorbed: regression coverage should extend `tests/test_build_chapter_html.py` instead of creating a new `tests/test_onward_table_regressions.py`, because the failure is localized to chapter-build segmentation logic and existing tests already cover that seam.

### Human Approval Gate

- No new dependencies or schema changes are anticipated.
- Main risk to watch: the segmentation fix could improve the reviewed table ownership cases while still leaving a few prose/title edge cases around first-page retitling. The unit tests will need to pin both sides of that contract before the resumed pipeline run.

## Work Log

### 20260312-1710 — story created from manual review
- **Result:** Created a focused follow-up story for reviewed genealogy-table regressions that remain in the final Onward HTML despite earlier table-fidelity work.
- **Evidence:** User review identified merged `BOY/GIRL` headers in `chapter-009.html` plus missing terminal summary rows/tails in `chapter-011.html`, `chapter-026.html`, `chapter-027.html`, and `chapter-028.html`.
- **Next:** Build-story should trace each reviewed defect through the rescued-table artifacts before deciding whether the fix belongs in rescue, continuation repair, or final HTML assembly.

### 20260313-0905 — round-2 manual review shows repeated cross-family table bleed
- **Result:** The latest verification run confirms the table problem is broader than missing terminal rows: genealogy-table tails are repeatedly assigned to the next family chapter.
- **Evidence:**
  - `output/runs/story137-onward-verify/output/html/chapter-009.html` through `chapter-015.html` show a repeated pattern where one family’s table tail appears at the start of the next family chapter
  - `output/runs/story137-onward-verify/output/html/chapter-017.html` through `chapter-022.html` show the same bleed pattern again, plus a missing `Antoine L'Heureux` table header
- **Decision:** Keep this story focused on family-table ownership and tail-row continuity, not just single-page header alignment.
- **Next:** Build this story from the current `story137-onward-verify` run and trace whether the bleed starts in `table_rescue_onward_tables_v1`, `table_fix_continuations_v1`, or chapter assignment.

### 20260313-1040 — inbox OCR stepping-stone idea folded into story
- **Result:** Triaged the inbox "two-step line-by-line transcription" idea into this story as a fallback experiment, not a new standalone story.
- **Evidence:** Story 131 already proved direct table rescue can hit the benchmark gate, but the real-run regressions in `story137-onward-verify` still show cross-family tail bleed and header loss that may warrant a stricter row-presence tactic on flagged spans.
- **Decision:** First trace whether the defect is post-processing/export. Only if the reviewed rows are genuinely wrong or missing upstream should this story compare direct HTML rescue against a literal-row JSONL stepping-stone pass.
- **Next:** During build-story execution, use the current reviewed spans to decide whether the fallback earns promotion into regression coverage or can be discarded after diagnosis.

### 20260313-1238 — Story 139 review confirms the table-continuation story remains the dominant Onward fidelity gap
- **Result:** Manual review of the page-safe `story139-onward-full127-composite-validate` run shows Story 139 fixed the chapter-boundary/title issues it targeted, but genealogy-table continuation is still repeatedly wrong in final HTML.
- **Evidence:**
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/output/html/chapter-010.html` and `chapter-011.html` still split one family table across two chapters
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/output/html/chapter-013.html` through `chapter-029.html` repeat the same spill pattern across multiple families
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/output/html/chapter-022.html` adds a new failure mode where the last quarter of the genealogy is no longer table-structured
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/output/html/chapter-025.html` is mostly detached middle-table content, not a self-contained family chapter
- **Decision:** These findings stay in Story 138. They are not evidence that Story 139 failed; they are confirmation that table ownership/continuation is still the next Onward bottleneck after boundary repair.
- **Next:** When building Story 138, use `story139-onward-full127-composite-validate` as the primary reviewed artifact set instead of the older unsafe `onward-story009-full` run.

### 20260313-1335 — exploration traced the dominant regression to generic stale-span ownership in build, not OCR loss
- **Result:** Traced the reviewed family-table bleed through the reused `story139-onward-full127-composite-validate` artifacts and found that the offending rows still exist upstream; the dominant defect is chapter ownership during `build_chapter_html_v1`, not table rescue or continuation repair.
- **Evidence:**
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/02_load_artifact_v1/pages_html_onward_tables.jsonl` and `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/05_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl` both still contain the reviewed table tails and summary rows on the boundary pages (for example printed pages 26, 48, 89, 90, 103)
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/06_build_chapter_html_v1/chapters_manifest.jsonl` shows repeated retitling where later owner headings absorb earlier headless pages, e.g. source portion `Arthur` (`26-36`) becomes `LEONIDAS L'HEUREUX`, and source portion `Pierre` (`103-108`) becomes `ANTOINE L'HEUREUX`
  - A diagnostic pass over `_refine_chapter_segments()` on the reviewed run found 9 portions with leading headless pages before the first owner heading; the current function retitles the whole accumulated span in 8 of those cases, matching the manual review pattern
- **Decision:** Keep the implementation focused on `build_chapter_html_v1` segmentation logic plus regression coverage in `tests/test_build_chapter_html.py`. Do not spend story scope on rescue-prompt changes unless the build fix fails to clear the reviewed spill cases.
- **Decision update:** Per user guidance, treat this as a generic PDF-processor stale-span problem, not an Onward-specific family-name fix. The build logic should reason from stale coarse titles, heading strength, and continuation pages so the same pattern works on other scanned books that overrun coarse TOC boundaries.
- **Next:** After approval, update `_refine_chapter_segments()` and the stale unit test that currently expects retroactive retitling, then rerun the pipeline from `build` and manually inspect the reviewed chapters.

### 20260313-1508 — implemented generic stale-span carry-back in chapter build and validated on a fresh driver run
- **Result:** Reworked `build_chapter_html_v1` so stale coarse TOC spans can emit carry-back segments for leading anonymous pages, then merge those pages into the previously emitted chapter instead of renaming them into the next owner chapter. Added trace fields for merged coarse sources and extended the existing build tests to lock the generic contract.
- **Impact:**
  - **Story-scope impact:** Cleared the dominant acceptance-criteria blocker: family-table tails and terminal summary rows now stay with the owning family chapter in the reviewed verification run.
  - **Pipeline-scope impact:** The rebuilt HTML no longer opens the reviewed downstream chapters with prior-family genealogy leftovers; stale duplicate spans now fold backward generically based on emitted-title staleness and heading strength instead of book-specific rules.
  - **Evidence checked:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/06_build_chapter_html_v1/chapters_manifest.jsonl`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-010.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-024.html`, `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-028.html`
  - **Next:** No immediate follow-up is required for this story. If later review still dislikes the `I WISH` late-heading split, treat that as a separate title/appendix policy story rather than reopening the genealogy-table ownership fix.
- **Evidence:**
  - Fresh driver run: `python driver.py --recipe /Users/cam/Documents/Projects/codex-forge/output/runs/story139-onward-full127-composite-validate/snapshots/recipe.yaml --run-id story138-onward-stale-span-validate --output-dir /Users/cam/Documents/Projects/codex-forge/output/runs`
  - `tests/test_build_chapter_html.py` now passes 59 focused build tests, including stale carry-back cases and CLI-level merge verification
  - Repo-wide checks passed:
    - `python -m pytest tests/ -q` → `551 passed, 6 skipped`
    - `python -m ruff check modules/ tests/` → clean
  - Manual artifact inspection on the fresh run:
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/06_build_chapter_html_v1/chapters_manifest.jsonl` now shows the reviewed coarse spans merged into the right chapters:
      - `chapter-010.html` `ARTHUR L'HEUREUX` covers printed pages `19-28` with `source_portion_titles=["Alma","Arthur"]`
      - `chapter-013.html` `PAUL L'HEUREUX` covers printed pages `45-50` with `source_portion_titles=["Leonidas","Josephine"]`
      - `chapter-024.html` `EMILIE (L'HEUREUX) NOLIN` covers printed pages `87-92` with `source_portion_titles=["Marie-Louise","Roseanna","Antoinette"]`
      - `chapter-027.html` `PIERRE L'HEUREUX` covers printed pages `99-106` with `source_portion_titles=["Wilfred","Pierre"]`
      - `chapter-028.html` `ANTOINE L'HEUREUX` covers printed pages `107-110` with `source_portion_titles=["Pierre","Antoine"]`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-010.html` begins with `ARTHUR L'HEUREUX` content instead of Alma tail rows, and its first genealogy table header is `NAME | BORN | MARRIED | SPOUSE | BOY | GIRL | DIED`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-013.html` ends with a self-contained summary table: `TOTAL DESCENDANTS 68`, `LIVING 65`, `DECEASED 3`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-024.html` retains Emilie’s detached span plus summary counts inside one chapter: `TOTAL DESCENDANTS 83`, `LIVING 78`, `DECEASED 5`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-028.html` includes the missing `ANTOINE’S FAMILY` row and ends with `TOTAL DESCENDANTS 38`, `LIVING 36`, `DECEASED 2`
- **Central Tenets:**
  - **T0 Traceability:** Added `source_portion_titles` and `source_portion_page_starts` alongside the existing `source_printed_pages`/`source_pages` fields so merged stale spans remain auditable in the chapter manifest.
  - **T1 AI-First:** The defect was downstream ownership, not missing OCR. Fixing build-time ownership was the correct cheaper move; no unnecessary rescue prompt escalation was added.
  - **T2 Eval Before Build:** Established a concrete baseline on the reviewed run (9 stale spans) and locked the contract with focused regression tests before changing the build flow.
  - **T3 Fidelity:** The fix reassigns already-extracted pages to the correct owning chapter without hand-editing content or losing rows.
  - **T4 Modular:** The change lives in the generic chapter builder and test suite, driven by title/heading relationships rather than Onward-specific names.
  - **T5 Inspect Artifacts:** Manually inspected the regenerated manifest and reviewed HTML chapters in the fresh run above.

### 20260313-1536 — manual review found residual same-family split regressions; story reopened
- **Result:** User review of `story138-onward-stale-span-validate` confirmed the cross-family bleed is much improved and no data appears lost, but several same-family prose/table pairs are still split across adjacent chapters, so this story is not done yet.
- **Evidence:**
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-014.html`, `chapter-016.html`, `chapter-018.html`, `chapter-020.html`, and `chapter-025.html` still keep prose in one chapter and push the same family’s genealogy table into the next chapter
  - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate/output/html/chapter-022.html` still leaves the last quarter of the genealogy outside table structure
  - Image-placement/caption issues in `chapter-011.html`, `chapter-014.html`, `chapter-024.html`, and `chapter-027.html`, plus the `chapter-003.html` logo/seal issue, are real but remain out of scope for this story because they are image-placement/caption problems rather than table-ownership logic
- **Decision:** Reopen Story 138 and keep it focused on the residual table/chapter-ownership problems. Do not fold the image-placement/caption regressions into this story unless explicitly requested.
- **Next:** Diagnose why first-owner pages that match the previous emitted chapter title are still being emitted as separate same-family chapters (`George`, `Joe`, `Mathilda`, `Marie-Louise`, `Wilfrid`) and patch the builder so those prefixes merge backward generically before re-running the pipeline.

### 20260313-1509 — fixed generic same-family stale-prefix ownership and isolated the last remaining upstream rescue miss
- **Result:** Tightened the generic title matcher so single-letter surname fragments no longer create false owner matches, extended `_refine_chapter_segments()` coverage for anonymous-prefix + previous-owner carry-back, and validated a fresh build run where the stray same-family split chapters collapse back into contiguous family chapters. Also fixed `table_rescue_onward_tables_v1` so `gpt-5`-family models no longer receive an unsupported `temperature` parameter, then used targeted one-page rescue experiments to trace the remaining Roseanna defect.
- **Impact:**
  - **Story-scope impact:** Cleared the reopened same-family chapter-split blocker. `GEORGE`, `JOE`, `MATHILDA`, `MARIE-LOUISE`, `EMILIE`, `PIERRE`, and `ANTOINE` now each own contiguous printed-page spans instead of splitting prose and genealogy tables into adjacent chapters.
  - **Pipeline-scope impact:** The fresh validation run dropped the stray split-chapter count from 29 chapter files to 24, eliminating the detached middle-family chapters that were still appearing after the first stale-span fix. The only remaining reviewed defect is now a single malformed rescued table page (printed page `80`, source `page_number=89`) that was already wrong upstream before build.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/06_build_chapter_html_v1/chapters_manifest.jsonl` shows `chapter-014.html` `GEORGE L'HEUREUX` at printed pages `51-56`, `chapter-016.html` `MATHILDA (L'HEUREUX) DEVLIN` at `63-68`, `chapter-020.html` `EMILIE (L'HEUREUX) NOLIN` at `87-92`, `chapter-022.html` `PIERRE L'HEUREUX` at `99-106`, and `chapter-023.html` `ANTOINE L'HEUREUX` at `107-110`; `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-014.html`, `chapter-016.html`, and `chapter-020.html` now end with their own genealogy material and summary counts instead of pushing tables into the next chapter; `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/02_load_artifact_v1/pages_html_onward_tables.jsonl` shows the Roseanna tail on printed page `80` is still paragraph-only upstream, so that remaining defect is not another build-stage ownership failure.
  - **Next:** Story 138 remains `In Progress` until the Roseanna tail is either accepted or repaired upstream. The current best rescue experiment is `/tmp/story138-page89-rerescue-gpt41/pages_html_onward_tables.jsonl`, which improves printed page `80` into mixed table/heading structure; `gpt-5` rescue is now API-compatible but still returned blank output on this page. Success is falsified if any further rescue attempt reopens the fixed chapter-ownership regressions or if Roseanna still renders as mostly loose paragraphs.
- **Evidence:**
  - Focused tests:
    - `python -m pytest tests/test_build_chapter_html.py -q` → `64 passed`
    - `python -m pytest tests/test_table_rescue_onward_tables_v1.py tests/test_build_chapter_html.py -q` → `66 passed`
  - Repo-wide checks:
    - `python -m pytest tests/ -q` → `558 passed, 6 skipped`
    - `python -m ruff check modules/ tests/` → clean
  - Fresh driver validation runs:
    - `story138-onward-stale-span-validate-r2` from the reused composite artifacts
    - `story138-onward-stale-span-validate-r3` using `/tmp/story138-page89-rerescue-gpt41/pages_html_onward_tables.jsonl` as the upstream table artifact
- **Decision:** Keep Story 138 open. The generic chapter-boundary/stale-span bugs are fixed, but the reviewed Roseanna tail remains an upstream rescue-quality issue rather than a build-stage ownership bug.

### 20260313-1528 — post-review triage confirmed chapter splitting is fixed; remaining failures are upstream table-rescue fidelity
- **Result:** Compared the user-reviewed `r3` HTML against `r2` and confirmed the newly noticed `chapter-010.html` and `chapter-020.html` table problems were already present before the Roseanna experiment. The only `r3`-specific table regression is `chapter-018.html` (Roseanna), so the one-page Roseanna rescue should not be treated as the new baseline. Then ran targeted `gpt-4.1` re-rescue experiments on source pages `35`, `97`, and `98` (printed pages `26`, `88`, `89`) and validated a new build run `story138-onward-stale-span-validate-r4`.
- **Impact:**
  - **Story-scope impact:** User review now effectively closes the chapter-splitting portion of Story 138: the family-content bleed/same-family split bug is fixed in the builder. The remaining open work is upstream genealogy-table fidelity on a small set of suspect rescued pages.
  - **Pipeline-scope impact:** `r4` shows targeted upstream AI rescue can materially improve at least one reviewed bad table page without reintroducing the chapter-boundary regressions. Arthur page `26` is substantially improved in final HTML, while Emilie pages `88-89` improve only partially and still need a better rescue/escalation strategy.
  - **Evidence:** `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-010.html` and `chapter-020.html` are byte-identical to `r3`, proving those table issues are not fallout from the Roseanna experiment; `/tmp/story138-multipage-rerescue-gpt41/pages_html_onward_tables.jsonl` shows `gpt-4.1` recovered missing Arthur family tables on `page_number=35` / printed `26`; `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/output/html/chapter-010.html` now includes `RICHARD'S FAMILY`, `PAUL'S FAMILY`, `VIVIAN'S FAMILY`, `HUBERT'S FAMILY`, `YVONNE'S FAMILY`, `FLOYD'S FAMILY`, and `NEIL'S FAMILY` with child rows instead of heading-only stubs.
  - **Next:** Keep Story 138 open and shift the active implementation seam upstream into rescue quality for a handful of suspect genealogy pages. Success is falsified if a rescue improvement reopens the fixed build-stage chapter ownership bugs or if the Emilie pages remain materially corrupted after targeted rescue.
- **Evidence:**
  - User-reviewed runs:
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r3/output/html/index.html`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-010.html`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-020.html`
  - Upstream diagnosis:
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/02_load_artifact_v1/pages_html_onward_tables.jsonl` page `35` already ends with `RICHARD'S FAMILY` / `PAUL'S FAMILY` / `VIVIAN'S FAMILY` heading-only stubs, and page `97` / `98` already contain the Emilie table corruption before build
  - Targeted rescue experiments:
    - `/tmp/story138-multipage-rerescue-gpt41/pages_html_onward_tables.jsonl`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/output/html/chapter-010.html`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r4/output/html/chapter-020.html`
- **Decision:** Do not promote `r3` as the preferred review run. `r4` is the better evidence run if the goal is “chapter splitting fixed plus targeted Arthur-table recovery,” but Emilie rescue quality is still not strong enough to close the story.

### 20260313-1539 — residual within-table rescue work split to Story 140 by user request
- **Result:** Split the remaining within-table OCR/rescue fidelity work into Story 140 so Story 138 stays aligned with its intended scope: keeping each family table treated as a whole and attached to the correct chapter.
- **Evidence:**
  - `/Users/cam/.codex/worktrees/f3ab/codex-forge/docs/stories/story-140-onward-targeted-genealogy-table-rescue-fidelity.md`
  - The latest review evidence shows the remaining open issues are table-internal rescue quality (`chapter-010.html`, `chapter-018.html`, `chapter-020.html`), not chapter ownership
- **Decision:** Story 138 no longer owns the residual within-table corruption. That follow-up work should proceed under Story 140, while Story 138 can be validated/closed against the whole-table ownership scope.

### 20260313-1602 — story rescoped to shipped whole-table continuity slice and marked done
- **Result:** Rescoped Story 138 to the delivered chapter-level genealogy-table ownership/continuity fix, reran the full repo checks, and closed the story. The delivered slice is coherent: reviewed genealogy tables now stay attached to the correct family chapter as whole units, while remaining within-table rescue defects are explicitly tracked in Story 140.
- **Evidence:**
  - Fresh validation checks:
    - `python -m pytest tests/` → `558 passed, 6 skipped`
    - `python -m ruff check modules/ tests/` → clean
  - Manual run evidence already recorded in this story and used for closure:
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/06_build_chapter_html_v1/chapters_manifest.jsonl`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-014.html`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-016.html`
    - `/Users/cam/Documents/Projects/codex-forge/output/runs/story138-onward-stale-span-validate-r2/output/html/chapter-020.html`
- **Decision:** Story 138 is complete for whole-table continuation/ownership. Story 140 owns the remaining Arthur/Roseanna/Emilie within-table rescue fidelity work.
