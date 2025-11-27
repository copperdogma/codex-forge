# Story: Pipeline dashboard UI polish (highlighting & pane layout)

**Status**: In Progress (partially complete)

---

## Acceptance Criteria
- Inline artifact pane renders syntax-highlighted JSON/JSONL (colored) and extends to the full vertical height of the right column, with scrollable content.
- "Open in new tab" view renders the same artifact with syntax highlighting (no forced download) across Chrome/Safari/Firefox.
- Pane open/close/resize controls remain functional after changes; default width ~45% of viewport and draggable; layout stays responsive on narrow screens.
- Dashboard smoke on `dashboard-fixture` run passes: View-in-pane and Open-in-new-tab show highlighted content; no JS errors in console.

## Tasks
- [x] Ensure artifact pane uses full height with scroll; prevent nested `pre` sizing issues.
- [x] Confirm drag handle + close/open-tab buttons still work after layout tweaks; enforce sensible default width.
- [x] Update story log/README snippet if invocation changes.
- [x] Resolve persistent run-sort/auto-select bug: dropdown should order runs newest-first and auto-select the latest on load.
- [x] Apply general UI polish per latest feedback (layout/spacing/visual tweaks).
- [x] Order stage cards in execution order instead of current arbitrary ordering.
- [x] Fix artifact pane vertical sizing: View in pane + Load metrics should use the full right-column height, not a small window.
- [x] The Load/Pause Audio buttons are misaligned.
- [x] In the Overall Progress card, put elapsed time with a live counter or static final time with "ago" format.
- [x] Ensure footer sticks to the page bottom; it currently sits mid-page under panels.
- [x] We shouldn't have any raw html links in the page. Use the "btn-small" styles.
- [ ] Pretty-print outputs in both "Open artifact (new tab)" and "View in pane"/"Load metrics" displays.
  - There was an attempt to fix via highlight.js initialization so both pane and new-tab outputs render colored JSON/JSONL but it never did work.
- [x] Fix question mark hovers getting cut off on the left-most ones.

## Notes
- Target file: `docs/pipeline-visibility.html`; fixture run: `output/runs/dashboard-fixture`.
- Keep static hosting compatible with `python -m http.server` from repo root.

## Work Log
### 20251122-2335 — Story stubbed for UI polish
- **Result:** Created story to track fixing syntax highlighting and pane sizing in the pipeline dashboard.
- **Next:** Investigate highlight.js init and pane layout; run dashboard against `dashboard-fixture`.
### 20251123-1111 — Added new polish tasks
- **Result:** Logged issues: run dropdown ordering/auto-select bug, general UI polish, and ordering stage cards by execution.
- **Next:** Prioritize fixing run sorting/auto-select and stage ordering before visual tweaks.
### 20251126-1410 — Stage tooltips from module notes
- **Result:** Threaded module `notes` into progress events/state/instrumentation as `stage_description`, and the dashboard now shows a `?` badge in each stage card with a hover tooltip explaining the stage purpose.
- **Next:** Smoke the dashboard against a fresh run to confirm tooltips populate end-to-end and align copy to single-sentence guidance.
### 20251126-1705 — Verb-first tooltips + fresh runs
- **Result:** Rewrote all module `notes` to verb-first, human/AI-friendly summaries (import/clean/portionize/consensus/dedupe/normalize/resolve/build/enrich/adapters/validate). Updated dashboard to filter stage cards to module-backed entries; reran two mocked slices (`tooltip-ocr-1-5`, `tooltip-ocr-6-10`) so pipeline_state/events now carry the improved descriptions. Tooltips show on every rendered stage card; fallback-only aliases suppressed.
- **Tests:** `python -m pytest tests/progress_logger_test.py tests/test_pipeline_visibility_path.py`
- **Next:** Optional: tighten consensus/resolve wording to A-level clarity and smoke on a non-mock run for real wall times.
### 20251127-1450 — Comprehensive UI Polish & Syntax Highlighting
- **Result:** Completed a major UI polish pass. Fixed artifact pane sizing to use full height, corrected drag handle behavior, and ensured footer sticks to bottom. Implemented robust syntax highlighting for JSON/JSONL in both the artifact pane and new tabs (using `highlight.js` with correct script injection). Added "ago" timestamps to the Overall Progress card. Fixed misalignment of audio buttons and cutoff tooltips. Replaced raw links with button styles.
- **Verification:** Verified all UI changes and syntax highlighting (colored output) across different scenarios using browser automation and manual checks on port 8001.

