/**
 * Tolerant crop validation prompt.
 * Designed for scanned historical book pages — understands that old photos
 * have natural composition that shouldn't be penalized.
 */

const { buildMessages } = require("./_image-helpers");

const PROMPT_TEXT = `This is a cropped illustration extracted from a SCANNED HISTORICAL BOOK (genealogy, early 1900s-1980s). Evaluate crop quality.

Return JSON: {"verdict": "pass" or "fail", "reason": "brief explanation"}

IMPORTANT CONTEXT — these are scanned pages from old books. The following are NORMAL and should NOT cause a fail:
- Portrait photos cropped at the chest, waist, or knees (standard portrait composition)
- Group photos where some people at edges are partially visible (natural group photo framing)
- White corners around oval or round portrait photos
- White/light backgrounds in line drawings, sketches, or illustrations
- Landscape photos with sky, grass, or other natural "empty" areas
- Handwritten annotations, stamps, or dates ON the original photograph
- Faint page numbers at the very edge/corner from the book scan
- Halftone dot patterns or grain from the printing/scanning process
- Historical text printed directly ON a photograph (e.g. "Smith family, 1920")

FAIL ONLY for these CLEAR crop errors:
1. EXTERNAL PAGE TEXT: Printed body text, italic captions, or typed text from the BOOK PAGE (not from the photo itself) is visible in the crop
2. MASSIVE BLANK SPACE: More than 30% of the crop is empty white with no image content at all (not counting photo backgrounds or drawing backgrounds)
3. OBVIOUS WRONG CROP: The crop clearly contains the wrong region (e.g., mostly text with a tiny image fragment)

When in doubt, PASS. A slightly imperfect crop is better than rejecting a valid image.

Return ONLY valid JSON.`;

module.exports = function (context) {
  const { vars, provider } = context;
  return buildMessages(PROMPT_TEXT, vars.image, provider?.id || "");
};
