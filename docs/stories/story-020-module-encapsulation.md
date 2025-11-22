# Story: Module encapsulation & shared common

**Status**: To Do

---

## Acceptance Criteria
- Shared utilities (e.g., utils, ocr) are provided via a common package/module under `modules/common` (or equivalent), with no sys.path bootstraps in module mains.
- Modules import shared code from the common package; no direct repo-root imports remain in module code.
- Driver runs existing recipes without requiring PYTHONPATH tweaks; CI smoke passes.
- Legacy helper duplication is removed or redirected to the common package.

## Tasks
- [ ] Create `modules/common` package and move/shared utilities (utils, ocr helpers) there; expose clean import paths.
- [ ] Update module entrypoints to import from the common package; remove sys.path mutation from module mains.
- [ ] Adjust driver/recipes if needed for new package layout; ensure stamping/validation unaffected.
- [ ] Update AGENTS/README to reflect common package usage.
- [ ] Run existing smokes (text mock CI, local text/OCR samples) to verify no regressions.

## Notes
- Keep backward compatibility with current artifacts; focus on imports/packaging only.
- Consider adding a `modules/common/__init__.py` for clear public surface.

## Work Log
- Pending
