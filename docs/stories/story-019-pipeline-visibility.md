# Story: Pipeline visibility dashboard

**Status**: Done

---

## Acceptance Criteria
- A single-page HTML dashboard lives in `docs/pipeline-visibility.html`, auto-refreshes, and visualizes live pipeline progress (per-stage status, percent, timestamps) by reading `pipeline_state.json` and `pipeline_events.jsonl`.
- Dashboard can open artifacts for each stage and surface lightweight metrics (counts, confidence ranges/samples) without breaking existing run layout.
- Pipeline emits incremental progress events during long-running stages (extract, clean, portionize; plus book-end signals for others) so UI updates in near real-time.
- State updates remain append-safe: `pipeline_events.jsonl` is append-only and `pipeline_state.json` keeps per-stage progress fields while preserving current consumers.
- README/docs note how to launch the dashboard (local http server target) and how it reads run data.

## Tasks
- [x] Add append-only event logging helper and thread through driver/modules with minimal friction.
- [x] Emit granular progress from extract/clean/portionize; add stage completion markers for consensus/dedupe/normalize/resolve/build.
- [x] Extend `pipeline_state.json` with per-stage progress + module/schema metadata without breaking skip/resume.
- [x] Build `docs/pipeline-visibility.html` UI (run selector, auto-refresh, stage grid, event timeline, artifact inspector, confidence snippets).
- [x] Document usage in story log/README and ensure sample runs appear in run manifest for discovery.
- [x] Add quick validation/dry-run to confirm commands still wire up with new flags.
- [x] Define event schema (fields/types) and add a small unit-style test for the logging helper to guard append-only behavior.
- [x] Produce a mock run (or fixture) so the dashboard can be smoked without executing the full pipeline; ensure it's discoverable in the run manifest.

## Notes
- Data sources: `pipeline_state.json` (authoritative stage status/artifacts) and `pipeline_events.jsonl` (append-only). Artifacts remain in `output/runs/<run_id>/`.
- Driver passes `--state-file/--progress-file/--run-id` into every module; modules ignore if unused, so backward compatibility is preserved.
- UI is static (no backend), designed to be served from repo root via `python -m http.server`.

## Work Log
### 20251121-1845 — Dashboard + event plumbing
- **Result:** Added ProgressLogger (append events + state progress), wired driver to emit stage start/done/skipped with module/schema info, and threaded `--state-file/--progress-file/--run-id` through all modules with per-iteration logging for extract/clean/portionize plus summaries for downstream stages. Created `docs/pipeline-visibility.html` with auto-refresh run selector, stage grid, event timeline, and artifact metrics/preview buttons.
- **Notes:** Driver now appends new runs into `output/run_manifest.jsonl` for discovery. UI reads `pipeline_state.json` + `pipeline_events.jsonl`; artifact metrics compute confidence stats on demand.
- **Next:** Smoke the dashboard against a live/mock run, add a short README blurb, and consider tail-limiting events for very long runs.
### 20251122-0945 — Groomed tasks and planning next validation steps
- **Result:** Added explicit tasks for event schema/test coverage and for creating a mock run fixture to let the dashboard be smoked without a long pipeline execution.
- **Notes:** Mock run should populate `pipeline_state.json`, `pipeline_events.jsonl`, and `run_manifest` entry to exercise run selector + timeline; test should guard append-only logging semantics.
- **Next:** Craft minimal fixture data and smoke `python -m http.server` + dashboard to confirm auto-refresh and artifact links behave against the mock run.
### 20251122-2200 — Event schema guardrails + dashboard fixture
- **Result:** Added progress event schema validation with allowed statuses, plus `tests/progress_logger_test.py` to ensure append-only writes and type checks. Created `output/runs/dashboard-fixture` with sample artifacts/state/events and appended it to `output/run_manifest.jsonl`; README now documents how to serve `docs/pipeline-visibility.html` and smoke the dashboard using the fixture.
- **Notes:** Fixture includes stage artifacts for extract→build and confidence metrics for UI; progress events/states align with module/schema ids used in the pipeline.
- **Next:** Run a quick dashboard smoke (`python -m http.server` + open the HTML) and add a tiny dry-run/validation command to cover the new flags.
### 20251122-2220 — Artifact pane + pretty print
- **Result:** Enhanced `docs/pipeline-visibility.html` with a side-pane inspector: stage cards now include a "View in pane" button that pretty-prints JSON/JSONL (clipped to 200 records) while keeping the existing open-in-new-tab link. Layout now uses a two-column pane row for events + artifact viewer.
- **Notes:** Pane shows path and stage chips; keeps timeline visible alongside artifact content.
- **Next:** Smoke UI via `python -m http.server 8000` to confirm the new pane renders and clipping behaves on large artifacts.
### 20251122-2235 — Artifact open fix
- **Result:** Replaced anchor-based artifact open with JS blob open to avoid forced downloads, reused pretty-printer for new tabs, and wired the pane button to load/fetch reliably.
- **Notes:** Open-in-new-tab now fetches, formats, and displays as text; pane remains for inline viewing.
- **Next:** Quick manual smoke in browser to verify buttons fire and content shows (no download prompt).
### 20251122-2245 — Syntax-highlighted artifacts
- **Result:** Added highlight.js for coloured JSON pretty-print; pane now scrolls into view when invoked. New-tab view renders highlighted JSON inside a generated HTML blob to avoid downloads.
- **Notes:** Pane still clips to 200 rows to stay responsive; fallback text shown on fetch error.
- **Next:** Manual browser smoke to confirm highlight.js loads in offline/localhost and pane buttons fire.
### 20251122-2255 — Fixed script breakage
- **Result:** Escaped inline `<script>` tags in new-tab HTML to stop the page from breaking; removed unused hljs manual registration. Pane/new-tab actions should now execute instead of rendering JS as text.
- **Next:** Re-open dashboard on localhost and click “View in pane” + “Open artifact (new tab)” to confirm JSON is highlighted and no download prompts appear.
### 20251122-2310 — Resizable right-hand pane + highlight guard
- **Result:** Reworked layout into a resizable/closable right pane (drag handle, close button, open-in-new-tab button). View-in-pane now opens the pane, stores the artifact path for the tab button, and keeps highlight.js optional-safe. Colored JSON should render inline and in new tab without downloads.
- **Next:** Manual smoke to confirm drag-to-resize works, pane takes ~45% width by default, and highlight colors appear.
### 20251122-2320 — Pane height + safer pretty print
- **Result:** Pane now flexes to full height (preview stretches); pretty printer uses `textContent` with highlight.js to avoid escaping issues; new-tab view calls `hljs.highlightAll` defensively. Layout keeps resize handle.
- **Next:** Verify highlight colors show up in both pane and new tab; ensure pane fills available vertical space.
### 20251122-2348 — Validation hook + task closure
- **Result:** Added driver unit test to assert state/progress/run-id flags are injected when building commands; marked core logging/UI/state tasks complete in story checklist.
- **Notes:** UI color/pane polish split to Story 021 for vision follow-up; tests cover append-only logger and command flag wiring.
- **Next:** Manual dashboard smoke remains (highlight/pane issues tracked in Story 021); consider tail-limiting timeline for very long runs.
### 20251122-2358 — Story closed
- **Result:** Marked Story 019 as Done; residual UI polish scoped into Story 021.
- **Next:** Execute Story 021 for highlight/pane improvements; optionally add a smoke checklist in README.

### 20251227-0122 — Fix stage-id mismatch from module progress logs
- **Result:** Success.
- **Notes:** ProgressLogger now honors `PIPELINE_STAGE_ID`/`STAGE_ID` env override and records the original stage as `extra.stage_alias` when overridden. Driver now sets `PIPELINE_STAGE_ID` for all module subprocesses so module progress logs land on the correct stage id (prevents duplicate “running” stages like `extract` alongside `ocr_ai`).
- **Next:** Smoke a short run to confirm stages reach 100% and no duplicate stage entries appear in `pipeline_state.json`.
