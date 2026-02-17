# Story: Onward to the Unknown — image-only → chapter-linked HTML

**Status**: To Do

---
**Depends On**: story-009 (layout-preserving table capture capability)

## Goal
Create a **generic, image-first recipe** that converts scanned book images into **one HTML page per chapter**, with an index/TOC that links chapters together. Output must preserve original wording, spelling, and structure exactly as printed. No cleanup or normalization is allowed.
**Primary implementation guidance:** reuse existing modules in full whenever they reasonably fit. When a full reuse is not appropriate (e.g., FF-specific assumptions), mimic the established approaches, code techniques, and patterns before attempting any new design. Do not reinvent a solution unless it is clearly better than the existing, battle-tested approach.

## Scope / Inputs
- **Book**: *Onward to the Unknown* (family history / genealogy)
- **Source**: image directory (authoritative)  
  `input/onward-to-the-unknown-images/`
- **Primary focus**: Genealogy tables with unusual layout. They must be represented faithfully and reliably.

## Acceptance Criteria
- **Recipe exists and runs end-to-end** on the image directory, producing artifacts under `output/runs/<run_id>/`.
- **Generic intake**: A reusable intake stage accepts any image directory and emits a `page_image_v1` manifest without book-specific rules.
- **OCR output is HTML-first**, and **preserves text exactly** (no spelling fixes, no normalization, no cleanup).
- **Genealogy tables are preserved** as HTML tables (row/col fidelity). If OCR is wrong, the fix is re-OCR or table rescue—not manual edits.
- **Chapter segmentation is heading-driven by default**: chapters are discovered from top-level headings and mapped to printed page ranges (TOC is optional/secondary).
- **Portionizer uses page numbers**: page numbers must be detected and preserved in JSON for segmentation, but removed from final HTML output.
- **Export produces one HTML file per chapter**, plus a TOC/index page linking all chapters.
- **TOC links are reciprocal**: TOC links to each chapter, and each chapter links back to TOC.
- **Image extractor available**: a module to detect/crop embedded images (family photos/diagrams) is included in the recipe or documented for reuse; prefer reusing the FF pipeline image extractor if feasible.
- **Every page is exported**: pages not covered by TOC chapters (frontmatter, standalone images, blanks) still get their own HTML output and appear in the index.
- **Manual verification completed**: at least 5 chapter pages and 5 genealogy tables are spot-checked against the scans, with paths recorded in the work log.

## Proposed Pipeline (Generic)
1. **Image intake**: Build `page_image_v1` manifest from an image directory.
2. **AI OCR → HTML**: Use `ocr_ai_gpt51_v1` with strict "do not correct text" hints.
3. **Table rescue loop**: Run `table_rescue_html_v1` (and/or a focused table rescuer) on flagged pages.
4. **HTML blocks**: Convert page HTML to blocks (for reliable heading detection).
5. **Heading extraction + chapter mapping**: Detect top-level headings and resolve chapter start pages.
6. **Chapter portionization**: Build chapter spans using headings + page-number boundaries (optionally cross-check TOC when reliable).
7. **HTML export**: Write `output/html/index.html` + `output/html/chapter-<n>.html`, stripping page numbers from final HTML while keeping them in JSON.

## Modules to Reuse (Preferred)
- `ocr_ai_gpt51_v1` (HTML OCR)
- `table_rescue_html_v1` (table grid rescue)
- `html_to_blocks_v1` (HTML → blocks)
- `render_html_from_elements_v1` (if Unstructured IR is introduced later)
- `crop_illustrations_guided_v1` or `crop_illustrations_from_ocr_v1` (FF pipeline image extractor)

## New / Missing Modules (Likely Needed)
- **`images_dir_to_manifest_v1`**: generic image-dir → `page_image_v1` manifest.
- **`portionize_headings_html_v1`**: identify top-level headings from OCR HTML and map to chapter boundaries.
- **`export_chapter_html_v1`**: emit per-chapter HTML files + TOC index.

## Non-Negotiables
- **No text cleanup**: do not normalize, correct spelling, or rewrite OCR text.
- **Re-OCR over edits**: suspected errors must trigger re-OCR or table rescue, never manual fixes.
- **Generic by default**: all heuristics must be opt-in and parameterized, not book-specific.
- **Reuse first**: prefer full module reuse when it makes sense; otherwise, mimic existing recipe approaches and patterns. Only introduce new logic with clear, documented benefit.

## Tasks
- [x] Confirm output format and naming for HTML files (`index.html`, `chapter-001.html`, etc.).
- [x] Design/implement **image-dir intake** → `page_image_v1` manifest.
- [x] Define OCR hints for strict text preservation (no normalization).
- [x] Implement TOC extraction + chapter segmentation modules with retry caps.
- [x] Add new recipe under `configs/recipes/` for image-only chapter HTML.
- [ ] **Image extraction quality** → broken out to **Story 125** (`story-125-image-extraction-eval-promptfoo.md`): use promptfoo to systematically evaluate VLM prompts/models for photo cropping with a golden dataset of manually cropped reference images.
- [ ] Run pipeline via `driver.py`, generate outputs in `output/runs/<run_id>/output/html/`.
- [ ] Manually inspect 5 chapter outputs + 5 genealogy tables, record evidence in work log.
- [ ] Document usage and troubleshooting in story + README if needed.

## Open Questions
- Should **page headers/footers** be preserved in chapter HTML or filtered?
- Should **chapter HTML** include inline page breaks or preserve page numbers?
- Is a **single index.html** sufficient, or should a standalone TOC page also be emitted?
- How should **genealogy tables** be represented when OCR cannot infer structure (fallback rules)?

## Work Log
### 20260117-0008 — Story rewrite + updated requirements
- **Result:** Rewrote Story 026 to align with image-only intake, TOC-driven chapter export, and strict text preservation. Added generic pipeline plan, likely modules, and open questions.
- **Notes:** Story now prioritizes OCR HTML fidelity and table rescue over cleanup, and calls out new intake/TOC modules as likely additions.
- **Next:** Confirm output format and TOC expectations, then implement intake + TOC segmentation modules and new recipe.
### 20260117-0018 — MVP intake module + recipe skeleton
- **Result:** Added a generic image-dir intake module (`images_dir_to_manifest_v1`) and an MVP recipe to OCR images to HTML with a table rescue pass.
- **Notes:** Module emits `page_image_v1` without modifying images; recipe is generic and avoids cleanup. Table rescue is included but not yet iterative.
- **Next:** Wire TOC extraction + chapter segmentation stages, then add chapter HTML export.
### 20260117-0030 — MVP smoke run + manual inspection (subset)
- **Result:** Ran MVP recipe on 10 images (Image027–Image036) and manually inspected OCR HTML output for narrative + genealogy pages.
- **Notes:** Output preserves tables but includes running heads and page numbers; these must be removed downstream to meet “no headers/footers/page numbers.” Some table cell content is collapsed (e.g., spouse names concatenated), indicating re‑OCR loop will be needed.
- **Artifacts inspected:**
  - `output/runs/onward-mvp-smoke-20260117/03_table_rescue_html_v1/pages_html_rescued.jsonl`
  - `output/runs/onward-mvp-smoke-20260117/02_ocr_ai_gpt51_v1/pages_html.jsonl`
- **Sample checks:**
  - Page 1 (Image027): narrative text present; `page-number` footer present in HTML and must be removed.
  - Page 2 (Image028): continuation narrative; footer present.
  - Page 3 (Image029): multi-table genealogy captured as `<table>` blocks; some cells concatenated (e.g., spouse names and dates run together).
  - Page 5 (Image031): multiple sub‑tables captured; running heads present.
  - Page 8 (Image034): dense tables captured; running heads and page number present.
- **Next:** Add a header/footer stripping stage and start a targeted re‑OCR loop for pages where table cells collapse.
### 20260117-0820 — Page-number extraction MVP
- **Result:** Added `extract_page_numbers_html_v1` and validated printed page numbers on the 10‑image subset; JSON now preserves printed page numbers for portionizing.
- **Notes:** Page numbers detected from `<p class="page-number">` tags output by OCR. Matches scans for pages 19–28 on Image027–Image036. HTML unchanged.
- **Artifacts inspected:**
  - `output/runs/onward-page-numbers-20260117/02_extract_page_numbers_html_v1/pages_html_with_page_numbers.jsonl`
- **Sample checks:**
  - Image027 → printed_page_number=19
  - Image028 → printed_page_number=20
  - Image029 → printed_page_number=21
  - Image030 → printed_page_number=22
  - Image031 → printed_page_number=23
  - Image034 → printed_page_number=26
- **Next:** Use printed_page_number for chapter boundaries; add HTML‑strip stage to remove page numbers from final output.
### 20260117-0830 — TOC portionizer + chapter HTML build MVP
- **Result:** Implemented TOC-based portionizer and chapter HTML builder; generated index + chapter files on TOC subset using printed page numbers.
- **Notes:** Portionizer parsed TOC lines and index table entries; chapter HTML strips running heads and page numbers. Index links to chapters; chapters link back to index.
- **Artifacts inspected:**
  - `output/runs/onward-toc-build-20260117/02_portionize_toc_html_v1/portions_toc.jsonl`
  - `output/runs/onward-toc-build-20260117/output/html/index.html`
  - `output/runs/onward-toc-build-20260117/output/html/chapter-002.html`
- **Sample checks:**
  - TOC entry “The First L'Heureux's in Canada” → page_start=2.
  - Index page lists chapter links without dot-leader artifacts for table entries (e.g., “Arthur”, “Alma”).
  - Chapter HTML has no `<p class="page-number">` and no running-head tags; original content preserved.
- **Next:** Run full recipe on a slightly larger range to validate TOC parsing + chapter assembly, then iterate on TOC edge cases.
### 20260117-0845 — End-to-end MVP subset run (TOC + early pages)
- **Result:** Ran full MVP flow (OCR → table rescue → page numbers → TOC portionize → chapter build → image extraction) on 6-page subset and validated outputs.
- **Notes:** Added `images` field to `page_html_v1` to prevent schema stamping from dropping OCR image metadata. Crop stage finds illustrations from HTML when metadata is missing.
- **Artifacts inspected:**
  - `output/runs/onward-full-mvp-subset-20260117/05_extract_page_numbers_html_v1/pages_html_with_page_numbers.jsonl`
  - `output/runs/onward-full-mvp-subset-20260117/06_portionize_toc_html_v1/portions_toc.jsonl`
  - `output/runs/onward-full-mvp-subset-20260117/output/html/index.html`
  - `output/runs/onward-full-mvp-subset-20260117/output/html/chapter-002.html`
  - `output/runs/onward-full-mvp-subset-20260117/03_crop_illustrations_guided_v1/illustration_manifest.jsonl`
- **Sample checks:**
  - Printed page numbers detected: TOC page (vii) recorded in printed_page_number_text; content page 2 recorded as printed_page_number=2.
  - Chapter HTML output contains no page-number or running-head elements; TOC index links correct.
  - Illustration manifest contains 4 crops for this subset (2 pages with images).
- **Next:** Expand subset to include more chapters and genealogy pages; validate TOC extraction and chapter spans at larger scale.
### 20260117-0918 — Table rescue loop + <br> preservation (in progress)
- **Result:** Added an iterative table rescue loop module (`table_rescue_html_loop_v1`), wired into the MVP recipe, and extended OCR HTML sanitization to preserve `<br>` for multi-line table cells. Fixed GPT-5.1 chat API parameter to use `max_completion_tokens`.
- **Notes:** End-to-end subset run (`onward-loop-subset-20260117`) completed OCR + crop stages but failed in table rescue due to unresolved table issues after 3 passes (expected with `fail_on_unresolved: true`). The rescue loop generated a per-pass report for targeted pages; however, the final rescued HTML still shows concatenated cell content on dense genealogy tables (likely because `<br>` was previously stripped). A follow-up rerun is required to validate whether the `<br>` preservation resolves the concatenation signal and allows the loop to pass.
- **Artifacts inspected:**
  - `output/runs/onward-loop-subset-20260117/04_table_rescue_html_loop_v1/pages_html_rescued.jsonl`
  - `output/runs/onward-loop-subset-20260117/table_rescue_html_loop_v1/table_rescue_report.jsonl`
  - `output/runs/onward-loop-subset-20260117/02_ocr_ai_gpt51_v1/pages_html.jsonl`
- **Sample checks:**
  - Page 30 (Image029) genealogy table still shows concatenated cell text (e.g., spouse and dates merged) in rescued HTML.
  - Rescue report shows repeated attempts on pages 30/33/34/35 across passes with remaining `suspect_cell_concatenation`.
- **Impact:**
  - **Story-scope impact:** Unblocked a generic re-OCR loop for table structure recovery and enabled `<br>` preservation needed for faithful genealogy tables.
  - **Pipeline-scope impact:** Added a retry-cap loop with explicit failure on unresolved tables; OCR sanitizer now retains intra-cell line breaks.
  - **Evidence:** `output/runs/onward-loop-subset-20260117/table_rescue_html_loop_v1/table_rescue_report.jsonl` shows multi-pass attempts; `output/runs/onward-loop-subset-20260117/04_table_rescue_html_loop_v1/pages_html_rescued.jsonl` contains rescued HTML; `output/runs/onward-loop-subset-20260117/02_ocr_ai_gpt51_v1/pages_html.jsonl` provides baseline OCR for comparison.
- **Next:** Re-run the subset after `<br>` preservation to confirm concatenation resolves and the loop can pass (or adjust detection thresholds if the OCR is already correct). Success is falsified if suspect concatenations persist after re-OCR with `<br>` allowed.
### 20260117-0936 — Onward-specific table escalation module (implemented)
- **Result:** Added `table_rescue_onward_tables_v1` to re-OCR genealogy tables using an Onward-specific prompt and strip page numbers/running heads post‑OCR (after page numbers are already extracted). Created a dedicated Onward recipe (`recipe-onward-images-html-mvp.yaml`) that inserts this escalation stage after page-number extraction and routes downstream stages to its output.
- **Notes:** The module detects genealogy tables by fuzzy header matching (NAME/BORN/MARRIED/SPOUSE/BOY/GIRL/DIED). It always re‑OCRs those pages for MVP. Page numbers remain in JSON from the earlier extraction stage; HTML output from the Onward step removes page numbers/running heads to avoid reintroducing them.
- **Impact:**
  - **Story-scope impact:** Adds a book‑specific escalation path focused on genealogy tables, aligning with the primary failure mode for *Onward to the Unknown*.
  - **Pipeline-scope impact:** Keeps generic OCR/table rescue intact while inserting a deterministic Onward‑only re‑OCR pass after page-number extraction.
  - **Evidence:** `configs/recipes/recipe-onward-images-html-mvp.yaml`, `modules/adapter/table_rescue_onward_tables_v1/main.py`, `modules/adapter/table_rescue_onward_tables_v1/module.yaml`
- **Next:** Run the new Onward recipe on a small subset and inspect 5 genealogy tables + 5 pages in HTML to validate column alignment and absence of page numbers.
### 20260117-1145 — Onward table rescue test (fast, load_artifact)
- **Result:** Ran a fast driver pipeline that reuses OCR output and applies the Onward table rescue on two targeted pages (30, 33) for validation.
- **Notes:** The Onward module successfully re‑OCRs and rewrites tables, splits `<br>` lines into separate rows, and inserts BOY/GIRL headers, but the top summary row still keeps combined values (e.g., “11 4” in BOY with empty GIRL) on page 30. This is a remaining structural defect to resolve.
- **Artifacts inspected:**
  - `output/runs/onward-onward-rescue-fast4-20260117/03_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`
  - `output/runs/onward-onward-rescue-fast4-20260117/04_portionize_toc_html_v1/portions_toc.jsonl`
  - `output/runs/onward-onward-rescue-fast4-20260117/output/html/index.html`
- **Sample checks:**
  - Page 30 (Image029): BOY/GIRL headers present; rows split per `<br>` lines; summary row still has “11 4” in BOY column with empty GIRL.
  - Page 33: BOY/GIRL headers present; multi‑section headings preserved; rows split into separate table lines.
- **Impact:**
  - **Story-scope impact:** Demonstrated the Onward escalation module in a driver run and verified the table format improvements, but found a remaining Boy/Girl split defect.
  - **Pipeline-scope impact:** Reuse‑based test reduced runtime; downstream portionize/build stages completed on the rescued HTML.
  - **Evidence:** `output/runs/onward-onward-rescue-fast4-20260117/03_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl` (page 30/33 HTML), `output/runs/onward-onward-rescue-fast4-20260117/output/html/index.html` (TOC links).
- **Next:** Fix BOY/GIRL numeric split on summary rows (deterministic post‑process or prompt reinforcement), then rerun the fast recipe and re‑inspect pages 30/33 plus at least 5 genealogy tables.
### 20260117-1205 — Canonical run established + BOY/GIRL split fix
- **Result:** Added deterministic BOY/GIRL split for summary rows in the Onward rescue module and re‑ran the pipeline using the canonical run id `onward-canonical` (reused via `--allow-run-id-reuse`). The summary row now splits “11 4” into BOY=11, GIRL=4.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/03_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`
  - `output/runs/onward-canonical/output/html/index.html`
  - `output/runs/onward-canonical/output/html/chapter-002.html`
- **Sample checks:**
  - Page 30 (Image029) genealogy summary row now shows BOY=11, GIRL=4 (no combined “11 4” in one cell).
  - Page 33 tables preserve BOY/GIRL headers and separate rows; headings preserved.
- **Impact:**
  - **Story-scope impact:** Resolves the BOY/GIRL split defect for the Onward genealogy tables in the canonical run.
  - **Pipeline-scope impact:** Establishes a single reusable run directory (`output/runs/onward-canonical`) for iterative testing; reduces run churn.
  - **Evidence:** `output/runs/onward-canonical/03_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl` (page 30/33 HTML), `output/runs/onward-canonical/output/html/index.html` (stable index output).
  - **Next:** Reuse `onward-canonical` for subsequent iterations; expand manual inspection to 5+ genealogy pages and 5+ chapter HTML outputs.
### 20260117-1235 — Heading-based portionizer for chapter segmentation
- **Result:** Added a generic heading-based portionizer (`portionize_headings_html_v1`) and updated the Onward recipe to use it instead of TOC parsing.
- **Notes:** Chapters are now detected from top-level `<h1>` headings and mapped to printed page numbers (starting at page 1). TOC remains optional/secondary for future refinement.
- **Impact:**
  - **Story-scope impact:** Addresses the unreliable TOC by switching to a generic heading-based chapter segmentation approach.
  - **Pipeline-scope impact:** Keeps segmentation generic and reusable; avoids book-specific TOC logic while still using printed page numbers.
  - **Evidence:** `modules/portionize/portionize_headings_html_v1/main.py`, `modules/portionize/portionize_headings_html_v1/module.yaml`, `configs/recipes/recipe-onward-images-html-mvp.yaml`
  - **Next:** Re-run the canonical pipeline on a small subset to validate chapter spans (ensure narrative + tables are merged under the same heading) and verify 5+ chapter HTML outputs.
### 20260117-1315 — Page-number fallback + heading chapters validated (subset)
- **Result:** Added a fallback extractor for standalone numeric/roman page numbers outside tables and re-ran the canonical subset with a resume recipe to refresh page numbers, Onward table rescue, heading-based portionize, and chapter build.
- **Notes:** Resume recipe used `load_artifact_v1` to avoid re-OCR; run covers the existing 30-page subset already cached in `onward-canonical`.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/02_extract_page_numbers_html_v1/pages_html_with_page_numbers.jsonl`
  - `output/runs/onward-canonical/03_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`
  - `output/runs/onward-canonical/output/html/chapter-001.html`
  - `output/runs/onward-canonical/output/html/chapter-002.html`
  - `output/runs/onward-canonical/output/html/chapter-005.html`
  - `output/runs/onward-canonical/output/html/chapter-012.html`
  - `output/runs/onward-canonical/output/html/chapter-013.html`
- **Sample checks (chapters):**
  - `chapter-001.html` (Ancestral Lineage) includes the lineage table and no page-number/running-head markup.
  - `chapter-002.html` (The First L'Heureux's in Canada) contains narrative paragraphs; no page-number markup.
  - `chapter-005.html` (Moise and Sophie) contains narrative text; no page-number markup.
  - `chapter-012.html` (Arthur L'Heureux) includes narrative paragraphs plus 18 tables; no page-number markup.
  - `chapter-013.html` (Roger's Family) includes tables with BOY/GIRL columns; no page-number markup.
- **Sample checks (tables):**
  - Page 15 (Marlyne’s Family): headers include BOY/GIRL; rows show BOY values in their own column.
  - Page 21 (Arthur L’Heureux): summary row shows BOY=11, GIRL=4; follow-up row preserved.
  - Page 23 (Joe’s/Thomas/Robert’s families): headers include BOY/GIRL; rows preserved.
  - Page 25 (Noel’s Family): headers include BOY/GIRL; rows preserved.
  - Page 26 (Dora’s Family): headers include BOY/GIRL; rows preserved.
- **Impact:**
  - **Story-scope impact:** Validated heading-based chapter segmentation on the subset and confirmed table rescue output for multiple genealogy pages.
### 20260118-1425 — JPEG output + crop dedupe (images)
- **Result:** Added JPEG output support to the illustration cropper (guided + OCR-bbox variants), set the Onward recipe to emit JPEGs, and deduped near-identical boxes to avoid duplicated crops on a page.
- **Notes:** Re-ran the crop stage in `onward-canonical` and confirmed `illustration_manifest.jsonl` now points to `.jpg` files with `has_transparency=false`. Deduping removed repeated identical boxes on pages where OCR expected multiple images but the VLM returned duplicates (e.g., page 12 and page 21). Captions are still present in some crops (e.g., page 21), so trimming likely needs stricter/alternate logic.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/illustration_manifest.jsonl`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`
- **Sample checks:**
  - Manifest entries now use `.jpg` filenames with `filename_alpha: null`.
  - Page 12 crops are distinct (seal + certificate area).
  - Page 21 crops still include caption text under each photo (“Aerial photo of ranch buildings”, “Ranch house and barn”).
- **Impact:**
  - **Story-scope impact:** Enables JPEG output for web-friendly images and removes duplicate crops when the detector returns overlapping boxes.
  - **Pipeline-scope impact:** Crop stage now emits smaller JPEG files; manifest is consistent with non-transparent output for Onward.
  - **Evidence:** `output/runs/onward-canonical/03_crop_illustrations_guided_v1/illustration_manifest.jsonl` (jpg filenames), `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg` (caption still present).
  - **Next:** Decide whether captions should be excluded; if yes, tighten caption-trim logic or add a post-trim pass to drop caption lines without cutting into images.
### 20260118-1545 — Caption trim tighten + HTML image linking
- **Result:** Tightened caption trimming in the cropper and added in-flow `img src` attachment during chapter build (no separate transform module). Images are copied into `output/html/images/` for static linking.
- **Notes:** Caption trim is now more aggressive (larger bottom band, lower text ratio threshold, stronger row detection). HTML preserves image locations semantically via `<img src="images/<filename>" data-crop-filename="...">` inline in the OCR flow.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`
  - `output/runs/onward-canonical/output/html/chapter-002.html`
- **Sample checks:**
  - HTML contains `<img>` tags with `src="images/<filename>"` and preserves their original text order.
- **Impact:**
  - **Story-scope impact:** Moves image handling toward web-ready HTML with images placed in-flow and captions excluded from crops (after re-run).
  - **Pipeline-scope impact:** Adds a reusable transform for linking cropped images to OCR HTML and preparing a static `output/html/images` folder.
  - **Evidence:** `modules/build/build_chapter_html_v1/main.py`, `configs/recipes/recipe-onward-images-html-mvp.yaml`.
  - **Next:** Re-run from crop_illustrations and attach_cropped_images, then verify captions are gone on photo pages and HTML `<img>` tags reference the new JPEGs.
### 20260118-1605 — Caption trim gap logic (iteration)
- **Result:** Removed the “skip trimming on photo-like ROI” guard and increased the whitespace-gap sensitivity for caption trimming.
- **Notes:** Re-ran crop stage and checked page 21; caption is still present, so trimming needs another approach (likely a stronger gap-based cutoff or a targeted OCR-aware caption detector).
- **Artifacts inspected:**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
- **Sample checks:**
  - Page 21 crop still includes caption text (“Aerial photo of ranch buildings”).
- **Impact:**
  - **Story-scope impact:** No improvement yet on caption removal; next iteration should focus on a more reliable caption cut line.
  - **Pipeline-scope impact:** None yet (logic changed but effect not observed).
  - **Evidence:** `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg` still includes caption.
  - **Next:** Add a caption cut that prefers a whitespace band above bottom text and verify on pages 21 and 22.
### 20260118-1635 — Caption trim thresholds (iteration)
- **Result:** Raised caption band height and nonwhite tolerance, and increased the whitespace-gap sensitivity to improve caption detection.
- **Notes:** Needs a fresh crop re-run to confirm captions are removed without cutting into image content.
- **Impact:**
  - **Story-scope impact:** Sets up a more aggressive caption removal pass per your requirement.
  - **Pipeline-scope impact:** None yet (verification pending).
  - **Next:** Re-run from crop_illustrations and inspect page 21/22 crops.
### 20260118-1745 — In-flow img src attachment + caption trim success (sample)
- **Result:** Folded image `src` attachment into `build_chapter_html_v1` (no separate attach module). Crops now map to existing OCR `<img>` tags in order and copy JPEGs into `output/html/images/`. Updated caption trimming logic to cut captions based on whitespace gaps; page 21 crop now excludes the caption.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/output/html/chapter-006.html`
  - `output/runs/onward-canonical/output/html/images/page-021-000.jpg`
  - `output/runs/onward-canonical/output/html/images/page-021-001.jpg`
- **Sample checks:**
  - Chapter 006 HTML includes `<img ... src="images/page-021-000.jpg">` and `<img ... src="images/page-021-001.jpg">` in-flow.
  - `page-021-000.jpg` no longer contains the caption line (“Aerial photo of ranch buildings”).
- **Impact:**
  - **Story-scope impact:** Uses OCR’s semantic `<img>` placement while attaching cropped JPEGs for web output; caption removal now works on at least one photo page.
  - **Pipeline-scope impact:** Removes the need for a separate image-attach stage and centralizes HTML image linking in chapter build.
  - **Evidence:** `modules/build/build_chapter_html_v1/main.py`, `output/runs/onward-canonical/output/html/chapter-006.html`.
  - **Next:** Validate caption removal on 3–5 additional photo pages and ensure all `<img>` tags have matching `src` when OCR expects multiple images.
### 20260119-1030 — Image cropper experiments + VLM rescue sanity
- **Result:** Ran focused crop experiments on pages 18/21/22/48/54/60 using CV-only variants and VLM rescue; CV-only modes either fragment photos into strips or miss full-page photos, while VLM rescue yields clean photo crops and respects the new “no-guess” prompt.
- **Notes:** `data-count` from OCR overstates expected images on some pages; for pages with multiple `<img>` tags, the cropper now prefers tag-count over `data-count`. This aligns VLM rescue to return 2 crops for page 21 (two `<img>` tags) and 2 for page 60.
- **Artifacts inspected:**
  - `/tmp/crop-exp/variantVLM2/images/page-021-000.jpg`
  - `/tmp/crop-exp/variantVLM2/images/page-021-001.jpg`
  - `/tmp/crop-exp/variantVLM2/images/page-018-000.jpg`
- **Sample checks:**
  - Page 21: top and bottom photos cropped cleanly (captions excluded) with VLM rescue.
  - Page 18: group portrait cropped without caption block.
- **Impact:**
  - **Story-scope impact:** Confirms VLM-guided boxes are the most reliable path for photo-heavy pages with halftone patterns.
  - **Pipeline-scope impact:** Establishes a deterministic preference for OCR `<img>` tag counts over noisy `data-count` fields.
  - **Evidence:** `/tmp/crop-exp/variantVLM2/illustration_manifest.jsonl`, `modules/extract/crop_illustrations_guided_v1/main.py`.
  - **Next:** Decide whether to run VLM rescue by default (or only when CV fragments photos), then re-run crop + build in `output/runs/onward-canonical/` and verify captions are removed on pages 21/22/60 in output HTML.
  - **Pipeline-scope impact:** Page-number extraction now captures standalone numeric footer lines outside tables; roman numerals remain in `printed_page_number_text`.
  - **Evidence:** `output/runs/onward-canonical/02_extract_page_numbers_html_v1/pages_html_with_page_numbers.jsonl`, `output/runs/onward-canonical/03_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`, `output/runs/onward-canonical/output/html/chapter-012.html`
  - **Next:** Expand the subset (or full image set) to verify headings and page-number extraction across the entire book; success is falsified if pages beyond the current subset fail to yield numeric page numbers or if chapter spans split narrative/table pairs.
### 20260117-1500 — Adapter progress logging + 60-page subset re-run
- **Result:** Enabled progress/state plumbing for adapter table-rescue modules in `driver.py`, re-ran the Onward rescue on the 60‑page subset using cached OCR, and completed the rescue + heading portionize + chapter build.
- **Notes:** Prior runs appeared “stuck” because driver skipped `--progress-file` for adapter stages. Progress is now visible in `pipeline_events.jsonl`. OCR was already completed earlier for the 60‑page subset; this run reused those artifacts via `load_artifact_v1`.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/02_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`
  - `output/runs/onward-canonical/04_build_chapter_html_v1/chapters_manifest.jsonl`
  - `output/runs/onward-canonical/output/html/chapter-012.html`
  - `output/runs/onward-canonical/output/html/chapter-013.html`
  - `output/runs/onward-canonical/output/html/chapter-014.html`
  - `output/runs/onward-canonical/output/html/chapter-015.html`
  - `output/runs/onward-canonical/output/html/chapter-016.html`
- **Sample checks (chapters):**
  - `chapter-012.html` (Edouard’s Family) includes tables; no page-number markup.
  - `chapter-013.html` (Leonidas’ Grandchildren) includes tables; no page-number markup.
  - `chapter-014.html` (Josephine Alain) includes narrative + tables; no page-number markup.
  - `chapter-015.html` (Paul L’Heureux) includes narrative + tables; no page-number markup.
  - `chapter-016.html` (George L’Heureux) includes narrative; no page-number markup.
- **Sample checks (tables):**
  - Page 21: BOY/GIRL headers present; summary row BOY=11, GIRL=4.
  - Page 23: BOY/GIRL headers present; rows preserved.
  - Page 25: BOY/GIRL headers present; rows preserved.
  - Page 34: BOY/GIRL headers present; rows preserved.
  - Page 40: BOY/GIRL headers present; rows preserved.
- **Impact:**
  - **Story-scope impact:** Restored adapter progress visibility and validated 60‑page subset output for chapters + genealogy tables.
  - **Pipeline-scope impact:** Adapter stages now emit progress into `pipeline_events.jsonl`, eliminating silent long‑running rescues.
  - **Evidence:** `output/runs/onward-canonical/02_table_rescue_onward_tables_v1/pages_html_onward_tables.jsonl`, `output/runs/onward-canonical/output/html/chapter-015.html`, `output/runs/onward-canonical/pipeline_events.jsonl`
  - **Next:** Expand to full image set (or larger subset) and verify additional chapters/tables; success is falsified if later pages lack printed page numbers or headings split narrative/table pairs.
### 20260117-1545 — Generic continuation-row table fix
- **Result:** Added a generic post‑processor (`table_fix_continuations_v1`) that fixes continuation‑row misalignment in tables (e.g., multi‑line spouse names where DIED dates drift to the previous row). Wired it into the Onward recipe after table rescue, then re‑ran portionize/build without re‑OCR.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/02_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`
  - `output/runs/onward-canonical/output/html/chapter-012.html`
- **Sample checks (continuation fix):**
  - Printed page 21: “Dorilla / David Gelinas” row now keeps “May 10, 1986” on the continuation row with “David” (not attached to the Gelinas line).
- **Impact:**
  - **Story-scope impact:** Fixes a common table parsing failure mode with a generic, reusable post‑process.
  - **Pipeline-scope impact:** Adds a lightweight, no‑OCR table correction step to keep dates aligned with continuation rows.
  - **Evidence:** `output/runs/onward-canonical/02_table_fix_continuations_v1/pages_html_onward_tables_fixed.jsonl`
  - **Next:** Expand the run to more pages and verify the continuation heuristic doesn’t introduce regressions in other tables.
### 20260119-0935 — Guided image cropper refinements + VLM-first experiments
- **Result:** Strengthened VLM prompt to exclude text, added text-line refinement and edge-trim logic, and switched crop outputs to JPEG in the Onward recipe. Re-ran the crop stage in `onward-canonical` and manually inspected multiple outputs.
- **Notes:** Photo crops now reliably exclude captions and body text on photo-heavy pages. A remaining defect is page 12 (certificate) where the crop for the seal/signatures still includes the header line “Saskatchewan’s 75th Anniversary Year 1980.”
- **Artifacts inspected:**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-022-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`
- **Sample checks:**
  - Page 21/22/60 photo crops exclude captions and surrounding body text.
  - Page 12 seal/signatures crop still includes the header line above the signatures.
- **Impact:**
  - **Story-scope impact:** Improves image extraction quality on photo pages and switches output to JPEG for downstream web use.
  - **Pipeline-scope impact:** Adds text-line-based refinement and edge trimming to reduce caption bleed without re-OCR.
  - **Evidence:** `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`, `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-022-000.jpg`, `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`.
  - **Next:** Fix the page 12 header bleed by improving top-edge text trimming or adding a VLM retry when text is detected inside the crop; success is falsified if the seal/signature crop still includes header text.
### 20260119-1440 — Text-line refinement tuning + VLM retry guard (blocked by quota)
- **Result:** Added `rescue_retry_on_text` (VLM retry when text bands remain), top-caption trimming in `_apply_caption_box`, and a tunable `refine_textlines_min_area_ratio` to allow shrinking around smaller non-text components (e.g., seals/signatures). Added fallback band/gap detection in edge trimming.
- **Notes:** A test run with `CROP_VLM_DEBUG_DIR` failed due to OpenAI quota (HTTP 429), so the crop stage fell back to CV-only and produced degraded outputs (9 crops instead of 16). The current `onward-canonical` crop artifacts are not trustworthy and must be regenerated once quota is restored.
- **Artifacts inspected:**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg` (still shows header text after last VLM run)
- **Impact:**
  - **Story-scope impact:** Adds hooks to tighten crops around small non-text regions and to trigger VLM retry when text bleed is detected.
  - **Pipeline-scope impact:** Introduces a new tunable for text-line refinement and a text-bleed retry guard for VLM.
  - **Evidence:** `modules/extract/crop_illustrations_guided_v1/main.py`, `modules/extract/crop_illustrations_guided_v1/module.yaml`, `configs/recipes/recipe-onward-images-html-mvp.yaml`.
  - **Next:** Restore VLM quota, rerun `crop_illustrations` in `onward-canonical`, and re-inspect page 12 crops plus 3–5 photo pages. Success is falsified if header/caption text remains in crops.
### 20260119-1705 — VLM crops clean + JPEG outputs + HTML src attachment verified
- **Result:** Re-ran crop stage with VLM retry-on-text enabled and confirmed clean crops (no caption/header text) on key pages. Verified build output attaches `src` in semantic order for image tags in chapter HTML.
- **Artifacts inspected (opened in Preview):**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-022-000.jpg`
- **Sample checks:**
  - Page 12 logo and seal/signatures crops exclude the “Saskatchewan’s 75th Anniversary Year 1980” header text.
  - Page 21/22 photo crops exclude captions and surrounding body text.
  - Chapter HTML attaches `src` and `data-crop-filename` in order for multi-image pages (e.g., `output/runs/onward-canonical/output/html/chapter-016.html`).
- **Impact:**
  - **Story-scope impact:** Image crops are now clean enough to attach directly into HTML without caption bleed.
  - **Pipeline-scope impact:** Confirms VLM retry/trim logic resolves text bleed on the hardest certificate page and JPEG output flows through to HTML output.
  - **Evidence:** `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`, `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`, `output/runs/onward-canonical/output/html/chapter-016.html`.
  - **Next:** Remove any legacy attach module from the recipe if it still exists and run `build_chapter_html_v1` from the updated crop outputs; success is falsified if any `<img>` lacks a `src` in the final HTML or crops re-include captions.
### 20260123-1430 — OCR-edge trim experiment (failed to remove captions)
- **Result:** Added OCR-based edge trimming using Tesseract TSV to remove caption/header text from crops; re-ran crop stage and manually inspected all 16 crops. Captions and adjacent body text still remain on multiple photo crops, so this approach is not acceptable yet.
- **Notes:** OCR-edge trimming is too noisy (many low-confidence words) and fails to exclude captions on pages 18/21/38/54/60. Signature crop still includes header text.
- **Artifacts inspected (all 16 crops):**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-001-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-004-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-009-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-014-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-018-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-022-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-038-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-038-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-048-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-054-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-001.jpg`
- **Impact:**
  - **Story-scope impact:** No improvement; captions/text still present in multiple crops.
  - **Pipeline-scope impact:** Added OCR-edge trim parameters but they are ineffective and should be revised or removed.
  - **Evidence:** `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg` (caption text still present), `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-001.jpg` (caption text still present), `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg` (header text still present).
  - **Next:** Replace OCR-edge trim with a VLM-driven mask or explicit caption-box usage (force trimming even when caption_box is null by re-prompting). Rerun crop stage and re-inspect.
### 20260124-0005 — VLM caption pass + crop refine (still failing)
- **Result:** Added a VLM caption second-pass and per-crop VLM refinement, re-ran crop stage, and manually inspected all 16 crops. Captions/body text still appear on multiple crops, so this is not acceptable yet.
- **Artifacts inspected (all 16 crops):**
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-001-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-004-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-009-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-014-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-018-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-022-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-038-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-038-001.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-048-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-054-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-000.jpg`
  - `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-001.jpg`
- **Sample failures:**
  - `page-021-001.jpg` still includes caption text “Ranch house and barn”.
  - `page-060-001.jpg` still includes caption text “Napoleon Paul and Beatrice L’Heureux.”
  - `page-012-001.jpg` still includes header text “Saskatchewan’s 75th Anniversary Year 1980”.
- **Impact:**
  - **Story-scope impact:** No improvement; captions/text remain.
  - **Pipeline-scope impact:** Added VLM caption pass + per-crop VLM refine, but still insufficient.
  - **Evidence:** `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-001.jpg`, `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-060-001.jpg`, `output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-001.jpg`.
  - **Next:** Replace the crop-refine step with a **text-masking VLM pass**: ask VLM for a **mask polygon of non-text pixels**, then derive a tight bounding box around that mask (or ask for a “text-free bounding box” and validate with a second VLM “text present?” check). Re-run crop stage and re-inspect.
### 20260124-0015 — Potential solutions for image/caption separation (planned)
- **Current approach + struggles:** We are using VLM box detection + heuristics (caption trimming, textline trimming, and a VLM caption second-pass). This still leaves captions/body text in multiple crops (pages 12/21/60). The failure mode appears to be that the VLM image boxes include nearby text and the caption box is either missing or too loose for reliable trimming.
- **Potential solutions (known-good approaches):**
  - **Layout detection models (PaddleOCR PP-Structure / DocLayout):** Detect `image/figure` and `caption` as separate layout classes, then crop only `image` regions and explicitly exclude `caption` regions. This is the most direct match to our failure mode.
  - **Text detection + masking (docTR or similar):** Detect all text lines, mask them out, then take the largest remaining connected component as the image region. More robust than morphology-only, but may still miss faint captions on halftone scans.
  - **Layout models trained on PubLayNet/DocLayNet:** Use a document layout detector (e.g., Detectron2-based) to segment `Picture` vs `Caption`. Higher accuracy but heavier dependencies.
- **Next planned experiment:** Run PaddleOCR layout detection on a small subset of pages (12/21/60), compare crops, and if quality is good, wire into a new module for the pipeline.
### 20260124-0925 — Why this is hard + candidate libraries (context for next iteration)
- **Why it’s not trivial in practice:** Halftone photos and faint borders make text/figure separation ambiguous; captions are visually connected to photos once binarized; layouts vary (full-page photos, embedded photos, multiple photos per page), so a single threshold/morphology recipe overfits; OCR `data-count` is noisy, which causes over-splitting or VLM hallucinated boxes when treated as hard truth.
- **Current approach + struggles:** VLM box detection + heuristics (caption trimming, textline trimming, VLM caption pass, per-crop VLM refine). Still fails on caption removal for pages 12/21/60; VLM boxes include surrounding text or captions are missed.
- **Potential solutions / known-good approaches:**
  - **PaddleOCR layout detection (PP-Structure / PP-DocLayout):** Dedicated layout models detect `image/figure` vs `caption/text` regions and return bounding boxes suitable for cropping (more direct fit to our failure mode). If it works, we can replace the heuristic cropper with layout detection.
  - **LayoutParser + Detectron2 (PubLayNet/DocLayNet):** Document layout detection models trained to separate figures and captions; heavier dependencies but likely strong for page layout segmentation.
  - **docTR (text detection + masking):** Use learned text-line detection to mask text, then take the largest remaining non-text component as the image region.
- **Next experiment:** Run PaddleOCR LayoutDetection on pages 12/21/60, compare crops to current VLM output, and decide whether to integrate as a new module or as a new detection mode in crop_illustrations_guided_v1.
### 20260124-1110 — Why figure-cropping is hard + candidate solutions (notes)
- **Context (why hard here):** Halftone photos + thin borders + nearby captions make simple thresholding/connected-components unstable; text/halftone often looks similar. OCR “data-count” is sometimes noisy, so naive expected-counts over-split or invent crops. Mixed layouts (full photos, logos, signatures, multi-photo pages) make a single CV kernel brittle.
- **Current approach (struggles):** `crop_illustrations_guided_v1` uses CV first (contour/nonwhite/layout) and VLM rescue to improve boxes. CV can fragment photos or return duplicates; VLM sometimes returns boxes that still include captions or header text without extra trimming. We added layout-text trimming and VLM retry guards, but several pages still show partial or duplicate crops.
- **Potential solutions to evaluate:**
  - **Layout detection models** (figures/text/headers) via LayoutParser/Detectron2 using PubLayNet/DocLayNet weights; use “figure” boxes as crops and text boxes to trim captions.
  - **PaddleOCR PP-Structure LayoutDetection** to get image + text regions (fast, no training), then trim text bands from image boxes.
  - **Document layout OCR stacks** (e.g., docTR) that expose block/region boxes for figures + text.
  - **Projection-profile + whitespace-gap splitting** as a classic heuristic for multi-photo pages (split by large horizontal gaps, then trim caption band per segment).
  - **Full VLM-first**: use GPT-5.1 vision to directly return image + caption boxes; keep CV only as fallback or validation.
- **Next:** run a controlled experiment matrix (layout-only vs VLM-first vs hybrid) on a fixed set of pages and pick the most reliable approach before full rerun.
### 20260124-1330 — Candidate libraries + why figure-cropping is hard (sources + plan)
- **Why it’s harder than “just find the photo”:** Halftone dots and faint borders cause photos to look like text to classic CV; captions are visually attached to photos after binarization; and multi-photo layouts vary a lot page-to-page.
- **Current approach + struggles:** `crop_illustrations_guided_v1` uses a mix of CV + VLM boxes + textline trimming. It still produces crops with captions/body text on pages like 12/21/60 or fragments around headers/signatures.
- **Potential solutions to try (known-good approaches):**
  - **PaddleOCR LayoutDetection / PP-DocLayout** to detect `image/figure` vs `caption/text` and crop only image boxes.
  - **LayoutParser + Detectron2** with PubLayNet/DocLayNet weights for figure/caption separation.
  - **DocLayNet-trained YOLO models** (e.g., YOLOv11) for `Picture`/`Caption` labels.
  - **Text detection + masking** (e.g., docTR or PaddleOCR text detector) to remove text and keep the largest non-text component.
- **Plan:** run a small experiment matrix (layout-only vs VLM-first vs hybrid), inspect outputs for all image pages, and lock in the best approach for the pipeline.
### 20260124-1515 — Why cropping is hard + known-good alternatives + current approach
- **Why this is harder than it looks:** these scans are halftone/photographic, so simple connected-components and morphology can fragment photos or absorb captions; captions are visually near photos but semantically separate, so classic CV often keeps them. Mixed layouts (text + photos + seals/signatures) increase false splits.
- **Current approach (in this repo):** VLM-first box detection (GPT-5.1 vision) with CV fallback, plus conservative caption/text trimming. This has been the most stable on the Onward scans but is more expensive and still sensitive to caption bleed or over-trim in rare cases.
- **Known-good alternatives to evaluate:**
  - Layout-aware detectors via LayoutParser with PubLayNet/DocLayNet-trained models (Detectron2 backends) for figure/graphic regions.
  - PaddleOCR PP-Structure (layout detection + figure/table/region parsing) as an off-the-shelf layout pipeline.
  - Train/fine-tune a layout model on a small labeled subset of this book (few pages) to better separate figures/captions in this domain.
- **Status:** keep VLM-first for correctness now; consider a layout-detector swap when cost or latency becomes a priority.
### 20260124-1535 — Why cropping is hard + potential solutions (notes + inspection)
- **Why this is harder than it seems:** Halftone photos + faint borders make text/figure separation ambiguous; captions become connected components after binarization; page layouts vary (full‑page photos, embedded photos, multi‑photo pages), so a single morphology recipe overfits.
- **Current approach + struggles:** `crop_illustrations_guided_v1` uses VLM box detection with CV fallback, plus caption/textline trimming. It is the most reliable so far, but still risks including header/body text on some non‑photo elements (e.g., signature blocks) and can over‑ or under‑trim when text is visually fused with photo grain.
- **Potential solutions / known‑good approaches to evaluate:**
  - **PaddleOCR PP‑Structure / LayoutDetection (PP‑DocLayout):** layout models return `figure`/`caption` regions; crop only figure boxes and explicitly exclude caption boxes.
  - **LayoutParser + Detectron2 (PubLayNet/DocLayNet weights):** layout detectors for figure/caption separation; heavier deps but accurate.
  - **docTR (text detection + masking):** detect text lines, mask them, then compute largest non‑text component as image region.
  - **OpenCV DNN text detectors (EAST/DB):** use learned text detection to create stronger text masks before connected‑component cropping.

Impact
- Story-scope impact: documented why CV is brittle here and listed concrete library options to test against our current VLM‑first approach.
- Pipeline-scope impact: establishes alternative paths (layout detection or text‑masking) if VLM‑first remains imperfect.
- Evidence: output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-001-000.jpg, output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-012-000.jpg, output/runs/onward-canonical/03_crop_illustrations_guided_v1/images/page-021-000.jpg.
- Next: run a focused experiment matrix (VLM‑first vs PaddleOCR layout vs text‑masking) on pages 12/21/38/60 and pick the most consistent approach.
### 20260216 — Image extraction broken out to sub-story
- **Result:** After ~10 iterations of heuristic VLM cropping + caption trimming without resolving caption/header bleed on pages 12/21/38/60, decided to take a systematic evaluation approach instead of more ad-hoc iteration.
- **Action:** Created **Story 125** (`story-125-image-extraction-eval-promptfoo.md`) as a sub-story focused on using **promptfoo** (adopted in cine-forge story-035) to build a golden dataset of manually cropped reference images and systematically evaluate prompt × model combinations for photo extraction. This mirrors the cine-forge benchmarking pattern: prompt templates × provider matrix × golden references × Python scorers.
- **Rationale:** The image cropping problem is fundamentally about finding the right VLM prompt and model, not about more CV heuristics. A structured eval with human-defined ground truth will converge faster than continued heuristic tuning.
- **Next:** Complete Story 125 (golden dataset + promptfoo eval + winning prompt/model), then return here to wire the result into the Onward recipe and finish the remaining acceptance criteria (end-to-end run, chapter HTML verification, table spot-checks).
### 20260216b — Story 125 complete: Gemini 3 Pro wired into image cropping
- **Result:** Story 125 evaluation found **Gemini 3 Pro + baseline prompt** as clear winner (0.856 avg score, 77% pass rate across 13 test pages). Also tested Florence-2 and Surya layout models — Florence-2 had highest pass rate (85%) but lower precision.
- **Action:** Created `modules/common/google_client.py` (Gemini vision wrapper), added Gemini dispatch to `crop_illustrations_guided_v1`, updated Onward recipe to use `rescue_model: gemini-3-pro-preview` with `rescue_max_tokens: 4096`.
- **Bug found during validation:** Gemini returns `image_box` as `[x0, y0, x1, y1]` array instead of `{x0, y0, x1, y1}` dict. Fixed parser in `_call_vlm_boxes()` and `_call_vlm_caption_boxes()` to handle both formats.
- **Validated:** 3-page smoke test (Image000, Image020, Image021) produced 4 clean crops with no caption/header bleed. Caption schema detection working correctly.
- **Next:** Full pipeline re-run on all 60 pages with new Gemini model, then chapter HTML verification and remaining acceptance criteria.
