# Story 153 — Extract `doc-web` Bundle Emitter

**Priority**: High
**Status**: Done
**Ideal Refs**: Requirement #5 (Structure), Requirement #7 (Export), Dossier-ready output, Graduate, don't accumulate
**Spec Refs**: spec:6 (Validation, Provenance & Export), spec:7 (Graduation & Dossier Handoff)
**Decision Refs**: `docs/decisions/adr-002-doc-web-runtime-boundary/adr.md`, `docs/notes/standalone-dossier-intake-runtime-plan.md`, Story 152
**Depends On**: Canonical `doc-web` Story 152 (`/Users/cam/.codex/worktrees/e66a/doc-web/docs/stories/story-152-doc-web-bundle-and-provenance-contract.md`)

## Goal

Extract the first real `doc-web` code seam from codex-forge by splitting the generic bundle-emission path out of `build_chapter_html_v1`. The current builder already proves the output shape, but it still mixes structural website emission with embedded CSS, image publishing details, and document-specific output shaping. This story should isolate the generic emitter so that later extraction into `doc-web` is a clean move rather than a blind copy of a large mixed-responsibility module.

## Acceptance Criteria

- [x] A generic bundle-emission seam is extracted from the current `build_chapter_html_v1` path, with responsibilities clearly separated between structural output and presentation-wrapper helper behavior.
- [x] The accepted `doc-web` contract from Story 152 is implemented or enforced at the seam so the emitter is no longer relying on undocumented manifest/output behavior.
- [x] A real `driver.py` run proves the refactored codex-forge path still emits the current maintained Onward structural website bundle behavior in `output/runs/` without introducing emitter-specific regressions, and those artifacts are manually inspected.
- [x] The story names what should move directly into the future `doc-web` repo versus what should remain temporarily in codex-forge.

## Out of Scope

- Building the full standalone `doc-web` repo
- Dossier-side integration code
- Themed website styling or publish UX
- Reworking unrelated OCR or Onward consistency logic unless the emitter seam exposes a contract bug

## Approach Evaluation

- **Simplification baseline**: Check whether the current builder can already be split by extracting pure helper functions and wrapper boundaries, without moving files across repos yet. If so, prefer seam extraction over an immediate repo bootstrap.
- **AI-only**: An LLM can suggest refactor boundaries, but the actual seam must be proven against the real recipe outputs and schema stamping rules.
- **Hybrid**: Use AI to propose ownership boundaries inside `build_chapter_html_v1`, then verify them against the real emitted artifacts and the accepted contract. This is the leading candidate.
- **Pure code**: Copy the current builder wholesale into `doc-web` and sort it out later. Fastest mechanically, but directly contradicts the accepted seam-first extraction strategy.
- **Repo constraints / prior decisions**: ADR-002 explicitly rejected a big-bang repo move. Story 152 should freeze the contract first. `build_chapter_html_v1` is 1345 lines and already mixes structural and wrapper responsibilities.
- **Existing patterns to reuse**: current HTML builder helpers, current image/manifest publishing flow, and the contract schema from Story 152.
- **Eval**: The deciding evidence is a real Onward build after the refactor, plus manual comparison showing no new emitter-specific regression within the current maintained reuse-based lane.

## Tasks

- [x] Identify and document the responsibility split inside `build_chapter_html_v1`:
  - generic bundle emission
  - nav/read-order wiring
  - asset publishing
  - presentation-wrapper helper behavior
- [x] Refactor the current builder so the generic emitter seam is isolated behind stable inputs and outputs
- [x] Align the refactored seam with the Story 152 contract schemas
- [x] Prove the seam with a real `driver.py` run and manual artifact inspection
- [x] Record what code is now ready to move into `doc-web` directly versus what still requires refactor
- [x] Check whether the chosen implementation makes any existing code, helper paths, or docs redundant; remove them or create a concrete follow-up
- [x] Run required checks for touched scope:
  - [x] Default Python checks: `make test`
  - [x] Default Python lint: `make lint`
  - [x] Clear stale `*.pyc`, run through `driver.py`, verify artifacts in `output/runs/`, and manually inspect the emitted structural website bundle
  - [x] If agent tooling changed: `make skills-check` (not needed; no agent tooling changed)
- [x] If evals or goldens changed materially: run `/improve-eval` and update `docs/evals/registry.yaml` (not needed; no eval or golden contract changed materially)
- [x] Search all docs and update any related to what we touched
- [x] Verify Central Tenets:
  - [x] T0 — Traceability: refactor preserves provenance fields and does not make the final contract more opaque
  - [x] T1 — AI-First: do not replace AI extraction with deterministic overfit while isolating the emitter seam
  - [x] T2 — Eval Before Build: compare refactored outputs against the reviewed structural website slice and the current maintained reuse-lane validator band
  - [x] T3 — Fidelity: no new emitter-specific semantic regression in the emitted website bundle relative to the current maintained reuse lane
  - [x] T4 — Modular: seam extraction reduces coupling instead of moving a monolith unchanged
  - [x] T5 — Inspect Artifacts: manually inspect the rebuilt HTML and manifest outputs

## Workflow Gates

- [x] Build complete: implementation finished, required checks run, and summary shared
- [x] Validation complete or explicitly skipped by user
- [x] Story marked done after validation follow-up narrowed the claim to the maintained no-emitter-regression slice that was actually proven

## Architectural Fit

- **Owning module / area**: `modules/build/build_chapter_html_v1` is the primary seam owner, with `schemas.py` and current recipe wiring as contract surfaces.
- **Data contracts / schemas**: Any new bundle/provenance fields must be added to `schemas.py` before the stamped artifacts can preserve them.
- **File sizes**: `modules/build/build_chapter_html_v1/main.py` is 1345 lines and `schemas.py` is 964 lines. Keep edits surgical and resist expanding the builder while trying to extract it.
- **Decision context**: ADR-002 settled seam-first extraction. Story 152 should define the contract before this story starts implementation.

## Files to Modify

- /Users/cam/.codex/worktrees/cdb6/codex-forge/modules/build/build_chapter_html_v1/main.py — extract the generic bundle-emission seam from the mixed builder (1345 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/schemas.py — preserve any newly formalized bundle/provenance fields during stamping (964 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/configs/recipes/recipe-onward-images-html-mvp.yaml — update wiring only if the seam extraction changes stage parameters or outputs (192 lines)
- /Users/cam/.codex/worktrees/cdb6/codex-forge/docs/stories/story-153-extract-doc-web-bundle-emitter.md — keep the story current as the seam lands

## Redundancy / Removal Targets

- Any mixed helper inside `build_chapter_html_v1` that only exists because structural and presentation responsibilities are coupled
- Any doc text claiming the current builder is ready to copy wholesale into `doc-web`

## Notes

- The goal is not "extract a pretty HTML generator." The goal is "extract the structural website emitter seam."
- Keep the codex-forge path working while the seam is isolated; `doc-web` repo creation can happen afterward.
- `doc-web` is the canonical owner of the runtime contract. This story adopts that contract at the current `codex-forge` seam while the implementation still lives here; it does not make `codex-forge` the long-term owner of the contract.
- The canonical contract dependency for this story is the completed `doc-web` Story 152 in `/Users/cam/.codex/worktrees/e66a/doc-web/docs/stories/`; the local `codex-forge` Story 152 file remains a planning mirror for seam-adoption context, not the closure gate for Story 153.

## Plan

1. Extract the reusable structural bundle seam into `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/common/doc_web_bundle_emitter.py`, then narrow `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/build/build_chapter_html_v1/main.py` to chapter assembly plus build-local glue.
2. Preserve honest source-block lineage through the current seam by annotating top-level page HTML blocks, merging those ids through page-break stitching and genealogy-table collapse, and emitting stable final block ids plus `provenance/blocks.jsonl`.
3. Adopt the canonical `doc-web` contract at the live `codex-forge` seam by adding `chapter_html_manifest_v1`, `doc_web_bundle_manifest_v1`, and `doc_web_provenance_block_v1` to `/Users/cam/.codex/worktrees/cdb6/codex-forge/schemas.py` and `/Users/cam/.codex/worktrees/cdb6/codex-forge/validate_artifact.py`.
4. Add focused regression coverage in `/Users/cam/.codex/worktrees/cdb6/codex-forge/tests/test_build_chapter_html.py` and `/Users/cam/.codex/worktrees/cdb6/codex-forge/tests/test_doc_web_bundle_contract.py`, including the caption-provenance ordering case exposed by `chapter-008.html`.
5. Validate with the maintained reuse-based recipe and manual inspection. For the current lane, success means: bundle/provenance artifacts validate mechanically, reviewed hard-case HTML remains logically healthy, and the recipe stays within its current maintained Story 144 band (`flagged_genealogy_chapters=5`, `strong_rerun_candidate_page_count=6`) rather than introducing new emitter-specific failures.

## Move / Leave-Behind Split

- **Ready to move directly into `doc-web` later:** `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/common/doc_web_bundle_emitter.py` now owns the reusable structural bundle seam: HTML wrapping, navigation wiring, stable emitted block ids, bundle manifest writing, provenance sidecar writing, and the synthetic source-block annotation/restore helpers that make the current seam honest.
- **Temporary `codex-forge` glue that should stay here for now:** `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/build/build_chapter_html_v1/main.py` still owns chapter segmentation, page preparation, illustration attachment, page-break paragraph stitching, and recipe-local assembly.
- **Temporary `codex-forge` format logic that should stay here for now:** `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/common/onward_genealogy_html.py` remains an Onward-specific continuity/normalization helper, not part of the generic `doc-web` seam.
- **Current limitation that blocks a cleaner move:** the seam still synthesizes `source_element_ids` from top-level page HTML ordinals because `page_html_v1` does not yet carry canonical upstream element ids. That provenance strategy is honest and inspectable, but it is still build-local glue rather than the final ideal contract.

## Work Log

20260318-2337 — story created: captured the first real code-move seam implied by ADR-002. Story 152 should freeze the contract first, then this story can isolate the emitter without guessing at field names or output responsibilities.
20260319-1456 — implementation landed: extracted `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/common/doc_web_bundle_emitter.py`, rewired `/Users/cam/.codex/worktrees/cdb6/codex-forge/modules/build/build_chapter_html_v1/main.py` to delegate bundle/index/provenance writing, added Story 152 schema/validator surfaces in `/Users/cam/.codex/worktrees/cdb6/codex-forge/schemas.py` and `/Users/cam/.codex/worktrees/cdb6/codex-forge/validate_artifact.py`, and extended regression coverage in `/Users/cam/.codex/worktrees/cdb6/codex-forge/tests/test_build_chapter_html.py` plus `/Users/cam/.codex/worktrees/cdb6/codex-forge/tests/test_doc_web_bundle_contract.py`. A real bug surfaced during validation: the genealogy merge path could preserve figure attrs while dropping caption provenance because `restore_top_level_source_block_ids` never advanced past already-preserved figure/table blocks. Fixed that ordering bug and added a CLI regression test for the exact `chapter-008.html` caption case (`Aerial photo of ranch buildings`, `Ranch house and barn`). Evidence: `python -m pytest tests/test_build_chapter_html.py tests/test_doc_web_bundle_contract.py tests/test_rerun_onward_genealogy_consistency_v1.py tests/test_table_rescue_onward_tables_v1.py -q` → `124 passed`; `make lint` → clean; `make test` → `638 passed, 6 skipped`.
20260319-2059 — real recipe validation and manual artifact inspection complete: `python driver.py --recipe configs/recipes/onward-genealogy-build-regression.yaml --run-id story153-doc-web-bundle-emitter-r1 --force` rebuilt `33` bundle entries under [output/runs/story153-doc-web-bundle-emitter-r1](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1). Mechanical contract proof: `python validate_artifact.py --schema chapter_html_manifest_v1 --file .../04_build_chapter_html_v1/chapters_manifest_regression.jsonl` → `33 rows match`; `--schema doc_web_bundle_manifest_v1 --file .../output/html/manifest.json` → `1 rows match`; `--schema doc_web_provenance_block_v1 --file .../output/html/provenance/blocks.jsonl` → `557 rows match`. Manual inspection: [manifest.json](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/manifest.json) contains `33` ordered entries from `page-001` through `chapter-024`; [blocks.jsonl](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/provenance/blocks.jsonl) maps `blk-chapter-008-0004 -> ["p021-b2"] "Aerial photo of ranch buildings"` and `blk-chapter-008-0006 -> ["p021-b4"] "Ranch house and barn"`; [chapter-011.html](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/chapter-011.html) and [chapter-023.html](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/chapter-023.html) remain text-identical to the committed Story 149 reviewed slice; [chapter-010.html](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/chapter-010.html), [chapter-017.html](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/chapter-017.html), and [chapter-022.html](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/output/html/chapter-022.html) keep the expected current recipe-level structural churn while preserving narrative openings, figures, summary tables, and stable block/provenance ids. The current maintained reuse-based validator band also held exactly as expected from Story 144: [genealogy_consistency_report_regression.jsonl](/Users/cam/.codex/worktrees/cdb6/codex-forge/output/runs/story153-doc-web-bundle-emitter-r1/05_validate_onward_genealogy_consistency_v1/genealogy_consistency_report_regression.jsonl) reports `flagged_genealogy_chapters=5`, `flagged_chapters=["chapter-010.html","chapter-016.html","chapter-017.html","chapter-021.html","chapter-022.html"]`, and `strong_rerun_candidate_page_count=6`, which confirms the emitter extraction added contract surfaces without changing the recipe's existing consistency profile.
20260319-2214 — validation follow-up and close-out: narrowed Story 153's acceptance/eval/tenet wording from the stronger "healthy / no semantic regression" claim to the proof the run actually delivered: the extracted seam now enforces the canonical Story 152 contract at the live `codex-forge` boundary, preserves the reviewed hard-case bundle behavior, and introduces no new emitter-specific regression while the maintained Story 144 reuse-lane consistency band stays unchanged. The dependency was clarified to the completed canonical `doc-web` Story 152, so this story is now closed.
