# Story 084: OCR Quality Validation Plan

## Critical Requirement

**Zero tolerance for quality degradation.** Cost savings are NOT worth even 1% OCR quality loss.

## Hypothesis to Validate

Fast extraction at native resolution (72 DPI for pristine, 150 DPI for old) maintains or improves OCR quality vs current rendering approach (120/150 DPI).

**Why this should be true:**
- Old PDF: Native 150 DPI = rendered 150 DPI → guaranteed identical
- Pristine PDF: Native 72 DPI vs rendered 120 DPI → 120 DPI is wasteful upscaling from 72 DPI source
- Upscaling via pdf2image just interpolates pixels; adds zero OCR information
- Native extraction saves 974× time + 2.78× AI tokens without quality loss

## Validation Tests (MUST PASS before implementation)

### Test 1: Old PDF Baseline (Expected: PASS)

**Setup:**
- Extract all benchmark pages using fast extraction at native 150 DPI
- Run GPT-5.1 OCR using same recipe as current baseline
- Compare vs existing benchmark results

**Pass criteria:**
- Text diff ratio ≥ 0.999 (effectively identical)
- HTML diff ratio ≥ 0.95
- Zero new errors or degraded pages
- Visual inspection: no obvious quality issues

**Expected result:** Should be pixel-perfect identical since native DPI = render DPI

---

### Test 2: Pristine PDF Full Benchmark (Expected: PASS, needs validation)

**Setup:**
- Extract all 9 mapped benchmark pages using fast extraction at native 72 DPI
- Run GPT-5.1 OCR with same recipe
- Compare vs story-082's xh-24 baseline (0.98779 avg text ratio)

**Pass criteria:**
- **CRITICAL**: avg_text_ratio ≥ 0.98779 (must match or exceed current baseline)
- avg_html_ratio ≥ 0.90 (reasonable HTML structure preservation)
- Zero table collapses not present in baseline (validate table-rescue still works)
- No degradation on edge cases: page-020R (tables), page-061 (multi-row tables)

**Reference baseline (from story-082):**
- xh-24 pristine: avg_text_ratio = 0.98779, avg_html_ratio = 0.9159
- xh-16 pristine: avg_text_ratio = 0.98061, avg_html_ratio = 0.8664

**Expected result:** Native 72 DPI (~14px x-height) should match or exceed xh-16 results (0.98061), possibly approach xh-24 (0.98779) since native extraction preserves original JPEG quality without re-encoding.

---

### Test 3: Pristine PDF Extended Set (If Test 2 passes)

**Setup:**
- Extract 20-50 pages covering diverse content types:
  - Table-heavy pages (061, 067, 091, 100, 190, etc.)
  - Map pages
  - Diagram/illustration pages
  - Text-only pages
  - Low-contrast pages
- Run full OCR pipeline with table rescue
- Compare quality metrics vs baseline

**Pass criteria:**
- No catastrophic failures (blank pages, garbled text)
- Table rescue effectiveness maintained
- avg_text_ratio ≥ baseline across page categories
- Visual spot-check: no obvious degradation

---

### Test 4: Edge Case Validation

**Setup:**
- Identify worst-performing pages from Test 2/3
- Extract at native resolution
- Run OCR with multiple prompt variations
- Compare vs baseline

**Pass criteria:**
- No edge cases worse than current approach
- Table rescue still handles page-061 correctly
- Low-contrast pages still readable
- Complex layouts (maps, diagrams) maintain structure

---

## Validation Workflow

### Step 1: Old PDF Validation (Low Risk)
```bash
# Extract benchmark pages at native 150 DPI
python scripts/extract_pdf_images_fast.py \
  --pdf "input/06 deathtrap dungeon.pdf" \
  --outdir /tmp/cf-fast-extract-old-bench \
  --start 1 --end 113

# Run OCR benchmark
python scripts/ocr_bench_openai_ocr.py \
  --images-root /tmp/cf-fast-extract-old-bench \
  --outdir testdata/ocr-bench/fast-extract/old-native-150dpi

# Compare results
python scripts/ocr_bench_diff.py \
  --test testdata/ocr-bench/fast-extract/old-native-150dpi \
  --gold testdata/ocr-bench/ai-ocr-simplification/gpt5_1-old-xh-24 \
  --outdir testdata/ocr-bench/fast-extract/old-native-150dpi/diffs
```

**Expected:** Near-perfect match (text_ratio ≥ 0.999)

---

### Step 2: Pristine PDF Benchmark Validation (CRITICAL)
```bash
# Extract mapped benchmark pages at native 72 DPI
# (Use pristine_bench_mapping.json for page selection)
python scripts/extract_pdf_images_fast.py \
  --pdf "input/deathtrapdungeon00ian_jn9_1 - from internet archive.pdf" \
  --outdir /tmp/cf-fast-extract-pristine-bench \
  --pages-from input/pristine_bench_mapping.json

# Run OCR benchmark
python scripts/ocr_bench_openai_ocr.py \
  --images-root /tmp/cf-fast-extract-pristine-bench \
  --outdir testdata/ocr-bench/fast-extract/pristine-native-72dpi

# Compare vs xh-24 baseline
python scripts/ocr_bench_diff.py \
  --test testdata/ocr-bench/fast-extract/pristine-native-72dpi \
  --gold testdata/ocr-bench/ai-ocr-simplification/gpt5_1-pristine-xh-24 \
  --outdir testdata/ocr-bench/fast-extract/pristine-native-72dpi/diffs-vs-xh24

# Also compare vs xh-16 (more similar x-height)
python scripts/ocr_bench_diff.py \
  --test testdata/ocr-bench/fast-extract/pristine-native-72dpi \
  --gold testdata/ocr-bench/xheight-sweep/pristine/xh-16 \
  --outdir testdata/ocr-bench/fast-extract/pristine-native-72dpi/diffs-vs-xh16
```

**MUST PASS:** avg_text_ratio ≥ 0.98779 (xh-24 baseline)

---

### Step 3: Extended Testing (If Step 2 passes)
- Expand to 50-page test set
- Include all table-heavy pages from story-082
- Run with table rescue enabled
- Validate edge cases

---

### Step 4: Statistical Analysis
- Compare distributions, not just averages
- Identify outliers and worst-case pages
- Validate no systematic degradation by page type
- Document any trade-offs

---

## Decision Criteria

### ✅ PROCEED to implementation if:
1. Old PDF: text_ratio ≥ 0.999 (virtually identical)
2. Pristine PDF: avg_text_ratio ≥ 0.98779 across benchmark set
3. No edge cases show catastrophic failure
4. Table rescue effectiveness maintained

### ⚠️ CONDITIONAL PROCEED if:
1. Pristine PDF: avg_text_ratio slightly lower (0.980-0.987) but:
   - Difference < 1% and within measurement noise
   - Visual inspection shows no quality loss
   - Specific page types (e.g., text-only) perform better

### ❌ BLOCK implementation if:
1. Pristine PDF: avg_text_ratio < 0.98 (>1% degradation)
2. Edge cases show new failures not in baseline
3. Table rescue breaks on pages that currently work
4. Visual inspection reveals obvious quality problems

---

## Contingency Plan

If pristine PDF validation fails:
1. Continue fast extraction for old PDF only (proven safe)
2. Keep current rendering approach for pristine PDF
3. Investigate hybrid: fast extract + selective re-rendering for quality-sensitive pages
4. Document findings: upscaling may have unexpected benefits in specific cases

---

## Success Metrics

**Primary:** OCR quality (text_ratio) ≥ baseline
**Secondary:** Speed (974× faster) + Cost (2.78× cheaper tokens)
**Tertiary:** Pipeline simplicity (direct extraction vs rendering)

**Remember:** Quality is non-negotiable. Speed/cost are bonuses, not trade-offs.
