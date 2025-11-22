# Story: Pipeline visibility dashboard

**Status**: In Progress

---

## Acceptance Criteria
- A single-page HTML dashboard lives in `docs/pipeline-visibility.html`, auto-refreshes, and visualizes live pipeline progress (per-stage status, percent, timestamps) by reading `pipeline_state.json` and `pipeline_events.jsonl`.
- Dashboard can open artifacts for each stage and surface lightweight metrics (counts, confidence ranges/samples) without breaking existing run layout.
- Pipeline emits incremental progress events during long-running stages (extract, clean, portionize; plus book-end signals for others) so UI updates in near real-time.
- State updates remain append-safe: `pipeline_events.jsonl` is append-only and `pipeline_state.json` keeps per-stage progress fields while preserving current consumers.
- README/docs note how to launch the dashboard (local http server target) and how it reads run data.

## Tasks
- [ ] Add append-only event logging helper and thread through driver/modules with minimal friction.
- [ ] Emit granular progress from extract/clean/portionize; add stage completion markers for consensus/dedupe/normalize/resolve/build.
- [ ] Extend `pipeline_state.json` with per-stage progress + module/schema metadata without breaking skip/resume.
- [ ] Build `docs/pipeline-visibility.html` UI (run selector, auto-refresh, stage grid, event timeline, artifact inspector, confidence snippets).
- [ ] Document usage in story log/README and ensure sample runs appear in run manifest for discovery.
- [ ] Add quick validation/dry-run to confirm commands still wire up with new flags.

## Notes
- Data sources: `pipeline_state.json` (authoritative stage status/artifacts) and `pipeline_events.jsonl` (append-only). Artifacts remain in `output/runs/<run_id>/`.
- Driver passes `--state-file/--progress-file/--run-id` into every module; modules ignore if unused, so backward compatibility is preserved.
- UI is static (no backend), designed to be served from repo root via `python -m http.server`.

## Work Log
### 20251121-1845 — Dashboard + event plumbing
- **Result:** Added ProgressLogger (append events + state progress), wired driver to emit stage start/done/skipped with module/schema info, and threaded `--state-file/--progress-file/--run-id` through all modules with per-iteration logging for extract/clean/portionize plus summaries for downstream stages. Created `docs/pipeline-visibility.html` with auto-refresh run selector, stage grid, event timeline, and artifact metrics/preview buttons.
- **Notes:** Driver now appends new runs into `output/run_manifest.jsonl` for discovery. UI reads `pipeline_state.json` + `pipeline_events.jsonl`; artifact metrics compute confidence stats on demand.
- **Next:** Smoke the dashboard against a live/mock run, add a short README blurb, and consider tail-limiting events for very long runs.
