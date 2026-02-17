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

## Current Evals

### Image Crop Extraction (Story 125)

Evaluates VLM prompts/models for extracting photo bounding boxes from scanned book pages.

**Test pages** (from *Onward to the Unknown*):

| Source File | Content | Failure Mode |
|------------|---------|-------------|
| `page-012.jpg` | Certificate with seal/signatures | Non-photo image, header text bleed |
| `page-018.jpg` | Group portrait | Single large photo with caption |
| `page-021.jpg` | Two photos with captions | Multi-image, caption separation |
| `page-022.jpg` | Single photo with caption | Caption-adjacent |
| `page-038.jpg` | Multi-photo page | Multiple images to detect/separate |
| `page-060.jpg` | Two photos with captions | Caption text in crops |

**Golden references**: Manually cropped photos in `golden/crops/` with bounding boxes in `golden/image-crops.json`.

**Naming convention for golden crops**:
```
golden/crops/page-NNN-MMM.jpg
```
Where `NNN` = source page number (matching source-pages/page-NNN.jpg), `MMM` = zero-indexed image number on that page (000, 001, ...).

Example: page 21 has two photos:
- `golden/crops/page-021-000.jpg` (top photo)
- `golden/crops/page-021-001.jpg` (bottom photo)

## Adding a New Eval

1. Copy test inputs to `input/`
2. Create golden references in `golden/` (hand-crafted, expert-validated)
3. Write prompt template in `prompts/` (use `{{var}}` placeholders)
4. Write Python scorer in `scorers/` (implement `get_assert(output, context)`)
5. Create promptfoo config in `tasks/` (providers x test cases x assertions)
6. Run eval, analyze, iterate on prompts, pick winning model
