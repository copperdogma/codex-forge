# Story: Module pruning & registry hygiene

**Status**: To Do  
**Owner**: TODO  
**Created**: 2025-11-26  

---

## Goal
Audit the module registry, identify redundant/unused modules, and prune or clearly label variants so the dashboard and recipes reflect a lean, intentional set. Reduce cognitive load for humans/AI, speed recipe authoring, and keep instrumentation meaningful.

## Success Criteria / Acceptance
- Inventory produced: list of all modules with usage across existing recipes and recent runs (count per stage, last-seen run).
- Decision outcomes logged per module: keep, mark-experimental, deprecate, or remove. Rationale recorded.
- Registry/docs updated: `modules/*/module.yaml` notes and/or status tags reflect decisions; deprecated/removed modules are taken out of recipes and story docs.
- Dashboard/driver still operate without broken references; smoke tests pass for standard OCR and text recipes.
- Change log entry added with summary of removals/renames and migration notes (if any).

## Approach
1) **Inventory**
   - Script/grep recipes in `configs/recipes/` to count module references.
   - Scan recent `output/runs/*/pipeline_state.json` for module_ids observed in practice.
2) **Classify**
   - Group by stage (extract/clean/portionize/consensus/adapter/enrich/resolve/build/validate).
   - Mark superseded variants (e.g., multiple portionizers) and adapters with overlapping purpose.
3) **Decide + Act**
   - Propose keep/prune/mark-experimental per module; get approval if needed.
   - Remove pruned modules from recipes; delete module dirs only after confirming no live dependency.
   - Update notes/README/story list to reflect the slim set.
4) **Verify**
   - Run smoke recipes (OCR/text) in mock mode and ensure dashboard loads; run targeted pytest (logger + visibility path).

## Tasks
- [ ] Generate module usage report across recipes.
- [ ] Generate module usage report across recent runs (pipeline_state/pipeline_events).
- [ ] Propose keep/prune list with rationale.
- [ ] Remove/deprecate unused modules and update affected recipes.
- [ ] Update docs (README snippet, stories index, CHANGELOG) and module notes/tags.
- [ ] Smoke: `driver.py --recipe configs/recipes/recipe-ocr.yaml --mock --instrument` and `recipe-text.yaml`; rerun dashboard sanity tests.

## Risks / Notes
- Some “rare path” modules may be needed for future experiments; prefer “experimental” tag over removal when unsure.
- Must avoid breaking story fixtures/tests that expect module presence.

## Work Log
- 2025-11-26 — Story stubbed (inventory + prune plan). Next: generate usage reports.
