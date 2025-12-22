# Story: Large-Image PDF Cost Optimization

**Status**: Done  
**Created**: 2025-12-22  
**Priority**: High  
**Parent Story**: story-081 (GPT-5.1 AI-First OCR Pipeline)

---

## Resume Notes (20251222)

**Why paused:** Need to implement table-rescue OCR and HTML-preservation stories before finishing downscale policy decisions.

**What’s done:**
- Baseline size audit (MediaBox @ 300 DPI): old pages ~5.47 MP; pristine pages ~180 MP (~33× larger per split page).
- Rendered pristine sample pages (1–3) at 300 DPI using `Image.MAX_IMAGE_PIXELS=None` to bypass Pillow decompression-bomb guard.
- Drafted DPI sweep plan (200/150/120/100 DPI).
- Downsampled pristine mapped pages to old benchmark sizes and ran GPT‑5.1 OCR; 9-page diff summary avg_text_ratio 0.971 (strong text fidelity).
- Found table collapse for **page‑061** at both 300 and 150 DPI; prompt tweaks (FF hints + table hints) did not fix.
- Verified **page‑020R** tables are preserved at 150/300 DPI (collapse only when downscaled to old size).

**Key paths:**
- Old benchmark images: `output/runs/ff-canonical-dual-full-20251219p/01_extract_ocr_ensemble_v1/images/`
- Pristine full images: `input/pristine_full_images/` (extracted by user; large JPEGs, 10k×17k)
- Mapping file: `input/pristine_bench_mapping.json`
- Downsampled bench set: `input/pristine_bench_downsampled/`
- OCR outputs (downsampled bench): `testdata/ocr-bench/ai-ocr-simplification/gpt5_1-pristine-downsampled/`
- Diff summary: `testdata/ocr-bench/ai-ocr-simplification/gpt5_1-pristine-downsampled/diffs-pristine-mapped/diff_summary.json`
- Page‑020R test (full size): `/tmp/ocr_pristine_020R_300_diffs/` and `/tmp/ocr_pristine_020R_150_diffs/`
- Table-heavy tests (full size): `/tmp/ocr_pristine_tables_300/` and `/tmp/ocr_pristine_tables_150/`

**Resume after stories 085 + 086:**
1) Implement table-rescue OCR pass (story‑085) and HTML preservation (story‑086).
2) Re-run table-heavy samples (including page‑061) at 150 DPI with rescue enabled.
3) Decide final downscale policy and record in this story.

---

## Goal

Control OCR cost for high-resolution PDFs by validating image sizes and defining a downscale policy that preserves OCR quality while minimizing token cost.

---

## Assumptions to Validate

- OCR cost scales with image size (pixels/tokens), so very large page images can be disproportionately expensive.
- The pristine PDF likely has larger page images than the legacy scan.

---

## Success Criteria

- [x] **Image size audit**: Baseline old vs pristine PDFs with exact page dimensions (px) and file sizes.
- [x] **Cost sensitivity**: Estimate cost impact at multiple resolutions (e.g., 100%, 75%, 50%, 35%).
- [x] **Optimal DPI target**: Determine minimum DPI (or max MP) that preserves section headers + choice tables with GPT‑5.1.
- [x] **Downscale policy**: Define target max dimension and/or max megapixels per page for OCR input.
- [x] **Quality check**: Verify OCR quality on a representative sample at chosen downscale (no loss in section headers and choice text).
- [x] **Configurable**: Policy is configurable via recipe/settings (not hard-coded).
- [x] **Auto DPI chooser**: Estimate target render DPI from sampled pages using pixel line-height (x-height proxy). DPI is a derived knob, not the target.
- [x] **Optional caps**: Allow optional caps (max DPI, max megapixels) but keep them **off by default**.
- [x] **X-height quality sweep**: Run OCR across multiple target line-heights for both old and pristine PDFs to find the lowest acceptable x-height.
- [x] **Max-available extraction**: Early pipeline stage extracts page images at the highest available DPI subject to the chosen x-height target and optional caps; proceed to split detection on those images.

---

## Tasks

- [x] Inventory page image sizes for **old** and **pristine** PDFs (min/median/max; include example page IDs).
- [x] Ensure large-image rendering works safely (Pillow decompression-bomb guard) for pristine PDFs.
- [x] Define a resolution sweep plan and estimate cost per page at each resolution.
- [x] Build a **downsampled benchmark set**: resize pristine pages to match old benchmark dimensions and run OCR bench diff.
- [x] Establish **page mapping** between old benchmark pages and pristine pages (manual or OCR-based), then re-run downsampled benchmark.
- [x] Run OCR on a small, representative page set at multiple resolutions; compare against gold outputs.
- [x] Determine **minimum viable DPI** for GPT‑5.1 that preserves headers + tables (document evidence).
- [x] Choose a default downscale policy with justification (quality vs cost) and document it.
- [x] Add settings/recipe knobs to control downscale behavior.
- [x] Document findings and decision in the story work log with evidence.
- [x] Add a **line-height based DPI chooser** that samples pages across the PDF, computes a target DPI, and feeds the capped extractor.
- [x] Add a pre-split **max-available extraction module**: extract page images at max available DPI guided by x-height target, then feed split detection.
- [x] Add **optional caps** (max DPI / max megapixels) with defaults off.
- [x] Run OCR bench at multiple target x-heights for both PDFs and record quality deltas.

---

## Findings (Draft)

### 2025-12-22 — PDF page size audit at 300 DPI (from MediaBox)

**Old PDF**: `input/06 deathtrap dungeon.pdf` (113 pages)
- Width px: min 2484, median 2548, max 2700
- Height px: min 2096, median 2144, max 2182
- Page megapixels: min 5.34, median 5.47, max 5.77
- **Split-page median** (half width): ~2.73 MP
- Rendered file sizes (PNG, 300 DPI): min ~35 KB, median ~972 KB, max ~1.68 MB

**Pristine PDF**: `input/deathtrapdungeon00ian_jn9_1 - from internet archive.pdf` (228 pages)
- Width px: min 9858, median 10387.5, max 10962.5
- Height px: min 17254.2, median 17341.7, max 17745.8
- Page megapixels: min 170.10, median 180.14, max 190.11
- **Split-page median** (half width): ~90.07 MP

**Note:** These values are derived from PDF page dimensions (MediaBox) at 300 DPI; not from rendered PNGs. A PyPDF2 warning about an incorrect startxref pointer appears but page sizes were still readable.

### 2025-12-22 — Pristine render sample (pages 1–3 @ 300 DPI)

Rendered with `Image.MAX_IMAGE_PIXELS=None` to bypass Pillow decompression bomb checks.
- Sample sizes: 180–188 MP per page
- File sizes: ~6.0 MB (min), ~11.9 MB (median), ~17.7 MB (max)

**Note:** `split_pages_v1` (pdf2image → PIL) currently raises `DecompressionBombError` on pristine pages without this override.

### Draft resolution sweep plan (pristine PDF)

Assume cost scales ~linearly with pixel count. Use DPI as the primary knob (render-time downscale):
- 300 DPI (baseline): ~180 MP/page (median)
- 200 DPI: ~80 MP/page
- 150 DPI: ~45 MP/page
- 120 DPI: ~29 MP/page
- 100 DPI: ~20 MP/page
- 80 DPI: ~13 MP/page

Plan: run OCR on a representative sample at 200/150/120/100 DPI and compare section headers + choice text accuracy vs 300 DPI.

---

## Work Log

### 20251222-0900 — Story created
- **Result:** Success.
- **Notes:** New requirement for large-image PDFs: validate image sizes, measure cost sensitivity, and define a downscale policy that preserves OCR quality.
- **Next:** Audit old vs pristine PDF image sizes and record baseline metrics.

### 20251222-0915 — Baseline size audit via PDF MediaBox
- **Result:** Partial success.
- **Notes:** Computed old vs pristine page sizes at 300 DPI from PDF MediaBox. Pristine pages are ~90 MP per split page vs ~2.7 MP in old scan (≈33× larger). Did not render full pristine images (process killed) and file sizes still pending.
- **Next:** Capture pristine rendered file sizes on a small sample; define downscale sweep targets.

### 20251222-0930 — Rendered pristine sample pages with Pillow override
- **Result:** Partial success.
- **Notes:** Rendered pages 1–3 at 300 DPI by setting `Image.MAX_IMAGE_PIXELS=None`. Sample files are ~6–18 MB at ~180–188 MP per page. `split_pages_v1` fails without this override due to `DecompressionBombError`.
- **Next:** Decide whether to adjust the pipeline to explicitly handle large-image PDFs, and define downscale sweep targets.

### 20251222-0940 — Drafted DPI sweep plan
- **Result:** Success.
- **Notes:** Added a DPI sweep plan (200/150/120/100) with estimated MP per page for the pristine PDF.
- **Next:** Run OCR on the representative sample at each DPI and compare against gold outputs.

### 20251222-0955 — Started full-size pristine render into input folder
- **Result:** In progress.
- **Notes:** Rendering full-size pages to `input/pristine_full_images/` in 5-page batches at 300 DPI to avoid memory blowups; `Image.MAX_IMAGE_PIXELS=None` required.
- **Next:** Confirm full page count and sample sizes once render completes.

### 20251222-1010 — Added render helper script
- **Result:** Success.
- **Notes:** Added `scripts/render_pristine_images.py` to batch-render pristine PDF pages with `Image.MAX_IMAGE_PIXELS=None`.
- **Next:** Run the script locally to complete full render.

### 20251222-1055 — Prepared downsampled benchmark tooling
- **Result:** Success.
- **Notes:** Added `scripts/build_pristine_bench_downsampled.py` to resize pristine pages to old benchmark sizes, and added `--images-root` override to `scripts/ocr_bench_openai_ocr.py` for targeted runs.
- **Next:** Generate downsampled benchmark images and run GPT‑5.1 OCR + diff.

### 20251222-1130 — Downsampled benchmark attempt (mapping mismatch)
- **Result:** Failure (mapping).
- **Notes:** Generated downsampled images by assuming split-page mapping (2n-1/2n) and ran GPT‑5.1 OCR. Diff scores collapsed (avg_html_ratio 0.052, avg_text_ratio 0.038), indicating the pristine page numbers do **not** align with the old benchmark pages. A quick dhash matching pass produced ambiguous candidates; mapping needs a better method.
- **Next:** Build a robust mapping (manual or fast OCR keyword search) from old benchmark pages to pristine pages, then regenerate downsampled benchmarks and re-run diffs.

### 20251222-1235 — Mapped pristine pages and re-ran downsampled benchmark
- **Result:** Success.
- **Notes:** Manual mapping provided for 9 benchmark pages (dropped page-004L and page-011). Built `input/pristine_bench_downsampled` and ran GPT‑5.1 OCR. Diff summary (9 pages): avg_html_ratio 0.877934, avg_text_ratio 0.971404. Lowest text score is `page-020R` (0.860697), likely table-structure sensitivity.
- **Next:** Inspect diffs for page-020R (and possibly page-009L HTML structure) to decide if a slightly higher DPI target is needed for tables.

### 20251222-1315 — Table check: page-020R at 150 DPI vs 300 DPI (pristine full size)
- **Result:** Success.
- **Notes:** Ran GPT‑5.1 OCR on pristine `page-020R` at 300 DPI (full size) and a 150 DPI downscale (50% linear). Table structure preserved in both; diffs mainly in tag choice (`<thead>` vs `<tbody>`, `h2` vs `p.page-number`) and image alt text. Text ratios: 300 DPI 0.991211, 150 DPI 0.982266. No table collapse observed at these resolutions.
- **Next:** Decide target downscale policy (likely >=150 DPI equivalent) and re‑test other table-heavy pages if needed.

### 20251222-1405 — Table-heavy pages at 150 DPI vs 300 DPI (pristine full size)
- **Result:** Mixed.
- **Notes:** Ran GPT‑5.1 OCR on pages 061, 067, 091, 100, 190 at 300 DPI and 150 DPI. Pages 091 and 100 preserved table structure at both resolutions; page 067/190 had no tables (expected). **Page 061 collapses the multi-row choice table into a single concatenated row at both 300 and 150**, suggesting the issue is layout/print variant rather than downscale.
- **Next:** Inspect page‑061 source layout to confirm table structure and decide whether to handle via post‑processing or a specialized table prompt.

### 20251222-1500 — Prompt tweak test for page-061 (FF hints + table preservation hint)
- **Result:** Failure (table still collapsed).
- **Notes:** Re-ran page‑061 at 150 DPI with FF-specific OCR hints plus a generic table‑preservation hint. Output still produced a single-row table with concatenated cells; no structural recovery.
- **Next:** Consider post-processing table reconstruction or a targeted table extractor for this layout; DPI alone and prompt hint did not fix it.

### 20251222-1520 — Added explicit “multiple Turn to options” hint
- **Result:** Failure (table still collapsed).
- **Notes:** Added a hint to split multiple “Turn to X” options into list/table rows. Page‑061 output remains a single-row concatenated table. Prompt tweaks alone are not enough for this layout.
- **Next:** Explore post‑processing or a targeted table extractor for this specific pattern.

### 20251222-1930 — Reviewed recent commits and added DPI requirement
- **Result:** Success.
- **Notes:** Recent commits (`28dde09` → `99510c1`) focused on GPT‑5.1 HTML pipeline + table rescue; no explicit optimal DPI decision landed yet. Added an explicit success criteria + task to determine minimum viable DPI/max MP for GPT‑5.1 (headers + tables preserved).
- **Next:** Run DPI sweep with table‑rescue enabled and record the minimal acceptable DPI/MP target.

### 20251222-1945 — Pulled completed story evidence (table rescue) into DPI decision
- **Result:** Success.
- **Notes:** Story‑085 confirmed table collapse is **not** DPI‑dependent for pristine page‑061 (fails at 300/150), and the new `table_rescue_html_v1` reliably repairs it. Validation across all pristine table pages (14 pages) shows only page‑061 requires rescue; others preserve structure. Artifacts: `/tmp/cf-pristine-table-check/pages_html_rescued_all.jsonl` and `/tmp/cf-table-rescue-smoke/pages_html_rescued_216b.jsonl`. This means the DPI decision can focus on text/heading fidelity without blocking on table collapse (rescue is now the mitigation).
- **Next:** Run DPI sweep with rescue enabled to pick the minimum viable DPI/max MP policy.

### 20251222-2030 — DPI sweep on pristine benchmarks + policy decision
- **Result:** Success.
- **Notes:** Rendered the 9 mapped pristine benchmark pages at 200/150/120/100 DPI and ran GPT‑5.1 OCR + diffs. Outputs:  
  - `testdata/ocr-bench/ai-ocr-simplification/gpt5_1-pristine-dpi-200/diffs/diff_summary.json` → avg_html 0.867418, avg_text 0.989851  
  - `.../gpt5_1-pristine-dpi-150/diffs/diff_summary.json` → avg_html 0.819466, avg_text 0.986478  
  - `.../gpt5_1-pristine-dpi-120/diffs/diff_summary.json` → avg_html 0.908099, avg_text 0.986947  
  - `.../gpt5_1-pristine-dpi-100/diffs/diff_summary.json` → avg_html 0.874036, avg_text 0.986266  
  Text ratios are effectively flat; 120 DPI produced the strongest HTML ratio with no meaningful text loss on the sample set.
- **Decision:** Default **120 DPI** for pristine PDFs (≈29 MP/page at 300‑DPI baseline → ~6× reduction vs 300 DPI) with table rescue enabled for rare collapses (page‑061).  
- **Config:** New settings file `configs/settings.ff-ai-ocr-gpt51-pristine-120dpi.yaml` sets `split_pages.dpi: 120`.
- **Next:** If needed, run a larger validation slice at 120 DPI on pristine pages before full‑book runs.

### 20251222-2105 — Added max-DPI extraction requirement
- **Result:** Success.
- **Notes:** Added requirement to cap extraction at 120 DPI in an early pipeline module before split detection.
- **Next:** Implement the max-DPI extraction module and wire it ahead of split detection.

### 20251222-2215 — Implemented capped PDF extraction + manifest-based splitting
- **Result:** Success.
- **Notes:** Added `extract_pdf_images_capped_v1` (per-page max DPI capped at 120) and `split_pages_from_manifest_v1` to split pre-rendered images. Updated GPT‑5.1 recipe and pristine settings to use the new stages.
- **Next:** Test extraction + split on both PDFs and inspect manifests/DPI reports.

### 20251222-2235 — Tested capped extraction on both PDFs
- **Result:** Success.
- **Notes:** Old PDF pages 1–2 render at 120 DPI (max_source_dpi ~150). Pristine PDF pages 1–2 report max_source_dpi 72, so render at 72 DPI (cap honored). Artifacts: `/tmp/cf-cap-old/render_dpi_report.jsonl`, `/tmp/cf-cap-pristine/render_dpi_report.jsonl`, split outputs under `/tmp/cf-cap-old-split/` and `/tmp/cf-cap-pristine-split/`.
- **Next:** Decide if 72 DPI is acceptable for pristine OCR or whether to override for quality; otherwise proceed with full‑book runs.

### 20251222-2310 — Added line-height based DPI chooser (in extractor)
- **Result:** Updated.
- **Notes:** Reworked `extract_pdf_images_capped_v1` to treat x-height as primary and DPI as a derived knob. Added optional sweep (`--sweep-line-heights`) plus optional caps (`max_mp`, `dpi_cap`), all off by default. Updated success criteria to reflect optional caps.
- **Next:** Run sweep on both PDFs to validate target selection and confirm caps remain off by default.

### 20251222-2340 — Ran x-height sweep (caps off)
- **Result:** Success.
- **Notes:** Swept line heights (20–36 px) on both PDFs. Old PDF: max_source_dpi ~150 caps effective line height (~15.9 px) even when target 20–36; best candidate picked 20 px (target_dpi 180, applied ~150). Pristine PDF: max_source_dpi 72 caps effective line height (~14 px); best candidate 20 px (target_dpi ~103, applied 72). Reports: `/tmp/cf-cap-old/line_height_sweep.json`, `/tmp/cf-cap-pristine/line_height_sweep.json`, summaries in `/tmp/cf-cap-old/render_dpi_summary.json` and `/tmp/cf-cap-pristine/render_dpi_summary.json`.
- **Next:** Decide whether to override low embedded DPI later by re-rendering select pages at higher DPI (separate story).

### 20251223-0025 — OCR quality sweep across x-height targets (old vs pristine)
- **Result:** Success.
- **Notes:** Ran GPT‑5.1 OCR bench across x-height targets 16/20/24/28 px for both PDFs (9-page mapped set).  
  Old PDF avg ratios: xh-16 (HTML 0.9134 / text 0.9895), xh-20 (0.9143 / 0.9921), xh-24 (0.9140 / 0.9923), xh-28 (0.9139 / 0.9888).  
  Pristine PDF avg ratios: xh-16 (0.8664 / 0.9806), xh-20 (0.9124 / 0.9806), xh-24 (0.9159 / 0.9878), xh-28 (0.8738 / 0.9858).  
  Artifacts under `testdata/ocr-bench/xheight-sweep/{old,pristine}/xh-*/diffs/diff_summary.json`.
- **Next:** Choose the lowest x-height that meets quality targets; consider 24 px as a stable default for both PDFs.

### 20251223-0105 — Set default x-height target + cost estimate
- **Result:** Success.
- **Notes:** Set `target_line_height: 24` in the GPT‑5.1 recipe. Estimated OCR cost at xh‑24 from bench usage: avg prompt 1304, completion ~378 (old) / ~372 (pristine). At GPT‑5.1 pricing ($1.25/M in, $10/M out), cost ≈ $0.00541 per split page (old) / $0.00535 (pristine) → ≈ $1.22–$1.21 for 226 split pages.
- **Next:** If desired, update settings to override target line height for specific runs.

### 20251223-0135 — Smoke run for x-height extraction + split
- **Result:** Success.
- **Notes:** Ran smoke with `--end-at split_pages` using `configs/settings.ff-ai-ocr-gpt51-table-rescue-smoke.yaml` (page 108). Extractor target_dpi=216 (xh‑24), render_dpi capped by max_source_dpi ~137.5 for page 108. Artifacts: `/tmp/cf-ff-ai-ocr-gpt51-xh24-smoke/01_extract_pdf_images_capped_v1/render_dpi_summary.json` and `render_dpi_report.jsonl`, plus split manifest under `/tmp/cf-ff-ai-ocr-gpt51-xh24-smoke/02_split_pages_from_manifest_v1/pages_split_manifest.jsonl`.
- **Next:** Proceed with full OCR runs only if/when x-height target and cap behavior are finalized.

### 20251223-0215 — Cost estimate at 120 DPI (GPT‑5.1)
- **Result:** Success.
- **Notes:** From `testdata/ocr-bench/ai-ocr-simplification/gpt5_1-pristine-dpi-120/openai_usage.jsonl` (9 pages), avg tokens/page: prompt 1240, completion 369.89. Using GPT‑5.1 pricing ($1.25/M input, $10/M output), cost ≈ $0.00525 per split page (~$0.52 cents) → ≈ $1.19 for 226 split pages. Pricing source: OpenAI API pricing page.
- **Next:** If needed, recompute with cached input or Batch pricing.
