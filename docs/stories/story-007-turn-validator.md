# Story: Turn-to validator (CYOA cross-refs)

**Status**: Done

---

## Acceptance Criteria
- Detect and validate cross-reference targets
- Flag missing/invalid links
- Configurable per run (disable for non-CYOA)

## Tasks
- [x] Parse 'turn to N' from text
- [x] Cross-check against portions/sections
- [x] Reporting/JSONL of issues

## Notes
- 

## Work Log
### 20251123-1505 — Completed turn-to validation via section pipeline
- **Result:** Section pipeline now extracts targets (`section_enrich_v1`), guards them via `section_target_guard_v1` (maps + backfills + coverage report/exit), and can be double-checked with `modules/validate/assert_section_targets_v1.py` if desired. Reporting CLIs (`report_missing_targets.py`, `report_targets.py`) emit JSON stats. Full run on the book produced zero missing targets.
- **Notes:** Validation is configurable per recipe by including/excluding the validator or using `--allow-missing`. Guard adapter is the primary path; legacy map/backfill chain is superseded.
- **Next:** None; story considered complete. Future consolidation is already delivered via Story 023.
### 20251123-1407 — Supersession note
- **Result:** Documented that `section_target_guard_v1` now replaces the map_targets/backfill chain for target coverage.
- **Notes:** Keep `assert_section_targets_v1` as an optional extra guard; primary path is guard adapter.
- **Next:** None.
