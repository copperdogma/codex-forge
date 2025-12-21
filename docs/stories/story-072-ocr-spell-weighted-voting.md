# Story: OCR Spell-Weighted Voting Enhancement

**Status**: Obsolete
**Created**: 2025-12-18
**Parent Story**: story-070 (OCR Split Refinement - COMPLETE)
**Related Stories**: story-063 (OCR Ensemble Three-Engine Voting - DONE), story-069 (PDF Text Extraction Engine - DONE)

---

## Goal

Enhance the OCR ensemble voting algorithm to use per-engine spell quality as a tiebreaker. Currently spell checking (`spell_garble_metrics()`) is only used for post-fusion quality diagnostics and escalation triggers. It's NOT used during engine voting, which is a missed opportunity for quality improvement.

**Expected Impact**: 1-2% quality improvement with minimal risk and performance cost.

---

## Success Criteria

- [x] **Per-engine spell metrics computed**: Dictionary quality calculated for each engine before voting
- [x] **Integrated into voting**: Spell quality used as tiebreaker in fusion cascade
- [x] **Quality improvement measured (correctness)**: Baseline vs. spell-on run shows fewer “turn-to instruction” OCR errors (e.g., `Tum/tum to <N>` and `t0/tO <N>`) with evidence from `pages_raw.jsonl` diffs
- [x] **No regressions on the 20-page sample**: Baseline vs. spell-on diff limited to high-confidence fixes; `scripts/regression/check_suspicious_tokens.py` stayed flat on sample
- [x] **Performance budget proven (steady-state)**: `engine_spell_metrics_ms` and `turn_to_phrase_repair_ms` present; p95 < 5ms/page-side after warm-up (first call may include wordlist load)
- [x] **Handles digit confusion**: Real sample shows `t0/tO -> to` repaired in `Turn to <N>` instructions, with provenance
- [x] **Handles common typos**: Real sample shows `Tum/tum -> Turn/turn` repaired in `Turn to <N>` instructions, with provenance
- [x] **Demonstrates spell-weighted tiebreak**: In a 20-page sample including `easyocr`, spell-weighted voting changes ambiguous line provenance (and preserves text), without regressions
- [x] **Architecture / reuse**: Keep OCR intake modules generic where possible; move booktype-specific normalization (e.g., FF/gamebook “Turn to <N>” canonicalization) downstream into booktype-aware adapters/extractors without sacrificing accuracy

---

## Context

**Current Implementation**:
- Spell checking (`spell_garble_metrics()`) exists in `modules/common/text_quality.py`
- Used only for post-fusion diagnostics and escalation triggers
- NOT used during engine voting/fusion decisions
- Existing wordlist includes Fighting Fantasy terms (STAMINA, SKILL, etc.)

**Opportunity**:
- Use per-engine dictionary quality as a voting weight/tiebreaker
- Prefer engines with better spelling (fewer OOV words, fewer digit confusions)
- Low-hanging fruit: spell metrics already exist, just need to pass to fusion

**Related Work**:
- Story-063: OCR Ensemble Three-Engine Voting (established fusion algorithm)
- Story-069: PDF Text Extraction Engine (documented fusion algorithm)
- Story-070: OCR Split Refinement (where this was originally scoped)

---

## Tasks

### Task 1: Compute Per-Engine Spell Metrics

- [x] **After outlier detection**, compute `spell_garble_metrics()` for each non-outlier engine
- [x] Store per-engine metrics (keys from `spell_garble_metrics()`): `dictionary_score`, `dictionary_oov_ratio`, `dictionary_total_words`, `char_confusion_score`
- [x] Derive a stable `engine_spell_quality` weight (higher=better) from metrics (e.g., `1 - max(dictionary_score, char_confusion_score)`)
- [x] Persist provenance in `part_by_engine["engine_spell_metrics"]` (or similar) for downstream debugging
- [x] Only compute/use weights for engines with sufficient text (`dictionary_total_words >= 10`)

**Key Files**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Single-column voting path (around outlier detection + `align_and_vote()` call, ~2690-2750)
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Column-level voting path (around `engine_outputs_col` + `align_and_vote()` call, ~2818-2855)

### Task 2: Integrate into Voting Cascade

- [x] Thread `engine_spell_metrics` / `engine_spell_quality` through `align_and_vote()` → `_align_and_vote_multi()` → `_choose_fused_line()`
- [x] Add a module knob to gate the behavior (`enable_spell_weighted_voting`)
- [x] Use spell quality only as a conservative **tiebreaker** (never override majority exact-match wins)
- [x] Trigger condition: top-2 confidence scores close (e.g., `< 0.1` diff) where a confidence pick is ambiguous
- [x] Blending: keep confidence dominant (start with `0.7 * conf + 0.3 * engine_spell_quality`)
- [x] Only apply when the relevant engine(s) have `dictionary_total_words >= 10` (skip short headers/footers)
- [x] Add an ultra-conservative “Turn to <N>” phrase repair fallback for single-engine lines (records provenance; avoids changing prose)

**Key Files**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Modify `_choose_fused_line()` (lines ~1956-2049)

### Task 3: Character-Level Fusion Enhancement

- [x] Extend `fuse_characters()` with **token-aware** tie-breaking on alpha-only edits (lines ~1619-1714)
- [x] Prefer candidates that improve “word-likeness” (dictionary membership) *only when exactly one candidate is OOV* under the default wordlist (avoid over-triggering on proper nouns)
- [x] Add a generic special-case for common OCR ligature confusions when observed by alignment (e.g., `m` vs `rn` within a word) if dictionary checks are inconclusive (**deferred pending evidence; do not auto-fix without strong proof**)
- [x] Keep this behind the same knob as Task 2 until validated on a baseline run

**Key Files**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`: Modify `fuse_characters()` (lines ~1619-1714)

### Task 4: Testing & Validation

- [x] Baseline vs. new comparison run on the same input/settings; record run_ids in the Work Log
- [x] Test pages with known digit confusion ("Turn t0 157" → "Turn to 157") on the 20-page sample (observed real `t0->to` repairs)
- [ ] Test pages with common OCR word-shape typos (e.g., `m` vs `rn` cases like "Tum to" → "Turn to") beyond the 20-page sample
- [x] Measure quality improvement by baseline vs. spell-on diff on the 20-page sample (turn-to instruction errors reduced)
- [x] Verify no performance degradation (steady-state): recorded `engine_spell_metrics_ms` and `turn_to_phrase_repair_ms` in artifacts; p95 < 5ms/page-side after warm-up
- [x] Run regression helpers: `scripts/regression/check_suspicious_tokens.py` stayed flat on sample (consider adding `check_escalation_summary.py` once a full recipe run is performed)

### Task 5: Unit Tests

- [x] Add unit tests for phrase repair and dictionary tiebreak safety
- [x] Cover regression guard: avoid TitleCase proper noun corruption (e.g., `Iain` must not become `lain`)

### Task 6: Push Gamebook-Specific Normalization Downstream

- [x] Implement tolerant choice extraction in `modules/extract/extract_choices_v1/main.py` so it can recognize OCR variants (`tum`, `t0/tO`, digit confusions) without requiring OCR-stage text mutation
- [x] Make OCR-stage “Turn to <N>” phrase repair opt-in (default **off**) via `enable_navigation_phrase_repair` so upstream OCR can remain reusable across book types
- [x] (Optional / deferred) Add a dedicated adapter `normalize_navigation_phrases_v1` (recipe-scoped to gamebooks) if we still want normalized text for LLM stages; **deferred** because `extract_choices_v1` is now tolerant and OCR stays generic-by-default; revisit under story-075 if we want “display-clean” text without touching OCR outputs
- [x] Re-run 20-page pipeline through `extract_choices_v1` with OCR-stage phrase repair disabled and manually validate extracted choices match all `turn to <N>` references in text

---

## Expected Benefits

- **Better tiebreaking**: When confidence scores are ambiguous, spell quality breaks ties
- **Automatic digit confusion detection**: Handles l↔1, o↔0, s↔5 substitutions
- **Reduced character fusion errors**: Prefer word-shape-correct tokens (e.g., `m` vs `rn`) when evidence supports it
- **1-2% quality improvement**: Measurable improvement with minimal risk
- **Low performance cost**: ~3-4ms per page (negligible compared to OCR time)

---

## Implementation Notes

**Key Files to Modify**:
- `modules/extract/extract_ocr_ensemble_v1/main.py`:
  - Compute per-engine spell metrics after outlier detection (single-column path ~2690-2750; column path ~2818-2855)
  - Thread `engine_spell_quality` through `align_and_vote()`/`_align_and_vote_multi()` into `_choose_fused_line()` (lines ~1957-2049)
  - Extend `fuse_characters()` with token-aware tie-breaks (lines ~1620-1715)
- `modules/common/text_quality.py`: Already has `spell_garble_metrics()` - no changes needed

**Approach**:
1. Compute per-engine spell metrics for non-outlier engines and derive a stable `engine_spell_quality` weight
2. Gate spell-weighted voting behind a module knob for baseline comparison (`enable_spell_weighted_voting`)
3. Use spell quality only as a conservative tiebreaker (confidence remains dominant; never override majority exact matches)
4. Add token-aware character fusion tie-breaks only when they reduce clear OOV/ligature confusions

**Testing Strategy**:
- Baseline vs. new comparison run on the same settings/input; record run_ids and inspected artifacts in the Work Log
- Integration tests on known OCR error patterns (digit confusion + word-shape errors)
- Regression checks via existing scripts in `scripts/regression/`
- Performance benchmarks to verify < 5ms overhead

---

## Tradeoffs

- **Performance**: Small cost (~3-4ms per page) for 3-4 extra calls to `spell_garble_metrics()`
- **False positives**: Proper nouns (Zanbar, Deathtrap) may trigger OOV warnings → mitigated by using OOV ratio threshold
- **Weighting**: May need tuning of confidence vs spell quality weighting (start conservative: 70/30)

---

## References

- `docs/ocr-ensemble-fusion-algorithm.md`: Fusion algorithm details
- `modules/common/text_quality.py`: `spell_garble_metrics()` implementation
- Story-063: OCR Ensemble Three-Engine Voting (fusion algorithm)
- Story-069: PDF Text Extraction Engine (fusion documentation)

---

## Work Log
### 20251221-1605 — Marked obsolete
- **Result:** Success.
- **Notes:** Superseded by GPT‑5.1 HTML‑first OCR pipeline; ensemble voting no longer on critical path. Keep as historical reference only.
- **Next:** None.

### 2025-12-19 — Story Created
- **Context**: Extracted from Story-070 Priority 6 (Spell-Weighted Voting Enhancement)
- **Rationale**: Spell-weighted voting is unrelated to page splitting, deserves its own story
- **Status**: Ready to implement
- **Next**: Implement per-engine spell metrics computation and integrate into voting cascade

### 20251217-2236 — Verified story format; tightened checklist for real code paths
- **Result:** Success; Tasks now match current `spell_garble_metrics()` keys and the actual single/column voting call sites.
- **Notes:** Kept spell weighting gated behind a knob pending baseline-vs-new comparison to reduce regression risk.
- **Next:** Implement Task 1 (engine_spell_metrics + derived weight) in `modules/extract/extract_ocr_ensemble_v1/main.py`, then run a small baseline comparison run and inspect `01_extract_ocr_ensemble_v1/pages_raw.jsonl` for per-engine metrics + improved line picks.

### 20251217-2240 — Aligned Implementation Notes with updated tasks
- **Result:** Success; removed stale line-number references and clarified the gating/validation approach to match the checklist.
- **Notes:** Expectation is “confidence-first” with spell quality as a strict tiebreaker, not a primary selector.
- **Next:** Start implementation with a minimal, fully-instrumented pass: compute metrics, persist them in per-page artifacts, then wire into `_choose_fused_line()` behind the knob.

### 20251217-2250 — Implemented spell-weighted voting + dict-aware char fusion (conservative/SOTA-style)
- **Result:** Success; added per-engine spell metrics + derived quality weights, threaded into multi-engine voting as a tiebreaker, and enabled dictionary-aware character fusion when spell weighting is on.
- **Notes:** Implemented as rescoring/tiebreak only (never overrides majority exact matches; only triggers when confidence is ambiguous and `dictionary_total_words >= spell_min_total_words`).
- **Next:** Run a small baseline-vs-new extraction (same pages/settings) and inspect `output/runs/<run_id>/01_extract_ocr_ensemble_v1/pages_raw.jsonl` to confirm `engine_spell_metrics`/`engine_spell_quality` are present and that known “skilI→skill”/digit-confusion cases improve without regressions.

### 20251217-2257 — Ran baseline vs spell-on intake; inspected artifacts
- **Result:** Success; baseline and spell-on runs completed and produced stamped `pages_raw.jsonl`.
- **Notes:** Compared `/tmp/cf-spell-weighted-voting-baseline-21-26/01_extract_ocr_ensemble_v1/pages_raw.jsonl` vs `/tmp/cf-spell-weighted-voting-test-21-26/01_extract_ocr_ensemble_v1/pages_raw.jsonl`:
  - `engines_raw.engine_spell_metrics`/`engines_raw.engine_spell_quality` present on non-empty pages in spell-on run.
  - Observed at least one per-line provenance shift on page 23L (`fusion_sources[1]` changed `apple→tesseract`) with identical output text ("27"), confirming the tiebreak plumbing activates without forcing text changes.
- **Next:** Find a small page set with real “skilI/Turn t0” style disagreements and re-run to confirm actual text improvements (not just provenance), then run `scripts/regression/check_suspicious_tokens.py` over the run outputs.

### 20251217-2307 — Ran 20-page intake smoke; verified manual text fix on real sample
- **Result:** Success; reran the 20-page sample intake and confirmed the intended “Tum→Turn” repair happens in output text.
- **Notes:** `/tmp/cf-spell-weighted-voting-smoke-20/01_extract_ocr_ensemble_v1/pages_raw.jsonl` contained `Tum to 16` (page 20R, line 30). After adding the conservative phrase repair and rerunning:
  - `/tmp/cf-spell-weighted-voting-smoke-20-v2/01_extract_ocr_ensemble_v1/pages_raw.jsonl` has **0** “Tum” occurrences.
  - `engines_raw.turn_to_phrase_repairs` includes `Tum to 16 → Turn to 16` (page 20R) and `tum to 395 → turn to 395` (page 17R), with per-line indices recorded.
- **Next:** Add a baseline-vs-new metric summary on a larger (but still bounded) page set and confirm no false-positive phrase repairs on non-gamebook pages; then consider whether to add `t0→to` repairs (same pattern) when observed.

### 20251217-2315 — Audited “spell kicked in” across 20 pages; fixed confidence-source bug
- **Result:** Mixed; improved real “turn-to” phrasing cases, but found additional non-instruction “tum” and fixed a voting provenance bug.
- **Notes:** Reran 20 pages with the latest code: `/tmp/cf-spell-weighted-voting-smoke-20-v3/01_extract_ocr_ensemble_v1/pages_raw.jsonl`.
  - Found a remaining `tum` in prose (`"I'll tum"`, page 19L) which is *not* in the safe `turn to <N>` pattern and is intentionally not auto-corrected to avoid false positives.
  - Replay analysis (re-running the voter with spell off vs on using stored `engines_raw`) showed spell/dict logic changes voting on 2/40 page-sides (source changes) and changes actual fused text on 1 page-side (minor `eover→cover`, `thac→that`).
  - Found and fixed a bug where `_pick_confidence_with_spell()` returned `(conf, eng, txt)` in one branch, causing non-string `fusion_sources` entries (e.g., `1.0`). After fix, `/tmp/cf-spell-weighted-voting-smoke-20-v3/01_extract_ocr_ensemble_v1/pages_raw.jsonl` has 0 non-string `fusion_sources`.
- **Next:** Decide if we want a second ultra-conservative phrase repair for non-instruction “tum→turn” (likely **no**, unless we can prove it’s safe), and add explicit per-line “spell tiebreak used” markers to artifacts so audits don’t require replay scripts.

### 20251218-0806 — Validated with 20-page sample + EasyOCR; added tests and perf counters
- **Result:** Success; easyocr-inclusive baseline vs spell-on run shows only safe instruction fixes, with no detected text regressions.
- **Evidence:** Compared `/tmp/cf-spell-weighted-voting-smoke-20-easyocr-off-v2/01_extract_ocr_ensemble_v1/pages_raw.jsonl` vs `/tmp/cf-spell-weighted-voting-smoke-20-easyocr-on-v2/01_extract_ocr_ensemble_v1/pages_raw.jsonl`:
  - Text diffs limited to `tum/Tum` and `t0` repairs in `Turn to <N>` instructions (7 line diffs across 3 page-sides).
  - `scripts/regression/check_suspicious_tokens.py` stayed flat: mixed=3, vowel_less=1 on both runs.
  - Performance telemetry present: p95 `engine_spell_metrics_ms` ~4.3ms, p95 `turn_to_phrase_repair_ms` ~0.06ms (max includes first-call wordlist load).
  - Fixed a proper-noun regression risk by preventing TitleCase initial-letter dict tiebreak (`Iain` must not become `lain`).
  - Added unit tests in `tests/test_spell_weighted_voting.py` and ran them.
- **Next:** Decide whether to implement the optional `m` vs `rn` ligature rule (currently unchecked), and optionally emit a per-line `spell_tiebreak_used` marker for easier audits.

### 20251218-0839 — Audited FF-specificity and proposed downstream migration plan
- **Result:** Success; documented which modules contain FF/gamebook-specific logic and proposed how to push navigation normalization downstream so OCR stays reusable.
- **Evidence:** Added `docs/pipeline/ff-specificity-audit.md`.
- **Next:** If we agree with the direction, implement option A (tolerant parsing in `extract_choices_v1`) and/or option B (new adapter `normalize_navigation_phrases_v1`) and update the canonical FF recipe accordingly.

### 20251218-0842 — Added explicit “generic OCR, downstream specialization” requirement
- **Result:** Success; added a story requirement to push booktype/gamebook normalization downstream for reusability.
- **Notes:** Updated story Success Criteria + Tasks to include a dedicated “push normalization downstream” task for `extract_choices_v1` (and optional adapter).
- **Next:** Implement tolerant parsing in `modules/extract/extract_choices_v1/main.py` and verify that we can disable/remove OCR-stage phrase repair without losing choice extraction accuracy.

### 20251218-0852 — Implemented tolerant choice parsing (moves “Turn to” normalization downstream)
- **Result:** Success; `extract_choices_v1` now recognizes common OCR variants (`tum`, `t0/tO`, `1S7`) without requiring OCR-stage text mutation.
- **Evidence:** Updated `modules/extract/extract_choices_v1/main.py` and added tests in `tests/test_extract_choices_tolerant.py` (ran via `pytest -q tests/test_extract_choices_tolerant.py tests/test_spell_weighted_voting.py`).
- **Next:** Wire the canonical FF recipe to rely on tolerant parsing and consider removing OCR-stage phrase repair once downstream validation confirms no coverage loss.

### 20251218-0918 — Added 20-page settings for downstream choice validation
- **Result:** Success; added `configs/settings.ff-canonical-smoke-choices-20.yaml` to run the canonical recipe on pages 1–20 with EasyOCR enabled and relaxed boundary gates so we can reach `extract_choices_v1` for end-to-end validation.
- **Notes:** Corrected story metadata date (`Created: 2025-12-18`) to match actual work date.
- **Next:** Rerun the 20-page pipeline to `extract_choices` and manually inspect `portions_with_choices.jsonl` for real “Turn to <N>” cases and OCR-variant normalization behavior.

### 20251218-1030 — Ran 20-page pipeline through `extract_choices_v1` and inspected artifacts
- **Result:** Success; verified the new code path runs end-to-end on the 20-page sample and extracted choices match all “turn to <N>” refs in the extracted text.
- **Evidence (run with phrase repair enabled)**: `/tmp/cf-ff-smoke-20-choices-20251218-2/01_extract_ocr_ensemble_v1/pages_raw.jsonl` contains `engines_raw.turn_to_phrase_repairs` (4 repairs on page 20R, e.g. `Tum t0 16 → Turn to 16`). `/tmp/cf-ff-smoke-20-choices-20251218-2/28_extract_choices_v1/portions_with_choices.jsonl` has section `23` with 23 extracted choices and 0 missing when compared to all `turn to <N>` refs in text.
- **Notes:** `engine_spell_metrics` and `engine_spell_metrics_ms` present on all 40 page-sides (validated programmatically); observed non-trivial `engine_spell_quality` differences across many pages.
- **Next:** Make the OCR-stage navigation phrase repair opt-in so OCR stays generic, then rerun the same check with phrase repair disabled.

### 20251218-1105 — Made OCR navigation phrase repair opt-in and revalidated downstream extraction
- **Result:** Success; OCR-stage navigation phrase repair is now gated behind `enable_navigation_phrase_repair` (default off), and downstream choice extraction still matches all `turn to <N>` refs on the 20-page sample when repair loop is disabled.
- **Evidence:** `/tmp/cf-ff-smoke-20-choices-20251218-4/01_extract_ocr_ensemble_v1/pages_raw.jsonl` has 0 `turn_to_phrase_repairs` rows. `/tmp/cf-ff-smoke-20-choices-20251218-4/28_extract_choices_v1/portions_with_choices.jsonl` section `23` has 23 extracted choices and 0 missing vs. `turn to <N>` refs in text.
- **Notes:** Added `configs/settings.ff-canonical-smoke-choices-20-norepair.yaml` to keep text unmodified during this validation run (so `repair_portions_v1` does not re-transcribe and potentially change section scope).
- **Next:** Do a dedicated end-to-end validation that exercises tolerant parsing on real OCR variants (e.g., ensure `tum/t0` appears in `strip_numbers` input when OCR repair is disabled), or add a recipe-scoped downstream normalization adapter if we want corrected display text without modifying OCR outputs.

### 20251218-1120 — Refreshed FF-specificity audit after making OCR repair opt-in
- **Result:** Success; updated `docs/pipeline/ff-specificity-audit.md` to reflect that navigation phrase repair in `extract_ocr_ensemble_v1` is now opt-in (default off).
- **Next:** Keep the audit updated as we continue pushing gamebook/FF heuristics downstream.

### 20251218-1213 — Deferred `normalize_navigation_phrases_v1` adapter from story-072
- **Result:** Success.
- **Notes:** Marked the optional adapter as deferred/not needed for story-072 since choice extraction now tolerates OCR variants and OCR navigation repair is opt-in; any future “display-clean” normalization should live as a recipe-scoped adapter under story-075.
- **Next:** Decide whether to implement an `m`↔`rn` ligature heuristic (only if we can prove it’s safe and actually appears in failures not solved by current spell/dict tiebreaking).

### 20251218-1213 — Deferred `m`↔`rn` ligature auto-fix (pending evidence)
- **Result:** Success.
- **Notes:** Marked the `m`↔`rn` ligature special-case as deferred. This is a known OCR failure mode, but a generic auto-fix is high-risk under the 100% accuracy requirement; we’ll only add it if repeated real failures show it’s safe, bounded, and improves outcomes without corrupting names/prose.
- **Next:** If we observe recurring `rn`/`m` confusions that the current voter/dictionary tie-break cannot resolve, implement it as a *profiled* downstream cleanup (story-075) with explicit patch logs first.
