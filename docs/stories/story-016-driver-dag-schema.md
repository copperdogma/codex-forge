# Story: Driver DAG & schema compatibility

**Status**: To Do

---

## Acceptance Criteria
- Driver supports DAG/explicit dependencies between stages (not just fixed linear order), with resume and state tracking.
- Recipes can declare multiple chains (e.g., coarse+fine portionize) and merges, and driver executes them topologically.
- Driver validates schema compatibility between connected stages; fails fast on mismatched input/output schemas.
- Resume logic checks both state and artifact existence/schema_version before skipping.

## Tasks
- [ ] Extend recipe format to declare stage ids, `needs` dependencies, and optional custom outputs.
- [ ] Implement DAG executor in `driver.py` with topo sort, state/resume, and `--skip-done/--force` semantics.
- [ ] Add schema-compatibility validation using registry `input_schema`/`output_schema`; support explicit adapter hooks.
- [ ] Enhance resume to verify artifact existence + schema_version match before skipping.
- [ ] Update docs/README with DAG recipe example (e.g., coarse+fine portionize merged before consensus).
- [ ] Add smoke covering multi-branch recipe (coarse+fine portionize merged).

## Notes
- Reuse stamping/validation hooks from Story 015; keep module registry as source of truth.
- Adapters can be modeled as modules with compatible schemas; clarify in docs.

## Work Log
- Pending
