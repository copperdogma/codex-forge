# Story: OCR Model Eval for Genealogy / Table-Heavy Books

**Status**: Done

---

## Acceptance Criteria
- [x] Select 25 benchmark pages covering table-only, image-heavy, mixed, TABLE-AS-TEXT failure, dense multi-table, and variable column layouts
- [x] Create hand-corrected golden HTML references with proper `<table>` structure and `<img>` placeholders
- [x] Build table structure scorer with 6 weighted metrics (table detection, column accuracy, cell text, row accuracy, header accuracy, img detection)
- [x] Evaluate 9 VLM models across 2 prompt variants (baseline, table-strict)
- [x] Identify winning model + prompt for genealogy OCR
- [x] Document results and update README

## Tasks
- [x] Select 14 table-heavy benchmark pages from Onward to the Unknown
- [x] Select 11 image-heavy benchmark pages from source-pages
- [x] Create base64-encoded input images (`benchmarks/input/onward-pages-b64/`)
- [x] Create 25 golden HTML references (`benchmarks/golden/ocr-genealogy/`)
- [x] Fix BOY/GIRL column splitting bug in golden files (pages 024, 026, 035)
- [x] Rewrite 3 TABLE-AS-TEXT failure pages (025, 031, 050) with proper table structure
- [x] Build `table_structure_scorer.py` with 5 table metrics + img_detection
- [x] Add dynamic weight allocation (image-only, mixed, table-only pages)
- [x] Create baseline and table-strict prompt variants
- [x] Create `_image-helpers.js` for provider-specific image formats
- [x] Configure promptfoo YAML with 9 providers x 2 prompts x 25 test cases
- [x] Run full eval (450 combinations) + GPT-only re-run at concurrency 1
- [x] Analyze results and document findings

## Results

**Winner**: Gemini 3 Pro + table-strict (0.877 avg, 100% pass, 25/25 pages)

### table-strict prompt (recommended)

| Rank | Model | Pages | Avg Score | Pass Rate |
|------|-------|-------|-----------|-----------|
| 1 | Gemini 3 Pro | 25/25 | 0.877 | 100% |
| 2 | Gemini 2.5 Pro | 25/25 | 0.870 | 96% |
| 3 | Claude Opus 4.6 | 25/25 | 0.866 | 96% |
| 4 | Claude Sonnet 4.5 | 25/25 | 0.861 | 92% |
| 5 | GPT-5 Mini | 14/25 * | 0.768 | 86% |
| 6 | GPT-5.2 | 14/25 * | 0.767 | 93% |
| 7 | Gemini 2.5 Flash | 24/25 | 0.763 | 83% |
| 8 | GPT-5.1 | 14/25 * | 0.761 | 71% |
| 9 | Gemini 3 Flash | 25/25 | 0.759 | 80% |

\* Partial data due to OpenAI rate limits (even at concurrency 1)

### baseline prompt

| Rank | Model | Pages | Avg Score | Pass Rate |
|------|-------|-------|-----------|-----------|
| 1 | Claude Opus 4.6 | 25/25 | 0.775 | 84% |
| 2 | Claude Sonnet 4.5 | 25/25 | 0.724 | 76% |
| 3 | Gemini 3 Pro | 25/25 | 0.718 | 72% |
| 4 | Gemini 2.5 Pro | 25/25 | 0.670 | 68% |
| 5 | GPT-5.1 | 14/25 * | 0.587 | 64% |
| 6 | Gemini 2.5 Flash | 25/25 | 0.568 | 56% |
| 7 | GPT-5.2 | 14/25 * | 0.562 | 57% |
| 8 | Gemini 3 Flash | 25/25 | 0.533 | 56% |
| 9 | GPT-5 Mini | 14/25 * | 0.235 | 21% |

### Key findings
- `table-strict` prompt dramatically outperforms `baseline` across all models
- Top 4 models all score 0.86+ with table-strict — very close race
- Gemini 3 Pro wins on both avg score (0.877) and reliability (100% pass, 0 errors)
- GPT-5.1 (current pipeline model) ranks 8th — switching to Gemini 3 Pro would be ~15% improvement
- Image detection (`<img>` placeholders) is near-perfect across all models (0.96-1.00)
- OpenAI models severely rate-limited even at concurrency 1 — only 14/25 pages completed

## Artifacts

| File | Purpose |
|------|---------|
| `benchmarks/tasks/ocr-genealogy-tables.yaml` | Full eval config (9 models × 2 prompts × 25 pages) |
| `benchmarks/tasks/ocr-genealogy-tables-gpt-only.yaml` | GPT-only eval config (concurrency 1) |
| `benchmarks/prompts/ocr-genealogy-baseline.js` | Baseline OCR prompt |
| `benchmarks/prompts/ocr-genealogy-table-strict.js` | Table-strict OCR prompt |
| `benchmarks/scorers/table_structure_scorer.py` | Table + image structure scoring |
| `benchmarks/golden/ocr-genealogy/page-*-golden.html` | 25 golden references |

## Notes
- Run command: `cd benchmarks && source ~/.zshrc && promptfoo eval -c tasks/ocr-genealogy-tables.yaml --no-cache -j 2`
- Full eval duration: ~2 hours at concurrency 2 (450 test cases)
- GPT-only re-run: ~1 hour at concurrency 1 (150 test cases)
- Scoring weights (table-only): table_detection 25%, column_accuracy 25%, cell_text 25%, row_accuracy 15%, header_accuracy 10%
- Scoring weights (mixed pages): table weights reduced, 15% allocated to img_detection
- Scoring weights (image-only): 100% img_detection
- Images >4MB resized with `sips -Z 2550` to fit Anthropic's 5MB base64 limit
- GEMINI_API_KEY must be sourced from ~/.zshrc (not available in default bash env)
- BOY/GIRL is a single column in this book (values like "1 1"), not two separate columns
