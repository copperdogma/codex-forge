# Story: Booktype Text Cleanup Adapter (Downstream Normalization)

**Status**: To Do  
**Created**: 2025-12-18  
**Priority**: Low
**Related Stories**: story-072 (spell-weighted voting + downstream tolerance), story-058 (post-OCR text quality & repair)  

---

## Goal

Add a **booktype-aware, downstream text cleanup** stage that normalizes **HTML output** (not pagelines) for domain-specific conventions (gamebooks/CYOA, math-heavy texts, tables, etc.) **without making upstream OCR modules book-specific**.

**First target profile:** `gamebook` (CYOA / Fighting Fantasy-style navigation + section references).

This is intentionally separate from OCR itself:
- OCR stages should aim to be **generic** and preserve “what we saw” (HTML).
- Cleanup stages can be **opinionated**, **recipe-scoped**, and **provenance-rich**.

---

## Background / Motivation

We want to avoid reinventing OCR post-processing. Where possible, we should lean on:
- **Tesseract language assets** (word lists / patterns / ambiguity tables) to improve recognition or to power conservative post-correction.
- **Existing spell/lexicon libraries** (e.g., Hunspell, SymSpell-style edit-distance candidate generators) for fast candidate suggestions.

We also want consistent architecture:
- Keep `extract_ocr_ensemble_v1` generic by default.
- Push booktype-specific normalization downstream into adapters/clean/extract modules.

---

## Success Criteria

- [ ] **OCR remains generic by default:** No required booktype-specific rewrites in OCR/intake modules (any domain normalization is opt-in and recipe-scoped).
- [ ] **Dedicated cleanup stage exists:** New module produces a cleaned **HTML** artifact from upstream OCR HTML.
- [ ] **Provenance is explicit:** Output includes per-change records (what changed, why, where, confidence) and preserves the original text as available upstream.
- [ ] **Configurable by booktype:** Recipe/settings can select a “profile” (e.g., `gamebook`, `math`, `tables`) plus optional dictionary/pattern files.
- [ ] **Leans on existing tools:** Candidate generation uses an existing library (Hunspell/SymSpell/etc.) and/or Tesseract assets, not bespoke heuristics.
- [ ] **Safe-by-default:** Cleanup is conservative; if uncertain, it flags and leaves text unchanged (or emits a suggested patch with low confidence).
  - Note: This may be lower priority if GPT‑5.1 OCR proves clean enough; re-evaluate after baseline run.
- [ ] **Validation on sample:** Run the 20-page sample through the pipeline up to the cleanup stage and manually inspect output artifacts:
  - Confirm the cleanup triggers on real cases (at least 1).
  - Confirm it does not introduce regressions (diff bounded to intended changes).

---

## Non-Goals

- Full-book perfection for every domain (this is an adapter framework + initial profile(s)).
- Replacing `repair_portions_v1` (LLM re-read) for truly garbled pages; this story is about **deterministic or lexicon-guided cleanup**.

---

## Design Sketch

### New module (preferred)

`modules/adapter/booktype_text_cleanup_v1/`
- **Input:** HTML pages (e.g., `pages_html.jsonl`)
- **Output:** HTML pages (new artifact), plus a **sidecar** patch log (e.g., `cleanup_patches.jsonl`)
- **Behavior:**
  - Generate candidate corrections per token/line using:
    - a dictionary / lexicon (booktype- or book-specific)
    - edit-distance candidates (existing library)
    - optional known-ambiguity maps (e.g., Tesseract “dangerous ambiguities” concepts)
  - Apply only when confidence is high and evidence is local (avoid broad prose rewrites).
  - Emit `patch` records: `{page, line_idx, before, after, reason, confidence, sources}`.

### Profiles (initial)

- `gamebook` profile (**first target**):
  - Focus: navigation phrases, section refs, simple OCR confusions around digits/letters.
  - Goal: improve downstream extraction and/or presentation while keeping raw OCR untouched.
- Additional profiles can be added later (`math`, `tables`, `genealogy`, etc.).

---

## Tasks

### Task 1: Define the cleanup contract
- [ ] Decide where cleanup plugs in (preferred: after OCR HTML output).
- [ ] Decide artifact outputs (cleaned HTML + `cleanup_patches.jsonl` sidecar).
- [ ] Add schema/validator if needed for patches (or reuse existing jsonl conventions).

### Task 2: Implement `booktype_text_cleanup_v1` module scaffold
- [ ] Create `modules/adapter/booktype_text_cleanup_v1/module.yaml` + `main.py`
- [ ] Support `--profile` plus optional `--dictionary` / `--patterns` inputs
- [ ] Emit patch records with confidence + reason codes

### Task 3: Integrate an existing correction engine
- [ ] Evaluate and pick a library for candidate generation (Hunspell/SymSpell/etc.) already compatible with this repo
- [ ] Prefer a minimal dependency footprint; document why the chosen library is acceptable
- [ ] Support loading a custom dictionary/wordlist

### Task 4: Gamebook profile (initial)
- [ ] Implement conservative normalization rules as *profile code*, not OCR code
- [ ] Ensure raw OCR remains available upstream; cleanup produces a new artifact only

### Task 5: 20-page sample validation
- [ ] Run the 20-page sample from the beginning up to the cleanup stage
- [ ] Manually inspect:
  - `.../pages_html.jsonl` (input)
  - `.../booktype_text_cleanup_v1/<output>.jsonl` (output)
  - `.../cleanup_patches.jsonl` (evidence)
- [ ] Confirm: at least one real cleanup applied, no unexpected diffs

---

## Work Log
### 20251221-1550 — Reframed for HTML-first OCR
- **Result:** Success.
- **Notes:** Updated scope to operate on HTML output (not pagelines). Likely lower priority given GPT‑5.1 OCR quality; re‑evaluate after baseline runs.
- **Next:** Confirm whether this stage is still needed after full‑book QA.

### 20251221-1615 — Lowered priority
- **Result:** Success.
- **Notes:** Set priority to Low based on GPT‑5.1 HTML‑first baseline quality.
- **Next:** Reassess after additional full‑book QA.

### 20251218-0000 — Story created
- **Result:** Success.
- **Notes:** Created as a follow-on to story-072 to push domain-specific normalization downstream while reusing existing OCR tooling where possible.
- **Next:** Decide the exact insertion point + artifact contract, then implement the module scaffold.

### 20251218-1206 — Expanded requirements for “lean on existing tooling”
- **Result:** Success.
- **Notes:** Clarified that this story should prefer Tesseract language assets and established spell/lexicon libraries for candidate generation, rather than bespoke heuristics embedded in OCR.
- **Next:** Inventory what dictionaries/pattern assets we already have for FF/gamebooks, and decide how recipes provide them (`stage_params` vs. module params).

### 20251218-1208 — Set first target profile to `gamebook`
- **Result:** Success.
- **Notes:** Updated the story Goal/Design to explicitly make `gamebook` the first supported cleanup profile (CYOA/FF navigation + section refs).
- **Next:** Define the exact patch record schema and which transformations are allowed under `gamebook` with safe-by-default confidence rules.
