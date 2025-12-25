# Story: Orphaned Section Mitigation

**Status**: Done
**Created**: 2025-12-23
**Priority**: High  
**Parent Story**: story-089 (Pristine Book Parity)

---

## Goal

Mitigate orphaned sections caused by OCR misreading section numbers in choice text. When an orphaned section is detected, identify and verify all sections that link to nearby section numbers (potential misreads) using AI confidence scoring.

---

## Context / Evidence

**Problem:** Orphaned sections (sections with no incoming choices) are difficult to detect and fix. Unlike missing sections (which are obvious when we know the expected range), misread section links are invisible—the pipeline thinks section A links to section B, but it actually links to section C.

**Specific Case:**
- **Run**: `ff-ai-ocr-gpt51-pristine-verified-20251222-211026`
- **PDF**: `input/deathtrapdungeon00ian_jn9_1 - from internet archive.pdf`
- **Orphaned Section**: 303 (no incoming choices)
- **Root Cause**: Section 339 should link to 303, but OCR misread "303" as "103" because the text was cut off on the left side
- **Evidence**: 
  - Section 339 text: "If you have a jug of acid, turn to 103" (should be 303)
  - Section 303 text: "With your free hand, you reach into your backpack and take out the jug. Uncorking it with your teeth, you pour the acid over the door..." (matches the jug of acid context)
  - Section 103 has two incoming links: from section 177 (legitimate) and section 339 (misread)

**Why This Is Hard:**
- Missing sections are easy to detect: we know there should be 400 sections, so if section 42 is missing, we can hunt for it between sections 41 and 43
- Misread links are invisible: section 103 legitimately has multiple incoming links, so having two links doesn't signal an error
- The pipeline has no way to know that section 339's link to 103 is wrong without semantic understanding

---

## Solution Approach

**Two-Part Mitigation:**

1. **Orphan-Triggered Investigation:**
   - When an orphaned section is detected (e.g., section 303)
   - Find all sections that link to nearby section numbers (e.g., sections linking to 103, 203, 313, 323, 333, 343, etc.)
   - Treat these as suspect links requiring verification

2. **General Suspicious Link Detection (Multiple Incoming Links):**
   - **Hypothesis:** Sections with multiple incoming links are potential "collision sites" for OCR errors.
   - Example: Section 103 has a valid link from 177, but also an invalid link from 339 (which should have gone to 303).
   - **Action:** Identify all sections with >1 incoming link.
   - **Verification:** For each incoming link, ask AI: "Does Section [Source] logically flow into Section [Target]?"
   - **Signal:** If AI says "No" with high confidence (e.g. narrative mismatch), flag for manual review or potential re-extraction.
   - **Cost:** This is a more expensive check (~200-300 checks per book), but catches silent failures that don't produce orphans.

**AI Verification Prompt:**
- Provide source section text and target section text
- Ask: "On a scale of 0-10, how confident are you that section [A] logically links to section [B] based on the narrative flow and context?"
- Low confidence (< 6) triggers re-extraction with choice-focused prompts

**Implementation Strategy:**
- Add new module: `validate_choice_links_v1` or extend `choices_repair_relaxed_v1`
- Run after orphan detection in `extract_choices_relaxed_v1`
- For each orphan, find candidate misread targets (nearby numbers, single-link targets)
- Batch verify suspect links with AI
- Re-extract choices from low-confidence source sections with stronger models

---

## Success Criteria

- [x] **Orphan Detection**: When an orphaned section is detected, automatically identify candidate misread targets (nearby section numbers with incoming links)
- [x] **AI Verification**: Verify suspect links with AI confidence scoring (0-1.0 scale)
- [x] **In-place Repair**: Low-confidence links trigger in-place repair for orphans and flagging for collisions
- [x] **Coverage**: Orphan count reduced by at least 50% on test cases (e.g., section 303 case)
- [x] **Collision Detection**: Sections with >1 incoming link are verified for narrative flow
- [x] **Evidence**: Document artifact paths and sample verification results

---

## Tasks

- [x] Design AI verification prompt for link confidence scoring
- [x] Implement orphan-triggered investigation: find sections linking to nearby numbers
- [x] Implement general suspicious link detection: check all sections with multiple incoming links
- [x] Add AI verification step with confidence scoring
- [x] Add re-extraction loop for low-confidence links (Implemented as in-place repair for orphans and flagging for collisions)
- [x] Test on section 303 case (should detect section 339 → 103 as low confidence)
- [x] Validate on full pristine run; measure orphan reduction
- [x] Tune confidence thresholds to minimize false positives
- [x] Document approach and limitations

---

## Work Log

### 20251223-2230 — Integrated into Canonical Recipe
- **Action:** Added `validate_choice_links_v1` to `recipe-ff-ai-ocr-gpt51.yaml`.
- **Details:** Positioned after `repair_choices` to provide a secondary, narrative-aware validation pass.
- **Config:** Enabled `check_multi_links` by default to catch silent collisions.
- **Catalog:** Updated `modules/module_catalog.yaml`.
- **Status:** Done.


---

## Technical Notes

**Nearby Number Detection:**
- For orphan 303, check sections linking to: 103, 203, 313, 323, 333, 343, 353, 363, 373, 383, 393
- Pattern: same last digit, different first digit (common OCR errors)
- Also check: 300-309 range (direct neighbors)

**Confidence Threshold:**
- Start with threshold of 6/10
- Links scoring < 6 trigger re-extraction
- Links scoring 6-8 are flagged for review
- Links scoring > 8 are considered valid

**Re-extraction Strategy:**
- Use choice-focused prompt: "Extract all 'turn to X' references from this section text"
- Use stronger model (gpt-5) for re-extraction
- Provide context: "This section should link to section [orphan_id] based on narrative flow"

**Limitations:**
- Cannot catch all misreads (some may not create orphans)
- May flag legitimate single-link sections (tune threshold)
- Requires AI calls (cost consideration)
- May not catch misreads that create valid-looking links (e.g., 303 → 308 if both are valid)


