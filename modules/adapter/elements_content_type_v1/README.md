# elements_content_type_v1

Text-first DocLayNet-style content type tagging for `element_core_v1` (`elements_core.jsonl`).

## What it does

Reads `elements_core.jsonl` and emits an enriched `element_core_v1` JSONL with:
- `content_type` (DocLayNet label)
- `content_type_confidence` (0-1)
- `content_subtype` (optional small dict; currently used for numeric section header `number`, `form_field`, FF `combat_stats`, and `key_value` pairs)

It also optionally emits a per-page debug JSONL with label counts and a few low-confidence examples.

## Labels (DocLayNet 11)

`Title`, `Section-header`, `Text`, `List-item`, `Table`, `Picture`, `Caption`, `Formula`, `Footnote`, `Page-header`, `Page-footer`.

Notes:
- v1 is heuristic and **text-first**. When `layout.y` is available, it uses only safe, evidence-driven
  geometry rules (repetition-based header/footer detection and bottom-of-page numeric page numbers).
- FF "character sheet" field labels like `STAMINA =` are tagged as `Text` with `content_subtype.form_field=true` (DocLayNet has no dedicated `Form` label).
- FF combat stat blocks like `MANTICORE  SKILL 11  STAMINA 11` are tagged as `Text` with `content_subtype.combat_stats=true` (they are not true layout tables).
- When high-precision patterns match, `content_subtype.key_value` is attached as a small dict like:
  - `{"pairs":[{"key":"SKILL","value":11},{"key":"STAMINA","value":11}],"entity":"MANTICORE"}`

## Driver usage (canonical FF recipe)

The canonical FF recipe inserts this stage after `pagelines_to_elements_v1` and rewires downstream stages to use `elements_core_typed.jsonl`.

## CLI usage

Example (direct):
- `python -m modules.adapter.elements_content_type_v1.main --inputs testdata/ff-20-pages/elements_core.jsonl --out /tmp/elements_core_typed.jsonl --debug_out /tmp/elements_content_type_debug.jsonl`

Key flags:
- `--out` (required): output JSONL path
- `--debug-out` / `--debug_out`: optional debug JSONL path
- `--disabled`: pass-through mode (no tagging)
- `--use-llm` / `--use_llm`: enable LLM classification for low-confidence items (off by default)
- `--llm-threshold` / `--llm_threshold`: heuristic confidence below which to escalate
- `--allow-unknown-kv-keys` / `--allow_unknown_kv_keys`: allow `content_subtype.key_value` for non-whitelisted keys (default: false)

Note: underscore aliases exist for driver compatibility (the driver emits `--debug_out`, etc.).
