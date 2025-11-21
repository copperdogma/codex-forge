# Story: Driver DAG & schema compatibility

**Status**: Done

---

## Acceptance Criteria
- Driver supports DAG/explicit dependencies between stages (not just fixed linear order), with resume and state tracking.
- Recipes can declare multiple chains (e.g., coarse+fine portionize) and merges, and driver executes them topologically.
- Driver validates schema compatibility between connected stages; fails fast on mismatched input/output schemas.
- Resume logic checks both state and artifact existence/schema_version before skipping.

## Tasks
- [x] Extend recipe format to declare stage ids, `needs` dependencies, and optional custom outputs.
- [x] Implement DAG executor in `driver.py` with topo sort, state/resume, and `--skip-done/--force` semantics.
- [x] Add schema-compatibility validation using registry `input_schema`/`output_schema`; support explicit adapter hooks.
- [x] Enhance resume to verify artifact existence + schema_version match before skipping.
- [x] Update docs/README with DAG recipe example (e.g., coarse+fine portionize merged before consensus).
- [x] Add smoke covering multi-branch recipe (coarse+fine portionize merged).
- [x] Validate recipe structure (ids unique, no cycles, dependencies satisfied, outputs keyed by stage id) before execution.
- [x] Persist per-stage state (artifact path, module id, schema_version) in `pipeline_state.json` for resume/debug.
- [x] Add cycle + schema mismatch unit tests around the DAG planner and adapter/mismatch failures.

## Notes
- Reuse stamping/validation hooks from Story 015; keep module registry as source of truth.
- Adapters can be modeled as modules with compatible schemas; clarify in docs.

## Plan (draft)
- **Recipe schema:** keep `run_id`, `input`, `output_dir`; add `outputs` map of `{stage_id: filename}` overrides. Stages list items `{id, stage, module, needs: [ids], params?, provides?}` where `provides` can pick an output key when module emits multiple files.
- **Validation:** ensure ids unique; `needs` only references earlier-declared ids; detect cycles with topo sort; verify `stage` matches registry.module.stage; warn if missing `needs` when non-root. Fail if a stage requires an input schema not produced by any dependency (unless adapter module staged).
- **Driver DAG executor:** build graph from stages, topo sort; for each stage gather upstream artifacts (default or overridden by `outputs` map), check registry input/output schemas and optional adapter compatibility; compute stage artifact path from `outputs` or module defaults.
- **Resume/state:** write `pipeline_state.json` with `{status, module_id, input_schema, output_schema, artifact, schema_version, updated_at, needs}` keyed by stage id. Resume should require both state `done` and artifact exists and (if schema stamped) schema_version matches before skipping unless `--force`.
- **CLI semantics:** retain `--skip-done`, `--force`, `--mock`, `--no-validate`; add `--dump-plan` to print resolved DAG/artifacts before execution for debugging.
- **Docs/smoke:** add DAG recipe example (coarse+fine portionize feeding consensus) and smoke test (maybe mock) that exercises a merge of two portionizers into consensus.
- **Data shapes (driver):**
  - `StageNode`: `{id, stage, module, entrypoint, needs: set[str], input_schema, output_schema, params, artifact_path}`.
  - `ResolvedPlan`: `{run_id, output_dir, outputs_map, nodes: list[StageNode], topo: list[str]}` after validation.
  - `ArtifactIndex`: map `stage_id -> {"schema": out_schema, "path": artifact_path}` built as stages resolve; used for downstream input resolution.
- **Adapters:** treat modules where `input_schema` != produced schema; allow explicit adapter stage id inserted in recipe; validation ensures mismatches either have adapter or are marked `allow_mismatch` flag.
- **Input resolution:** default is single-input from last dependency with matching output schema; allow explicit `inputs` map per stage `{arg_name: stage_id}` for scripts that take multiple artifacts (e.g., `build` needs `pages` + `portions`). If unspecified, driver infers by schema (exact match) and errors on ambiguity.

## Work Log
- Pending
### 20251121-1712 — Reviewed driver baseline and DAG gaps
- **Result:** Success — confirmed driver currently executes a linear stage list from recipes; module manifests carry stage/input/output schemas but driver ignores them for dependency planning.
- **Notes:** Resume only checks state flag + artifact presence; no schema compatibility or DAG validation. Recipes lack ids/needs/custom-output semantics. Tasks updated to cover validation and state metadata.
- **Next:** Draft DAG-aware recipe schema (stage ids, needs, outputs map) and outline driver/state changes before implementation.
### 20251121-1728 — Drafted DAG recipe/driver plan
- **Result:** Success — outlined recipe additions (ids, needs, outputs map, provides), validation rules, DAG executor responsibilities, and state/resume semantics; captured in Plan section.
- **Notes:** Still need to map module defaults to artifacts and define adapter contract; pending unit test cases list.
- **Next:** Translate plan into concrete interfaces (data structures in `driver.py`) and adjust sample recipes to new format before coding executor.
### 20251121-1746 — Detailed driver data shapes
- **Result:** Success — added data-shape details for StageNode/ResolvedPlan/ArtifactIndex and adapter expectations into Plan. Clarified state fields with needs + schema_version.
- **Notes:** Need to reconcile artifact naming (outputs map vs module defaults) and define how multi-input stages specify source selection.
- **Next:** Design resolver logic for picking upstream artifact(s) per stage (single vs multi-input), then begin `driver.py` scaffolding changes.
### 20251121-1758 — Clarified multi-input resolution
- **Result:** Success — added input resolution rule (schema-based inference plus optional `inputs` map) to Plan.
- **Notes:** Still need concrete mapping for build stage argument names and how to surface errors for ambiguous schemas.
- **Next:** Draft updated recipe example with ids/needs/inputs for coarse+fine portionize merge to consensus.
### 20251121-1815 — Added DAG sample recipes
- **Result:** Success — created `configs/recipes/recipe-ocr-dag.yaml` and `configs/recipes/recipe-text-dag.yaml` with full ids/needs/inputs and output overrides, illustrating coarse+fine portionizers merged into consensus then resolve/build.
- **Notes:** Current consensus CLI only accepts a single hypotheses file; will require concat or adapter step when DAG executor is built. Driver still linear; recipes are reference fixtures for upcoming DAG implementation.
- **Next:** Scaffold driver DAG planner/validator to load these recipes, detect multi-input consensus need, and design adapter/concat strategy.
### 20251121-1850 — Scaffolded DAG executor path in driver
- **Result:** Success — added plan builder (ids/needs, outputs map, toposort, validation) and new driver execution path keyed by stage ids with `--dump-plan`. Input resolution wired for single-input stages and build’s multi-input via `inputs` map; consensus currently errors on multi-input to enforce adapter merge.
- **Notes:** Mock helpers adjusted to honor per-stage artifact names. Schema compatibility checks and adapter handling still TODO; consensus merge not implemented.
- **Next:** Add schema/link validation between stages, support multi-input consensus via concat/adapter, and exercise new DAG recipes under `--dry-run --dump-plan`.
### 20251121-1925 — Added schema checks + multi-input merge stub
- **Result:** Success — driver now concatenates multiple portionize outputs for consensus when present (guarded in dry-run), performs schema compatibility checks between producers/consumers, and requires schema match on resume before skipping. Mock paths updated accordingly.
- **Notes:** Merge is naive concat; no dedupe/ordering. Need adapter hook or smarter merge later. Still need resume artifact existence+schema validation tests and consensus multi-input real path.
- **Next:** Add unit-ish tests for cycle/schema mismatch, and refine consensus merge or adapter contract; consider storing schema in state for all stages.
### 20251121-1945 — Dry-run validation of DAG recipes
- **Result:** Success — `--dry-run --dump-plan` now works for both DAG recipes (ocr/text) showing topo order and artifact names; consensus merge path prepared to concat on real runs.
- **Notes:** Consensus CLI still single-input; concat temp will feed it but lacks dedupe/ordering semantics.
- **Next:** Add test scaffolding for cycle/schema mismatch and finalize adapter/merge design before real run.
### 20251121-2008 — Added plan validation + tests
- **Result:** Success — introduced `validate_plan_schemas` (fails fast when no deps match required input_schema) and hooked it into driver startup. Added `tests/driver_plan_test.py` covering cycle detection and schema mismatch; tests passing.
- **Notes:** Tests are lightweight unittest; no CI wiring yet. Build input special-case passes (at least one matching schema).
- **Next:** Improve consensus multi-input merge (ordering/dedupe) and extend resume checks to verify artifact existence+schema before skip.
### 20251121-2028 — Resume/schema checks tightened
- **Result:** Success — driver now verifies artifact file + stamped schema_version before honoring `--skip-done`; otherwise reruns stage. Added `artifact_schema_matches` helper.
- **Notes:** Build-stage schema special-case retained; consensus merge still naive concat.
- **Next:** Add ordered/deduped consensus merge or adapter hook and extend tests to cover resume/schema_skip paths.
### 20251121-2045 — Added positive schema test
- **Result:** Success — extended `tests/driver_plan_test.py` with a passing schema-match case; all tests green.
- **Notes:** Tests remain unit-level only; no integration with real artifacts/resume logic yet.
- **Next:** Cover resume/schema skip behavior and consensus multi-input concat ordering.
### 20251121-2100 — Dry-run verification of DAG runs
- **Result:** Success — executed `--dry-run` for both DAG recipes (ocr/text); commands show merged consensus inputs via temp concat and correct artifact paths with state/progress flags.
- **Notes:** Still need real run or mock to confirm concat behavior; consensus merge lacks dedupe/ordering semantics.
- **Next:** Implement ordered/deduped merge or adapter and add resume/schema skip tests.
### 20251121-2125 — Added deduped consensus merge + tests
- **Result:** Success — consensus multi-input now uses `concat_dedupe_jsonl` (stable order, dedupe by portion_id) before calling CLI. Added helper plus `tests/driver_merge_test.py`; all tests green.
- **Notes:** Merge still ignores ordering heuristics beyond stage order; adapter hook still TBD. Resume schema checks unchanged.
- **Next:** Add tests for resume/schema skip path and consider adapter interface for consensus/other multi-input cases.
### 20251121-2140 — Added duplicate-id guard test
- **Result:** Success — plan tests now include duplicate stage id rejection; all plan/merge tests still pass.
- **Notes:** Resume tests still missing; adapter hook still open.
- **Next:** Cover resume/schema skip behavior and design adapter interface.
### 20251121-2158 — Added resume/schema helper tests
- **Result:** Success — new `tests/driver_resume_test.py` validates `artifact_schema_matches` positive/negative cases; all driver_* tests run via unittest discovery (7 total).
- **Notes:** Tests are unit-level; adapter interface still TBD.
- **Next:** Decide adapter contract for multi-input stages or leave concat as stopgap; consider CI wiring for tests.
### 20251121-2220 — Added adapter module + wired recipes
- **Result:** Success — introduced `merge_portion_hyp_v1` adapter module (deduping merge) and added adapter stage handling in driver + build_command. DAG recipes now use adapter between coarse/fine portionize and consensus; dry-runs show clean command chain. Tests expanded for adapter path; full driver_* suite (8 tests) passes.
- **Notes:** Adapter currently focused on portion hypotheses; could generalize later. CI still not wired.
- **Next:** Decide if more adapters are needed or if consensus multi-input concat can be removed; consider marking Story 016 tasks as done after a mock/real run.
### 20251121-2245 — Mock DAG run with adapter
- **Result:** Success — ran `recipe-text-dag.yaml` with `--mock --skip-done`; adapter merged coarse+fine outputs, consensus mock validated, downstream stages stamped and validated. State skip honored; run completes to portions_final_raw.json.
- **Notes:** Adapter CLI now skips state/progress flags; merge dedupes by portion_id. Real LLM/OCR run still pending but path exercised end-to-end with mock.
- **Next:** Optionally run real (non-mock) small-page DAG; wire tests to CI; consider marking Story 016 tasks complete.
### 20251121-2300 — Real DAG run (text ingest)
- **Result:** Success — ran `recipe-text-dag.yaml` end-to-end (non-mock, `--force`). Coarse+fine portionize completed, adapter merged 4 hypotheses, consensus/dedupe/normalize/resolve/build finished with stamped artifacts (locked_portion_v1/resolved_portion_v1). Final `portions_final_raw.json` generated under `output/runs/sample-text-dag/`.
- **Notes:** Removed unsupported `min_conf` from fine portionize params. Pipeline_state updated; resume skip works on rerun. OCR DAG not yet run live.
- **Next:** Optionally real-run OCR DAG or mark Story 016 tasks done and proceed to docs/CI wiring.
### 20251121-2345 — Real DAG run (OCR ingest)
- **Result:** Success — ran `recipe-ocr-dag.yaml` end-to-end with OCR pages 1–20. Adapter merged coarse+fine hypotheses (96 rows), consensus produced 15 locked portions, resolve yielded 14, build completed. Artifacts stamped/validated in `output/runs/deathtrap-ocr-dag/`.
- **Notes:** Removed `images` input and unsupported `min_conf` flag for fine portionizer. Long clean/portionize runtimes but completed with resume. State reflects completed stages.
- **Next:** Wire tests into CI and mark Story 016 tasks complete.
### 20251122-0010 — Wired driver tests into CI
- **Result:** Success — added GitHub Actions workflow `.github/workflows/tests.yml` running `python -m unittest discover -s tests -p "driver_*test.py"` on push/PR.
- **Notes:** No badge yet; workflow installs requirements.txt before tests.
- **Next:** Evaluate Story 016 tasks for completion; consider badge/docs note.
