# Story: Module UX polish (params & outputs)

**Status**: Complete

---

## Acceptance Criteria
- Registry supports parameter schemas per module; driver validates params before execution with clear errors.
- Recipes can override output filenames per stage; driver respects overrides and propagates to downstream stages.
- Resume logic handles custom outputs correctly.

## Tasks
- [ ] Define `param_schema` shape for module registry entries (JSON Schema-ish fields, required/optional, types) and document it in the story + module docs.
- [ ] Extend driver to merge defaults + recipe params, validate against `param_schema` before execution, and emit clear stage/module-specific error messages (fail fast).
- [ ] Support per-stage output filename overrides via stage-level `out` key in addition to recipe `outputs` map; ensure DAG + resume/skip-done paths propagate custom names to downstream inputs.
- [ ] Update README/docs with examples of param validation failures and custom output overrides in a recipe.
- [ ] Add a smoke/integration test covering custom output naming (DAG + resume) and param schema validation (both pass + fail cases).

## Notes
- Coordinate with DAG story if both land; ensure output override works in DAG executor variant.

## Work Log
### 20251121-1754 — Story read-through and gap scan
- **Result:** Success.
- **Notes:** Verified story format and existing tasks; inspected `driver.py` (build_plan, build_command, skip/resume) and sample recipes. Outputs map already exists but only via global `outputs`; no per-stage `out` handling. No parameter validation beyond defaults. Modules’ `module.yaml` files currently expose `default_params` only.
- **Next:** Propose `param_schema` structure and update driver plan/command flow to validate; design stage-level output override wiring and tests.

### 20251121-1757 — Planned param_schema and output override approach
- **Result:** Plan drafted.
- **Notes:** Proposed `param_schema` per module (module.yaml) using a small JSON-Schema subset: keys map to fields with `{type: string|number|integer|boolean, enum?, min?, max?, pattern?, required: bool, default?}` plus top-level `required` list for clarity. Driver to merge `default_params` + recipe `params`, then validate via helper (fail fast) with errors including module_id, stage_id, param name, expected type/constraints. Unknown params should raise to avoid silent typos. For outputs: stage-level `out` key should override before recipe-level `outputs` map; `_artifact_name_for_stage` to take `stage_conf.get("out")` precedence. Artifact path stored in state/skip-done uses resolved name so resume works. DAG inputs should read downstream via `artifact_index` so custom names propagate automatically.
- **Next:** Implement schema parsing/validation helper and wire into build_plan; add stage-level `out` precedence in plan/build_command; craft smoke recipe + test cases (pass/fail) and doc updates.

### 20251121-1801 — Implemented validation + overrides and tests
- **Result:** Success (tests green).
- **Notes:** Added param schema plumbing and validation in `driver.py` (type/enum/range/pattern, unknown/required checks, schema defaults, stage/module-specific errors). Stage-level `out` now takes precedence over recipe `outputs` map. Added param_schema definitions to key modules (`extract_ocr_v1`, `extract_text_v1`, `clean_llm_v1`, `portionize_sliding_v1`, `merge_portion_hyp_v1`, `consensus_vote_v1`). Expanded unit tests for param errors and out precedence; integration test now uses stage-level `out` and verifies custom files plus adds a failing-param dry-run case. Pytest run: 11 tests passed in ~3s (warnings only from pydantic deprecation). Files touched: `driver.py`, modules/*/module.yaml, `tests/driver_plan_test.py`, `tests/driver_integration_test.py`.
- **Next:** Update README/docs with param_schema shape + error examples and custom output override usage; consider adding resume-specific smoke and pydantic warning cleanup later.

### 20251121-1802 — Docs updated for params/output overrides
- **Result:** Success.
- **Notes:** README now documents the JSON-Schema-lite `param_schema`, fail-fast error shape (example), and stage-level `out:` precedence over recipe `outputs:` plus resume implications.
- **Next:** Consider adding a resume-focused smoke plus pydantic warning cleanup; keep `CHANGELOG` in sync once story completes.

### 20251121-1803 — Resume test + changelog
- **Result:** Success.
- **Notes:** Added integration test to assert `--skip-done` honors stage-level `out` without rewrites; reran integration tests (pass). Logged changes in CHANGELOG with new param-schema/out override entry.
- **Next:** Optional: address pydantic v1 deprecation warnings; consider broader resume smoke across more stages if needed.

### 20251121-1805 — Pydantic v2 validators
- **Result:** Success.
- **Notes:** Migrated `schemas.py` from deprecated `@validator` to v2 `field_validator`/`model_validator`, eliminating warnings; reran plan+integration tests (12 pass).
- **Next:** None for this story unless more resume coverage is requested.

### 20251121-1810 — Recommendations applied
- **Result:** Success.
- **Notes:** Added README recipe snippet showing stage-level `out`; extended `param_schema` stubs to dedupe/normalize/resolve/build modules; added multi-stage custom-output smoke test (propagation over >2 hops). Re-ran plan+integration tests: 13 pass.
- **Next:** Ready for review/merge.

### 20251121-2113 — Story closed
- **Result:** Success.
- **Notes:** All acceptance criteria satisfied: param_schema validation in driver + manifests, per-stage out overrides with resume support, docs updated, tests added (plan+integration, including resume/custom out). Status marked Complete.
- **Next:** None; ready to merge.
