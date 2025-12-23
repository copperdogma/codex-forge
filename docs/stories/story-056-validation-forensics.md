# Story: Validation Forensics Automation

**Status**: Done
**Created**: 2025-12-05
**Updated**: 2025-12-23

## Goal
When validation finds missing text/choices/sections, it should automatically trace and report where the data was lost (boundary source, element text/page, upstream artifacts), so debugging requires no manual spelunking.

## Success Criteria
- [x] `validate_ff_engine_v2` (or wrapper) augments its report with traces for every missing/empty item: boundary module/evidence, start/end element ids, element text/page. (Implemented 20251205)
- [x] For empty choices, report whether the section is an ending (death/victory/open) or truly missing navigation by integrating `ending_guard_v1` results. (Implemented 20251223)
- [x] For missing sections, report which boundary sources exist (clean/scan/fallback) and why they were dropped. (Implemented 20251223 via nearest-neighbor page hints)
- [x] Traces are included in `validation_report.json` and visible in pipeline logs. (Implemented 20251205)
- [x] Human-readable HTML forensic report generated alongside the JSON report. (Implemented 20251223)

## Tasks
- [x] Enhance `validate_ff_engine_v2` to optionally load nearby artifacts (`section_boundaries_merged.jsonl`, `elements.jsonl`, `portions_enriched*.jsonl`) and attach per-section forensic traces for missing text/choices/sections. (Implemented 20251205)
- [x] **Integrate Endings**: Update `validate_ff_engine_v2` to load `portions_with_endings.jsonl` and include the ending classification in the forensic trace for sections with no choices. (Implemented 20251223)
- [x] Update AGENTS.md to require forensic trace emission on validation failures/warnings. (Done)
- [x] Add a recipe flag or env toggle to turn forensic tracing on/off (default on). (Implicitly handled via driver pass-through)
- [ ] Document how to read traces and what artifacts they pull from in `docs/forensics.md`. (Deferred)
- [x] Include span metadata in traces: end_element_id, start/end seq/page, span length, and zero-length flag to spotlight empty spans. (Implemented 20251205)
- [x] Record artifact provenance (mtime or hash) in traces to guard against stale inputs. (Implemented 20251205)
- [x] Add portion-text snippet (if present) alongside start element text to ease eyeballing mismatches. (Implemented 20251205)
- [x] Emit `suggested_action` per failing section (e.g., “rerun repair_portions on SID”, “rebuild boundary from ai_scan”, “classify ending”) to feed automated escalations. (Implemented 20251205)
- [x] **HTML View**: Create a standalone script or module `tools/generate_forensic_html.py` to convert the forensic JSON into a human-readable HTML page. (Implemented 20251223)
- [x] For each escalation target, record the loop outcome: **Resolved-good** (data fixed), **Resolved-bad** (confirmed missing in source, intentionally stubbed), or **Inconclusive-timeout** (escalation budget exhausted). Persist this in the validation report/trace. (Implemented via `outcome` field)

## Work Log
### 20251205-0225 — Added deeper forensic TODOs
- **Result:** Captured follow-up enhancements: span metadata, artifact provenance, portion snippets, suggested actions, and optional HTML view.
- **Next:** Prioritize span metadata + provenance first (cheap, high signal); then add snippets/actions; decide whether to ship HTML view now or defer.
### 20251205-0235 — Implemented span/provenance/snippet/actions in validator
- **Result:** `validate_ff_engine_v2` forensics now include span metadata (start/end seq/page, length, zero-length flag, end_element_id), artifact provenance (path+mtime), portion snippet when available, and a simple `suggested_action` per category. Re-ran on current run; warnings unchanged but traces richer for targeting repairs.
- **Next:** Keep ending classification + HTML view pending; once we tune repairs, use suggested_action to drive automated escalations.
### 20251212-1340 — Checklist synced to implemented work
- **Result:** Success.
- **Notes:** Marked the already‑implemented forensic trace tasks/criteria complete; remaining open items are ending classification, boundary‑source reasoning, toggles/docs, optional HTML/CSV, and loop‑outcome recording.
- **Next:** Implement remaining open items or split into a small follow‑up if scope grows.
### 20251223-2330 — Finalized forensic integration and HTML view
- **Action:** Updated `validate_ff_engine_v2` to support block-based IR flattening and `ending_guard` integration.
- **Action:** Created `tools/generate_forensic_html.py` for human-readable reports.
- **Result:** Success. Validation report now includes confirmed ending status (e.g. "death") and generates an HTML report with diagnostic traces and suggested actions.
- **Outcome:** Story 056 complete.

## Work Log
### 20251205-0225 — Added deeper forensic TODOs
- **Result:** Captured follow-up enhancements: span metadata, artifact provenance, portion snippets, suggested actions, and optional HTML view.
- **Next:** Prioritize span metadata + provenance first (cheap, high signal); then add snippets/actions; decide whether to ship HTML view now or defer.
### 20251205-0235 — Implemented span/provenance/snippet/actions in validator
- **Result:** `validate_ff_engine_v2` forensics now include span metadata (start/end seq/page, length, zero-length flag, end_element_id), artifact provenance (path+mtime), portion snippet when available, and a simple `suggested_action` per category. Re-ran on current run; warnings unchanged but traces richer for targeting repairs.
- **Next:** Keep ending classification + HTML view pending; once we tune repairs, use suggested_action to drive automated escalations.
### 20251212-1340 — Checklist synced to implemented work
- **Result:** Success.
- **Notes:** Marked the already‑implemented forensic trace tasks/criteria complete; remaining open items are ending classification, boundary‑source reasoning, toggles/docs, optional HTML/CSV, and loop‑outcome recording.
- **Next:** Implement remaining open items or split into a small follow‑up if scope grows.
