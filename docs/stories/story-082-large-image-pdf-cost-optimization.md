# Story: Large-Image PDF Cost Optimization

**Status**: To Do  
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

- [ ] **Image size audit**: Baseline old vs pristine PDFs with exact page dimensions (px) and file sizes.
- [ ] **Cost sensitivity**: Estimate cost impact at multiple resolutions (e.g., 100%, 75%, 50%, 35%).
- [ ] **Downscale policy**: Define target max dimension and/or max megapixels per page for OCR input.
- [ ] **Quality check**: Verify OCR quality on a representative sample at chosen downscale (no loss in section headers and choice text).
- [ ] **Configurable**: Policy is configurable via recipe/settings (not hard-coded).

---

## Tasks

- [ ] Inventory page image sizes for **old** and **pristine** PDFs (min/median/max; include example page IDs).
- [ ] Ensure large-image rendering works safely (Pillow decompression-bomb guard) for pristine PDFs.
- [ ] Define a resolution sweep plan and estimate cost per page at each resolution.
- [ ] Build a **downsampled benchmark set**: resize pristine pages to match old benchmark dimensions and run OCR bench diff.
- [ ] Establish **page mapping** between old benchmark pages and pristine pages (manual or OCR-based), then re-run downsampled benchmark.
- [ ] Run OCR on a small, representative page set at multiple resolutions; compare against gold outputs.
- [ ] Choose a default downscale policy with justification (quality vs cost) and document it.
- [ ] Add settings/recipe knobs to control downscale behavior.
- [ ] Document findings and decision in the story work log with evidence.

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
