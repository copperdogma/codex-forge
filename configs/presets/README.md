# Preset snippets (cost/perf benchmarks)

These YAML fragments mirror the settings schema (model/temperature/max_tokens/max_retries) plus a portionize window. Use them via `--settings` or merge into an existing settings file:

```bash
python driver.py --recipe configs/recipes/recipe-text.yaml --settings configs/presets/speed.text.yaml
python driver.py --recipe configs/recipes/legacy/recipe-ocr.yaml  --settings configs/presets/cost.ocr.yaml
```

Presets correspond to measured benchmarks (window=8) in `output/runs/bench-cost-perf-*/bench_metrics.csv`:

- `speed.text.yaml` — gpt-4.1-mini, ~8s/page, ~$0.00013/page (text recipe).
- `cost.ocr.yaml` — gpt-4.1-mini, ~13–18s/page, ~$0.0011/page.
- `balanced.ocr.yaml` — gpt-4.1, ~16–34s/page, ~$0.014–0.026/page.
- `quality.ocr.yaml` — gpt-5, ~70–100s/page, ~$0.015–0.020/page.

Notes:
- Text preset assumes pre-extracted text input (no OCR).
- You can override portion window/stride in recipes if needed; defaults here match the benchmark runs.
