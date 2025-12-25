# Story: Pipeline Visibility Cost Display Enhancement

**Status**: To Do  
**Created**: 2025-01-27  
**Priority**: Medium  
**Parent Story**: story-019 (Pipeline visibility dashboard), story-022 (Pipeline instrumentation)

---

## Goal

Enhance the pipeline visibility dashboard to prominently display API costs at the top of the page, with a detailed per-module cost breakdown below. This makes cost tracking immediately visible without requiring users to dig into the instrumentation card.

---

## Success Criteria

- [ ] Add API cost tracking into every module that uses API calls. Perhaps centralize all API calls so they're tracked in a single place?
- [ ] **Total cost** is displayed prominently at the top of the dashboard (in the summary grid).
- [ ] **Per-module cost breakdown** is shown in a clear, scannable format (table or card list).
- [ ] Cost display updates automatically when instrumentation data refreshes.
- [ ] Cost values are formatted consistently (currency symbol, decimal precision).
- [ ] Cost display gracefully handles missing instrumentation data (shows "N/A" or hides section).
- [ ] **Run selector** only shows runs that actually exist on disk (filters out deleted runs from manifest).

---

## Tasks

- [ ] Add a "Total Cost" card to the summary grid at the top of the dashboard.
- [ ] Extract cost data from `instrumentation.json` (totals.cost and stages[].llm_totals.cost).
- [ ] Create a per-module cost breakdown section (table or card list) showing:
  - Module/stage name
  - Cost for that module
  - Percentage of total cost (optional, for context)
- [ ] Ensure cost display updates when auto-refresh loads new instrumentation data.
- [ ] Format costs with appropriate currency (from instrumentation.pricing.currency or default to USD).
- [ ] Handle edge cases: missing instrumentation, zero costs, partial data.
- [ ] Test with a real run that has instrumentation data enabled.
- [ ] Verify cost display works with both old and new instrumentation schema versions.
- [ ] **Investigate run manifest discrepancy**: Why does the dropdown show 100+ runs when only ~40 exist in `output/runs/`?
  - Check story-001 and story-019 design rationale for append-only manifest
  - Determine if manifest should remain append-only (historical record) or be filtered to existing runs
  - Implement filtering: verify `pipeline_state.json` exists before adding run to dropdown
  - Consider adding a "Show all (including deleted)" toggle if historical access is needed

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

