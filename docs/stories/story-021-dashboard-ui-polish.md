# Story: Pipeline dashboard UI polish (highlighting & pane layout)

**Status**: To Do

---

## Acceptance Criteria
- Inline artifact pane renders syntax-highlighted JSON/JSONL (colored) and extends to the full vertical height of the right column, with scrollable content.
- "Open in new tab" view renders the same artifact with syntax highlighting (no forced download) across Chrome/Safari/Firefox.
- Pane open/close/resize controls remain functional after changes; default width ~45% of viewport and draggable; layout stays responsive on narrow screens.
- Dashboard smoke on `dashboard-fixture` run passes: View-in-pane and Open-in-new-tab show highlighted content; no JS errors in console.

## Tasks
- [ ] Fix highlight.js initialization so both pane and new-tab outputs render colored JSON/JSONL.
- [ ] Ensure artifact pane uses full height with scroll; prevent nested `pre` sizing issues.
- [ ] Confirm drag handle + close/open-tab buttons still work after layout tweaks; enforce sensible default width.
- [ ] Cross-browser smoke on dashboard-fixture (Chrome + Safari/Firefox) and log console results.
- [ ] Update story log/README snippet if invocation changes.

## Notes
- Target file: `docs/pipeline-visibility.html`; fixture run: `output/runs/dashboard-fixture`.
- Keep static hosting compatible with `python -m http.server` from repo root.

## Work Log
### 20251122-2335 — Story stubbed for UI polish
- **Result:** Created story to track fixing syntax highlighting and pane sizing in the pipeline dashboard.
- **Next:** Investigate highlight.js init and pane layout; run dashboard against `dashboard-fixture`.
