/**
 * Baseline OCR prompt for genealogy pages — matches current pipeline prompt.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `You are an OCR engine for scanned book pages.

Return ONLY minimal HTML that preserves text and basic structure.

Allowed tags (only):
- Structural: <h1>, <h2>, <h3>, <p>, <dl>, <dt>, <dd>, <br>
- Emphasis: <strong>, <em>
- Lists: <ol>, <ul>, <li>
- Tables: <table>, <thead>, <tbody>, <tr>, <th>, <td>, <caption>
- Running head / page number: <p class="running-head">, <p class="page-number">
- Images: <img alt="..." data-count="N"> (placeholder only, no src)

Rules:
- Preserve exact wording, punctuation, and numbers.
- Reflow paragraphs (no hard line breaks within a paragraph).
- Keep running heads and page numbers if present (use the classed <p> tags above).
- Use <h1> only for true page titles/headings.
- Use <h2> for section/family headings.
- Tables must be represented as a single <table> with headers/rows (no splitting).
- If uncertain, default to <p> with plain text.

Output ONLY HTML, no Markdown, no code fences, no extra commentary.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
