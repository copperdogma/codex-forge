## [2025-11-21] - Pluginized modules and validated pipelines

### Added
- Moved all pipeline modules into self-contained plugin folders under `modules/<stage>/<module_id>/` with `module.yaml` manifests.
- Updated driver to scan plugin folders, merge defaults, and run modules from their encapsulated paths.
- Added stories 016–018 to track DAG/schema, module UX, and enrichment/alt modules.

### Tested
- `python driver.py --recipe configs/recipes/recipe-text.yaml --force` (passes; stamps/validates).
- `python driver.py --recipe configs/recipes/recipe-ocr-1-20.yaml --skip-done` (passes; stamps/validates).

## [2025-11-21] - Added modular pipeline story

### Added
- New story 015 document outlining modular pipeline and registry plan.
- Indexed story 015 in `docs/stories.md` to track status.
- Scaffolded `modules/registry.yaml`, sample recipes under `configs/recipes/`, `extract_text.py` stub, and `validate_artifact.py` validator CLI.
- Added pipeline driver with stamping/validation hooks and resume/skip toggles; added schemas for page/clean/resolved/enriched artifacts.
- Reorganized modules into per-module plugin folders with manifests; driver now scans `modules/` for entrypoints.
