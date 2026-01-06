# Story: Make output/ Canonical Location for gamebook.json

**Status**: To Do

**Summary**: Eliminate duplication of `gamebook.json` files by making `output/` the single canonical location. Currently, `gamebook.json` exists in both the run root (with broken image paths) and `output/` (working). This story consolidates to a single source of truth in `output/`.

---

## Problem Statement

Currently, the pipeline creates two `gamebook.json` files:

1. **Run root**: `output/runs/{run_id}/gamebook.json`
   - Created by `clean_presentation` stage (marked as "final output")
   - Has image paths like `images/page-XXX.png`
   - **Problem**: No `images/` folder in run root, so paths are broken

2. **Output folder**: `output/runs/{run_id}/output/gamebook.json`
   - Created by `package_game_ready` stage (copy from `apply_edgecase_patches`)
   - Has same image paths
   - **Works**: `images/` folder exists in `output/`, so paths resolve correctly

### Current Pipeline Flow

```
associate_illustrations (transform)
  → writes: 26_associate_illustrations_to_sections_v1/gamebook_with_images.json
  → copies images to: 26_associate_illustrations_to_sections_v1/images/
  → (tries to copy to run root, but fails)

clean_presentation (export)
  → reads: associate_illustrations output
  → writes: run_root/gamebook.json (FINAL OUTPUT)
  → preserves images field ✅

apply_edgecase_patches (export)
  → reads: clean_presentation (run root gamebook.json)
  → writes: module_folder/gamebook_patched.json

package_game_ready (export)
  → reads: apply_edgecase_patches
  → copies to: output/gamebook.json
  → copies images to: output/images/
```

### Root Cause

The `associate_illustrations_to_sections_v1` module attempts to copy images to run root (lines 205-223), but:
- It writes `gamebook_with_images.json` to module folder
- It copies images to module folder successfully
- It tries to also copy to run root, but the run_dir detection logic may be failing
- Result: Images only exist in module folder and `output/`, not run root

## Goals

1. **Single canonical location**: `output/gamebook.json` is the only `gamebook.json` file
2. **No broken paths**: Image paths in `gamebook.json` resolve correctly
3. **Clean architecture**: Final outputs go to `output/`, intermediate artifacts in module folders
4. **No duplication**: Remove redundant `gamebook.json` from run root

## Solution: Option 2 + 3 Combined

### Proposed Flow

```
associate_illustrations (transform)
  → writes: 26_associate_illustrations_to_sections_v1/gamebook_with_images.json
  → copies images to: output/images/ (not run root)

clean_presentation (export)
  → reads: associate_illustrations output
  → writes: output/gamebook.json (FINAL OUTPUT, not run root)
  → preserves images field ✅

apply_edgecase_patches (export)
  → reads: clean_presentation (output/gamebook.json)
  → writes: module_folder/gamebook_patched.json

package_game_ready (export)
  → reads: apply_edgecase_patches
  → copies to: output/gamebook.json (overwrites clean_presentation version)
  → copies images to: output/images/ (already there, but ensures completeness)
  → Result: output/gamebook.json is the final patched version
```

### Key Changes

1. **Driver**: Write final outputs to `output/` instead of run root
2. **Driver**: Create `output/` directory early (in setup)
3. **associate_illustrations**: Copy images to `output/images/` instead of run root
4. **apply_edgecase_patches**: Update fallback logic to check `output/gamebook.json` instead of run root
5. **Tests**: Update any tests that expect run root `gamebook.json`

## Implementation Plan

### Phase 1: Driver Changes

**File**: `driver.py`

1. **Modify final output detection** (line ~554):
   - Keep detection of `gamebook.json` and `validation_report.json` as final outputs
   - Change path resolution to write to `output/` instead of run root

2. **Create output/ directory early**:
   - In `main()` function, after `run_dir` is determined
   - Create `output_dir = os.path.join(run_dir, "output")` and ensure it exists
   - Pass `output_dir` to `build_command` or make it available globally

3. **Update artifact path resolution** (line ~556-558):
   ```python
   if is_final_output:
       # Final outputs go to output/ directory
       output_dir = os.path.join(run_dir, "output")
       ensure_dir(output_dir)
       artifact_path = os.path.join(output_dir, artifact_name)
   ```

4. **Update dry-run path resolution** (line ~1793-1795):
   - Same change: final outputs to `output/` instead of run root

### Phase 2: Module Updates

**File**: `modules/transform/associate_illustrations_to_sections_v1/main.py`

1. **Update image copying logic** (lines 205-223):
   - Instead of copying to run root, copy to `output/images/`
   - Find `output/` directory relative to run root
   - Ensure `output/images/` exists before copying

2. **Simplified logic**:
   ```python
   # Copy images to output/images/ directory
   if copy_images:
       run_dir = _find_run_dir(output_path)  # Existing logic
       output_dir = os.path.join(run_dir, "output")
       images_output_dir = os.path.join(output_dir, image_base_path)
       ensure_dir(images_output_dir)
       # ... rest of copying logic
   ```

**File**: `modules/export/apply_edgecase_patches_v1/main.py`

1. **Update fallback logic** (lines 146-150):
   - Change fallback to check `output/gamebook.json` instead of run root
   ```python
   if not isinstance(gamebook, dict) or "sections" not in gamebook:
       run_dir = os.path.abspath(os.path.join(os.path.dirname(args.out), ".."))
       # Check output/ first, then run root as secondary fallback
       fallback = os.path.join(run_dir, "output", "gamebook.json")
       if not os.path.exists(fallback):
           fallback = os.path.join(run_dir, "gamebook.json")  # Legacy fallback
       if os.path.exists(fallback):
           with open(fallback, "r", encoding="utf-8") as f:
               gamebook = json.load(f)
   ```

### Phase 3: Test Updates

**File**: `tests/test_integration_combat_outcomes.py`

1. **Update gamebook path** (line ~12):
   ```python
   candidate = os.path.join("output", "runs", run_id, "output", "gamebook.json")
   ```

**Search for other consumers**:
- Grep for `gamebook.json` references that expect run root
- Update any scripts, tools, or documentation that reference run root `gamebook.json`

### Phase 4: Validation

1. **Run full pipeline**:
   - Verify `output/gamebook.json` is created correctly
   - Verify no `gamebook.json` in run root
   - Verify image paths resolve correctly
   - Verify `apply_edgecase_patches` reads from `output/gamebook.json`

2. **Test fallback logic**:
   - Verify `apply_edgecase_patches` fallback works if input is invalid

3. **Test image copying**:
   - Verify images are copied to `output/images/` by `associate_illustrations`
   - Verify `package_game_ready` doesn't duplicate images unnecessarily

## Design Decisions

### Why output/ is canonical

1. **Already the distribution target**: `package_game_ready` copies everything to `output/` for engine consumption
2. **Self-contained**: All artifacts (gamebook, images, validator) in one place
3. **Clear separation**: Intermediate artifacts in module folders, final artifacts in `output/`
4. **No broken paths**: Images and gamebook in same directory structure

### Why clean_presentation writes to output/

- It's marked as a "final output" in driver logic
- Keeps the pattern: final outputs → `output/`
- `package_game_ready` still has a role (copying validator, ensuring completeness)
- Overwriting is intentional: patched version replaces cleaned version

### Why not keep both locations

- Duplication is confusing
- Run root version has broken paths
- No clear use case for run root version
- Single source of truth is cleaner

## Risks and Mitigations

### Risk 1: Breaking existing scripts/tools
- **Mitigation**: Search codebase for all `gamebook.json` references
- **Mitigation**: Update fallback logic in `apply_edgecase_patches` to check both locations (temporary)

### Risk 2: output/ directory doesn't exist early enough
- **Mitigation**: Create `output/` in driver setup, before any stages run
- **Mitigation**: Ensure `associate_illustrations` creates `output/images/` if needed

### Risk 3: Image paths break if images aren't copied correctly
- **Mitigation**: Verify `associate_illustrations` copies to `output/images/`
- **Mitigation**: Test end-to-end pipeline with images

### Risk 4: package_game_ready overwrites clean_presentation output
- **Mitigation**: This is intentional - patched version should replace cleaned version
- **Mitigation**: Document this behavior clearly

## Success Criteria

- [ ] `output/gamebook.json` is the only `gamebook.json` file (no run root version)
- [ ] Image paths in `gamebook.json` resolve correctly (`images/page-XXX.png` works)
- [ ] All pipeline stages read/write from correct locations
- [ ] Tests pass with updated paths
- [ ] No broken references to run root `gamebook.json`
- [ ] Documentation updated if needed

## Related Stories

- **Story 024**: Image cropper follow-up (introduced image association)
- **Story 108**: Game-Ready Output Package (established `output/` structure)

## Notes

- This is a refactoring story focused on architecture cleanup
- Low risk if implemented carefully with thorough testing
- Improves maintainability and reduces confusion
- Sets up cleaner structure for future enhancements
