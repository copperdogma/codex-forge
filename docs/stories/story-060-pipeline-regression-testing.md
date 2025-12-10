# Story: Pipeline Regression Testing Suite

**Status**: Open  
**Created**: 2025-12-09  
**Parent Story**: story-054 (canonical recipe - COMPLETE)

## Goal
Establish a comprehensive test suite using the 20-page set (pages 1-20 from Deathtrap Dungeon) as the standard test input to prevent regressions when modifying the pipeline. Catch integration breakages early and ensure pipeline changes don't break one thing while fixing another.

## Success Criteria
- [ ] 20-page test suite created and integrated with existing test infrastructure
- [ ] Test fixtures/golden files established for the 20-page set
- [ ] Tests cover OCR quality, section detection, text reconstruction, and element extraction
- [ ] Regression tests run before/after pipeline changes
- [ ] Tests are fast enough to run frequently (< 5 minutes for 20 pages)
- [ ] Tests integrated into CI or easily runnable locally

## Context

**Current State**:
- Smoke test exists (`story-053-smoke-test-pipeline.md`) but uses different test set (`testdata/tbotb-mini.pdf`)
- Existing test infrastructure: `tests/` directory with `unittest`-based tests (e.g., `driver_integration_test.py`)
- No automated tests using the 20-page set
- Pipeline changes risk breaking one thing while fixing another
- **Note**: Pipelines are distinct (OCR ensemble vs. text intake vs. sectionizing) but share fundamental components

**Problem**:
- We keep modifying the pipeline and risk breaking one thing to fix another
- No automated way to detect regressions
- Manual inspection of artifacts is time-consuming and error-prone
- Need baseline to compare against when making changes

**Solution**:
- Use pages 1-20 from `input/06 deathtrap dungeon.pdf` as standard test input
- Create golden files (expected outputs) for all key artifacts
- Run tests before/after any pipeline changes
- Compare outputs to golden files and flag regressions

## Tasks

### High Priority

- [ ] **Create 20-Page Test Suite**
  - Use pages 1-20 from `input/06 deathtrap dungeon.pdf` as standard test input
  - Create test fixtures/expected outputs for the 20-page set
  - Document expected artifacts (pagelines, elements, section boundaries, etc.)
  - Add to CI or make easily runnable locally
  - **Location**: Add to `tests/` directory, follow existing `unittest` pattern
  - **Baseline**: Use current `ff-canonical-full-20-test` run as initial baseline

- [ ] **Test Coverage - OCR Quality**
  - No fragmentation (page 018L should not be split into columns)
  - Correct column detection (pages 7-10, 12-13 should have columns; page 018L should not)
  - No obvious OCR errors (no "sxrLL", "otk", "ha them", "decic" in output)
  - Escalation logic works (pages with high disagree_rate are escalated)
  - Column quality check rejects bad splits (page 008L should not be fragmented)
  - Adventure Sheet forms handled correctly (page 011R should not be split into columns)

- [ ] **Test Coverage - Section Detection**
  - Expected sections found (at minimum: sections 1, 2, 7, 12 should be detected)
  - Boundaries have required fields (page, start_element_id populated)
  - Section numbers extracted correctly (no "in 4" instead of "4")
  - Section coverage validation (check if expected number of sections found)

- [ ] **Test Coverage - Text Reconstruction**
  - Lines merged correctly (no huge jumbled lines >500 chars)
  - Hyphen handling works ("twentymetre" not "twenty metre")
  - Fragmented text guard works (prevents merging extremely fragmented text)
  - Text is readable and coherent

- [ ] **Test Coverage - Element Extraction**
  - Reasonable element count per page (not too few, not too many)
  - Elements have required metadata (_codex fields populated)
  - Element text quality is acceptable

### Medium Priority

- [ ] **Regression Testing Infrastructure**
  - Run tests before/after any pipeline changes
  - Compare outputs to expected fixtures (golden files)
  - Flag any regressions (missing sections, OCR errors, fragmentation, etc.)
  - Document known issues vs. new regressions
  - **Baseline**: Use current `ff-canonical-full-20-test` run as initial baseline

- [ ] **Integration with Existing Tests**
  - Extend existing `unittest` infrastructure in `tests/` directory
  - Consider if smoke test (`story-053`) should also use 20-page set or keep separate
  - Ensure tests are fast enough to run frequently (< 5 minutes for 20 pages)
  - **Pattern**: Follow `driver_integration_test.py` pattern (unittest.TestCase, temp directories)

- [ ] **Test Artifacts & Fixtures**
  - Create `testdata/ff-20-pages/` directory for fixtures
  - Store expected outputs (pagelines, elements, boundaries) as golden files
  - Document how to regenerate golden files when expected behavior changes
  - Version control golden files (commit to git)
  - Include quality reports, escalation logs, and other diagnostic artifacts

- [ ] **Test Execution & Reporting**
  - Make tests easily runnable locally (simple command)
  - Add to CI pipeline (if applicable)
  - Generate test reports showing pass/fail status
  - Show diffs when tests fail (what changed from golden files)
  - Track test execution time

### Low Priority

- [ ] **Test Maintenance**
  - Document how to update golden files when expected behavior legitimately changes
  - Add test for test infrastructure itself (meta-tests)
  - Consider pytest for better assertion messages and fixtures
  - Add test coverage reporting

- [ ] **Extended Test Coverage**
  - Test edge cases (blank pages, illustration-only pages, form pages)
  - Test error handling (what happens when OCR fails, when LLM times out, etc.)
  - Test pipeline resume functionality
  - Test with different settings/configurations

## Implementation Details

**Test Structure**:
- Follow existing `tests/driver_integration_test.py` pattern
- Use `unittest.TestCase` with temporary directories
- Test full pipeline run: `python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --start 1 --end 20`
- Compare outputs to golden files in `testdata/ff-20-pages/`

**Golden Files**:
- `testdata/ff-20-pages/pagelines_final.jsonl` - Expected OCR output
- `testdata/ff-20-pages/pagelines_reconstructed.jsonl` - Expected reconstructed text
- `testdata/ff-20-pages/elements_core.jsonl` - Expected elements
- `testdata/ff-20-pages/section_boundaries_scan.jsonl` - Expected section boundaries
- `testdata/ff-20-pages/ocr_quality_report.json` - Expected quality metrics
- `testdata/ff-20-pages/README.md` - Documentation on golden files

**Test Assertions**:
- File existence checks
- Schema validation (use `validate_artifact.py`)
- Content comparison (line-by-line for JSONL, key-value for JSON)
- Quality metric checks (fragmentation_score, corruption_score, etc.)
- Count checks (element count, section count, etc.)

**Test Execution**:
```bash
# Run 20-page regression tests
python -m pytest tests/test_ff_20_page_regression.py -v

# Or using unittest
python -m unittest tests.test_ff_20_page_regression -v
```

## Related Work

**Previous Work**:
- Story-053: Smoke test pipeline (uses different test set)
- Story-054: Canonical recipe (provides pipeline to test)
- Story-057: OCR quality improvements (affects test expectations)
- Story-058: Post-OCR text quality (affects test expectations)
- Story-059: Section detection improvements (affects test expectations)

**Baseline Run**:
- Run ID: `ff-canonical-full-20-test`
- Output directory: `output/runs/ff-canonical/`
- This run serves as the initial baseline for golden files

## Work Log

### 2025-12-09 — Story created from story-054
- **Context**: Story-054 (canonical recipe) is complete. Testing requirements were identified as critical for preventing regressions.
- **Action**: Extracted testing requirements from story-054 into this focused story.
- **Scope**: Focus on creating comprehensive 20-page test suite with golden files, test coverage for all pipeline stages, and regression testing infrastructure.
- **Priority**: **TOP PRIORITY** - We keep modifying the pipeline and risk breaking one thing to fix another. A test suite will catch regressions early.
- **Next**: Create test infrastructure, establish golden files from baseline run, implement test assertions, integrate with CI/local testing.

