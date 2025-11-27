# Story: AI planner to assemble pipelines

**Status**: To Do

---

## Acceptance Criteria
- Assistant collects user goals and emits pipeline config (YAML) with a proposed recipe path.
- Suggests modules/params or flags missing capabilities (recommends building new modules when needed).
- Interactive flow: presents plan summary, allows user edits/confirmation before execution, and logs rationale/assumptions.
- Plan aligns with existing recipes/modules and can branch to the recommended recipe on approval.

## Tasks
- [ ] Prompt + config generator (plan YAML + rationale) that consumes module manifest and user goals.
- [ ] Module manifest/catalog export for planner (list modules, stages, capabilities).
- [ ] CLI/driver integration to run planner, present plan, allow edits, and dispatch to chosen recipe.
- [ ] Gap-detection hook to surface missing capabilities (e.g., formulas) and suggest build tasks or fallbacks.
- [ ] Logging/trace: store plan, user edits, and final chosen recipe under `output/runs/<run_id>/`.

### Intake handoff notes (from Story 027)
- Run intake before planning: `python driver.py --recipe configs/recipes/recipe-intake-contact-sheet.yaml --run-id intake-<book> --output-dir output/runs/intake-<book> --force`.
- Planner inputs: `output/runs/intake-<book>/overview_plan_final.jsonl` (intake_plan_v1), contact sheets (`contact-sheets/`), manifest (`build_contact_sheets.jsonl`).
- Intake plan already carries `signals`, `signal_evidence` (pages + reasons), and `capability_gaps`; intake recipe does **not** dispatch downstream.
- Planner flow: load intake plan → summarize signals/gaps to the user → capture their choices (ignore gap, build module, pick existing recipe, defer) → run/queue the chosen recipe or module-build steps while recording decisions.

## Notes
- Should work in tandem with the contact-sheet intake (Story 027) where applicable; planner should consume its `intake_plan_v1` and module-gap results.
- Keep web lookup optional; default to local signals and module catalog.
- Emphasize confirmation gate to prevent unexpected runs.

## Work Log
### 20251126-1640 — Aligned planner with contact-sheet intake
- **Result:** Expanded acceptance criteria and tasks to include gap detection, user confirmation flow, and integration with module catalog; noted linkage to Story 027 outputs.
- **Notes:** Planner should be able to take `intake_plan_v1` (book type, gaps) and map to a recipe; capture user edits before dispatch.
- **Next:** Define module catalog format and prompt contract; sketch CLI flow that asks to proceed and branches on approval.
### 20251126-1707 — Added module catalog dependency
- **Result:** Introduced `modules/module_catalog.yaml` (via Story 027 work) as a dependency for planner gap checks and recipe selection.
- **Notes:** Planner needs to consume this catalog and the `capability_gaps` produced by intake to advise users before executing.
- **Next:** Draft prompt/CLI contract that reads the catalog and plan, presents options, and dispatches to chosen recipe.
### 20251126-1752 — Confirmation gate added (Story 027 linkage)
- **Result:** Story 027 added `confirm_plan_v1` module and recipe pause. Planner should treat this as the handoff point for user edits/approval before dispatch.
- **Notes:** We need to integrate this gate into the planner UX (auto_approve flags, user-edited plan overrides) and ensure downstream branching is coordinated.
- **Next:** Define the planner’s CLI flow to reuse/drive `confirm_plan_v1` or subsume its logic, and map approved plans to recipes.
