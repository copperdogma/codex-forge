# Story: Modular pipeline & module registry

**Status**: To Do

---

## Acceptance Criteria
- Any stage (extract, clean, portionize, consensus, enrich, build) is selectable via config without code edits.
- At least two extractor modules runnable end-to-end: existing PDF→OCR and a text/HTML/Markdown ingester that skips imaging.
- Shared schemas (versioned) validate artifacts between stages; artifacts record schema version and module id used.
- Single driver reads a pipeline recipe, invokes modules, updates `pipeline_state.json`, and can resume.
- Swapping a module (e.g., text extractor instead of OCR) requires only changing config and rerunning driver on existing inputs.

## Tasks
- [ ] Define shared schemas for stage inputs/outputs (PageDoc, CleanPage, PortionHypothesis, Locked/Resolved/Enriched portions) with version tags.
- [ ] Create `modules/registry` manifest describing module ids, entrypoints, inputs/outputs, defaults.
- [ ] Refactor existing scripts into callable modules with thin CLIs that conform to contracts; centralize OpenAI client/model config.
- [ ] Implement second extractor module for text/HTML/Markdown (`pages_raw.jsonl` producer) using `/input` files.
- [ ] Add driver that executes a pipeline recipe, handles state, and validates IO against schemas.
- [ ] Add smoke tests/fixtures for both extractor paths (OCR and text) and document a “swap a module” walkthrough.

## Notes
- Favor append-only artifacts; keep compatibility with existing `output/runs/<run_id>/` layout.
- Keep costs visible in config; allow per-module model overrides (boost model optional).

## Work Log
- Pending
