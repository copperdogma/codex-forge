# Story: Validation Forensics Automation

**Status**: To Do  
**Created**: 2025-12-05  

## Goal
When validation finds missing text/choices/sections, it should automatically trace and report where the data was lost (boundary source, element text/page, upstream artifacts), so debugging requires no manual spelunking.

## Success Criteria
- [x] `validate_ff_engine_v2` (or wrapper) augments its report with traces for every missing/empty item: boundary module/evidence, start/end element ids, element text/page. (Implemented 20251205)
- [ ] For empty choices, report whether the section is an ending (death/victory/open) or truly missing navigation.
- [ ] For missing sections, report which boundary sources exist (clean/scan/fallback) and why they were dropped.
- [x] Traces are included in `validation_report.json` and visible in pipeline logs. (Implemented 20251205)

## Tasks
- [x] Enhance `validate_ff_engine_v2` to optionally load nearby artifacts (`section_boundaries_merged.jsonl`, `elements.jsonl`, `portions_enriched*.jsonl`) and attach per-section forensic traces for missing text/choices/sections. (Implemented 20251205)
- [ ] Add ending classification fallback in validation traces for no-choice sections (reuse `ending_guard_v1` logic or a cheap heuristic).
- [ ] Update AGENTS.md to require forensic trace emission on validation failures/warnings. (Done)
- [ ] Add a recipe flag or env toggle to turn forensic tracing on/off (default on).
- [ ] Document how to read traces and what artifacts they pull from.
- [x] Include span metadata in traces: end_element_id, start/end seq/page, span length, and zero-length flag to spotlight empty spans. (Implemented 20251205)
- [x] Record artifact provenance (mtime or hash) in traces to guard against stale inputs. (Implemented 20251205)
- [x] Add portion-text snippet (if present) alongside start element text to ease eyeballing mismatches. (Implemented 20251205)
- [x] Emit `suggested_action` per failing section (e.g., “rerun repair_portions on SID”, “rebuild boundary from ai_scan”, “classify ending”) to feed automated escalations. (Implemented 20251205)
- [ ] Optional: produce a lightweight HTML/CSV trace view for humans; JSON remains the source of truth.
- [ ] For each escalation target, record the loop outcome: **Resolved-good** (data fixed), **Resolved-bad** (confirmed missing in source, intentionally stubbed), or **Inconclusive-timeout** (escalation budget exhausted). Persist this in the validation report/trace.

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
