# Story: Coarse Portionizer Endmatter Filter

**Status**: To Do  
**Created**: 2025-12-23  
**Priority**: High  
**Parent Story**: story-081 (GPT‑5.1 AI‑First OCR Pipeline)

---

## Goal

Fix the coarse portionizer to exclude endmatter content that appears on the same page as the last gameplay section. Endmatter patterns (ads, book previews, author bios) should be filtered out even when they share a page with numbered sections.

**Critical: This must be a generic Fighting Fantasy portionizer, not overfit to Deathtrap Dungeon or any specific book.** Pattern detection should be based on structural/semantic signals (running heads, book title patterns, author name patterns) that apply across FF books, not hard-coded strings specific to one book.

---

## Motivation

The coarse segmenter correctly identifies that pages containing numbered sections (1-400) belong to gameplay, even if they also contain ads/previews. However, when portionizing, all content from those pages is included, causing endmatter to leak into the final gameplay sections.

**Specific Issue:**
Section 400 includes endmatter content that should be excluded:
- The actual section 400 narrative (correct)
- An image tag (acceptable, will be handled separately)
- **Endmatter content that should be removed:**
  - `<p class="running-head">More Fighting Fantasy in Puffins</p>`
  - `<h2>1. THE WARLOCK OF FIRETOP MOUNTAIN</h2>`
  - `<p>Steve Jackson and Ian Livingstone</p>`

This endmatter appears on the same page as section 400, so the coarse segmenter correctly includes the page in gameplay, but the portionizer should filter out the endmatter patterns.

---

## Success Criteria

- [ ] **Endmatter patterns detected**: Identify common endmatter patterns:
  - Running heads with book series names (e.g., "More Fighting Fantasy in Puffins")
  - Book title headers (e.g., "1. THE WARLOCK OF FIRETOP MOUNTAIN")
  - Author names/bios
  - "Also available" / "Coming soon" type text
- [ ] **Endmatter filtered from sections**: All endmatter content excluded from gameplay sections, even when on same page
- [ ] **Section 400 clean**: Section 400 contains only its narrative content, no endmatter
- [ ] **No false positives**: Legitimate gameplay content not incorrectly filtered
- [ ] **Validation**: Spot-check last 5-10 sections to verify no endmatter leakage

---

## Solution Approach

**Option 1: Enhance Portionizer Filtering (Recommended)**
- Add endmatter pattern detection in `portionize_html_extract_v1`
- Filter out blocks that match endmatter patterns:
  - Running heads with series/book names
  - Headers that look like book titles (numbered titles like "1. BOOK TITLE")
  - Author name patterns
  - Blocks after the last numbered section on a page
- Apply filtering when assembling HTML/text for sections

**Option 2: Improve Coarse Segmenter Precision**
- Enhance `coarse_segment_html_v1` prompt to better detect endmatter even when mixed with gameplay
- Use more granular page-level analysis to identify endmatter blocks within gameplay pages
- Output block-level annotations for endmatter vs gameplay content

**Option 3: Post-Processing Cleanup**
- Add a dedicated endmatter filter module after portionization
- Scan sections for endmatter patterns and remove them
- Can be combined with story-092 (HTML Presentation Cleanup)

**Recommended: Option 1 + Option 3**
- Add pattern-based filtering in portionizer (fast, deterministic)
- Add post-processing cleanup as safety net (catches edge cases)

**Endmatter Pattern Detection (Generic, Not Book-Specific):**
- Running heads: `<p class="running-head">...</p>` containing series names, publisher names, or book titles (pattern-based, not hard-coded)
- Book titles: `<h2>N. BOOK TITLE</h2>` or `<h2>BOOK TITLE</h2>` where N is a number and the title is not a section number (structural detection)
- Author names: Patterns like "Author Name" or "By Author Name" appearing after book title headers (semantic pattern, not specific names)
- Series ads: Generic patterns like "Also available", "Coming soon", "More [Series]" (pattern matching, not exact strings)
- Positional: Content appearing after the last numbered section on a page that matches endmatter patterns

**Non-Overfitting Requirements:**
- Use structural patterns (HTML class names, tag types, positional relationships)
- Use semantic patterns (author name formats, series ad language) that generalize
- Avoid hard-coding book titles, author names, or publisher names
- Test on multiple FF books to verify generality

---

## Tasks

- [ ] Analyze endmatter patterns in section 400 and other affected sections
- [ ] Design generic pattern detection (structural/semantic, not book-specific strings)
- [ ] Implement endmatter pattern detection (regex/pattern matching for generic patterns)
- [ ] Add filtering logic to `portionize_html_extract_v1` or create dedicated filter module
- [ ] Test on section 400 and last 5-10 sections of Deathtrap Dungeon
- [ ] **Validate generality**: Test on at least one other FF book to ensure no overfitting
- [ ] Verify no false positives (legitimate gameplay content preserved)
- [ ] Run full pipeline and validate cleanup
- [ ] Document results and impact in work log

---

## Work Log

### 20251223-XXXX — Story created
- **Result:** Story defined.
- **Notes:** Coarse portionizer is including endmatter content in section 400. Endmatter patterns (book ads, titles, author names) appear on the same page as the last gameplay section and need to be filtered out during portionization. **Critical: Solution must be generic for all Fighting Fantasy books, not overfit to Deathtrap Dungeon.**
- **Next:** Analyze endmatter patterns (structural/semantic) and implement generic filtering logic.

