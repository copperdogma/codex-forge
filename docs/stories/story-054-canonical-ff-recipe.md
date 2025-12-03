# Story: Canonical FF Recipe Consolidation

**Status**: Open  
**Created**: 2025-12-03  

## Goal
Reduce the FF pipeline to a single canonical recipe that runs end-to-end with the modules currently present in this repo, and mark/remove stale/legacy recipes to avoid drift.

## Success Criteria
- [ ] One canonical FF recipe in `configs/recipes/` that runs end-to-end with in-repo modules.
- [ ] Legacy/duplicate FF recipes are removed or clearly marked deprecated.
- [ ] The canonical recipe supports the smoke settings/overrides pattern (skip_ai/stubs) without separate DAGs.
- [ ] Documentation updated with the canonical recipe name and the standard invocation (including smoke overrides).

## Tasks
- [ ] Inventory current FF-related recipes; identify canonical base (likely `recipe-ff-redesign-v2.yaml`).
- [ ] Patch the canonical recipe to only reference modules that exist in the repo today.
- [ ] Add/propagate `skip_ai`/stub params where needed to support smoke runs via settings.
- [ ] Deprecate/remove legacy FF recipes (or add README note) to prevent drift.
- [ ] Document the canonical run command and the smoke invocation (settings + driver overrides).
- [ ] Validate the canonical recipe with a short run (can be stubbed/smoke) to confirm wiring.

## Work Log
### 20251203-1405 — Story opened
- **Context:** FF recipes are fragmented; legacy DAG referenced removed modules. Need single canonical recipe aligned with current modules; smoke will hook onto it later.
- **Next:** Inventory recipes and pick canonical base; patch to in-repo modules only.
