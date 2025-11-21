# Story: Enrichment & alternate modules

**Status**: To Do

---

## Acceptance Criteria
- Enrichment module implemented and registered; extracts choices/combat/items/endings into `enriched_portion_v1`.
- At least one alternate module each for portionize and consensus (e.g., coarse portionizer or heuristic; different consensus strategy) to demonstrate swapability.
- Recipes include examples selecting the new modules; driver executes them end-to-end.
- Validator updated to cover new module outputs if schemas differ.

## Tasks
- [ ] Implement enrichment module (LLM or rule-based) emitting `enriched_portion_v1`; add to registry.
- [ ] Add alternate portionizer module (e.g., coarse-window) and alternate consensus module; register them.
- [ ] Add recipes showcasing module swaps and enrichment stage usage.
- [ ] Extend validator/ schemas if enrichment output needs updates.
- [ ] Add smoke(s) covering enrichment + alternate modules (can be mock-friendly for cost control).

## Notes
- Build on existing resolved portions; keep compatibility with Story 015 stamping.
- Consider cost controls (mock or small-page samples) for CI-ish runs.

## Work Log
- Pending
