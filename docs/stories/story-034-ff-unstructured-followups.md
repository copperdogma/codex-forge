# Story: FF Unstructured follow-ups (elements, helpers, graph quality)

**Status**: To Do  
**Created**: 2025-11-29  

---

## Goal

Build on Story 032’s Unstructured-native intake and successful FF run to:
- Consolidate element→page conversion helpers into a shared utility,
- Evolve FF portions and export to reference Unstructured elements by ID (not just page spans),
- Address FF Engine validator graph warnings (unreachable gameplay sections) so section connectivity is robust by default.

This story focuses on refactoring and quality hardening of the Unstructured-based FF pipeline, not on adding new domains or inputs.

## Success Criteria / Acceptance

- **Shared helpers**
  - A single, well-tested helper (or small helper module) exists under `modules/common/` that converts `elements.jsonl` into page-ordered text views.
  - `portionize_sliding_v1`, `section_enrich_v1`, and `build_ff_engine_v1` all use this shared helper instead of copy-pasted `elements_to_pages*` functions.
  - Behavior is unchanged for existing runs (same text slices, ordering, and filtering) aside from bug fixes explicitly documented in this story.

- **Element-id-aware portions and export**
  - Portions can (optionally) carry **element ID references** (e.g., `element_ids: ["elem-1", "elem-2"]`) that point back into `elements.jsonl`.
  - `build_ff_engine_v1` can assemble section text either from page spans or from element IDs, preferring element IDs when present.
  - Provenance for each FF Engine section includes either:
    - `source_elements` (element IDs, pages, coordinates), or
    - a clear statement that the section is page-span-based only (for legacy runs).

- **FF graph quality (validator warnings)**
  - For the `ff-unstructured-test` run (and future FF runs), the FF Engine validator:
    - still reports `valid: true`, and
    - **no longer emits “unreachable from startSection ‘1’” warnings for any legitimate gameplay sections**.
  - Root causes of previously unreachable sections are documented (e.g., missing links, mis-typed targets, stub behavior) with concrete fixes.
  - New guardrails (validation or build-time checks) fail loudly or emit high-priority warnings when:
    - a non-trivial fraction of numbered sections are unreachable from the start section, or
    - link targets reference non-existent sections without an explicit stub/override rationale.

---

## Approach

1. **Centralize Unstructured element helpers**
   - Extract the existing `elements_to_pages*` logic from `portionize_sliding_v1`, `section_enrich_v1`, and `build_ff_engine_v1` into a shared utility (e.g., `modules/common/elements_utils.py`).
   - Ensure the helper:
     - groups elements by `metadata.page_number`,
     - sorts by `_codex.sequence` and coordinates (y-first, x-second) for stable reading order,
     - filters headers/footers when configured,
     - returns both:
       - a **page→text map** used by existing modules, and
       - a **page→[element_ids] map** to support element-id-based portions.
   - Add lightweight tests or spot-check scripts to confirm identical output before and after refactor for a known run.

2. **Add element-ID references to portions and export**
   - Extend portion schemas and/or enrichment output (for FF recipes) so portions can include `element_ids` where feasible.
   - Update `build_ff_engine_v1` to:
     - detect when `element_ids` are present for a portion,
     - load the corresponding elements from `elements.jsonl`,
     - assemble section text directly from those elements (falling back to page slices when IDs are absent).
   - Keep backward compatibility:
     - legacy runs without `element_ids` still work,
     - new behavior is gated behind explicit recipe/config toggles if needed.

3. **Investigate and fix FF graph reachability warnings**
   - Re-open `output/runs/ff-unstructured-test/{gamebook.json,gamebook_validation_node.json}` and:
     - enumerate all sections the validator marks as unreachable,
     - trace their inbound links (or lack thereof) from other sections,
     - classify causes as:
       - true dead-ends (book design),
       - missing/incorrect links in enrichment or build,
       - stubs or mis-parsed targets.
   - Implement targeted fixes in enrichment and/or `build_ff_engine_v1` so:
     - legitimate gameplay sections get correct inbound links,
     - accidental stubs or orphan sections are either eliminated or clearly annotated as intentional.
   - Re-run the FF recipe and Node validator to confirm that:
     - all expected gameplay sections are reachable from the start section,
     - remaining warnings (if any) are documented as intentional (e.g., non-gameplay/unused sections).

4. **Guardrails and documentation**
   - Add validator or build-time checks that:
     - compute the set of reachable gameplay sections from `startSection`,
     - compare it to the set of all gameplay sections,
     - emit a hard error or high-priority warning when the unreachable fraction exceeds a configurable threshold.
   - Document:
     - how element IDs are threaded from `elements.jsonl` through portions into FF Engine sections,
     - how to interpret and act on new graph-quality warnings,
     - how to disable or relax these checks for experimental runs.

---

## Tasks

- [ ] **Shared Unstructured helpers**
  - [ ] Extract `elements_to_pages*` logic into `modules/common/` helper(s).
  - [ ] Update `portionize_sliding_v1` to use the shared helper.
  - [ ] Update `section_enrich_v1` to use the shared helper.
  - [ ] Update `build_ff_engine_v1` to use the shared helper.
  - [ ] Spot-check a known run (e.g., `ff-unstructured-test`) to confirm text/page outputs are unchanged.

- [ ] **Element-ID-aware portions and export**
  - [ ] Extend portion/enrichment outputs to optionally include `element_ids`.
  - [ ] Teach `build_ff_engine_v1` to assemble sections from element IDs when present (fallback to page spans).
  - [ ] Update FF provenance to record `source_elements` when IDs are used.
  - [ ] Verify that legacy runs without `element_ids` still build correctly.

- [ ] **FF graph reachability fixes**
  - [ ] Analyze `gamebook_validation_node.json` for `ff-unstructured-test` and list unreachable sections.
  - [ ] For each unreachable section, trace its intended inbound links in `gamebook.json` and upstream artifacts.
  - [ ] Fix enrichment/build logic so legitimate gameplay sections have correct inbound links.
  - [ ] Re-run the FF recipe and Node validator to confirm graph warnings are resolved or intentionally documented.

- [ ] **Guardrails & docs**
  - [ ] Add a graph-quality check (reachable vs. total gameplay sections) to the FF validation pipeline.
  - [ ] Fail loudly or emit high-priority warnings when reachability falls below a configured threshold.
  - [ ] Update docs (Story 031 and/or docs/document-ir.md / README.md) to describe new element-ID usage and graph-quality checks.

---

## Work Log

- _TBD — work not yet started._


