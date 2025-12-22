# Story: Run Summary UX (Missing Sections + Stage Metrics)

**Status**: To Do  
**Created**: 2025-12-23  
**Priority**: Medium  
**Parent Story**: story-081 (GPT-5.1 AI-First OCR Pipeline)

---

## Goal

Make pipeline output summaries **actionable and obvious**: missing sections must be as prominent as orphaned sections, and each stage should emit a concise metric summary relevant to that stage.

---

## Success Criteria

- [ ] **Missing sections** count is printed in the run summary (same prominence as orphaned sections).
- [ ] **Stage summaries** include 1–2 key metrics per stage (e.g., coarse segments count, sections found, portions emitted).
- [ ] **Warnings** are surfaced at the end with pointers to artifact paths.
- [ ] **No noise**: summaries stay short and consistent across runs.

---

## Tasks

- [ ] Update `detect_boundaries_html_loop_v1` to report **missing section count** in its summary.
- [ ] Update `extract_choices_relaxed_v1` summary to include missing sections (if available) and link to issues report.
- [ ] Add summary lines for key stages (coarse segments, boundaries, portions, choices) in a consistent format.
- [ ] Ensure summaries are emitted in `pipeline_events.jsonl` and stdout.
- [ ] Validate with a smoke run and a full run (old + pristine).

---

## Work Log

### 20251223-0910 — Story created
- **Result:** Success.
- **Notes:** Pristine run output did not surface missing section counts in summary; only orphaned sections were called out. Need missing sections to be prominent and per-stage summaries more informative.
- **Next:** Identify the best place to surface missing-section counts (boundary loop + final report) and add consistent summary format.
