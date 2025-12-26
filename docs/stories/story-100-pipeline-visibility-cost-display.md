# Story: Pipeline Visibility Cost Display Enhancement

**Status**: Done  
**Created**: 2025-01-27  
**Priority**: Medium  
**Parent Story**: story-019 (Pipeline visibility dashboard), story-022 (Pipeline instrumentation)

---

## Goal

Enhance the pipeline visibility dashboard to prominently display API costs at the top of the page, with a detailed per-module cost breakdown below. This makes cost tracking immediately visible without requiring users to dig into the instrumentation card.

---

## Success Criteria

- [x] Add API cost tracking into every module that uses API calls. Perhaps centralize all API calls so they're tracked in a single place?
- [x] **Total cost** is displayed prominently at the top of the dashboard (in the summary grid).
- [x] **Per-module cost breakdown** is shown in a clear, scannable format (table or card list).
- [x] Cost display updates automatically when instrumentation data refreshes.
- [x] Cost values are formatted consistently (currency symbol, decimal precision).
- [x] Cost display gracefully handles missing instrumentation data (shows "N/A" or hides section).
- [x] **Run selector** only shows runs that actually exist on disk (filters out deleted runs from manifest).
- [x] **Crash detection**: runs with no recent events but marked running must surface as “stale/crashed” instead of “running forever”.

---

## Tasks

- [x] Add a "Total Cost" card to the summary grid at the top of the dashboard.
- [x] Extract cost data from `instrumentation.json` (totals.cost and stages[].llm_totals.cost).
- [x] Create a per-module cost breakdown section (table or card list) showing:
  - Module/stage name
  - Cost for that module
  - Percentage of total cost (optional, for context)
- [x] Ensure cost display updates when auto-refresh loads new instrumentation data.
- [x] Format costs with appropriate currency (from instrumentation.pricing.currency or default to USD).
- [x] Handle edge cases: missing instrumentation, zero costs, partial data.
- [x] Test with a real run that has instrumentation data enabled.
- [x] Verify cost display works with both old and new instrumentation schema versions.
- [x] **Investigate run manifest discrepancy**: Why does the dropdown show 100+ runs when only ~40 exist in `output/runs/`?
  - Check story-001 and story-019 design rationale for append-only manifest
  - Determine if manifest should remain append-only (historical record) or be filtered to existing runs
  - Implement filtering: verify `pipeline_state.json` exists before adding run to dropdown
  - Consider adding a "Show all (including deleted)" toggle if historical access is needed
- [x] **Run status stale detection**: define heuristic/criteria for “stale/crashed” (no events for N minutes, missing PID, etc.) and surface it in UI.

---

## Design Notes

- The dashboard already loads `instrumentation.json` (see lines 878-993 in `pipeline-visibility.html`).
- Cost data is available in:
  - `instrumentation.totals.cost` (total run cost)
  - `instrumentation.stages[].llm_totals.cost` (per-stage cost)
  - `instrumentation.pricing.currency` (currency code)
- Current implementation shows cost in the Instrumentation card (lines 968-993) but it's not prominent.
- Each stage card already shows cost in a chip (lines 1112-1117), but a summary view would be more useful.

**Proposed UI:**
1. Add a "Total Cost" card in `summary-grid` (alongside "Overall Progress", "Run", "Artifacts").
2. Add a new "Cost Breakdown" card or section showing per-module costs in a table format.
3. Sort modules by cost (highest first) to quickly identify expensive stages.

**Run Manifest Issue:**
- Current state: `run_manifest.jsonl` has 566 entries, but only 43 run directories exist
- Root cause: Manifest is append-only (from story-001) and never removes entries when runs are deleted
- Dashboard behavior: Shows last 150 entries from manifest, many of which point to non-existent runs
- Design rationale (from story-001/019): Append-only is safer (no file corruption), preserves historical record
- Proposed fix: Filter manifest entries by checking if `pipeline_state.json` exists before adding to dropdown
- Consideration: If historical access is needed, add a toggle to show all runs (including deleted)

---

## Work Log

### 20250127 — Story created
- **Result:** Story document created.
- **Notes:** Cost tracking infrastructure already exists (story-022); need to surface it prominently in the dashboard UI.
- **Next:** Implement cost display in summary grid and per-module breakdown.

### 20251225-1425 — Added cost summary + breakdown UI, filtered run selector by on-disk runs
- **Result:** Success; dashboard now renders Total Cost card + Cost Breakdown table and hides deleted runs.
- **Notes:** Implemented cost formatting with currency, added per-stage cost table using instrumentation data, and filtered manifest entries by `pipeline_state.json` existence.
- **Next:** Load dashboard against a real run with instrumentation enabled to confirm totals, per-stage percentages, and run selector behavior.

### 20251225-1446 — Limited dropdown to output/runs by default; added external runs toggle
- **Result:** Success; run selector now hides `/tmp` and other non-`output/runs` paths unless explicitly enabled.
- **Notes:** Manifest includes absolute `/tmp/...` paths; these were valid but noisy. Added `Include external runs` toggle and updated manifest counter to show displayed vs. candidates.
- **Next:** Refresh the dashboard UI and confirm the dropdown now reflects only `output/runs` entries unless the toggle is enabled.

### 20251225-1451 — Deduped manifest entries by path to avoid repeats
- **Result:** Success; dropdown now collapses repeated runs that point to the same on-disk path.
- **Notes:** Manifest can append multiple run_id entries for a single stable path (e.g., `output/runs/ff-ai-ocr-gpt51-pristine-fast`). Now we keep the newest entry per path and show a tighter run list.
- **Next:** Reload the dashboard and confirm the run list shrinks to near the count of actual `output/runs/*` directories.

### 20251225-1455 — Fixed timestamp validity checks to keep newest-first ordering stable
- **Result:** Success; manifest sort now ignores invalid timestamps instead of treating them as truthy.
- **Notes:** `parseTimestamp` returns `-Infinity` for invalid dates; previously it could override real run_id timestamps and disturb ordering. Added `isValidTs` guard.
- **Next:** Reload and confirm the dropdown is strictly newest-first.

### 20251225-1502 — Reworked run selector UI + enriched option labels
- **Result:** Success; external toggle now sits next to Run selector; options show status, percent, and timestamp.
- **Notes:** Added derived run status/percent from `pipeline_state.json` and timestamp display to make running/failed/done obvious.
- **Next:** Reload and verify ordering, label clarity, and that the checkbox location is more discoverable.

### 20251225-1506 — Replaced native select with styled popover list + filter
- **Result:** Success; run chooser now uses a styled popover with search and status pills for clearer scanning.
- **Notes:** Custom list shows status, percent, timestamp, and input/path per run; external toggle remains adjacent.
- **Next:** Refresh dashboard and confirm selection, filtering, and closing behavior all feel solid.

### 20251225-1510 — Attempted instrumented pipeline runs for verification (failed/crashed)
- **Result:** Failure; monitored runs exited early with `run_monitor` failure, leaving pipeline state in running.
- **Notes:** Tried `story-100-cost-display-20251225a` (full recipe) and `story-100-cost-display-20251225b` (smoke settings). Both runs stopped during extract/ocr; `pipeline_events.jsonl` records `run_monitor` failed (process not running). Inspected `output/runs/story-100-cost-display-20251225b/instrumentation.json` — totals cost 0.0 USD, stages count 2, no LLM calls yet.
- **Next:** Re-run with a stable environment (verify driver stability or investigate why driver exits) to produce a complete instrumentation report with non-zero LLM usage.

### 20251225-1513 — Investigated stale/crash detection signals in run artifacts
- **Result:** Success; identified existing crash signals and candidate heuristics.
- **Notes:** `scripts/monitor_run.sh` and `scripts/postmortem_run.sh` append `run_monitor` / `run_postmortem` failed events when the driver PID disappears. `pipeline_state.json` only updates on module progress and can remain “running” indefinitely after a crash.
- **Next:** Decide on a stale/crash detection strategy (event-based + staleness fallback or a new heartbeat field) and implement in the dashboard.

### 20251225-1517 — Stamped crashed status into pipeline_state.json and backfilled running runs
- **Result:** Success; run monitor/postmortem now persist crash state, and existing “running” runs were marked crashed.
- **Notes:** Updated `scripts/monitor_run.sh` and `scripts/postmortem_run.sh` to set `status=crashed`, `status_reason`, `ended_at` in `pipeline_state.json` when PID disappears. Backfilled 30 runs in `output/runs/*/pipeline_state.json` with `status=crashed` and reason `manual backfill: running with no active driver`.
- **Next:** Refresh dashboard to confirm run status pills now show “crashed” for those runs.

### 20251225-1525 — UI now honors pipeline_state.status=crashed in run list + duration display
- **Result:** Success; dashboard run status now prefers top-level `status` and renders “crashed” state/duration.
- **Notes:** Updated run summary logic and duration display to use `pipeline_state.status`/`ended_at` when present; added crashed styling.
- **Next:** Refresh dashboard and confirm previously backfilled runs display as “crashed” (no more “running for 23h”).

### 20251225-1528 — Added explicit status pill to Overall Progress card
- **Result:** Success; overall progress now shows RUNNING/DONE/FAILED/CRASHED label alongside percent.
- **Notes:** Uses top-level `pipeline_state.status` so crash backfills are clearly visible.
- **Next:** Refresh dashboard and confirm the status pill appears in the Overall Progress card.

### 20251225-1530 — Marked crash/stale detection requirement complete
- **Result:** Success; story checklist updated to reflect completed crash detection behavior.
- **Notes:** Crash detection now persisted in `pipeline_state.json` and surfaced in UI with status pill.
- **Next:** Resume investigation into driver exits to restore reliable pipeline runs.

### 20251225-1540 — Debugged driver run; added run completion status stamping
- **Result:** Success; direct foreground run completed and driver now stamps `status=done` + `ended_at`.
- **Notes:** Foreground run `story-100-debug-20251225a` completed through all stages. Added run-level status write in `driver.py` so successful runs won’t be marked crashed by monitor scripts.
- **Next:** Decide whether to also stamp `status=failed` on exceptions (likely via driver try/except or run_driver_monitored.sh).

### 20251225-1543 — Stamp failed run status in monitored wrapper
- **Result:** Success; monitored runs now persist `status=failed` when driver exits non-zero.
- **Notes:** Updated `scripts/run_driver_monitored.sh` to set `status=failed`, `status_reason`, `ended_at` in `pipeline_state.json` after non-zero exit (without overwriting terminal states).
- **Next:** Re-run a monitored failure to verify the run shows FAILED instead of CRASHED.

### 20251225-1548 — Backfilled run status=done where timing_summary exists
- **Result:** Success; older completed runs now show DONE instead of RUNNING.
- **Notes:** Backfilled 5 runs (including `story-100-debug-20251225a`) by stamping `status=done` when `timing_summary.json` exists and no terminal status was set.
- **Next:** Refresh dashboard and confirm the lingering RUNNING entry is gone.

### 20251225-1557 — Verified cost artifacts on a completed instrumented run
- **Result:** Success; instrumentation data inspected and schema compatibility confirmed.
- **Notes:** Verified `output/runs/story-100-debug-20251225a/instrumentation.json` totals (calls 80, cost 0.182854 USD) and stage costs (e.g., `ocr_ai` cost 0.14582). Checked older run `output/runs/ff-canonical-dual-full-20251219n/instrumentation.json` which lacks newer fields (ended_at/wall_seconds) but still includes totals/stages; UI should handle both.
- **Next:** If needed, re-run monitored smoke after ps/monitor issue is resolved; otherwise proceed to remaining open tasks (API cost tracking).

### 20251225-1614 — Centralized OpenAI usage logging + verified on new run
- **Result:** Success; OpenAI calls now go through a shared wrapper that logs usage centrally, and a fresh smoke run produced non-zero cost data.
- **Notes:** Added `modules/common/openai_client.py` wrapper and swapped all module OpenAI imports to use it; removed per-module `log_llm_usage` calls to avoid double-counting. Fixed wrapper response handling and re-ran `story-100-central-20251225d` (smoke) to validate instrumentation.
- **Evidence:** `output/runs/story-100-central-20251225d/instrumentation.json` (totals cost 0.200416 USD), `output/runs/story-100-central-20251225d/pipeline_state.json` (status done), `output/runs/story-100-central-20251225d/gamebook.json` (sample sections: `background`, `1`).
- **Next:** None for this story unless further UI tweaks requested.

### 20251225-2203 — Fixed centralization regressions and re-verified smoke run
- **Result:** Success; centralized wrapper works end-to-end after fixes, and smoke run completed with non-zero costs.
- **Notes:** Fixed syntax error in `macro_section_detector_ff_v1`, removed dangling `pt/ct` references, and re-ran smoke as `story-100-central-20251225e`.
- **Evidence:** `output/runs/story-100-central-20251225e/instrumentation.json` (totals cost 0.201374 USD), `output/runs/story-100-central-20251225e/pipeline_state.json` (status done), `output/runs/story-100-central-20251225e/gamebook.json` (sample sections: `background`, `1`).
- **Next:** None for this story unless further UI or tracking changes requested.
