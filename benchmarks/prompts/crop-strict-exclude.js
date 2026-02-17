/**
 * Strict-exclude prompt for image crop extraction.
 * Adapts image format per provider via shared helpers.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `Find every photograph, illustration, or graphic on this scanned book page. Return their bounding boxes.

CRITICAL RULES:
1. Bounding boxes must contain ONLY the visual element — zero text of any kind
2. Captions are NOT part of the image. If italic text like "Aerial photo of ranch buildings" appears below a photo, your box must end ABOVE that text.
3. Credit lines like "Illustration by..." are NOT part of the image.
4. Page numbers are NOT part of any image.
5. If a photo has a physical border or frame in the print, include the border but not any text outside it.
6. For oval/vignette photos, use a rectangular bounding box that tightly encloses the oval.
7. Decorative title text (e.g., large stylized book titles) counts as a graphic element.

Return JSON: {"images": [{"description": "...", "bbox": [x0, y0, x1, y1]}]}
Coordinates are normalized 0.0-1.0 (top-left origin).
Return ONLY the JSON.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
