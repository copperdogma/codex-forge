# Story 123: Patch File Support for Manual Corrections

## Status: Draft

## Problem

Some gamebook issues cannot be reliably solved by automated systems:

1. **Contextual puzzles** - Section 17 in Robot Commando asks "what you might find in this building" with no explicit item name. Requires narrative context that keyword filtering can't provide.

2. **Cut content** - Section 338 has no incoming links in the original book. No automated fix possible.

3. **Complex calculations** - Some puzzles reference items in ways that require human understanding of game flow.

Trying to solve every edge case with AI is both expensive and unreliable. We need a way to apply human-verified corrections.

## Solution: Patch Files

A patch file sits beside the input PDF and contains manual corrections that the pipeline applies automatically.

### File Location Convention

```
input/
  robot-commando.pdf
  robot-commando.patch.json    ← optional, human-created
```

The patch file has the same name as the PDF with `.patch.json` suffix.

### Pipeline Behavior

**Critical**: Patch handling must be in the pipeline harness, NOT per-module responsibility. If left to individual modules, programmers will forget and introduce bugs.

1. **On every run start/continue** (even partial re-runs):
   - Check for `{book_name}.patch.json` beside the input PDF
   - Copy it into `output/runs/{run_id}/patch.json`
   - This ensures patches are captured as run artifacts

2. **Before and after EVERY module**:
   - Check if any patches should be applied at this point
   - Apply relevant patches to gamebook.json (or other artifacts)
   - Log what was applied

### Patch File Schema

```json
{
  "book_id": "ff-robot-commando",
  "schema_version": "patch_v1",
  "patches": [
    {
      "id": "section-17-cloak-puzzle",
      "apply_after": "resolve_calculation_puzzles_v1",
      "operation": "add_link",
      "target_file": "gamebook.json",
      "section": "17",
      "link": {
        "kind": "item_check",
        "item": "Cloak of Invisibility",
        "has": {"targetSection": "53"},
        "metadata": {
          "patchApplied": true,
          "patchId": "section-17-cloak-puzzle"
        }
      },
      "reason": "Section 17 asks 'what you might find in this building' - contextually the Cloak of Invisibility, Model 3. Calculation: 3 + 50 = 53"
    },
    {
      "id": "section-338-expected-orphan",
      "apply_after": "validate_ff_engine_v2",
      "operation": "suppress_warning",
      "warning_pattern": "section \"338\" is unreachable",
      "reason": "Cut content - no incoming links exist in original book"
    }
  ]
}
```

### Supported Operations

| Operation | Description |
|-----------|-------------|
| `add_link` | Add a choice/item_check to a section's sequence |
| `remove_link` | Remove a link from a section's sequence |
| `override_field` | Override a specific field in a section |
| `suppress_warning` | Mark a validation warning as expected/known |
| `add_section` | Add an entirely new section (rare) |

### Implementation Approach

#### Option A: Harness-Level Integration (Recommended)

Modify the pipeline runner (`driver.py` or equivalent) to:

1. **At run start**: Copy patch file into run directory
2. **Wrap each module execution**:
   ```python
   def run_module(module_id, ...):
       apply_patches_before(module_id)
       result = module.main(...)
       apply_patches_after(module_id)
       return result
   ```

This keeps patch logic centralized and invisible to module authors.

#### Option B: Dedicated Module with Frequent Insertion

Create `apply_patches_v1` module and insert it at multiple points in the recipe:
- After each enrichment module
- Before validation

**Downside**: Recipe becomes cluttered; easy to forget insertions.

### Patch Application Logic

```python
def apply_patches_after(module_id: str, run_dir: str):
    patch_file = os.path.join(run_dir, "patch.json")
    if not os.path.exists(patch_file):
        return

    patches = load_patches(patch_file)
    for patch in patches:
        if patch.get("apply_after") == module_id:
            apply_patch(patch, run_dir)
            log_patch_applied(patch)
```

### Validation Integration

The validation report should distinguish between:
- **Actual issues** - Problems found in the gamebook
- **Suppressed issues** - Known issues marked as expected via patches

```json
{
  "unreachable_sections": ["7", "22", "53", "111", "338"],
  "suppressed_unreachable": ["338"],
  "effective_unreachable": ["7", "22", "53", "111"]
}
```

### Workflow

1. Run pipeline on new book
2. Validation reports issues (e.g., 5 unreachable sections)
3. Human/AI investigates each issue
4. For issues that can't be auto-fixed:
   - Determine correct fix manually
   - Add patch to `{book}.patch.json`
5. Re-run pipeline (or just affected modules)
6. Patches applied automatically
7. Validation now shows fewer issues (or suppressed warnings)

## Acceptance Criteria

- [ ] Pipeline harness copies patch file into run directory on every run start
- [ ] Patches are applied before/after modules as specified
- [ ] `add_link` operation works correctly
- [ ] `suppress_warning` operation works correctly
- [ ] Patch application is logged
- [ ] Validation report distinguishes suppressed vs actual issues
- [ ] Patches have metadata marking them as patch-applied (for traceability)

## Future Considerations

- **Patch validation**: Warn if a patch references a non-existent section
- **Patch staleness**: Detect if patches no longer apply (e.g., section was fixed upstream)
- **Patch UI**: Dashboard view to manage patches for a book
- **Patch generation**: AI suggests patches for unresolved issues

## Related Stories

- Story 121: Robot Commando Unreachable Sections Investigation (discovered need for patches)
- Story 110: Edgecase Scanner and Patch Module (earlier related work)
