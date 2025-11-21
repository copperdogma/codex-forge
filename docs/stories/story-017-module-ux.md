# Story: Module UX polish (params & outputs)

**Status**: To Do

---

## Acceptance Criteria
- Registry supports parameter schemas per module; driver validates params before execution with clear errors.
- Recipes can override output filenames per stage; driver respects overrides and propagates to downstream stages.
- Resume logic handles custom outputs correctly.

## Tasks
- [ ] Add param schema (JSON Schema or simple type/required) to registry entries; validate in driver pre-run.
- [ ] Allow per-stage `out` override in recipes; wire into driver and downstream path resolution.
- [ ] Update docs/README with examples of param validation errors and custom output names.
- [ ] Add smoke test to verify custom output naming and param validation.

## Notes
- Coordinate with DAG story if both land; ensure output override works in DAG executor variant.

## Work Log
- Pending
