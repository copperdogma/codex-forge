# Story: Pipeline instrumentation (timing & cost)

**Status**: To Do

---

## Acceptance Criteria
- Capture per-stage wall time, CPU time, and count of LLM/API calls with model names and token usage (prompt/completion).
- Emit run-level cost estimate using configurable price sheet per model.
- Expose a human-readable report (JSON + markdown summary) in the run directory.
- Wire instrumentation into `driver.py` without breaking existing recipes; can be toggled via recipe or CLI flag.
- Document how to enable instrumentation and interpret reports.

## Tasks
- [ ] Define instrumentation data schema (per stage + run summary) and add to `schemas.py` or dedicated report format.
- [ ] Add driver hooks to record start/end timestamps, durations, and system resource info (CPU wall/elapsed).
- [ ] Integrate OpenAI usage capture (model, prompt_tokens, completion_tokens, total_cost via price table).
- [ ] Add price table configuration (YAML) and default pricing for current models; allow overrides per run.
- [ ] Emit report files (JSON + markdown) into `output/runs/<run_id>/` and link from manifest.
- [ ] Provide CLI/recipe flag to enable instrumentation; ensure default off to avoid overhead where undesired.
- [ ] Add validator or smoke test to ensure instrumentation outputs parse and include required fields.
- [ ] Update docs (`README` or `docs/requirements.md`) with enablement and sample report.

## Notes
- Consider piggybacking on existing `ProgressLogger` events; append instrumentation instead of duplicating state.
- Pricing: store cents/token for prompt/completion by model; fall back to defaults if model not found.
- Should work for both local-only stages and LLM stages; local stages can record duration without cost.

## Work Log
### 20251122-1424 — Created instrumentation story stub
- **Result:** Success; added story entry and acceptance/tasks for pipeline timing & cost instrumentation.
- **Notes:** Need to design schema and driver hooks next.
- **Next:** Draft instrumentation schema and price table format; plan driver integration approach.
