# Story: Module encapsulation & shared common

**Status**: To Do

---

## Acceptance Criteria
- Shared utilities (e.g., utils, ocr) are provided via a common package/module under `modules/common` (or equivalent), with no sys.path bootstraps in module mains.
- Modules import shared code from the common package; no direct repo-root imports remain in module code.
- Driver runs existing recipes without requiring PYTHONPATH tweaks; CI smoke passes.
- Legacy helper duplication is removed or redirected to the common package.

## Tasks
- [x] Create `modules/common` package and move/shared utilities (utils, ocr helpers) there; expose clean import paths.
- [x] Update module entrypoints to import from the common package; remove sys.path mutation from module mains.
- [x] Adjust driver/recipes if needed for new package layout; ensure stamping/validation unaffected.
- [x] Update AGENTS/README to reflect common package usage.
- [x] Run existing smokes (text mock CI, local text/OCR samples) to verify no regressions (text mock and OCR mock runs completed; full OCR LLM run still optional).

## Notes
- Keep backward compatibility with current artifacts; focus on imports/packaging only.
- Consider adding a `modules/common/__init__.py` for clear public surface.

## Work Log
- Pending

### 20251121-1707 — Initial assessment and inventory
- **Result:** Success; story doc reviewed and current tasks cover common package, import cleanup, driver/docs updates, and smokes.
- **Notes:** Located sys.path bootstraps in multiple module mains (build_portions_v1, extract_ocr_v1, normalize_ids_v1, resolve_overlaps_v1, consensus_vote_v1, extract_text_v1, dedupe_ids_v1, portionize_sliding_v1, clean_llm_v1). Confirmed shared helpers live at repo root (`utils.py`, `ocr.py`) and are imported directly by modules.
- **Next:** Draft layout for `modules/common` (utils/ocr), update imports for affected modules, and plan validation steps (smoke recipes).

### 20251121-1710 — Common package created; imports cleaned; dry-run
- **Result:** Success; moved `utils.py` and `ocr.py` to `modules/common/`, added `modules/common/__init__.py`, and rewired all module mains plus driver/validator to import from `modules.common.*` with sys.path hacks removed. Ran `python driver.py --recipe configs/recipes/recipe-text.yaml --dry-run` to confirm command wiring.
- **Notes:** sys.path inserts now absent across modules; dry-run produced expected command chain. AGENTS guide still needs update to reflect new layout; smokes not yet executed for real.
- **Next:** Update AGENTS/README docs, adjust any remaining driver/recipe references if discovered, and run at least the mock/text smokes to validate runtime imports.

### 20251121-1711 — Docs refresh and syntax sanity check
- **Result:** Success; updated `AGENTS.md` and README layout bullet to point at `modules/common` helpers. Ran `python -m compileall modules/common driver.py validate_artifact.py` (ok).
- **Notes:** Remaining work is to run actual smokes (text mock/ocr) to validate runtime behavior without sys.path tweaks.
- **Next:** Execute smoke runs (mock text, OCR subset) and capture results; adjust if any import/runtime issues surface.

### 20251121-1712 — Driver module execution + text smoke
- **Result:** Success; updated `driver.py` to run module entrypoints via `python -m modules.<...>.main`, fixing package resolution without sys.path hacks. Ran `python driver.py --recipe configs/recipes/recipe-text.yaml --mock --force` (pass; artifacts stamped) and `python driver.py --recipe configs/recipes/recipe-ocr.yaml --dry-run` to verify OCR command wiring.
- **Notes:** Imports now resolve under package execution; text mock smoke succeeded end-to-end. OCR smoke not yet executed (Tesseract run pending).
- **Next:** Decide whether to run full OCR smoke (could be slow, needs Tesseract) or defer; if run, confirm artifacts validate without sys.path tweaks.

### 20251121-1719 — OCR smoke attempt timed out
- **Result:** Partial; fixed driver to skip None-valued params when building flags (prevents `--end None`), but full OCR smoke (`python driver.py --recipe configs/recipes/recipe-ocr.yaml --force`) timed out after ~7 minutes while cleaning pages (reached ~25% of 113 pages). Tesseract/OCR stage completed; LLM clean stage is slow.
- **Notes:** End flag bug resolved. OCR run is long due to real LLM cleaning per page; needs higher timeout or use `--mock` to bypass LLM for smoke-level check.
- **Next:** Need decision: run again with longer wall clock (15–25 min) for full LLM clean, or run OCR with `--mock` to validate imports/flow without LLM cost/time.

### 20251121-1752 — OCR mock smoke completed
- **Result:** Success; ran `python driver.py --recipe configs/recipes/recipe-ocr.yaml --mock --force` to validate end-to-end flow with new packaging/imports. All stages ran, artifacts stamped: 113 pages -> final portions under `output/runs/deathtrap-ocr-full/`.
- **Notes:** Mock run confirms driver/module import wiring without sys.path hacks. Full LLM clean remains optional (cost/time).
- **Next:** If desired, schedule full LLM clean with longer timeout; otherwise story can proceed to review.
