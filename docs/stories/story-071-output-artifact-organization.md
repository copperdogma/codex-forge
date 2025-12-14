# Story: Output Artifact Organization

**Status**: Open
**Created**: 2025-12-19
**Parent Story**: story-001 (Establish run layout & manifests - COMPLETE)

---

## Goal

Clean up the output structure of pipeline runs. Currently, artifacts are scattered in a random jumble with a few subfolders, making it difficult to understand what belongs to which module and what are the final pipeline outputs.

**Current Problem**:
- Artifacts are mixed in the root of `output/runs/<run_id>/` alongside subdirectories
- No clear separation between module-specific working artifacts and final pipeline outputs
- Difficult to identify which artifacts belong to which module
- Hard to distinguish intermediate artifacts from final outputs

**Target**: Organized structure where each module has its own working folder, and the main folder contains only final output artifacts or whole-pipeline artifacts.

---

## Success Criteria

- [ ] **Module-specific folders**: Each module has its own working folder for its artifacts
- [ ] **Numbered prefixes**: Subfolders are prefixed with their pipeline order (e.g., `01_`, `02_`) to make execution order obvious
- [ ] **Clean root directory**: Main folder contains only final output artifacts or whole-pipeline artifacts
- [ ] **Clear organization**: Easy to identify which artifacts belong to which module and in what order they run
- [ ] **Backward compatibility**: Existing tools/scripts that reference artifacts continue to work (with migration path)
- [ ] **Documentation**: Updated documentation reflects new structure
- [ ] **Migration**: Existing runs remain accessible (no data loss)

---

## Context

**Current Structure** (example from `output/runs/<run_id>/`):
```
output/runs/<run_id>/
├── adapter_out.jsonl          # Module artifact (root level)
├── pages_raw.jsonl            # Module artifact (root level)
├── pages_clean.jsonl          # Module artifact (root level)
├── window_hypotheses.jsonl    # Module artifact (root level)
├── portions_locked.jsonl      # Module artifact (root level)
├── portions_resolved.jsonl    # Module artifact (root level)
├── portions_enriched.jsonl    # Module artifact (root level)
├── gamebook.json              # Final output (root level)
├── images/                    # Subdirectory
├── ocr_ensemble/              # Subdirectory
├── ocr_ensemble_picked/       # Subdirectory
├── pagelines_final/           # Subdirectory
├── snapshots/                 # Subdirectory
├── pipeline_state.json        # Pipeline metadata (root level)
└── pipeline_events.jsonl     # Pipeline metadata (root level)
```

**Proposed Structure** (suggestion):
```
output/runs/<run_id>/
├── gamebook.json              # Final output (whole-pipeline artifact)
├── pipeline_state.json        # Pipeline metadata
├── pipeline_events.jsonl      # Pipeline metadata
├── snapshots/                 # Recipe/config snapshots
├── modules/
│   ├── 01_extract_ocr_ensemble_v1/
│   │   ├── pages_raw.jsonl
│   │   └── ocr_ensemble/
│   ├── 02_clean_llm_v1/
│   │   └── pages_clean.jsonl
│   ├── 03_portionize_llm_v1/
│   │   └── window_hypotheses.jsonl
│   ├── 04_consensus_v1/
│   │   └── portions_locked.jsonl
│   ├── 05_resolve_v1/
│   │   └── portions_resolved.jsonl
│   ├── 06_enrich_v1/
│   │   └── portions_enriched.jsonl
│   └── 07_adapter_inject_missing_headers_v1/
│       └── adapter_out.jsonl
└── shared/
    └── images/                # Shared across modules
```

**Note**: The numbered prefixes (01_, 02_, etc.) make it immediately obvious what order modules execute in the pipeline, which helps with debugging and understanding the flow.

**Alternative Considerations**:
- Could organize by stage instead of module (e.g., `stages/extract/`, `stages/clean/`)
- Could keep final outputs in root and only organize intermediate artifacts
- Could use symlinks for backward compatibility during transition

**Related Work**:
- Story-001: Established run layout & manifests (initial structure)
- Story-015: Modular pipeline (module system)
- Story-022: Pipeline instrumentation (timing & cost artifacts)

---

## Tasks

### Priority 1: Design & Planning

- [ ] **Analyze current artifact usage**:
  - [ ] Identify all artifacts produced by each module
  - [ ] Map artifacts to their producing modules
  - [ ] Identify which artifacts are final outputs vs intermediate
  - [ ] Document dependencies between artifacts (which modules read which artifacts)

- [ ] **Design new structure**:
  - [ ] Decide on organization scheme (module-based vs stage-based)
  - [ ] Determine execution order for numbered prefixes (01_, 02_, etc.)
  - [ ] Determine what stays in root (final outputs, metadata)
  - [ ] Plan for shared artifacts (images, OCR outputs used by multiple modules)
  - [ ] Consider backward compatibility strategy

- [ ] **Review impact**:
  - [ ] Identify all code that references artifact paths
  - [ ] Check driver.py, modules, validators, dashboards
  - [ ] Plan migration path for existing runs

### Priority 2: Implementation

- [ ] **Update driver.py**:
  - [ ] Modify artifact path generation to use new structure with numbered prefixes
  - [ ] Determine module execution order from DAG to assign correct prefixes
  - [ ] Update `_artifact_name_for_stage()` to include numbered module folder
  - [ ] Ensure `stamp_artifact()` works with new paths
  - [ ] Update state tracking to use new paths

- [ ] **Update modules**:
  - [ ] Update all modules to write artifacts to module-specific folders
  - [ ] Update all modules to read artifacts from new locations
  - [ ] Ensure relative path handling works correctly
  - [ ] Update any hardcoded artifact paths

- [ ] **Update validators & tools**:
  - [ ] Update `validate_artifact.py` to find artifacts in new locations
  - [ ] Update dashboard to read from new structure
  - [ ] Update any scripts that reference artifact paths

### Priority 3: Backward Compatibility & Migration

- [ ] **Backward compatibility**:
  - [ ] Implement path resolution that checks both old and new locations
  - [ ] Or provide migration script to reorganize existing runs
  - [ ] Document transition period

- [ ] **Migration tool** (if needed):
  - [ ] Create script to reorganize existing runs
  - [ ] Preserve all artifacts (no data loss)
  - [ ] Update pipeline_state.json with new paths
  - [ ] Test on sample runs

### Priority 4: Testing & Verification

- [ ] **Test new structure**:
  - [ ] Run full pipeline with new structure
  - [ ] Verify all artifacts are created in correct locations
  - [ ] Verify all modules can read their inputs
  - [ ] Verify final outputs are accessible

- [ ] **Regression testing**:
  - [ ] Run smoke test (20 pages)
  - [ ] Verify no functionality broken
  - [ ] Check dashboard still works
  - [ ] Verify validators still work

- [ ] **Documentation**:
  - [ ] Update README.md with new structure
  - [ ] Update AGENTS.md with new paths
  - [ ] Update any other docs referencing artifact locations
  - [ ] Add migration guide if needed

---

## Implementation Notes

**Key Files to Modify**:
- `driver.py`: Artifact path generation, state tracking
- `modules/*/main.py`: All modules that read/write artifacts
- `validate_artifact.py`: Artifact discovery
- `docs/pipeline-visibility.html`: Dashboard artifact paths
- `README.md`, `AGENTS.md`: Documentation

**Approach**:
1. Design structure and get approval
2. Update driver.py to generate new paths
3. Update modules incrementally (one stage at a time)
4. Test after each stage update
5. Update validators and tools
6. Add backward compatibility or migration
7. Update documentation

**Testing Strategy**:
- Unit tests for path generation
- Integration tests on full pipeline
- Manual artifact inspection (mandatory per AGENTS.md)
- Verify backward compatibility if implemented

**Considerations**:
- Some artifacts are shared across modules (e.g., images, OCR outputs)
- Final outputs (gamebook.json) should be easily accessible
- Pipeline metadata (state, events) should remain in root
- Snapshots should remain in root (they're recipe/config, not module artifacts)

---

## Work Log

### 2025-12-19 — Story created
- **Context**: User identified that output runs have artifacts scattered in root directory mixed with subdirectories, making it hard to understand organization
- **Action**: Created story document to track cleanup of output artifact organization
- **Scope**: Reorganize artifacts so each module has its own working folder (with numbered prefixes like 01_, 02_ to show pipeline order), with main folder containing only final outputs or whole-pipeline artifacts
- **Next**: Analyze current artifact usage and design new structure
