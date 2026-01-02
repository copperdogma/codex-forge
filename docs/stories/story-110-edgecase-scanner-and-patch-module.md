# Story: Edge-Case Scanner + Patch Module (Post-Extraction)

**Status**: To Do

---

## Problem Statement

Even with generalized extraction rules, some books will contain rare or book-specific mechanics that are too brittle to handle with global heuristics. We need a dedicated post-extraction scanner that identifies likely edge cases, routes them to targeted AI analysis, and writes deterministic patch artifacts that repair the gamebook output without baking book-specific hacks into core modules.

## Goals

- Detect edge cases after the gamebook is assembled (combat, checks, choices, stat mods, etc.).
- Escalate only flagged sections to AI for structured interpretation.
- Emit a patch artifact keyed by section/event id with explicit edits.
- Apply patches in a dedicated module to keep core extraction generic.
- Make patch generation repeatable, auditable, and reversible.

## Acceptance Criteria

- [ ] Scanner produces a structured report of candidate edge cases with reason codes and pointers to source artifacts.
- [ ] AI analysis is only invoked for flagged sections and returns structured patch entries.
- [ ] Patch artifact format is documented and versioned.
- [ ] Patch apply module runs after build_gamebook and updates the final gamebook deterministically.
- [ ] Patch application is idempotent and logs every change (before/after diff)
- [ ] Patch application is optional and recipe-controlled (opt-in).
- [ ] At least one real book run demonstrates detection + patching of a combat edge case.

## Tasks

- [ ] Define edge-case signals per mechanic (combat, stat checks, choices, stat mods, inventory).
- [ ] Add a scanner module that consumes `gamebook.json` and emits a JSONL report with reason codes and pointers.
- [ ] Draft patch schema (target path, operation, provenance, AI rationale).
- [ ] Implement AI analysis module that consumes scanner output and emits patch entries.
- [ ] Implement patch apply module (post-build) that applies patch entries to gamebook.
- [ ] Add recipe hook/flag for patch application.
- [ ] Add tests for patch schema + idempotent patch application.
- [ ] Update docs with patch workflow and recommended usage.

## Work Log

<!-- Append-only log entries. -->

### 20260102-1104 — Created story stub for edge-case scanner + patch workflow
- **Result:** Success.
- **Notes:** Added problem statement, acceptance criteria, and tasks for a post-extraction edge-case scanner and patch module.
- **Next:** Prioritize signal definitions and draft patch schema.
