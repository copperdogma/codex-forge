# codex-forge
AI-first, modular pipeline for turning scanned books into structured JSON with full traceability.

## 📚 Documentation
- **[Runbook & Operations Guide](docs/RUNBOOK.md)**: **START HERE** for running the pipeline, resuming runs, and troubleshooting.
- **[Agent Guide](AGENTS.md)**: Guidelines for AI agents and developers contributing to the codebase.
- **[Benchmarks](benchmarks/README.md)**: Systematic model evaluation using `promptfoo`.

## Pipeline Architecture

The pipeline follows a 5-stage model:

1. **Intake → IR (generic)**: PDF/images → structured elements (Unstructured library provides rich IR with text, types, coordinates, tables)
2. **Verify IR (generic)**: QA checks on completeness, page coverage, element quality
3. **Portionize (domain-specific)**: Identify logical portions (CYOA sections, genealogy chapters, textbook problems) and reference IR elements
4. **Augment (domain-specific)**: Enrich portions with domain data (choices/combat for CYOA, relationships for genealogy)
5. **Export (format-specific)**: Output to target format (FF Engine JSON, HTML, Markdown) using IR + augmentations

Steps 1-2 are universal across all document types. Steps 3-4 vary by domain (gamebooks vs genealogies vs textbooks). Step 5 is tied to output requirements.

**Reusability goal:** Keep upstream intake/OCR modules as generic as possible. Prefer pushing booktype-specific heuristics/normalization downstream into booktype-aware modules.

## Repository Layout
- `driver.py`: Main orchestration script.
- `modules/`: Pipeline stages (`extract`, `transform`, `adapter`, etc.).
- `configs/recipes/`: YAML files defining pipeline stages (logic).
- `configs/presets/`: YAML files defining model/cost settings (parameters).
- `output/runs/`: All pipeline artifacts and logs.
- `docs/`: Documentation and story tracking.
- `benchmarks/`: Model evaluation workspace.

## Setup & Dependencies

### Python Environment
- **Canonical (GPT-5.1 OCR)**: Runs on any architecture (x86_64 or ARM64).
  ```bash
  pip install --no-cache-dir -r requirements.txt
  ```

### API Keys
Set the following environment variables:
- `OPENAI_API_KEY`: For GPT-4/5 models.
- `GEMINI_API_KEY`: For Google Gemini models.
- `ANTHROPIC_API_KEY`: For Claude models (benchmarking/judging).

### Legacy Environment (Unstructured/EasyOCR)
If using the deprecated legacy pipeline with local OCR:
- **ARM64 (Apple Silicon)**: Recommended for `hi_res` strategy using `jax-metal`.
- **x86_64 (Rosetta)**: Use for `ocr_only` compatibility.
- See `docs/legacy/environment_setup.md` (if created) or check git history for detailed setup of legacy environments.

## Development

### Unit Tests
```bash
python -m unittest discover -s tests -p "driver_*test.py"
```

### Dashboard
View pipeline progress and artifacts visually:
```bash
python -m http.server 8000
# Open http://localhost:8000/docs/pipeline-visibility.html
```
