# Story: Post-OCR Text Quality & Error Correction

**Status**: Open  
**Created**: 2025-12-09  
**Parent Story**: story-054 (canonical recipe - COMPLETE)

## Goal
Improve post-OCR text quality by adding spell-check, character confusion detection, and context-aware error correction. Address OCR errors that slip through because engines agree (both wrong) or because errors aren't detected by current quality metrics.

## Success Criteria
- [ ] Spell-check integrated into quality metrics to catch obvious OCR errors
- [ ] Character confusion detection catches common OCR errors (K↔x, I↔r, O↔0, l↔1)
- [ ] Escalation logic considers absolute quality, not just engine disagreement
- [ ] Context-aware post-processing available (BERT/T5) for fixing fragmented sentences
- [ ] OCR errors like "sxrLL", "otk", "y0u 4re f0110win9" are caught and corrected

## Context

**Issues Identified** (from artifact analysis - see `docs/artifact-issues-analysis.md`):

1. **Page 007L - OCR Error "sxrLL" Not Escalated**
   - Text contains "sxrLL" instead of "SKILL"
   - Source: `tesseract` (single column, not escalated)
   - `needs_escalation: False`, `disagree_rate: 0.0` (engines agreed, but both were wrong)
   - **Root Cause**: Escalation only triggers on disagreement, not absolute quality; no spell-check

2. **Page 001R - OCR Error "otk" Not Escalated**
   - Text contains "otk" (likely "book" or similar)
   - Source: `tesseract`
   - `needs_escalation: False`
   - **Root Cause**: Short line fragment not caught; no spell-check to catch nonsensical words

3. **Page 019R - Character Confusion Errors**
   - Text contains: "y0u 4re f0110win9 5t4rt t0 peter 0ut 45."
   - Leetspeak-like errors: "y0u" (you), "4re" (are), "f0110win9" (following), "5t4rt" (start), "t0" (to), "45" (as)
   - **Root Cause**: OCR confused letters with numbers (o→0, l→1, s→5, a→4)

4. **Page 018L - Incomplete Section Number**
   - Text starts with "in 4" instead of "4"
   - Section number partially OCR'd
   - **Root Cause**: OCR merged "4" with preceding text; no post-processing to extract section numbers

**Root Causes**:
- Escalation only triggers on engine disagreement, not absolute quality
- No dictionary/spell-check validation
- No character-level error detection (confusing similar characters)
- Quality metrics focus on structure (fragmentation, corruption patterns) not content accuracy
- No post-processing to correct common OCR confusions

## Tasks

### High Priority

- [ ] **Add Spell-Check to Quality Metrics**
  - **Issue**: OCR errors like "sxrLL" (SKILL), "otk" not caught by escalation
  - **Root Cause**: Escalation only triggers on engine disagreement, not absolute quality; no spell-check
  - **Mitigations**:
    - Add spell-check to quality metrics: use dictionary/spell-checker to detect obvious OCR errors
    - Character confusion detection: detect common OCR confusions (K↔x, I↔r, O↔0, l↔1)
    - Context-aware error detection: use language model to detect nonsensical words in context
    - Escalate on absolute quality: don't just escalate on disagreement - escalate on low absolute quality
    - Post-OCR correction: add spell-check/correction pass after OCR (but preserve original)

- [ ] **Improve Escalation Logic**
  - **Issue**: Pages with OCR errors not escalated because engines agreed (both wrong)
  - **Root Cause**: Escalation relies on `disagree_rate` - if engines agree, no escalation
  - **Mitigations**:
    - Escalate on absolute quality: add spell-check, character confusion detection, fragmentation detection
    - Don't just escalate on disagreement: escalate on low absolute quality even when engines agree
    - Add quality score threshold: escalate if quality_score < threshold regardless of disagreement
    - Integrate spell-check results into quality_score calculation

- [ ] **Character Confusion Correction**
  - **Issue**: OCR errors like "y0u 4re f0110win9" (you are following) - leetspeak-like errors
  - **Root Cause**: OCR confused letters with numbers (o→0, l→1, s→5, a→4)
  - **Mitigations**:
    - Character confusion correction: post-process common OCR confusions (0↔o, 1↔l, 5↔s, 4↔a)
    - Context-aware correction: use language model to correct based on context
    - Spell-check: run spell-check and suggest corrections
    - Apply corrections while preserving original text

### Medium Priority

- [ ] **Implement Context-Aware Post-Processing**
  - Use BERT/T5 for context-aware spell checking and missing word prediction
  - Fix fragmented sentences: "ha them" → "have nothing of any use to you on them"
  - Add to `reconstruct_text_v1` or new post-processing module
  - Only escalate if post-processing fails
  - **Research**: See `docs/ocr-post-processing-research.md` for SOTA techniques

- [ ] **Section Number Extraction**
  - **Issue**: Page 018L has "in 4" instead of "4" - section number partially OCR'd
  - **Root Cause**: OCR merged "4" with preceding text; no post-processing to extract section numbers
  - **Mitigations**:
    - Section number extraction: after OCR, extract section numbers even if merged with text
    - Fuzzy matching: when looking for section numbers, use fuzzy matching
    - Context-aware extraction: use LLM to identify section numbers in context

- [ ] **Incomplete Text Detection**
  - **Issue**: Some lines end mid-sentence (may be legitimate page breaks or OCR truncation)
  - **Root Cause**: Need to distinguish between legitimate page breaks and OCR truncation
  - **Mitigations**:
    - Context validation: use LLM to check if text is complete or truncated
    - Cross-page validation: check if next page continues the sentence
    - Flag suspicious truncations: if line ends mid-word or mid-sentence without page break marker, flag

### Low Priority

- [ ] **Add Spell/Dictionary IVR Metric**
  - Per page/engine spell-check score
  - Log deltas to guide engine choice/escalation
  - Detect anomalies (e.g., one engine has much higher spell-check score)

- [ ] **Post-OCR Semantic Correction**
  - LLM-based post-processing for known error patterns
  - Fine-tuned language models (ByT5) for semantic-aware correction
  - Apply corrections while preserving original OCR text

## Related Work

**Previous Improvements** (from story-054):
- ✅ Text reconstruction integrated (`reconstruct_text_v1`)
- ✅ Hyphen-aware merging implemented
- ✅ Fragmented text guard added
- ✅ Enhanced quality assessment with corruption pattern detection
- ✅ Escalation bug fixed (needs_escalation flag now accurate)

**Research Completed**:
- See `docs/ocr-post-processing-research.md` for SOTA techniques
- See `docs/artifact-issues-analysis.md` for comprehensive artifact analysis
- See `docs/ocr-issues-analysis.md` for detailed OCR issue analysis

## Work Log

### 2025-12-09 — Story created from story-054
- **Context**: Story-054 (canonical recipe) is complete. Post-OCR text quality improvements were identified as separate domain concerns.
- **Action**: Extracted post-OCR text quality & error correction tasks from story-054 into this focused story.
- **Scope**: Focus on spell-check, character confusion detection, context-aware correction, and improving escalation logic to consider absolute quality.
- **Next**: Implement spell-check integration into quality metrics, add character confusion detection, improve escalation logic.

