/**
 * Two-step prompt for image crop extraction.
 * Adapts image format per provider via shared helpers.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `Analyze this scanned book page in two steps.

STEP 1 — INVENTORY: List every visual element on the page (photographs, illustrations, logos, seals, diagrams). For each, note what text appears directly adjacent (captions, credit lines, labels).

STEP 2 — BOUNDING BOXES: For each visual element from Step 1, provide a tight bounding box that includes ONLY the visual element and excludes ALL adjacent text (captions, credits, page numbers, body text).

Return your final answer as JSON: {"images": [{"description": "...", "adjacent_text": "...", "bbox": [x0, y0, x1, y1]}]}

Coordinates are normalized 0.0-1.0 where (0,0) is the top-left corner of the page.

IMPORTANT: The bbox must NOT include any text. If you're unsure where text ends and the image begins, err on the side of a smaller box that definitely excludes text.

Return ONLY the JSON object.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
