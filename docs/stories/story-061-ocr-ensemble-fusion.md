# Story: OCR Ensemble Fusion Improvements

**Status**: Open
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
- [ ] Apple OCR is never discarded at document level
- [ ] Per-line fusion still respects distance threshold
- [ ] `apple_dropped` flag removed or repurposed to track per-line drops

### R2: Implement Character-Level Voting Within Lines

**Problem**: Current line selection is binary (pick primary or alt based on length)

**Solution**: For lines where both engines produce similar-length output but disagree on specific characters, implement character-level voting:

1. Align characters within the line using edit distance alignment
2. For each position, if engines agree, use that character
3. For disagreements, use confidence scores or voting (with 3 engines)

**Acceptance Criteria**:
- [ ] Character alignment function implemented
- [ ] Per-character voting when engines disagree
- [ ] Demonstrated improvement on test cases like "sTAMINA" vs "STAMINA"

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

### R4: Implement Levenshtein Distance Outlier Detection

**Problem**: No mechanism to detect when one engine produces garbage

**Solution**: Before fusion, compute pairwise Levenshtein distances between engine outputs:

1. Calculate distance between each pair of engines
2. Identify outlier results (distance > threshold from best pair)
3. Exclude outliers from voting

**Acceptance Criteria**:
- [ ] Pairwise distance calculation implemented
- [ ] Outlier detection with configurable threshold
- [ ] Outlier engine excluded from fusion for that page/line

### R5: Add Confidence-Weighted Selection

**Problem**: No use of OCR confidence scores in fusion

**Solution**: Where available, use engine confidence scores to weight voting:

1. Apple Vision provides per-recognition confidence
2. Tesseract can provide word-level confidence
3. Weight character/word votes by confidence

**Acceptance Criteria**:
- [ ] Extract confidence from Apple Vision output
- [ ] Extract confidence from Tesseract (if available)
- [ ] Confidence-weighted voting implemented

### R6: Inline Escalation for Critical Failures

**Problem**: Pages flagged for escalation still output poor-quality text

**Solution**: For pages meeting critical failure criteria, trigger GPT-4V escalation inline:

1. Define critical failure: corruption_score > 0.8 OR disagree_rate > 0.8
2. Call vision model immediately for these pages
3. Replace OCR output with vision model output

**Acceptance Criteria**:
- [ ] Critical failure threshold configurable
- [ ] Inline escalation calls vision model
- [ ] Budget tracking for inline escalation
- [ ] Pages marked as escalated in output

## Tasks

### Phase 1: Fix Apple OCR Handling
- [ ] Remove document-level discard check (lines 1104-1110)
- [ ] Always run `align_and_vote()` for available engines
- [ ] Update logging to track per-line source selection
- [ ] Run regression test on 20-page dataset

### Phase 2: Enable EasyOCR
- [ ] Implement fixes from story-055-easyocr-reliability.md
- [ ] Add warmup/retry logic
- [ ] Verify 3-engine output on full book
- [ ] Update histogram to show EasyOCR contribution

### Phase 3: Improve Fusion Algorithm
- [ ] Implement character-level alignment within lines
- [ ] Add Levenshtein distance outlier detection
- [ ] Implement voting with 3 engines
- [ ] Add confidence weighting (where available)

### Phase 4: Inline Escalation
- [ ] Define critical failure thresholds
- [ ] Implement inline vision model call
- [ ] Add budget tracking
- [ ] Test on high-disagreement pages

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
