# Story: Consolidate section target adapters

**Status**: To Do

---

## Acceptance Criteria
- Replace the current map_targets_v1 + backfill_missing_sections_v1 chain with a single adapter that maps targets, backfills missing sections, and emits a coverage summary/exit code.
- Update the no-consensus section recipe to use the consolidated adapter and keep zero-missing-target behavior.
- Add or update tests to cover pass/fail paths of the consolidated adapter.
- Document the new adapter and usage (command example) in AGENTS.md and the relevant story logs.

## Tasks
- [ ] Design the consolidated adapter contract (inputs/outputs, flags such as allow-missing).
- [ ] Implement the adapter (map + backfill + coverage report) and module.yaml.
- [ ] Update recipes (at least `configs/recipes/recipe-ocr-enrich-sections-noconsensus.yaml`) to use the new adapter.
- [ ] Update tests (reuse or extend `tests/assert_section_targets_test.py`) to cover both success and failure cases.
- [ ] Refresh docs (AGENTS safe command + story log) with the new adapter usage.

## Notes
- Keep portionize_sections_v1 and section_enrich_v1 separate to preserve swap flexibility across book types; consolidation targets only the tiny adapter tail.

## Work Log
