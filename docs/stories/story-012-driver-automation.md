# Story: Automation wrapper (driver + config snapshots)

**Status**: Done

---

## Acceptance Criteria
- Single driver to run stages from config
- Snapshot configs per run for reproducibility

## Tasks
- [x] Driver script to execute recipe-defined stages (DAG + linear) via `driver.py`.
- [x] Config snapshot write into each run directory (recipe, resolved plan, registry metadata, settings used).
- [x] Hooks for manifest update (`output/run_manifest.jsonl` entry per run).
- [x] Validate snapshot artifacts are referenced in manifest/metadata and covered by tests or dry-run check.

## Notes
- 

## Work Log
- Pending

### 20251124-1102 — Baseline audit of driver automation
- **Result:** Partial success; driver implementation and manifest hook already present, config snapshot missing.
- **Notes:** Reviewed `driver.py` to confirm DAG/linear execution plan, state/progress logging, and `register_run` writing `output/run_manifest.jsonl`; no logic found to persist recipe/registry/settings snapshots per run.
- **Next:** Implement config snapshot into run directory and reference in manifest/metadata; add validation or tests to assert snapshot files exist after a driver run.

### 20251124-1106 — Added per-run config snapshots + manifest links
- **Result:** Success; driver now saves recipe/plan/registry snapshots per run, optional settings copy, and records paths in run_manifest. Added integration test to cover snapshots.
- **Notes:** Implemented `snapshot_run_config` (writes `snapshots/{recipe.yaml,plan.json,registry.json,settings.*}`) and enhanced `register_run` to include snapshot paths. Manifest paths stored as relpaths. New test `DriverIntegrationTests.test_snapshots_written_and_manifest_links` verifies files and manifest entry. Ran test locally (pass).
- **Next:** Consider copying settings automatically when recipe references a settings path; optional follow-up to snapshot pricing table/instrumentation configuration if needed.

### 20251124-1120 — Snapshotted pricing/instrument config; skip dump side-effects; added settings relpath test
- **Result:** Success; pricing/instrumentation configs are now captured in snapshots; dump-plan no longer writes snapshots; settings snapshot covered by new integration test.
- **Notes:** Snapshot now copies pricing table (if used), writes instrumentation config blob, and defers manifest write until after dump-plan guard. Added test `test_settings_snapshot_and_relpaths_outside_repo` to ensure settings file copies into snapshots and manifest stores relative paths even for runs outside repo root. Cleaned snapshot creation to occur after dump-plan early return.
- **Next:** If desired, add small check to avoid creating run_dir on dump-plan (currently avoided); could also snapshot ENV overrides in the future.

### 20251124-1123 — Added pricing/instrument snapshot test, README note, full test run
- **Result:** Success; added integration test for pricing/instrumentation snapshots, documented snapshots in README, and ran full pytest suite (34 passed).
- **Notes:** New test `test_pricing_and_instrumentation_snapshots_when_enabled` covers pricing copy and instrumentation JSON with manifest relpaths. README now mentions snapshot bundle contents. Full suite green; only pydantic deprecation warning (pre-existing).
- **Next:** Optional: document warning suppression or migrate to Pydantic v2 models; consider ENV snapshot/redaction if needed.
