# Story 128: Onward Table Fidelity Verification

**Status**: To Do

---
**Depends On**: story-026 (Onward to the Unknown pipeline)
**Blocks**: story-129 (HTML output polish)

## Goal
Verify that every genealogy table in *Onward to the Unknown* faithfully represents the original scan — no LLM normalization, no column drift, no invented/dropped data. Fix anything that's wrong.

This is the hardest problem in the Onward pipeline. The genealogy tables use an unusual NAME / BORN / MARRIED / SPOUSE / BOY / GIRL / DIED column layout where data doesn't always align rationally with headers (remarriages span rows, BOY/GIRL counts are sometimes combined, dates appear in unexpected columns). LLMs consistently try to "fix" or normalize this data, which corrupts it.

## Context
- **Full book**: 127 pages (Image000–Image126); only ~60 have been processed so far.
- **Genealogy table pages** (identified by pipeline): ~18 pages in the 60-page subset. More expected in the remaining 67 pages.
- **Known failure modes** (from Story 026 iterations):
  - LLM normalization: reordering, reformatting, or "correcting" irregular data
  - BOY/GIRL count merging (e.g., "11 4" in one cell instead of split columns)
  - Continuation-row misalignment (remarriage lines, multi-line spouse names)
  - Date drift (dates shifting to adjacent rows)
  - Column count mismatches (missing or extra columns vs. the scan)
  - Running heads / page numbers leaking into table cells

## Acceptance Criteria
- [ ] **Full book processed**: All 127 pages run through the Onward pipeline (not just the 60-page subset).
- [ ] **Every genealogy table manually verified**: Each table page compared side-by-side against the original scan image. Discrepancies documented per-page.
- [ ] **All critical discrepancies fixed**: Any cell content that differs from the scan (wrong column, normalized text, missing data, invented data) is resolved — either by improving prompts/post-processing or by documenting as an accepted limitation.
- [ ] **Verification checklist recorded**: A table in this story listing every genealogy page, its verification status (pass/fail/accepted), and notes on any issues found.
- [ ] **No regressions on passing pages**: Fixes for failing pages don't break pages that were already correct.

## Approach
This is primarily a **manual verification story** — the human compares pipeline output against scans and the pipeline is iterated until the output is faithful. The workflow:

1. **Run the full 127-page pipeline** (expand beyond the 60-page subset).
2. **Identify all genealogy table pages** in the full output.
3. **For each table page**: open the scan image and the pipeline HTML side-by-side. Compare every cell. Record pass/fail + specific issues.
4. **Batch fix**: Group similar failures (e.g., "all BOY/GIRL merges") and fix at the prompt/post-processing level rather than per-page patches.
5. **Re-run and re-verify** until all tables pass or remaining issues are documented as accepted limitations.

## Verification Checklist
<!-- Fill in as pages are verified. Add rows for new table pages found in the full run. -->
| Page | Printed Page | Chapter | Status | Issues |
|------|-------------|---------|--------|--------|
| | | | | |

## Tasks
- [ ] Run full 127-page pipeline (expand `onward-canonical` beyond 60-page subset)
- [ ] Identify all genealogy table pages in the full output
- [ ] Manual verification: compare each table page against scan (side-by-side)
- [ ] Document all discrepancies in the verification checklist above
- [ ] Fix critical issues (prompt improvements, post-processing, table rescue tuning)
- [ ] Re-run pipeline on affected pages and re-verify
- [ ] Confirm no regressions on previously passing pages
- [ ] Final sign-off: all tables pass or remaining issues accepted

## Non-Negotiables
- **No normalization**: Pipeline output must match the scan exactly, even when the original data looks "wrong" or inconsistent.
- **Cell-level fidelity**: Every cell in the HTML table must match the corresponding cell in the scan. Column assignment matters.
- **Fix at the pipeline level**: Don't manually edit HTML output. If something is wrong, fix the prompt, post-processing, or table rescue logic so it's correct for all similar cases.

## Work Log
