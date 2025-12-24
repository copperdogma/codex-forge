# Story: Late-Stage Section Validation and Reachability Analysis

**Status**: Done
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-083 (Game-Ready Validation Checklist)

---

## Goal

Implement a comprehensive validation pass at the end of the pipeline that aggregates all referenced section IDs from all enriched mechanics (Choices, Combat, Stat Checks, Inventory) and verifies their reachability and existence against the final set of extracted sections.

---

## Motivation

Earlier validation passes (like choice linking) only see a subset of game book navigation. With the addition of Combat win/loss paths, Stat Check outcomes, and Inventory conditional jumps, navigation has become multi-dimensional. 

A final, late-stage validation pass ensures:
- **100% Graph Integrity**: Every "Turn to X" in the book (regardless of source) points to a valid, extracted section.
- **Orphan Detection**: Identify sections that exist but are never referenced (Dead Ends).
- **Dead-End Detection**: Identify sections that have no outgoing links (excluding legitimate endings).
- **Holistic Accuracy**: High confidence that the produced `gamebook.json` is fully playable without broken links.

---

## Success Criteria

- [x] **Aggregate all references**: Collect referenced section IDs from:
    - `choices.target`
    - `combat.win_section`, `combat.loss_section`, `combat.escape_section`
    - `stat_checks.pass_section`, `stat_checks.fail_section`
    - `inventory_checks.target_section`
- [x] **Verify reachability**: Compare the aggregated list against the authoritative list of `section_id`s in the run.
- [x] **Broken Link Detection**: Flag any reference to a section ID that does not exist in the final artifact.
- [x] **Island Section Detection**: Flag any section (except Section 1 and Frontmatter) that has zero incoming references from any mechanic.
- [x] **Unified Validation Report**: Emit a detailed JSON/HTML report summarizing the "connectivity health" of the book.
- [x] **Recipe Integration**: Insert this as a final safety gate in `recipe-ff-ai-ocr-gpt51.yaml` before export.

---

## Solution Approach

**New Module**: `modules/validate/validate_holistic_reachability_v1/`

**Strategy:**
1. **Source Agnostic Collection**: The module should walk the `EnrichedPortion` or `gamebook.json` and collect every string that represents a target section ID.
2. **Set Comparison**: 
    - `AuthoritativeSet` = {all extracted section IDs}
    - `ReferencedSet` = {all target section IDs found in mechanics}
    - `BrokenLinks` = `ReferencedSet` - `AuthoritativeSet`
    - `Orphans` = `AuthoritativeSet` - `ReferencedSet` - {1, "background", etc.}
3. **Forensics**: For broken links, provide snippets of the source text/html where the reference was found to aid in manual or automated repair.

---

## Tasks

- [x] Design the holistic reachability validator module.
- [x] Implement reference aggregation for all enrichment types (Choices, Combat, Stats, Inventory).
- [x] Implement broken link and orphan section logic.
- [x] Generate a visual or structured connectivity report.
- [x] Integrate into the canonical Fighting Fantasy recipe.
- [x] Verify on a full book run (e.g., Deathtrap Dungeon) and document findings.

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Shifting validation to the end of the pipeline allows us to catch broken links that regex-only or single-mechanic validators miss.

### 20251223-XXXX — Implementation and Integration
- **Result:** Success. Implemented `validate_holistic_reachability_v1` and integrated it as a final safety gate.
- **Notes:** Updated `driver.py` to support flexible flag passing for the `validate` stage. Verified on *Deathtrap Dungeon*, successfully identifying the known orphan section (281) and confirming overall graph integrity.
- **Outcome:** Holistic connectivity analysis is now part of the canonical enrichment pipeline.
