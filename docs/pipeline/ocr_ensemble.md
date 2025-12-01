# OCR Ensemble, Escalation, and Resolver

## Resolver defaults (env overrides)

- `RESOLVER_OUTDIR` (default: `output/runs/ocr-ensemble-better-gpt4v-iter-r5`)
- `RESOLVER_MODEL` (default: `gpt-4.1`)
- `RESOLVER_MAX_PAGES` (default: `40`)
- `RESOLVER_BATCH_SIZE` (default: `25`)

These map to the resolver params block in `configs/recipes/recipe-pagelines-two-pass.yaml` and are expanded if provided as `${VAR}`.

## How the resolver works
1) Reads detected headers, finds missing IDs.
2) Skips known-absent IDs (currently 169–170 for this PDF).
3) Infers candidate pages from neighboring detected headers.
4) If candidates exist, runs `escalate_gpt4v_iter_v1` on those pages, re-cleans pagelines, and reruns numeric headers (fuzzy on) writing back to the headers file.
5) Emits `missing_header_report.json` into the resolver outdir with counts and candidate pages.

## Running
The resolver runs inside the pagelines-two-pass recipe. Override defaults by exporting env vars before running:

```bash
export RESOLVER_OUTDIR=output/runs/ocr-ensemble-better-gpt4v-iter-rX
export RESOLVER_MODEL=gpt-4.1
export RESOLVER_MAX_PAGES=30
export RESOLVER_BATCH_SIZE=15
python driver.py --recipe configs/recipes/recipe-pagelines-two-pass.yaml
```

## Spot check note
In run r5, section 272 was recovered post-escalation; final coverage 398/400 with 169–170 absent from source PDF.

