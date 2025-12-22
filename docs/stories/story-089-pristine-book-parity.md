# Story: Pristine Book Parity (Missing Sections + Robustness)

**Status**: To Do  
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-081 (GPT-5.1 AI-First OCR Pipeline)

---

## Goal

Bring the **pristine PDF** (`deathtrapdungeon00ian_jn9_1 - from internet archive.pdf`) to **100% section coverage** with the same pipeline that already succeeds on the legacy PDF, and document any required robustness improvements. The output must match the old-book coverage rules (allowing known missing sections only if verified).

---

## Context / Evidence

Full run (pristine) completed but produced **far fewer sections** and many orphans:
- Run ID: `ff-ai-ocr-gpt51-pristine-full-20251223a`
- Sections in final gamebook: **308**
- Orphaned sections: **88**
- Warnings: **133**

Likely causes:
- OCR HTML structure differs from legacy copy (headers missed, running-head confusion, layout variance).
- Boundary detection and repair loop may be overfit to old-book patterns.

---

## Success Criteria

- [ ] **Parity:** Pristine PDF produces **400 sections + background**, with only known missing sections allowed (169/170 if still missing).
- [ ] **Robustness:** Section detection + repair succeeds without book-specific hacks that break generality.
- [ ] **Choices:** Orphans reduced to known missing / verified manual exceptions.
- [ ] **Evidence:** Provide artifact paths and sample section inspections validating fixes.

---

## Tasks

- [ ] Inspect `issues_report.jsonl` + `missing_bundles` from pristine run; summarize missing section clusters and likely root causes.
- [ ] Compare HTML structure for a small sample where pristine is missing sections but old book is correct.
- [ ] Validate `coarse_segments.json` for pristine run; confirm gameplay span is accurate.
- [ ] Evaluate `detect_boundaries_html_loop_v1` on pristine pages; identify missed headers (e.g., running heads vs section numbers).
- [ ] Add or refine **FF-specific hinting** if needed, but keep it **separate** from generic OCR prompt.
- [ ] Re-run targeted repair loop on a minimal page set; verify recovered sections.
- [ ] Run full pristine pipeline; confirm section count = 401 (background + 1–400) and orphan count only for known-missing.

---

## Work Log

### 20251223-0900 — Story created
- **Result:** Success.
- **Notes:** Pristine run produced 308 sections and 88 orphans; need parity with legacy PDF. Run ID: `ff-ai-ocr-gpt51-pristine-full-20251223a`.
- **Next:** Inspect pristine missing bundles + boundary repair logs and compare with old-book HTML for same sections.
