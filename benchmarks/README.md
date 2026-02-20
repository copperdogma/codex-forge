# codex-forge Benchmarks

Systematic evaluation of AI models/prompts for pipeline tasks using [promptfoo](https://www.promptfoo.dev/).

## Setup

```bash
# Node.js 22+ required (24 LTS recommended)
source ~/.nvm/nvm.sh && nvm use 24

# Install promptfoo globally
npm install -g promptfoo

# API keys needed
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GEMINI_API_KEY=...
```

## Workspace Layout

```
benchmarks/
├── tasks/              # promptfoo YAML configs (one per eval task)
├── prompts/            # Prompt templates with {{variable}} placeholders
├── golden/             # Hand-crafted reference data for scoring
│   └── crops/          # Manually cropped reference images
├── input/
│   └── source-pages/   # Source page images for evaluation
├── scorers/            # Python scoring scripts (get_assert interface)
├── results/            # JSON output from eval runs
└── scripts/            # Analysis helpers
```

## Running Evals

```bash
cd benchmarks/

# Run an eval (no cache for reproducibility)
promptfoo eval -c tasks/image-crop-extraction.yaml --no-cache -j 3

# Save results
promptfoo eval -c tasks/image-crop-extraction.yaml --no-cache --output results/image-crop-run1.json

# View results in web UI leaderboard
promptfoo view
```

## Eval Catalog

Quick reference for all promptfoo eval setups. Re-run any eval when new models come out to check for improvements.

### 1. Image Crop Extraction (Story 125)

**Task**: Extract photo/illustration bounding boxes from scanned book pages.
**Winner**: Gemini 3 Pro (0.856 avg score, 77% pass rate)
**Config**: `tasks/image-crop-extraction.yaml`
**Scorer**: `scorers/image_crop_scorer.py` — IoU + coverage metrics
**Prompts**: 3 variants (baseline, strict-exclude, two-step)
**Test set**: 13 pages from *Onward to the Unknown* with diverse image content

```bash
cd benchmarks && source ~/.zshrc && promptfoo eval -c tasks/image-crop-extraction.yaml --no-cache
```

**Key findings** (Feb 2026):
- Gemini 3 Pro best for bbox accuracy, lowest hallucination rate
- GPT-5.1 baseline: decent but over-crops (includes text regions)
- `strict-exclude` prompt marginally better than baseline across all models

---

### 2. OCR Model Eval — Genealogy Pages (Story 127)

**Task**: Single-pass VLM OCR — model sees raw page image, outputs structured HTML with `<table>` elements and `<img>` placeholders.
**Winner**: Gemini 3 Pro + table-strict (0.877 avg score, 100% pass rate)
**Config**: `tasks/ocr-genealogy-tables.yaml`
**Scorer**: `scorers/table_structure_scorer.py` — table detection, column/row/cell accuracy, header detection, img detection
**Prompts**: 2 variants (baseline, table-strict)
**Test set**: 25 pages from *Onward to the Unknown* covering:
  - 14 table-heavy pages (6-column genealogy tables, dense multi-table, TABLE-AS-TEXT failures)
  - 11 image-heavy pages (photos, illustrations, certificates, mixed narrative+images)

```bash
cd benchmarks && source ~/.zshrc && promptfoo eval -c tasks/ocr-genealogy-tables.yaml --no-cache -j 2
```

**Scoring**: Dynamic weights based on page content:
- Table-only: table_detection 25%, column_accuracy 25%, cell_text 25%, row_accuracy 15%, header_accuracy 10%
- Mixed (tables + images): table weights reduced, 15% to img_detection
- Image-only: 100% img_detection

**Golden references**: `golden/ocr-genealogy/page-NNN-golden.html` — hand-corrected HTML with `<table>` and `<img>` tags.
**Inputs**: `input/onward-pages-b64/ImageNNN.b64.txt` — base64-encoded page images.

**Key findings** (Feb 2026):
- `table-strict` prompt dramatically outperforms `baseline` across all models
- Top 4 (table-strict): Gemini 3 Pro (0.877, 100% pass), Gemini 2.5 Pro (0.870), Claude Opus 4.6 (0.866), Claude Sonnet 4.5 (0.861)
- GPT models rate-limited to 14/25 pages even at concurrency 1; best GPT: GPT-5 Mini (0.768)
- Image detection (`<img>` placeholders) near-perfect across all models (0.96-1.00)
- GPT-5.1 (current pipeline model) ranks 8th at 0.761 — switching to Gemini 3 Pro = ~15% improvement

## Adding a New Eval

1. Copy test inputs to `input/`
2. Create golden references in `golden/` (hand-crafted, expert-validated)
3. Write prompt template in `prompts/` (use `{{var}}` placeholders)
4. Write Python scorer in `scorers/` (implement `get_assert(output, context)`)
5. Create promptfoo config in `tasks/` (providers x test cases x assertions)
6. Run eval, analyze, iterate on prompts, pick winning model
