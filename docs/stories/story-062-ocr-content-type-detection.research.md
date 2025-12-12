# Story 062 - OCR Content Type Detection Research Notes

Created: 2025-12-12

This note summarizes practical "content type detection" outputs from common OCR/layout systems,
and what is actionable for codex-forge's `elements_content_type_v1`.

## Executive Summary

- In practice, "content type detection" is usually document structure/layout analysis on top of OCR.
- Commercial APIs often expose hierarchy (page -> blocks/lines/words) plus specialized objects (tables, forms).
- For codex-forge, DocLayNet's 11-label taxonomy is a good default; PubLayNet is a coarse fallback.

## Google Cloud Vision OCR

- Vision OCR's document text detection can return a structured hierarchy (pages/blocks/paragraphs/words).
- This is useful for geometry-driven reasoning, but it is not a DocLayNet-style semantic label set by default.

Docs: https://cloud.google.com/vision/docs/fulltext-annotations

## AWS Textract

- Textract returns elements as "Block" objects with types such as PAGE/LINE/WORD and table/form-related types.
- Textract also has layout-oriented block types/roles (for example: title, header/footer, section header, list, table)
  depending on the API operation and feature set used.

Docs:
- https://docs.aws.amazon.com/textract/latest/dg/API_Block.html
- https://docs.aws.amazon.com/textract/latest/dg/how-it-works-selectables.html

## Azure AI Document Intelligence (Document Intelligence / Form Recognizer)

- The Layout model is described as extracting structure such as titles/headings/paragraphs/tables/selection marks.
- Some versions expose "paragraph roles" that are directly relevant to DocLayNet mapping (title, headings,
  page header/footer, page number, footnote, etc.).

Docs:
- https://learn.microsoft.com/azure/ai-services/document-intelligence/overview
- https://learn.microsoft.com/azure/ai-services/document-intelligence/concept-layout

## Dataset taxonomies (recommended defaults)

DocLayNet (recommended default): 11 labels
- Title, Section-header, Text, List-item, Table, Picture, Caption, Formula, Footnote, Page-header, Page-footer

Project: https://github.com/DS4SD/DocLayNet

PubLayNet (coarse fallback): 5 labels
- Title, Text, List, Table, Figure

Paper: https://arxiv.org/abs/1908.07836

## Actionable guidance for codex-forge

1) Prefer upstream-provided layout roles when available.
   - If an upstream adapter provides roles like TITLE/HEADER/FOOTER/LIST/TABLE, map those directly to DocLayNet
     with high confidence before heuristics/LLM.

2) Preserve bbox end-to-end.
   - Most "layout role" signals become much more reliable once bbox (normalized) is preserved through
     pagelines -> reconstructed pagelines -> elements_core.

3) Model form signals explicitly.
   - DocLayNet has no dedicated Form label. For gamebooks, treat:
     - "form fields" like "STAMINA =" as Text with subtype `form_field=true`
     - selection marks / key-value hints as Text with subtypes (when upstream provides them)

4) Do not force combat stat blocks into Table.
   - FF combat stat blocks like "MANTICORE  SKILL 11  STAMINA 11" often appear inline with narrative text.
     Treat as Text with subtype `combat_stats=true` rather than Table.

