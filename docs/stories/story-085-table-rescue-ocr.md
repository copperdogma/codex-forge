# Story: Table Rescue OCR Pass

**Status**: To Do  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-082 (Large-Image PDF Cost Optimization)

---

## Goal

Recover collapsed table/grid structures (e.g., choice tables) by adding a targeted OCR rescue step **early** in the HTML pipeline.

---

## Motivation

Even at high DPI with hints, some pages (notably `page-061.jpg`) collapse multi-row choice tables into a single concatenated row. Once layout is lost at OCR time, downstream recovery is difficult.

---

## Success Criteria

- [ ] **Detection**: Identify pages where table structure has collapsed (e.g., multiple “Turn to X” options merged into single cells).
- [ ] **Rescue**: Re-run OCR on a **targeted crop** (e.g., top portion) with a table-focused prompt and replace the table HTML.
- [ ] **Generic**: Works without FF-specific hard-coding; detection uses structure patterns (rows, repeated options).
- [ ] **Validation**: Page-061 and page-020R tables retain proper row/column structure after rescue.
- [ ] **Artifact trace**: Rescue provenance recorded in artifacts (what changed, why).

---

## Tasks

- [ ] Define a “collapsed table” detector (single-row tables with concatenated cells, repeated “Turn to” patterns).
- [ ] Implement a table-rescue OCR step that re-reads a crop (top region or detected table region).
- [ ] Merge rescued HTML back into the page output with clear provenance.
- [ ] Test on page-061 (and page-020R) at 150 DPI equivalent.
- [ ] Document results in the work log with before/after snippets.

---

## Work Log

### 20251222-1535 — Story created
- **Result:** Success.
- **Notes:** New requirement to add an OCR rescue step for collapsed tables (layout loss at OCR stage).
- **Next:** Implement detection + targeted crop OCR on the known failing page.
