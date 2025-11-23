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
- **Result:** Section pipeline now extracts targets (`section_enrich_v1`), maps them (`map_targets_v1`), backfills missing sections (`backfill_missing_sections_v1`), and enforces coverage via `modules/validate/assert_section_targets_v1.py` (fails on missing targets; `--allow-missing` to soften). Reporting CLIs (`report_missing_targets.py`, `report_targets.py`) emit JSON stats. Full run on the book produced zero missing targets.
- **Notes:** Validation is configurable per recipe by including/excluding the adapter or using `--allow-missing`.
- **Next:** None; story considered complete. Future consolidation tracked in Story 023 (merge map/backfill into one adapter).
