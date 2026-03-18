# Story 149 — Onward Scanned-Genealogy Collapse Implementation

**Priority**: High
**Status**: Done
**Ideal Refs**: Requirement #3 (Extract), Requirement #5 (Structure), Requirement #6 (Validate), Fidelity to Source, Transparency over Magic, Graduate, don't accumulate
**Spec Refs**: spec:2.1 C1 (Multi-Stage OCR Pipeline), spec:3.1 C3 (Heuristic + AI Layout Detection), spec:5.1 C7 (Page-Scope Extraction with Document-Level Consistency Planning)
**Decision Refs**: `docs/build-map.md`, `docs/decisions/adr-001-source-aware-consistency-strategy/adr.md`, `docs/runbooks/document-consistency-planning.md`, Story 146 work log, Story 147 work log
**Depends On**: Story 146, Story 147

## Goal

Implement the first real simplification pass for the Onward scanned-genealogy seam named in Story 147 and the build map. The story should collapse the active workaround stack by deleting, narrowing, or merging at least one late repair layer only after proving a simpler maintained path still preserves the reviewed hard cases from `story146-onward-build-stitch-r5`. Success is not "move the same workaround somewhere else"; success is a smaller, still-inspectable seam that keeps subgroup rows, table continuity, and row-shape fixes correct in a real `driver.py` run.

## Acceptance Criteria

- [x] The implementation removes, narrows, or merges at least one of the collapse targets named in `docs/build-map.md` for the Onward seam, and the story work log records a file-level before/after mapping of what was deleted, what absorbed any retained logic, and why provenance/inspectability remain intact.
- [x] A real `driver.py` run on `configs/recipes/recipe-onward-images-html-mvp.yaml` or a clearly named replacement path produces artifacts in `output/runs/`, and manual inspection verifies the reviewed hard cases from `story146-onward-build-stitch-r5` remain acceptable in final HTML: `chapter-010.html`, `chapter-011.html`, `chapter-017.html`, and `chapter-022.html`, plus unchanged reference `chapter-023.html`.
- [x] The simplified path preserves the specific reviewed behaviors that justified Story 147's collapse candidate: page-break continuation tables remain merged, subgroup rows stay full-width, death values such as `, 1956` still land in `DIED`, and embedded-family header fixes such as `chapter-022.html` do not regress back to literal `BOY/GIRL` table headers.
- [x] If `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml` or another story-scoped proof loop becomes redundant, it is replaced by a smaller permanent regression bundle or clearly narrowed validation path rather than being left as a second permanent operating path.
- [x] Any layer that survives the collapse still has an explicit justification in the work log; the story does not silently keep duplicate repair responsibility across `rerun_onward_genealogy_consistency_v1`, `table_rescue_onward_tables_v1`, and `build_chapter_html_v1`.

## Out of Scope

- Claiming C1, C3, or C7 are fully deleted
- Reopening the row-structured / CSV / JSON fallback experiment from `docs/inbox.md` unless the simplification baseline clearly fails and the story is explicitly expanded
- Generalizing the collapse beyond the Onward scanned-genealogy recipe
- Re-running OCR from scratch unless the chosen simplification seam truly depends on OCR behavior
- Adding new intake-format stories such as born-digital PDF, DOCX, or handwriting support

## Approach Evaluation

- **Simplification baseline**: First measure whether disabling or sharply narrowing one late repair layer on reused Onward artifacts still passes the reviewed hard-case bar. If an earlier seam already carries the slice cleanly, prefer proving that over inventing new glue. If no such baseline works, the story should say so explicitly instead of claiming collapse by reshuffling code.
- **AI-only**: Push more of the seam into a broader source-aware rerun or a single stronger reread so late deterministic cleanup disappears. This may produce the largest conceptual simplification, but it risks higher OCR/runtime cost and weaker inspectability unless acceptance/fallback sidecars stay explicit.
- **Hybrid**: Keep the current planner/rerun architecture, but collapse one of the downstream deterministic layers after proving an earlier accepted seam now preserves table continuity, subgroup rows, and row shape by default. This is the most plausible compromise-elimination path because it can delete real code while keeping Story 146's traceability discipline.
- **Pure code**: Merge or relocate the existing deterministic repairs without changing upstream extraction quality. Cheapest to implement, but the weakest fit with the Ideal because it can make the workaround stack harder to inspect rather than smaller.
- **Repo constraints / prior decisions**: Story 147 and `docs/build-map.md` explicitly say the next step on this seam is complexity collapse, not another repair layer. ADR-001 keeps direct HTML as the default repair target and reserves structured fallback for evidence-driven escalation. OCR remains expensive, so artifact reuse and bounded reruns still matter.
- **Existing patterns to reuse**: `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml`, `modules/adapter/rerun_onward_genealogy_consistency_v1`, `modules/adapter/table_rescue_onward_tables_v1`, `modules/build/build_chapter_html_v1`, `tests/test_rerun_onward_genealogy_consistency_v1.py`, `tests/test_table_rescue_onward_tables_v1.py`, `tests/test_build_chapter_html.py`, and Story 146's reviewed artifact set.
- **Eval**: The deciding evidence is a real `driver.py` run plus manual inspection of the reviewed hard-case chapters, alongside a file-level layer map showing what truly became redundant. If the simplification materially changes the documented planning/rerun regression signal, update the relevant manual eval note in `docs/evals/registry.yaml`.

## Tasks

- [x] Re-read the Story 147 collapse inventory and Story 146 reviewed artifacts, then choose one explicit collapse seam to test first:
  - narrow or delete late `build_chapter_html_v1` genealogy stitching / subgroup-row cleanup
  - narrow or delete deterministic normalization in `table_rescue_onward_tables_v1`
  - absorb one of those responsibilities into an earlier accepted seam in `rerun_onward_genealogy_consistency_v1`
- [x] Measure the simplification baseline on reused Onward artifacts before broad edits:
  - identify which reviewed behaviors are already preserved upstream
  - identify which late layer is still doing unique work
  - stop and record the result if no deletion candidate is credible yet
- [x] Implement the smallest coherent collapse that deletes, narrows, or merges one layer without reopening the Story 146 hard cases.
- [x] If the chosen collapse still needs shared genealogy normalization across stages, consolidate that logic under one explicit owner instead of leaving private cross-imports between build, rescue, and rerun modules.
- [x] Update focused regressions so the hard-case behaviors are guarded at the seam that still owns them:
  - `tests/test_build_chapter_html.py`
  - `tests/test_rerun_onward_genealogy_consistency_v1.py`
  - `tests/test_table_rescue_onward_tables_v1.py`
- [x] Run the maintained Onward recipe or a clearly proposed replacement path through `driver.py`, verify artifacts in `output/runs/`, and manually inspect the final HTML plus any decision sidecars for `chapter-010.html`, `chapter-011.html`, `chapter-017.html`, `chapter-022.html`, and `chapter-023.html`.
- [x] If the story-scoped proof loop is no longer needed as-is, replace it with a smaller permanent regression bundle or clearly narrowed validation recipe and document that swap.
- [x] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [x] Run required checks for touched scope:
  - [x] Default Python checks: `make test`
  - [x] Default Python lint: `make lint`
  - [x] If pipeline behavior changed: clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and manually inspect the hard-case HTML / JSONL data
  - [x] If agent tooling changed: not applicable; no agent tooling changed
- [x] If evals or goldens changed materially: committed the reviewed HTML slice under `benchmarks/golden/onward/reviewed_html_slice/` and updated `docs/runbooks/golden-build.md`; no promptfoo score or `docs/evals/registry.yaml` update was required
- [x] Search all docs and update any related to what we touched
- [x] Verify Central Tenets:
  - [x] T0 — Traceability: the simplified seam still emits inspectable artifacts and does not hide repair responsibility
  - [x] T1 — AI-First: do not replace a now-adequate AI seam with deeper deterministic workaround code
  - [x] T2 — Eval Before Build: baseline the candidate collapse seam before deleting code
  - [x] T3 — Fidelity: subgroup rows, table continuity, and row-shape details remain faithful to source
  - [x] T4 — Modular: remove duplicate responsibility instead of smearing it across more modules
  - [x] T5 — Inspect Artifacts: manual hard-case review is required before claiming the seam is simpler and still correct

## Workflow Gates

- [x] Build complete: implementation finished, required checks run, and summary shared
- [x] Validation complete or explicitly skipped by user
- [x] Story marked done

## Architectural Fit

- **Owning module / area**: The simplified seam should move responsibility toward the earliest layer that can already preserve the reviewed hard cases. That likely means narrowing `build_chapter_html_v1` and/or `table_rescue_onward_tables_v1` after proving `rerun_onward_genealogy_consistency_v1` or a smaller upstream seam now carries the slice. Do not deepen all three large files at once.
- **Data contracts / schemas**: No schema change is expected if the story stays inside existing sidecar artifacts and final HTML outputs. If new cross-stage fields are introduced to preserve inspectability, they must be added to `schemas.py` before relying on them.
- **File sizes**: `modules/build/build_chapter_html_v1/main.py` is 1809 lines, `modules/adapter/rerun_onward_genealogy_consistency_v1/main.py` is 1669 lines, `modules/adapter/table_rescue_onward_tables_v1/main.py` is 1467 lines, `tests/test_build_chapter_html.py` is 1294 lines, `tests/test_rerun_onward_genealogy_consistency_v1.py` is 1098 lines, `tests/test_table_rescue_onward_tables_v1.py` is 518 lines, `configs/recipes/recipe-onward-images-html-mvp.yaml` is 192 lines, `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml` is 101 lines, and `docs/build-map.md` is 419 lines. The size risk is real; the story should prefer deletion/narrowing over piling on more code in these files.
- **Decision context**: Reviewed `docs/ideal.md`, `docs/spec.md`, `docs/build-map.md`, `docs/decisions/adr-001-source-aware-consistency-strategy/adr.md`, `docs/runbooks/document-consistency-planning.md`, Story 146, and Story 147. No other ADRs materially constrain this seam after search.

## Files to Modify

- `modules/common/onward_genealogy_html.py` — explicit shared owner for retained Onward genealogy HTML stitching and row-shape normalization
- `modules/build/build_chapter_html_v1/main.py` — narrowed to chapter build orchestration that calls the shared genealogy stitch helper
- `modules/adapter/table_rescue_onward_tables_v1/main.py` — narrow or absorb deterministic genealogy header/subgroup normalization only if a simpler layer map still passes review (1467 lines)
- `modules/adapter/rerun_onward_genealogy_consistency_v1/main.py` — now reuses the shared genealogy stitch helper instead of importing build internals
- `configs/recipes/recipe-onward-images-html-mvp.yaml` — wire the maintained Onward path or a clearly named replacement path to the collapsed layer set (192 lines)
- `configs/recipes/onward-genealogy-build-regression.yaml` — smaller permanent build/validate regression bundle for the reviewed Onward hard cases
- `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml` — historical proof recipe, explicitly demoted from the maintained regression path
- `tests/test_build_chapter_html.py` — keep only the build-stage behavior that still owns unique value after collapse (1294 lines)
- `tests/test_rerun_onward_genealogy_consistency_v1.py` — guard the earlier seam if it absorbs more responsibility (1098 lines)
- `tests/test_table_rescue_onward_tables_v1.py` — keep only the deterministic normalization that remains justified (518 lines)
- `docs/build-map.md` — update the collapse-candidate status once the simplification actually lands (419 lines)

## Redundancy / Removal Targets

- `build_chapter_html_v1 --merge_contiguous_genealogy_tables` follow-up cleanup passes that only compensate for weak earlier outputs
- Deterministic header / subgroup rewrites in `table_rescue_onward_tables_v1` that become redundant once an earlier seam preserves the same shape by default
- `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml` as a permanent second operating path once a smaller regression bundle exists
- Any duplicated genealogy normalization split across rerun, rescue, and build stages without unique justification
- Private cross-imports where build and rerun reach into downstream rescue/build internals just to reuse late normalization helpers

## Notes

- The story is only worth doing if it produces a smaller workaround stack. "Same logic, different file" does not count as collapse.
- Direct HTML remains the default repair target unless the baseline proves it can no longer carry the reviewed slice.
- Use artifact reuse aggressively. The expensive OCR stages are not the target of this story.
- The reviewed proof bundle from Story 146 is the anchor:
  - `story146-onward-build-stitch-r5/output/html/chapter-010.html`
  - `story146-onward-build-stitch-r5/output/html/chapter-011.html`
  - `story146-onward-build-stitch-r5/output/html/chapter-017.html`
  - `story146-onward-build-stitch-r5/output/html/chapter-022.html`
  - `story146-onward-build-stitch-r5/output/html/chapter-023.html`
- If the simplification candidate fails the hard-case review, record that clearly and stop. That is still useful evidence for the next architectural choice.

## Plan

### Exploration Findings

- Story 149 is aligned with the Ideal and ADR-001. It moves toward the Ideal by shrinking an already-accepted workaround stack rather than adding another repair layer, so this is compromise-elimination work, not compromise entrenchment.
- The maintained Onward recipe still carries five distinct repair/validation layers after OCR: `table_rescue`, `onward_table_rescue`, `table_fix_continuations`, `build_chapters` with `merge_contiguous_genealogy_tables: true`, and `validate_genealogy_consistency`.
- The strongest executable baseline available in this worktree is the focused regression suite guarding the Story 146 hard-case behaviors. Current baseline: `python -m pytest tests/test_build_chapter_html.py tests/test_rerun_onward_genealogy_consistency_v1.py tests/test_table_rescue_onward_tables_v1.py -q` → `110 passed in 8.89s`.
- The seam is more coupled than the story text originally implied:
  - `build_chapter_html_v1` imports `_normalize_rescue_html` from `table_rescue_onward_tables_v1`
  - `rerun_onward_genealogy_consistency_v1` imports multiple rescue helpers and optionally reuses `build_chapter_html_v1._merge_contiguous_genealogy_tables`
  - this means a real collapse may require helper-ownership cleanup, not just toggling one recipe flag
- The reviewed `story146-onward-build-stitch-r5` artifact paths cited in Story 146 are not present in this worktree's repo-local `output/`, so implementation-phase driver validation will need either a relinked shared output root or a fresh reuse-capable run.
- Files likely to change: `modules/build/build_chapter_html_v1/main.py`, `modules/adapter/table_rescue_onward_tables_v1/main.py`, `modules/adapter/rerun_onward_genealogy_consistency_v1/main.py`, `configs/recipes/recipe-onward-images-html-mvp.yaml`, `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml`, the three focused test files, and `docs/build-map.md`.
- Files at risk: all three module files and two test files are already >1000 lines, so the plan must prefer deletion, narrowing, or helper extraction over adding another layer of branchy logic.
- Patterns to follow: preserve explicit sidecars and acceptance/fallback reporting, reuse artifacts instead of re-running OCR, keep direct HTML as the default target, and avoid Onward-specific page/chapter allowlists in module code.

### Eval / Baseline

- **Baseline metric 1 — active repair/validation layers on the maintained Onward path:** `5`
- **Baseline metric 2 — focused hard-case regression suite:** `110/110` passing
- **Decision rule:** the winning approach must reduce one layer's unique responsibility or remove one layer entirely while keeping the focused regression suite green and preserving the hard-case driver review bar.
- **Simplest first:** test the late `build_chapter_html_v1` merge/cleanup seam before broader architectural moves. It is the latest layer, it is enabled by one recipe flag, and it already reuses rescue normalization internals, making it the cheapest falsifiable collapse candidate.

### Task Plan

#### Task 1 — Establish seam ownership baseline (`S`)

- **Files:** `configs/recipes/recipe-onward-images-html-mvp.yaml`, `tests/test_build_chapter_html.py`, `tests/test_rerun_onward_genealogy_consistency_v1.py`, `tests/test_table_rescue_onward_tables_v1.py`
- **Change:** measure which reviewed behaviors still depend on each repair layer, starting with the build-stage merge path. Use the existing focused tests and a bounded recipe/flag experiment rather than guessing from code alone.
- **Impact / risk:** without an ownership baseline, the story could "simplify" the wrong layer and immediately re-open the Story 146 hard cases.
- **Done when:** the work log names one winning collapse seam and explains what unique behavior the losing layers still own, if any.

#### Task 2 — Collapse the late build-stage seam first (`M`)

- **Files:** `modules/build/build_chapter_html_v1/main.py`, `configs/recipes/recipe-onward-images-html-mvp.yaml`, `tests/test_build_chapter_html.py`
- **Change:** try the simplest coherent collapse first by narrowing or deleting `merge_contiguous_genealogy_tables` behavior that is now redundant, and remove or reduce the main-recipe dependency on that late cleanup if the earlier seam already preserves the same structure.
- **Impact / risk:** this is the cheapest candidate but also the easiest place to re-open page-break continuation, subgroup-row, and `DIED`-column regressions.
- **Done when:** either the build-stage seam is genuinely smaller and the guarded behaviors still pass, or the story records clear evidence that this seam still owns indispensable logic and should not be the one collapsed first.

#### Task 3 — Consolidate surviving normalization ownership (`M`)

- **Files:** `modules/adapter/table_rescue_onward_tables_v1/main.py`, `modules/adapter/rerun_onward_genealogy_consistency_v1/main.py`, optionally `modules/build/build_chapter_html_v1/main.py`
- **Change:** if the simplification still needs shared genealogy normalization, move that logic under one explicit owner instead of leaving private cross-imports between build, rescue, and rerun modules.
- **Impact / risk:** helper extraction is a small coherent scope delta, not a new story, because leaving the current hidden coupling in place would fake collapse rather than achieve it.
- **Done when:** the remaining owner of the shared normalization logic is explicit, and the other layers call it through a clear boundary or stop needing it.

#### Task 4 — Replace the story-scoped proof loop with a smaller permanent guardrail (`S-M`)

- **Files:** `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml`, `configs/recipes/recipe-onward-images-html-mvp.yaml`, `docs/build-map.md`, optionally `docs/evals/registry.yaml`
- **Change:** if Story 149 lands a stable simplification, narrow or retire the Story 146 proof recipe and replace it with a smaller permanent regression bundle or clearly documented validation path.
- **Impact / risk:** if the old proof loop stays untouched forever, the project keeps a second permanent operating path even after the simplification supposedly landed.
- **Done when:** the maintained path and a smaller guardrail cover the reviewed slice without relying on the full story-scoped validation loop as a permanent crutch.

#### Task 5 — Real-run validation and manual review (`M`)

- **Files:** runtime artifacts under `output/runs/` plus whichever recipe/module files changed
- **Change:** run `driver.py` on the maintained Onward path or a clearly proposed replacement path, then manually inspect `chapter-010.html`, `chapter-011.html`, `chapter-017.html`, `chapter-022.html`, and `chapter-023.html`, along with any decision sidecars needed to explain what changed.
- **Impact / risk:** this is the true quality gate. A green test suite alone is not enough to prove the collapse kept the reviewed HTML correct.
- **Done when:** artifacts exist in `output/runs/`, the reviewed hard cases still pass manual inspection, and the work log records exact artifact paths and what was verified.

### Scope Adjustments Folded Into This Build

- Small coherent delta: helper-ownership cleanup is now explicit story scope because the current build/rerun modules already reach into downstream rescue/build internals.
- No large scope expansion is justified yet. If collapse requires a structured intermediate or a broader architecture change, stop and recommend a follow-up instead of silently absorbing it here.

### Human-Approval Blockers

- No new external dependency is expected.
- No schema change is expected unless a new cross-stage inspectability field is introduced.
- Environment risk: this worktree does not currently contain the cited `story146-onward-build-stitch-r5` artifacts, so implementation will need either a relinked shared output root or a fresh reuse-capable run before the manual-review gate.
- Recommended first implementation target: the late `build_chapter_html_v1` merge/cleanup seam.
- Not recommended as the first move: redesigning C7 around a structured intermediate or reopening the row-structured fallback experiment.
- Relative effort: `M`

### Done Criteria

- Story 149 is done only when one late repair layer is genuinely removed, narrowed, or merged; the focused hard-case regression suite stays green; a real `driver.py` run produces inspectable artifacts; manual review confirms the reviewed hard cases still hold; and any remaining surviving layer has an explicit justification.

## Work Log

20260318-1024 — story created: promoted the build-map next action into a concrete pending story so the Onward scanned-genealogy seam can be simplified deliberately rather than accumulating more repair logic; evidence is the Story 147 collapse inventory, the build-map candidate/proof block, and the reviewed `story146-onward-build-stitch-r5` hard cases; next step is `/build-story 149` to choose the winning collapse seam and write the implementation plan
20260318-1034 — build-story exploration: promoted Story 149 to active work after verifying the story was fully specified and aligned with the Ideal, then reviewed `docs/ideal.md`, `docs/spec.md`, Story 146, Story 147, ADR-001, the document-consistency runbook, the maintained Onward recipe, the three candidate module seams, and the focused regression tests; baseline evidence is that the maintained recipe still carries `5` distinct post-OCR repair/validation layers and the focused hard-case regression suite currently passes cleanly (`110 passed in 8.89s`); the main surprise is hidden coupling, because `build_chapter_html_v1` imports rescue normalization helpers and `rerun_onward_genealogy_consistency_v1` imports both rescue helpers and the build-stage merge helper, so a real collapse may require helper-ownership cleanup instead of a simple flag flip; the other practical surprise is that the cited `story146-onward-build-stitch-r5` artifacts are not present in this worktree's repo-local `output/`, so implementation-phase driver validation will need either relinked shared artifacts or a fresh reuse-capable run; next step is the written implementation plan and approval gate before any code changes
20260318-1050 — collapse implementation and validation: first falsified the cheapest collapse candidate by checking the rescue normalizer against the build hard cases; it failed the chapter-build continuation and name-list cases, so deleting the build seam outright would have reopened Story 146 regressions. Landed the smallest real collapse instead: moved the retained genealogy HTML stitch and row-shape logic into new shared owner `modules/common/onward_genealogy_html.py`, narrowed `modules/build/build_chapter_html_v1/main.py` to chapter-build orchestration that calls that shared helper, and pointed `modules/adapter/rerun_onward_genealogy_consistency_v1/main.py` at the shared helper so rerun no longer imports build internals. Replaced the maintained story-scoped proof path with `configs/recipes/onward-genealogy-build-regression.yaml` and demoted `configs/recipes/story-146-onward-plan-aware-genealogy-reruns-validate.yaml` to historical-only status. File-level before/after mapping: before, shared late normalization lived privately in `build_chapter_html_v1` and rerun reused it through a private build import; after, the retained normalization lives in `modules/common/onward_genealogy_html.py`, build only invokes it during chapter assembly, rerun reuses that same owner directly, and the maintained regression path is the smaller permanent build/validate recipe. Verification evidence: focused suite `python -m pytest tests/test_build_chapter_html.py tests/test_rerun_onward_genealogy_consistency_v1.py tests/test_table_rescue_onward_tables_v1.py -q` → `110 passed in 8.86s`; `make lint` clean; `make test` → `620 passed, 5 skipped`; cleared stale `*.pyc` and ran `python driver.py --recipe configs/recipes/onward-genealogy-build-regression.yaml --run-id story149-onward-build-regression-r1 --allow-run-id-reuse --force`, which produced `output/runs/story149-onward-build-regression-r1/04_build_chapter_html_v1/chapters_manifest_regression.jsonl` and `output/runs/story149-onward-build-regression-r1/05_validate_onward_genealogy_consistency_v1/genealogy_consistency_report_regression.jsonl` with `flagged_genealogy_chapters: 0`. Manual artifact review covered `output/runs/story149-onward-build-regression-r1/output/html/chapter-010.html`, `chapter-011.html`, `chapter-017.html`, `chapter-022.html`, and `chapter-023.html`: chapters `010/011/017/022/023` all retain split `BOY`/`GIRL` headers and full-width subgroup rows, `chapter-010.html` still contains `Richard | , 1951 | ... | , 1956` with the death value in `DIED`, `chapter-022.html` still contains `SANDRA'S FAMILY` as a subgroup row and no literal `BOY/GIRL` header, and `chapter-023.html` remains a clean two-table reference chapter. Remaining justified layers: planner/rerun still own source-aware targeted rereads, `table_rescue_onward_tables_v1` still owns page-level deterministic rescue, the shared helper owns retained genealogy HTML normalization, and chapter build still owns chapter-local continuity assembly; any future collapse needs new evidence that one of those surviving owners is redundant
20260318-1338 — build-map clarification: updated the Onward candidate block in `docs/build-map.md` so it now states the seam-level state explicitly (`climb` overall, `hold` on the reviewed trusted slice, not yet `converge`) and points readers at the real detailed tracking surfaces instead of implying the build map is itself the full registry; detailed operational truth is now called out as `output/run_assessments.jsonl`, `output/run_health.jsonl`, `output/run_manifest.jsonl`, `benchmarks/golden/onward/`, and `docs/runbooks/golden-build.md`. This does not change pipeline behavior; it makes the methodology surface match the actual trust model for Onward and clarifies that scoped trusted slices are accumulating toward one eventual canonical Onward baseline
20260318-1351 — historical back-fill comparison: compared the available shared milestone runs `story140-onward-targeted-rescue-r19`, `story143-onward-genealogy-reruns-r1`, and `story149-onward-build-regression-r1` on the reviewed hard-case chapters `chapter-010.html`, `chapter-011.html`, `chapter-017.html`, `chapter-022.html`, and `chapter-023.html` to check whether the newer simplification path hides any regression the original spot checks missed. `python tools/run_registry.py check-reuse --run-id <run> --scope html` reports all three runs as `done` with no fatal signals, but none yet has a recorded `html` assessment, so this remains candidate evidence rather than a blessed baseline. Findings: `chapter-023.html` is byte-identical across all three runs; Story 143 leaves `chapter-011.html`, `chapter-017.html`, `chapter-022.html`, and `chapter-023.html` byte-identical to Story 140 while materially changing only `chapter-010.html`; Story 149 then sharply reduces table fragmentation while preserving nearly all text (`chapter-010.html` `10 -> 2` tables, text similarity vs `story143` `0.9959`; `chapter-017.html` `8 -> 2`, `0.9946`; `chapter-022.html` `4 -> 2`, `0.9976`). The structural deltas are directionally good rather than suspicious: in `story143` `chapter-011.html` still contains fused subgroup headings such as `Leonidas' Grandchildren LUCIENNE'S FAMILY`, while `story149` splits them into separate subgroup rows; in `story143` `chapter-017.html` labels such as `Marie Louise's Grandchildren<br/>LEOPOLD'S FAMILY` and `Marie Louise's Great Grandchildren<br/>Leopold's Grandchildren<br/>THERESE'S FAMILY` still live inside row headers, while `story149` emits them as explicit subgroup rows inside two merged genealogy tables; and in `story143` `chapter-022.html` `SANDRA'S FAMILY` still appears as a scope-column header with literal `BOY/GIRL`, while `story149` restores it as a full-width subgroup row and retains only the main table header pair. `chapter-010.html` likewise keeps the reviewed `Richard | , 1956` death-field case while converting loose late headings such as `ULRIC'S FAMILY`, `RENE'S FAMILY`, `Theodore's Grandchildren`, and `RANDOLPH'S FAMILY` back into in-table subgroup rows. Conclusion: within the currently available milestone artifacts, the historical line is monotonic and Story 149 is the strongest current candidate for a scoped Onward golden once the manual review is blessed. Missing evidence remains the originally cited `story146-onward-build-stitch-r5` artifacts, which are still not present under the shared `output/runs/` root for direct byte-level comparison
20260318-1355 — recovered manual-note back-fill: user-supplied manual notes from older Story 146 and Story 143 runs materially improve the historical record even though the cited old-worktree artifact paths no longer exist on disk for direct reinspection. The notes fill the missing pre-149 failure taxonomy clearly enough to tighten the progress narrative. Story 146 `story146-onward-plan-aware-genealogy-reruns-r1` and `r2-page112-fast` were still dominated by split-table failures across `chapter-010.html` through at least `chapter-022.html`, with repeated notes about fragmented continuation tables, concatenated subgroup headings, left-cell-only family headers, and occasional column-shape errors such as child counts landing under `BOY` instead of split `BOY` / `GIRL`. The later Story 146 `story146-onward-build-stitch-r3` notes narrow that down to the exact hard cases that drove the build-stitch work: `chapter-010.html` still misplaced `Richard ... , 1956`, `chapter-011.html` still emitted the run-on `Leonidas’ Great Great Grandchildren Alma’s Great Grandchildren Dolly’s Grandchildren SHARON’S FAMILY`, and `chapter-017.html` / `018.html` / `019.html` / `020.html` / `022.html` still had many headings only in the left-hand cell instead of spanning the table. Those note-only historical defects line up with what is directly observable in the surviving shared runs: `story143-onward-genealogy-reruns-r1` still shows broad residual consistency failures outside the small reviewed rerun target set, while `story149-onward-build-regression-r1` clears several of the exact failure signatures the notes call out. Quantified from direct artifact inspection: `chapter-016.html` changes from `3` tables with `2` combined `BOY/GIRL` headers and `1` fused left-cell row header in Story 143 to `2` tables with `35` subgroup rows and no combined/fused header defects in Story 149; `chapter-017.html` changes from `8` tables with `5` combined `BOY/GIRL` headers and `12` fused left-cell row headers to `2` tables with `73` subgroup rows and no such defects; `chapter-021.html` changes from `3` tables with `2` combined `BOY/GIRL` headers and `5` fused left-cell row headers to `2` tables with `32` subgroup rows and no such defects; and `chapter-022.html` changes from `4` tables with `2` literal `BOY/GIRL` subgroup headers and `1` fused left-cell row header to `2` tables with `37` subgroup rows and no combined/fused header defects. This recovered note lineage does not prove Story 149 is globally golden, but it does materially strengthen the claim that the seam has moved from broad structural inconsistency in Story 146 / 143 toward a much narrower, more trustworthy reviewed slice
20260318-1436 — scoped golden blessing recorded: after user manual HTML review, `story149-onward-build-regression-r1` is now the current trusted Onward baseline for the reviewed genealogy slice. Recorded two explicit run-registry assessments in `output/run_assessments.jsonl`: `scope=onward_genealogy_reviewed_html_slice` with `status=known_good`, and `scope=html` with `status=partial`. The split is intentional and reflects the actual review bar: the reviewed hard-case HTML is trusted and reusable as the current golden slice, while generic full-run HTML remains only partially blessed because this pass did not repeat exhaustive cell-by-cell table-value verification against source pages. `python tools/run_registry.py check-reuse --run-id story149-onward-build-regression-r1 --scope onward_genealogy_reviewed_html_slice` now returns `recommendation=\"safe\"`; the same command with `--scope html` returns `recommendation=\"caution\"`. This gives the build map and future diff work an exact, honest trust anchor instead of another informal \"looks good\" note
20260318-1439 — committed reviewed golden slice captured: copied the exact blessed Story 149 reviewed artifacts into `benchmarks/golden/onward/reviewed_html_slice/story149-onward-build-regression-r1/` so the current trusted slice now exists as committed, diffable files rather than only a registry row in shared output. The committed bundle includes `chapter-010.html`, `chapter-011.html`, `chapter-017.html`, `chapter-022.html`, `chapter-023.html`, `chapters_manifest_regression.jsonl`, and `genealogy_consistency_report_regression.jsonl`, plus a local `manifest.json` with source paths, checksums, and trust caveats. Updated `docs/runbooks/golden-build.md` to distinguish run-backed golden slices from promptfoo eval fixtures, and updated `docs/build-map.md` to point at the new committed path for the current blessed evidence run. This keeps the trust model aligned across all three layers: run registry for scope status, build map for the high-level pointer, and `benchmarks/golden/onward/reviewed_html_slice/` for the exact artifacts future runs should diff against
20260318-1459 — validation follow-up cleanup: closed the remaining documentation-quality gaps found by `/validate` without changing pipeline behavior. Corrected the stale Story 149 task text so it now admits that the reviewed HTML slice was committed as a golden, normalized the committed `manifest.json` to use output-root-relative identifiers instead of machine-local absolute paths, and added `CHANGELOG.md` entry `2026-03-18-02` for Story 149. This leaves the story's implementation and closure docs in agreement: the reviewed slice is blessed and committed, full generic HTML remains only `partial`, and the changelog now records the shipped collapse + golden-capture slice
