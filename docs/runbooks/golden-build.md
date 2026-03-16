# Golden Build Runbook

Operational guide for creating and maintaining golden reference files for evals.

## Golden File Locations

| Eval | Golden Path | Format |
|------|-------------|--------|
| Image crop extraction | `benchmarks/golden/` | JSON bounding boxes per page |

## Creating a New Golden

1. **Run the pipeline** on representative input pages.
2. **Manually verify** each output against the source material.
3. **Save as golden** in the appropriate directory with clear naming.
4. **Register the eval** in `docs/evals/registry.yaml` with target metrics.

## Eval-Driven Golden Improvement

When `/improve-eval` identifies golden-wrong mismatches:

1. **Review the mismatch table** — each item classified as golden-wrong needs fixing.
2. **Apply fixes**:
   - For < 5 changes: edit golden files directly
   - For > 5 changes: write a batch Python script for consistency
3. **Validate** that golden fixture tests still pass.
4. **Re-run the eval** to get verified scores.
5. **Document the delta** in the story work log.

`/improve-eval` now owns both improvement attempts and the old verification
discipline. Raw scores do not count until mismatches are classified and any
golden/scorer corrections are re-measured.

## Quality Standards

- Every golden entry must be manually verified against source material
- Golden files should cover diverse cases (simple pages, multi-illustration, tables, edge cases)
- When adding new test cases, include at least one "tricky" case per category
- Golden changes that affect > 5% of test cases require user approval

## Scoped Fixture Variants

Use masked or cleaned fixture variants only when the eval explicitly scopes some visible source content out of bounds.

- Keep the original source artifact as the primary reference; a masked variant is a benchmark fixture, not a replacement for the real input
- Document exactly what was removed or ignored and why in the owning story/work log
- Use this only for content the eval intentionally excludes, such as illegible marginalia that the golden does not score
- Do not use masking to hide recurring failures on in-scope content or to claim broader pipeline capability than the raw source supports
- When possible, keep both paths obvious in naming so reviewers can inspect raw vs scoped fixtures side by side

## Pitfalls

- **Don't assume golden is always right** — models sometimes find real issues the golden missed
- **Version golden with the code** — golden files are tracked in git, not generated
- **Document golden conventions** — what counts as an illustration vs. decoration, how to handle partial crops, etc.
- **Don't turn benchmark scoping into product policy** — masking or cleaning a fixture may make a specific eval fairer, but it does not reduce the product requirement to handle handwritten or noisy real-world inputs
