# AI Self-Improvement Log

Living memory for AI agents. When you discover a mistake, pitfall, or effective pattern during work, record it here so future sessions avoid repeating errors.

Entry format: `YYYY-MM-DD — short title`: summary plus explanation including file paths.

## Effective Patterns
- 2026-01-17 — Story-first implementation with focused smoke checks: Implement in dependency order and validate each milestone with a targeted subset run before expanding.
- 2026-01-17 — Reuse existing modules first: Before building new logic, check if an existing module (even from a different recipe) can be reused or adapted. Mimicking battle-tested patterns avoids new bugs.
- 2026-01-24 — Dual evaluation catches what code can't: Python scorers measure structural quality (IoU, field coverage) but miss semantic issues. LLM rubric judges catch qualitative problems. Always use both in promptfoo evals.
- 2026-01-24 — Cross-provider judging reduces bias: Use Claude Opus 4.6 as default judge when evaluating models from OpenAI/Google.

## Known Pitfalls
- 2026-01-17 — Schema stamping drops undeclared fields: `driver.py` stamps artifacts using `schemas.py`. New fields not in the schema are silently dropped. Always add new output fields to the corresponding schema.
- 2026-01-17 — Stale .pyc files cause silent failures: Always `find modules/<module> -name "*.pyc" -delete` before integration testing a modified module.
- 2026-01-24 — VLM image box detection includes nearby text: VLM bounding boxes for photos often absorb captions, headers, and body text. Heuristic trimming is unreliable; systematic eval with golden data is needed.
- 2026-02-16 — promptfoo `max_tokens` trap: OpenAI providers silently truncate long outputs without `max_tokens` set, producing invalid JSON.
- 2026-02-16 — promptfoo `---` in prompts is a separator: Three dashes split one prompt into two fragments. Use `==========` instead.
- 2026-02-16 — Gemini extended thinking eats output tokens: Set `maxOutputTokens: 16384` for Gemini providers (4096 is insufficient).
- 2026-02-16 — Gemini model IDs: No dated preview suffixes. Use `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-pro-preview`.
- 2026-02-16 — promptfoo `raw` prompts bypass format translation: When using `raw:` prompt key, content is sent verbatim to every provider. Anthropic expects `type: "image"` (not `image_url`), Google expects `inlineData` (not `image_url`). Use JS prompt functions with `id: "file://..."` that detect `provider.id` and adapt the image content block format per provider.
- 2026-02-16 — GEMINI_API_KEY in wrong shell: If key is in `.zshrc` but promptfoo runs in bash, it won't be found. Export the key before running or add to `.bashrc`.
- 2026-02-16 — `file://` corrupts binary image data: promptfoo's `file://` loader corrupts binary JPEG when interpolated into prompt templates. Pre-encode images as base64 data URI text files (`data:image/jpeg;base64,...`) stored as `.b64.txt`.

## Lessons Learned
- 2026-01-17 — Cost discipline on OCR: Treat OCR as expensive and single-run. Iterate downstream by reusing OCR artifacts, not re-running OCR.
- 2026-01-24 — Systematic eval beats ad-hoc iteration: After ~10 rounds of heuristic tuning on image cropping without converging, switching to a promptfoo-based eval with golden data was the right move.
- 2026-01-17 — Escalate-to-success loops need caps: Every escalation loop must have a max retry/budget cap to prevent infinite loops.
- 2026-02-16 — Provider-specific image format handling: OpenAI uses `{type: "image_url", image_url: {url: "data:..."}}`, Anthropic uses `{type: "image", source: {type: "base64", media_type: "...", data: "..."}}`, Google uses `{inlineData: {mimeType: "...", data: "..."}}`. For multi-provider evals, use a shared JS helper that adapts format based on `provider.id`.
- 2026-02-16 — Simpler prompts win for stronger models: Gemini 3 Pro scored best with the simplest (baseline) prompt. Overly prescriptive prompts (strict-exclude) can hurt strong models while helping weaker ones. Always test prompt complexity as a variable.
