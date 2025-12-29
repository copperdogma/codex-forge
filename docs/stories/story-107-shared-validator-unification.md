# Story: Shared Validator Unification (Node/AJV Canonical)

**Status**: To Do  
**Created**: 2025-12-29  
**Priority**: High  
**Parent Story**: story-030 (FF Engine format), story-083 (Game-ready validation checklist)

---

## Goal

Make the **Node/AJV FF validator** the canonical, portable validation engine shared between the pipeline and the game engine, with explicit versioning so mismatches are detectable without blocking correct validation.

---

## Motivation

We require the pipeline and the game engine to use **identical validation logic**. The Node validator is portable but has drifted behind the pipeline output (e.g., combat arrays). This story restores a single source of truth and documents how to use it in both contexts.

---

## Success Criteria

- [ ] **Validator updated**: `validate_ff_engine_node_v1` accepts current pipeline output (combat arrays, etc.).
- [ ] **Canonical in pipeline**: Recipes use Node validator as the authoritative schema validator; Python validator remains for forensics.
- [ ] **Portability documented**: README + AGENTS explain what the validator is, why it matters, and that it must ship with `gamebook.json` to the game engine.
- [ ] **Versioning**: Introduce a clear version stamp and mismatch signaling (warning on mismatch, no hard fail if validation passes).
- [ ] **Game-ready alignment**: `story-083` checklist updated/confirmed to require Node validator pass.

---

## Approach

1. **Audit validator drift** vs current pipeline output schema.
2. **Update Node validator** to handle current structures (e.g., combat arrays).
3. **Wire canonical validation** in recipes (`recipe-ff-ai-ocr-gpt51*.yaml`).
4. **Add versioning**:
   - Add a `validatorVersion` (or similar) in `gamebook.json` metadata.
   - Node validator emits its own version.
   - On mismatch: warn + record in report (do not fail if validation succeeds).
5. **Documentation**: Update README + AGENTS with “ship validator with gamebook” guidance.

---

## Tasks

- [ ] Identify and fix validator drift (combat arrays, other schema mismatches).
- [ ] Update Node validator to handle new shapes without breaking legacy.
- [ ] Rewire canonical validation stage in recipes to use Node validator.
- [ ] Add version stamp in gamebook output + validator report.
- [ ] Implement mismatch warning logic (no fail on mismatch if validation passes).
- [ ] Update README and AGENTS.md with validator guidance and portability note.
- [ ] Run Node validator on `ff-ai-ocr-gpt51-pristine-fast-full` and record artifacts.

---

## Work Log

### 20251229-1615 — Story created
- **Result**: Success; stubbed story to re‑canonize Node validator and add versioning/portability guidance.
- **Notes**: Current Node validator crashes on combat array output; pipeline uses Python validators instead.
- **Next**: Audit validator drift, then update Node validator and recipes.

