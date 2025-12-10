# Gameplay Section Detection Playbook

**Module**: `fine_segment_gameplay_v1`  
**Approach**: Code-first detection with validation and escalation loop  
**Goal**: Find numbered gameplay sections (e.g., 1-400) with high accuracy and minimal false positives

---

## Detection Flow (In Order)

### 1. **Code-First Detection** (`detect_sections_code_first`)
- **What**: Scans `elements_core.jsonl` for standalone numeric lines that match section number patterns
- **Logic**:
  - Filters to gameplay pages only (from coarse segmenter)
  - Looks for elements with:
    - Text that's mostly numeric (after normalization)
    - Max 1 space, max 12 characters
    - Not navigation text ("turn to...")
    - Not page ranges ("123-125")
    - Within expected ID range (e.g., 1-400)
  - Uses `expand_candidates()` to handle OCR glitches (e.g., "1" vs "l" vs "I")
  - Keeps first occurrence if duplicate section IDs found
- **Output**: List of section candidates with `section_id`, `start_element_id`, `confidence=0.7`, `source="code_first"`

---

### 2. **Initial Validation** (`validate_section_count`)
- **When**: Immediately after code-first detection
- **Checks**:
  1. **Duplicate section IDs**: Flags if same section_id appears multiple times
  2. **Minimum coverage**: Ensures `found_count >= min_present` (default: 320/400)
  3. **Page ordering**: Validates that sections appear in sequential page order
     - For each section, checks that its page is between previous and next sections' pages
     - Flags out-of-order sections as "likely false positive"
- **Output**: `(is_valid, errors, missing_ids)`

---

### 3. **Escalation Loop** (if validation fails and `missing_ids` exist)
- **Max retries**: 2 attempts
- **Pattern**: `detect → validate → targeted escalate → validate` (per AGENTS.md)

#### 3a. **Code-First Backfill** (`backfill_missing_sections_v2`)
- **When**: First escalation attempt only
- **What**: Searches all elements for digit hits matching missing section IDs
- **Logic**:
  - For each missing section ID, finds elements containing that number:
    - Exact match: text == "42" (standalone number)
    - Normalized match: "42." → "42" (number with punctuation)
    - Pattern match: Any 1-3 digit groups within text (but this is filtered by page ordering)
  - **Page ordering filter**: Only accepts matches where the element's page is between the immediately previous and next detected sections' pages
    - Rejects matches on pages that are out of order (e.g., section 169 on page 95 when section 163 is on page 49 and section 171 is on page 56)
  - Creates boundaries with `confidence=0.4`, `evidence="digit-only element match in elements_core"`
- **Output**: New boundaries for found sections

#### 3b. **LLM Backfill** (`backfill_missing_sections_llm_v1`)
- **When**: All escalation attempts (if sections still missing after code backfill)
- **What**: Uses LLM to analyze text spans between detected sections to find missing ones
- **Model**: `gpt-4.1-mini` on attempt 1, `gpt-5` on retry
- **Logic**: 
  - For each gap between detected sections, sends elements in that span to LLM
  - LLM identifies missing section headers within the gap
  - Creates boundaries for found sections
- **Output**: New boundaries for found sections

#### 3c. **Re-check Missing** (after each escalation step)
- Rebuilds `missing_ids` list from current boundaries
- Continues escalation loop if sections still missing

---

### 4. **Backward Escalation** (after escalation loop completes)
- **When**: If sections are still missing after all escalation attempts
- **What**: Traces missing sections backward through upstream artifacts to determine where data was lost
- **Steps**:
  1. **Infer candidate pages**: For each missing section, finds pages between immediately previous and next detected sections (±1 page)
  2. **Trace upstream artifacts**:
     - Check `pagelines_final.jsonl` (OCR output) for section number presence
     - Determine if section is:
       - **In OCR but not detected** → `detection_issue` (section exists, detection failed)
       - **Not in OCR** → `ocr_issue` (need re-OCR candidate pages with GPT-4V)
       - **Unknown** → Can't trace further
  3. **Resolution tracking**: Marks each missing section as:
     - `resolved-not-found` with reason and upstream trace
     - Includes candidate pages for re-OCR if needed

---

### 5. **Post-Escalation Validation** (`validate_section_count`)
- **When**: After all escalation attempts complete
- **What**: Re-validates final section list with page ordering check
- **Checks**: Same as initial validation (duplicates, coverage, page ordering)

---

### 6. **Filter Out-of-Order Sections**
- **When**: If validation finds page ordering errors
- **What**: Removes sections that fail page ordering validation
- **Logic**:
  - Extracts section IDs from ordering error messages
  - Removes those sections from boundaries list
  - Rebuilds sections list from filtered boundaries
- **Re-validates**: Runs validation again after filtering

---

### 7. **Final Output**
- Converts sections to final format with page ranges
- Includes resolution tracking for all missing sections
- Outputs `gameplay_sections.json` with:
  - `sections`: List of detected sections
  - `coverage`: Statistics (total, expected, missing)
  - `escalation`: Escalation summary
  - `resolution`: Per-section resolution status
  - `validation`: Final validation status

---

## Key Design Principles

1. **Code-first, validate, escalate**: Start with fast code-based detection, validate, then escalate only what's needed
2. **Page ordering as truth**: Sections must appear in sequential page order - violations are false positives
3. **Generic, not book-specific**: All logic works on any Fighting Fantasy gamebook, no hardcoded section IDs
4. **Explicit resolution**: Every missing section gets a resolution status (found, not-found with reason, or unresolved)
5. **Upstream traceability**: Missing sections are traced back to OCR to identify where data was lost

---

## Validation Checkpoints

1. **After code-first detection**: Initial validation
2. **After code backfill**: Re-check missing (implicit validation)
3. **After LLM backfill**: Re-check missing (implicit validation)
4. **After escalation loop**: Post-escalation validation with page ordering
5. **After filtering**: Final validation

---

## Escalation Strategy

- **Attempt 1**: Code backfill → LLM backfill (gpt-4.1-mini)
- **Attempt 2**: LLM backfill (gpt-5) only
- **After escalation**: Backward escalation (trace upstream) for remaining missing sections

---

## False Positive Prevention

1. **Page ordering validation**: Rejects sections that appear out of sequential page order
2. **Page range filtering in backfill**: Code backfill only accepts matches within expected page range
3. **Text pattern filtering**: Code-first detection filters navigation text, page ranges, long text
4. **Post-escalation filtering**: Removes any out-of-order sections that slip through

---

## Current Limitations

1. **LLM confirmation disabled**: Currently skipped (was expensive, page ordering is more reliable)
2. **Page range heuristic**: Final output uses heuristic page ranges, not accurate element-based ranges
3. **Backward escalation doesn't auto-re-OCR**: Identifies candidate pages but doesn't automatically trigger re-OCR (manual step)

