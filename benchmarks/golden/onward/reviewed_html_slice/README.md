# Onward Reviewed HTML Slice Goldens

This directory holds committed run-backed Onward golden slices.

These files are different from the older eval fixtures in
`benchmarks/golden/onward/`:

- The older top-level files like `alma.html`, `arthur.html`, and
  `marie_louise.html` are hand-shaped eval fixtures.
- The files in `reviewed_html_slice/` are exact copies of blessed pipeline
  outputs from a specific run.

Current blessed slice:

- Run: `story149-onward-build-regression-r1`
- Scope: `onward_genealogy_reviewed_html_slice`
- Trust level: `known_good` for the reviewed genealogy hard-case HTML slice
- Full-run caveat: generic `html` is still only `partial`, because this review
  did not repeat exhaustive cell-by-cell table-value verification across the
  whole run

The current blessed run folder is:

- `story149-onward-build-regression-r1/`

That folder contains:

- the exact reviewed chapter HTML artifacts
- the supporting chapter manifest and genealogy consistency report
- a machine-readable manifest tying the committed files back to the run
  registry blessing

Use this directory when you want a committed, diffable baseline for the
reviewed Onward genealogy HTML slice rather than a promptfoo eval fixture.
