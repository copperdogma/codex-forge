/**
 * Conditional crop validation prompt.
 * Two-phase: classify image type, then validate with appropriate criteria.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `Analyze this cropped region from a scanned book page in two steps.

STEP 1 - CLASSIFY the image type:
- "photo": A photograph (portrait, group photo, landscape, etc.)
- "graphic": A logo, seal, drawing, sketch, diagram, or illustration
- "plaque": A plaque, monument, sign, or inscription where text is part of the object

STEP 2 - VALIDATE the crop quality based on type:

For ALL types, FAIL if:
- External text is present (captions, body text, page numbers, credit lines that are NOT part of the photographed/drawn object)
- More than 10% of the area is blank white space
- The main subject is obviously cut off (missing body parts, truncated objects)

Additional checks by type:
- "photo": Subject should be centered and complete. Look for caption text below/above.
- "graphic": Drawing/logo should be fully contained with minimal bleed.
- "plaque": Text ON the plaque is expected and acceptable.

Return JSON:
{
  "image_type": "photo" | "graphic" | "plaque",
  "verdict": "pass" or "fail",
  "has_external_text": true or false,
  "image_pct": estimated percentage of crop that is actual image content (0-100),
  "reason": "brief explanation"
}

Return ONLY valid JSON.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
