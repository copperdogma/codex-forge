# Codex Forge Inbox

This file captures ideas, insights, and potential architectural improvements discovered during development and manual tasks.

## OCR Pipeline Strategy: Two-Step Line-by-Line Transcription

**Context:** During the creation of 100% accurate Golden References for the dense, irregular genealogy tables in *Onward to the Unknown* (Story 128), we found that single-pass "Image -> HTML Table" prompts frequently fail on complex layouts. 

**The Problem with Single-Pass:**
1. **Semantic Hallucination:** Models (even strong ones like GPT-4o and Gemini 3 Pro) try to be "smart" and group data logically rather than visually (e.g., pulling a remarriage date from the row below up into the SPOUSE column of the current row).
2. **Summarization/Row Dropping:** On very dense pages, models often tire out and drop entire families or skip rows, failing to maintain 100% coverage.

**The Proposed Solution (The "CSV/JSONL Stepping Stone" Approach):**
Instead of asking the VLM to generate a complex HTML structure directly, force it into a rigid, line-by-line transcription mode.

*   **Step 1: Literal Row Extraction.** Prompt the VLM to output a flat format (like JSONL or CSV) where **one physical line on the page equals exactly one record in the output**. 
    *   *Prompt rule:* "Do NOT logically group data. If a person's info spans two lines, output TWO separate objects. Be a literal coordinate transcriber."
*   **Step 2: Structural Assembly.** Use a deterministic Python script (or a much cheaper, non-vision LLM pass) to convert the 100% accurate flat data into the required output format (HTML `<table>` with `colspan` headers).

**Why this works better for production:**
*   **Forces exhaustiveness:** It's much harder for the model to skip rows when the task is simply "read line 1, read line 2...".
*   **Defeats "smart" formatting:** By removing HTML structure from the prompt, the model stops trying to "fix" the author's weird column alignments.
*   **Highly Auditable:** You can easily write verification scripts to check if `len(jsonl_rows) == expected_row_count` before proceeding to the expensive structural assembly phase.

**Observed Failure Modes (Marie Louise & Arthur Audit):**
- **Header vs. Sparse Row Confusion:** Rows with only a NAME (e.g. children with no recorded birthdate) are easily misclassified as section headers by the assembly logic.
- **Interleaved Sequence Drift:** While the "CSV" pass ensures row *presence*, the model may still attempt to "organize" the output by grouping all discovered headers together and all children below them, destroying the original interleaved sequence of the family tree.
- **Transposition across Section Boundaries:** Models can erroneously assign a block of children to the preceding family header, leaving the correct parent header with zero children (e.g. assigning Monica's children to Camille).
- **Major Block Drops:** Even with line-by-line instructions, VLMs can still drop entire multi-row sections (e.g. missing Mabel's family of 10+ people) if the image is dense or the model "tires" mid-page.
- **Silent Date Hallucination:** Models may correctly transcribe an entire row but hallucinate a specific date (e.g. transcribing "Nov. 14, 1951" as "Aug. 7, 1949") even when that hallucinated date does not appear anywhere else on the page.

## Input Sanitization: Handling Handwritten Annotations

**Problem:** Many source scans in *Onward to the Unknown* contain faint or complex handwritten notes. Deciphering these accurately is extremely difficult for both humans and VLMs, and reconciling them into a "Golden" output creates an unreachable bar for automated modules.

**Insight:** The goal of the Codex Forge pipeline is to prove we can reach **100% accuracy** from a given input to a predefined golden output. If the input contains ambiguous handwritten noise that we don't want in the final structured data, it sabotages the evaluation.

**Action Item:**
- Create "Cleaned" or "Type-Only" versions of the source images that remove/ignore the handwriting.
- Ensure the **Input Image** and the **Golden Reference** are perfectly aligned. If a piece of data is too messy to be in the Golden, it should be removed from the Input used for benchmarking.
- This creates a fair test for the pipeline module: can it extract the *intended* data with 100% fidelity without being tripped up by historical artifacts/noise that are out of scope for the digital edition.
