/**
 * Baseline prompt for image crop extraction.
 * Adapts image format per provider via shared helpers.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `You are analyzing a scanned book page to find all photographs, illustrations, logos, seals, or other non-text visual elements.

Return a JSON object with a single key "images" containing an array of objects. Each object should have:
- "description": brief description of the image
- "bbox": bounding box as [x0, y0, x1, y1] in normalized coordinates (0.0 to 1.0, where 0,0 is top-left)

Rules:
- Include photographs, illustrations, drawings, logos, seals, and signatures-with-seal blocks
- EXCLUDE all text: captions, headings, body text, page numbers, credit lines
- The bounding box must tightly contain ONLY the visual element, not any surrounding text
- If a caption appears below a photo, the box must stop ABOVE the caption
- If the entire page is a single image (like a book cover), return one box covering the full page

Return ONLY valid JSON, no other text.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
