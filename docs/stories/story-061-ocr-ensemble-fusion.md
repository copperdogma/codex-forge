# Story: OCR Ensemble Fusion Improvements

**Status**: Done
**Created**: 2025-12-09
**Parent Story**: story-057 (OCR quality - COMPLETE)

## Goal

Improve OCR output quality by implementing smarter multi-engine fusion strategies. Replace the current conservative "discard if >35% divergent" approach with SOTA techniques that align and fuse text from multiple OCR engines (Tesseract, Apple Vision, EasyOCR) to produce higher-quality output.

## Background

### Current Problems

1. **Apple OCR discarded too aggressively**: When whole-document similarity diverges >35%, Apple OCR is dropped entirely (lines 1104-1110 in `main.py`). This happens on 57.5% of pages (23/40 in test run).

2. **Line-level fusion underutilized**: The `align_and_vote()` function already does per-line voting, but it only runs if Apple wasn't dropped at document level.

3. **EasyOCR not running**: The third engine (EasyOCR) is configured in defaults but fails on full runs due to language/model issues (see story-055-easyocr-reliability.md).

4. **No inline escalation**: When engines disagree significantly, pages are flagged for later escalation but not re-OCR'd immediately. This means poor-quality text passes through.

### SOTA Research Findings

Academic research and production systems use these fusion strategies:

1. **Consensus Sequence Voting** ([Lopresti & Zhou, 1997](https://www.semanticscholar.org/paper/Using-Consensus-Sequence-Voting-to-Correct-OCR-Lopresti-Zhou/e17d8b64d137e904fa611b7be082090f5cbe0625))
   - Scanning a page 3x and running consensus voting eliminates 20-50% of OCR errors
   - Character-level alignment with voting across multiple sources

2. **ROVER (Recognizer Output Voting Error Reduction)** ([NIST](https://www.researchgate.net/publication/2397671_A_Post-Processing_System_To_Yield_Reduced_Word_Error_Rates_Recognizer_Output_Voting_Error_Reduction_ROVER))
   - Combines multiple recognizer outputs into a word transition network via dynamic programming alignment
   - Voting process selects output with lowest error score
   - Used in speech recognition, applicable to OCR

3. **Multiple Sequence Alignment (MSA)** ([rafelafrance/ocr_ensemble](https://github.com/rafelafrance/ocr_ensemble))
   - Adapts bioinformatics MSA algorithms with visual similarity scoring
   - Uses Levenshtein distance outlier detection to filter bad results
   - Keeps best-scoring pair, removes outliers, then aligns survivors

4. **Progressive Alignment with Naive Bayes** ([Adaptive Combination of Commercial OCR Systems](https://link.springer.com/chapter/10.1007/978-3-540-24642-8_8))
   - Achieved 2.59% absolute gain over best single engine
   - Starts with two most similar sequences, extends progressively
   - Character selection via trained classifier

5. **Calamari Ensemble** (from research)
   - Confidence-based voting at each time-step
   - If one model misreads due to noise but others agree, wrong one is outvoted
   - Reduces character error rates by 30-50%

6. **Engine Complementarity** ([OCR Engine Comparison](https://medium.com/swlh/ocr-engine-comparison-tesseract-vs-easyocr-729be893d3ae))
   - Tesseract excels at alphabet recognition
   - EasyOCR excels at number recognition
   - Different engines have different failure modes → fusion can leverage both

### Current Fusion Logic

The existing `align_and_vote()` function (lines 843-887):
```python
def align_and_vote(primary_lines, alt_lines, distance_drop=0.35):
    # Uses SequenceMatcher to align line lists
    # For each aligned pair:
    #   - If distance > 0.35, use primary (Tesseract)
    #   - Else pick longer trimmed line
    # Returns fused lines, sources, distances
```

**Weaknesses**:
- Only picks "longer" line, not necessarily "better" line
- No character-level voting within lines
- No confidence weighting
- Discards alt (Apple) entirely if document-level similarity <65%

## Requirements

### R1: Remove Document-Level Apple OCR Discard

**Problem**: Lines 1104-1110 discard Apple OCR entirely when document similarity <65%

**Solution**: Always run `align_and_vote()` regardless of document-level similarity. The per-line threshold (0.35) already protects against bad merges.

**Acceptance Criteria**:
- [x] Apple OCR is never discarded at document level ✅
- [x] Per-line fusion still respects distance threshold ✅
- [x] `apple_dropped` flag removed or repurposed to track per-line drops ✅ (replaced with `apple_doc_similarity`)

### R2: Implement Character-Level Voting Within Lines

**Problem**: Current line selection is binary (pick primary or alt based on length)

**Solution**: For lines where both engines produce similar-length output but disagree on specific characters, implement character-level voting:

1. Align characters within the line using edit distance alignment
2. For each position, if engines agree, use that character
3. For disagreements, use confidence scores or voting (with 3 engines)

**Acceptance Criteria**:
- [x] Character alignment function implemented ✅ (`fuse_characters()`)
- [x] Per-character voting when engines disagree ✅
- [x] Demonstrated improvement on test cases like "sTAMINA" vs "STAMINA" ✅ (test passes)

### R3: Enable EasyOCR as Third Engine

**Problem**: EasyOCR fails on full runs (see story-055-easyocr-reliability.md)

**Solution**: Fix EasyOCR initialization issues to enable 3-engine voting:

1. Force language to `en` for all pages
2. Add warmup step before page loop
3. Retry with `download_enabled=True` on error

**Acceptance Criteria**:
- [ ] EasyOCR runs successfully on full book (113 pages)
- [ ] `engines_raw` includes `easyocr` text for ≥95% of pages
- [ ] Three-engine voting produces better results than two-engine

**Status**: ⏸️ DEFERRED to story-063 (requires story-055 EasyOCR reliability first)

### R4: Implement Levenshtein Distance Outlier Detection

**Problem**: No mechanism to detect when one engine produces garbage

**Solution**: Before fusion, compute pairwise Levenshtein distances between engine outputs:

1. Calculate distance between each pair of engines
2. Identify outlier results (distance > threshold from best pair)
3. Exclude outliers from voting

**Acceptance Criteria**:
- [x] Pairwise distance calculation implemented ✅
- [x] Outlier detection with configurable threshold ✅ (default 0.6)
- [x] Outlier engine excluded from fusion for that page/line ✅

### R5: Add Confidence-Weighted Selection

**Problem**: No use of OCR confidence scores in fusion

**Solution**: Where available, use engine confidence scores to weight voting:

1. Apple Vision provides per-recognition confidence
2. Tesseract can provide word-level confidence
3. Weight character/word votes by confidence

**Acceptance Criteria**:
- [x] Extract confidence from Apple Vision output ✅ (already in apple_helper.swift)
- [ ] Extract confidence from Tesseract (if available) — DEFERRED to story-063
- [x] Confidence-weighted voting implemented ✅

### R6: Inline Escalation for Critical Failures

**Problem**: Pages flagged for escalation still output poor-quality text

**Solution**: For pages meeting critical failure criteria, trigger GPT-4V escalation inline:

1. Define critical failure: corruption_score > 0.8 OR disagree_rate > 0.8
2. Call vision model immediately for these pages
3. Replace OCR output with vision model output

**Acceptance Criteria**:
- [x] Critical failure threshold configurable ✅ (`--critical-corruption-threshold`, `--critical-disagree-threshold`)
- [x] Inline escalation calls vision model ✅ (`inline_vision_escalate()`)
- [x] Budget tracking for inline escalation ✅ (`--inline-escalation-budget`)
- [x] Pages marked as escalated in output ✅ (`inline_escalated` flag)

## Tasks

### Phase 1: Fix Apple OCR Handling
- [x] Remove document-level discard check (lines 1104-1110) ✅
- [x] Always run `align_and_vote()` for available engines ✅
- [x] Update logging to track per-line source selection ✅
- [x] Run regression test on 20-page dataset ✅

### Phase 2: Enable EasyOCR — ⏸️ DEFERRED to story-063
- [ ] Implement fixes from story-055-easyocr-reliability.md
- [ ] Add warmup/retry logic
- [ ] Verify 3-engine output on full book
- [ ] Update histogram to show EasyOCR contribution

### Phase 3: Improve Fusion Algorithm
- [x] Implement character-level alignment within lines ✅
- [x] Add Levenshtein distance outlier detection ✅
- [ ] Implement voting with 3 engines (requires R3) — DEFERRED to story-063
- [x] Add confidence weighting (where available) ✅

### Phase 4: Inline Escalation
- [x] Define critical failure thresholds ✅
- [x] Implement inline vision model call ✅
- [x] Add budget tracking ✅
- [ ] Test on high-disagreement pages — DEFERRED to story-063

### Phase 5: Quality Refinements (from manual inspection)

#### Task 5.1: Lower Critical Failure Thresholds for Form Pages ✅
**Problem**: Current thresholds (corruption > 0.8, disagree_rate > 0.8) are too high. Form pages like Adventure Sheets have severe OCR errors ("ADVENCURE SEEEC", "Shit =") but don't trigger inline escalation because corruption_score=0.

**Solution**:
- Add form page detection to `is_critical_failure()` check
- Lower thresholds for pages detected as forms (corruption > 0.3 or disagree_rate > 0.5)
- Consider IVR (in-vocab ratio) as additional signal - form pages have very low IVR

**Acceptance Criteria**:
- [x] Form pages with severe OCR errors trigger inline escalation ✅
- [x] Non-form pages still use conservative thresholds ✅
- [x] Test with Adventure Sheet page (011R) ✅

#### Task 5.2: Filter Two-Column Fragment Artifacts ✅
**Problem**: Two-column pages like 007L produce fragment artifacts ("his", "LL.", "ured", "ser") from right-column word endings being read separately. These fragments pollute the output.

**Solution**:
- Detect and filter very short lines (< 4 chars) that appear to be fragments
- Only filter when they cluster at the end of the line list (column-edge pattern)
- Preserve legitimate short lines (e.g., "10" page numbers, "Battles" headers)

**Acceptance Criteria**:
- [x] Fragment artifacts filtered from two-column pages ✅
- [x] Legitimate short content (page numbers, headers) preserved ✅
- [x] Fragmentation score reflects post-filtering quality ✅

## Research Sources

- [Consensus Sequence Voting (Lopresti & Zhou)](https://www.semanticscholar.org/paper/Using-Consensus-Sequence-Voting-to-Correct-OCR-Lopresti-Zhou/e17d8b64d137e904fa611b7be082090f5cbe0625)
- [ROVER System (NIST)](https://www.researchgate.net/publication/2397671_A_Post-Processing_System_To_Yield_Reduced_Word_Error_Rates_Recognizer_Output_Voting_Error_Reduction_ROVER)
- [ocr_ensemble (GitHub)](https://github.com/rafelafrance/ocr_ensemble) - MSA + Levenshtein outlier detection
- [ocr_fusion (GitHub)](https://github.com/DaiHaoguang3151/ocr_fusion) - Multi-engine OCR comparison
- [BetterOCR (GitHub)](https://github.com/junhoyeo/BetterOCR) - LLM-based reconciliation
- [Post-OCR Correction with Ensembles (arXiv)](https://arxiv.org/abs/2109.06264) - Seq2seq character correction
- [Adaptive Combination of Commercial OCR Systems (Springer)](https://link.springer.com/chapter/10.1007/978-3-540-24642-8_8) - Progressive alignment

## Related Stories

- story-055-easyocr-reliability.md - EasyOCR stabilization (prerequisite for R3)
- story-057-ocr-quality-column-detection.md - Column detection (COMPLETE)
- story-037-ocr-ensemble-with-betterocr.md - Original ensemble design (COMPLETE)

## Work Log

### 2025-12-09 — Story created
- **Context**: Analysis of OCR ensemble revealed Apple OCR dropped on 57.5% of pages due to aggressive document-level similarity check. Research identified SOTA fusion techniques.
- **Findings**:
  - Current `align_and_vote()` only runs if Apple not dropped at document level
  - EasyOCR (third engine) not running due to initialization issues
  - Academic research shows 20-50% error reduction with consensus voting
  - Character-level fusion can catch errors like "sTAMINA" → "STAMINA"
- **Next**: Implement R1 (remove document-level discard) as first step

### 2025-12-10 — Implemented R1 and R2 (document-level fix + character fusion)
- **Result**: Success - major improvement in Apple OCR utilization
- **Changes**:
  1. **Added `fuse_characters()` function** (`main.py:843-909`)
     - Character-level alignment using SequenceMatcher
     - Prefers uppercase over lowercase (fixes "sTAMINA" → "STAMINA")
     - Prefers letters over digits for OCR confusions (fixes "cru5he5" → "crushes")
     - Only triggers when lines are very similar (distance ≤ 0.15)

  2. **Enhanced `align_and_vote()` function** (`main.py:912-1006`)
     - Added `enable_char_fusion` parameter (default True)
     - New source type "fused" for character-level fusion
     - New source type "agree" when engines produce identical output
     - Better handling of empty alt_lines

  3. **Removed document-level Apple discard** (`main.py:1222-1243, 1313-1333`)
     - No longer sets `apple_dropped = True` and clears alt_lines
     - Added `apple_doc_similarity` metric for logging (still useful for stats)
     - Always attempts per-line fusion regardless of document similarity
     - Updated source attribution to track "fused" contributions

  4. **Added 9 new tests** (`tests/test_ocr_quality_checks.py:357-436`)
     - `fuse_characters`: identical, case difference, digit vs letter, empty, length
     - `align_and_vote`: identical, empty alt, char fusion triggered, too different

- **Regression Test Results** (20 pages / 40 sides):

  | Metric | Before (story-057) | After (story-061) | Change |
  |--------|-------------------|-------------------|--------|
  | Apple selected | 9 pages (22.5%) | 26 pages (65%) | **+189%** |
  | Tesseract selected | 25 pages | 12 pages | -52% |
  | Fused (char-level) | 0 pages | 2 pages | New! |
  | Lines from Apple | ~22% | **56.2%** | +155% |
  | Lines where engines agree | Unknown | **20.4%** | New metric |
  | Character-level fused lines | 0 | **11 (0.7%)** | New! |

- **Sample verification**:
  - Page 6R: Shows "fused" source with proper "SKILL and STAMINA scores" text
  - Apple doc similarity now tracked (e.g., 0.978 for high agreement, 0.2 for low)
  - Mixed source selection working: lines selected from agree/primary/alt/fused as appropriate

- **All 24 tests pass**
- **Next**: Consider R3 (EasyOCR) and R4 (outlier detection) for further improvements

### 2025-12-10 — Implemented R4 (Levenshtein outlier detection)
- **Result**: Success - outlier detection function added and integrated
- **Changes**:
  1. **Added `detect_outlier_engine()` function** (`main.py:912-998`)
     - Computes pairwise Levenshtein distance between all engine outputs
     - Identifies outlier engines (avg distance > threshold, default 0.6)
     - Returns best agreeing pair, distances, and outlier list
     - Useful when 3+ engines available to detect garbage output

  2. **Integrated into main OCR flow** (`main.py:1313-1326`)
     - Runs after collecting all engine outputs
     - Records `outlier_engines`, `outlier_info` in part_by_engine
     - If engine marked as outlier, excludes from fusion
     - Added `apple_excluded_as_outlier` flag when Apple is outlier

  3. **Added 5 new tests** (`tests/test_ocr_quality_checks.py:357-414`)
     - Single engine: no outliers
     - Two similar: no outliers
     - Two very different: both can be outliers (correct behavior)
     - Three engines with one garbage: detect outlier correctly
     - Empty/error engines: properly ignored

- **R3 (EasyOCR) blocked**: numpy version conflict (numpy 2.x vs 1.x)
  - easyocr requires numpy<2 but was installed with numpy 2.x
  - Fixed by downgrading to numpy 1.26.4
  - EasyOCR dependency management deferred to story-055

- **All 29 tests pass**

### 2025-12-10 — Implemented R5 and R6 (confidence weighting + inline escalation)
- **Result**: Success - both features implemented and tested

- **R5: Confidence-Weighted Selection**:
  1. **Modified `align_and_vote()` function** (`main.py:1038-1150`)
     - Added `alt_confidences` parameter for Apple Vision confidence scores
     - High confidence (≥0.8): prefer alt line, source="alt_confident"
     - Low confidence (<0.5): prefer primary
     - Otherwise: use length heuristic
  2. **Updated all 3 callers** to extract and pass confidence from `apple_lines_meta`

- **R6: Inline Escalation for Critical Failures**:
  1. **Added `is_critical_failure()` function** (`main.py:151-185`)
     - Detects critical OCR failures requiring immediate GPT-4V escalation
     - Criteria: corruption_score > 0.8 OR disagree_rate > 0.8 OR (line_count < 3 AND missing_content > 0.7)

  2. **Added `inline_vision_escalate()` function** (`main.py:87-148`)
     - Encodes image to base64 and calls GPT-4V
     - Returns transcribed text, lines, success status
     - Lazy OpenAI client initialization

  3. **New CLI arguments** (`main.py:1316-1334`):
     - `--inline-escalation`: Enable inline GPT-4V escalation
     - `--inline-escalation-model`: Vision model to use (default: gpt-4.1)
     - `--critical-corruption-threshold`: Corruption threshold (default: 0.8)
     - `--critical-disagree-threshold`: Disagree rate threshold (default: 0.8)
     - `--inline-escalation-budget`: Max pages to escalate inline (default: 5)

  4. **Integration into main OCR flow** (`main.py:1753-1796`):
     - After quality metrics computed, check for critical failure
     - If critical and budget available, call GPT-4V inline
     - Replace OCR output with vision model output
     - Track `inline_escalated` flag in page payload and quality report

  5. **Updated histogram** (`main.py:1896-1909`):
     - Added `inline_escalated` count to source histogram

  6. **Added 7 new tests** (`tests/test_ocr_quality_checks.py:527-605`):
     - `is_critical_failure`: high corruption, high disagree, few lines + missing, normal page, moderate issues, custom thresholds

- **All 37 tests pass**
- **Next**: R3 (EasyOCR) blocked by numpy conflict - deferred to story-055

### 2025-12-10 — Implemented Phase 5 (Quality Refinements)
- **Result**: Success - both refinement tasks completed based on manual inspection findings

- **Manual Inspection Findings**:
  - Pages 002L, 005L, 006L, etc. with 100% disagree_rate are blank/sparse pages (one engine finds nothing)
  - Page 007L shows two-column fragment artifacts ("his", "LL.", "ured", etc.)
  - Page 011R (Adventure Sheet) has severe OCR errors but doesn't trigger escalation

- **Task 5.1: Lower Critical Thresholds for Form Pages**:
  1. **Enhanced `is_critical_failure()` function** (`main.py:151-204`)
     - Added `is_form_page` and `ivr` parameters
     - Form pages with very low IVR (<0.15) trigger escalation
     - Form pages with moderate disagree (>0.5) AND low IVR (<0.4) trigger escalation
     - Form pages with high fragmentation (>0.3) AND low IVR (<0.5) trigger escalation
  2. **Updated main OCR flow** (`main.py:1776-1790`)
     - Pre-computes IVR and form detection before escalation check
     - Passes `is_form_page` and `ivr` to `is_critical_failure()`
  3. **Added 3 new tests** for form page escalation thresholds

- **Task 5.2: Filter Two-Column Fragment Artifacts**:
  1. **Added `filter_fragment_artifacts()` function** (`main.py:1149-1228`)
     - Detects trailing clusters of very short lines (<4 chars)
     - Preserves page numbers (digits), common short words, empty lines
     - Only filters when 3+ fragments cluster at end (not scattered)
  2. **Integrated into main OCR flow** (`main.py:1908-1919`)
     - Runs after fusion, before creating line_rows
     - Records removed fragments in `engines_raw` for provenance
  3. **Added 6 new tests** for fragment filtering

- **All 46 tests pass**

### 2025-12-10 — Story marked DONE
- **Completed**: R1, R2, R4, R5 (partial), R6, Task 5.1, Task 5.2
- **Deferred to story-063**: R3 (EasyOCR), 3-engine voting, Tesseract confidence, inline escalation testing
- **Reason**: R3 blocked by numpy version conflict requiring story-055 (EasyOCR reliability) to be completed first
- **Deliverables**: 46 passing tests, 5 new functions, 6 CLI arguments for inline escalation
