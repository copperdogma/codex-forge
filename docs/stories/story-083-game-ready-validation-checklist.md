# Story: Game-Ready Validation Checklist

**Status**: To Do  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-081 (GPT-5.1 AI-First OCR Pipeline)

---

## Goal

Define and implement a strict validation checklist to determine when a pipeline run is “game-ready” (safe to use as the authoritative source for a game engine).

---

## Success Criteria

- [ ] **Checklist defined**: A clear, reproducible checklist for game-ready status.
- [ ] **Section coverage verified**: 400 sections present, with explicit handling of known-missing physical pages.
- [ ] **Choice completeness verified**: Code-first choice extraction matches all “turn to” references; no orphaned sections without explanation.
- [ ] **Graph validation**: Incoming edges for all sections except known-missing; orphans flagged with manual-review notes.
- [ ] **Artifact inspection**: Manual spot-check across representative pages (tables, stat blocks, multi-section pages).
- [ ] **Final report**: Single validation report that states Pass/Fail and enumerates unresolved items.

---

## Tasks

- [ ] Define game-ready checklist criteria and thresholds (sections, choices, orphans, known-missing).
- [ ] Implement or reuse validators to compute coverage, orphaned sections, and choice mismatches.
- [ ] Produce a consolidated validation report artifact (Pass/Fail + details).
- [ ] Run checklist on the **pristine PDF** pipeline output and record evidence.
- [ ] Document manual spot-checks (5–10 samples) with artifact paths and notes.

---

## Work Log

### 20251222-0905 — Story created
- **Result:** Success.
- **Notes:** New requirement: define a strict, reproducible validation checklist for game-ready output on pristine scans.
- **Next:** Draft the checklist and decide which validators/artifacts will produce the pass/fail report.
