# FF 20-page Golden Fixtures

Baseline run for this suite: `ff-canonical-full-20-test` (recipe `configs/recipes/recipe-ff-canonical.yaml`, pages 1-20 of `input/06 deathtrap dungeon.pdf`).

Expected golden artifacts to store in this directory (all JSON/JSONL UTF-8, newline terminated):
- `pagelines_final.jsonl`
- `pagelines_reconstructed.jsonl`
- `elements_core.jsonl`
- `section_boundaries_scan.jsonl`
- `ocr_quality_report.json`

Regeneration playbook:
1) Run the canonical recipe on pages 1-20 with a fresh run id, e.g.:
   ```
   python driver.py --recipe configs/recipes/recipe-ff-canonical.yaml --start 1 --end 20 --run-id ff-canonical-full-20-test --output-dir output/runs/ff-canonical
   ```
2) Inspect the resulting artifacts under `output/runs/ff-canonical/` for data quality (spot-check pages, section coverage, OCR quality).
3) Copy the vetted artifacts into this directory with the filenames above.
4) Commit the golden files alongside this README so regression tests can execute offline.

Notes:
- Keep artifacts append-only; never edit in place. If expectations change, regenerate all artifacts and replace as a new commit.
- If a deliberate behavior change modifies expected outputs, update the golden files and include a note in the story work log describing the change.
- Fast regression check (counts + schema + fingerprints): `scripts/tests/run_ff20_regression_fast.sh`
- Full rerun comparison (slow, requires API access): `FF20_RUN_PIPELINE=1 scripts/tests/run_ff20_regression_fast.sh`
