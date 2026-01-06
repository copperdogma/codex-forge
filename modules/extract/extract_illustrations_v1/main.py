"""Extract illustrations from rendered page images using CV contour detection.

Based on the existing spike_cropper_cv.py approach with added transparency processing.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from modules.common import ensure_dir, save_jsonl, read_jsonl

Image.MAX_IMAGE_PIXELS = None


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _log(message: str):
    """Simple logging function."""
    print(message, flush=True)


def _is_bw_image(img: Image.Image) -> bool:
    """Check if image is black & white (grayscale or near-grayscale)."""
    if img.mode in ('L', '1'):
        return True

    if img.mode == 'RGB' or img.mode == 'RGBA':
        # Sample pixels to check if color channels are similar
        img_array = np.array(img)
        if img.mode == 'RGBA':
            rgb = img_array[:, :, :3]
        else:
            rgb = img_array

        # Check standard deviation across color channels
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        color_variance = np.std([np.mean(r), np.mean(g), np.mean(b)])

        return color_variance < 5

    return False


def _make_transparent(img: Image.Image, threshold: int = 240) -> Image.Image:
    """Convert white background to transparent for B&W artwork using grayscale as alpha.

    This creates smooth anti-aliased edges by using the inverted grayscale value
    as the alpha channel (dark = opaque, white = transparent). Light pixels above
    the threshold are forced to fully transparent to avoid white fringing.

    Args:
        img: Input image
        threshold: Grayscale value above which pixels become fully transparent (default 240)

    Returns:
        RGBA image with grayscale-based alpha
    """
    # Convert to grayscale to get luminance
    if img.mode != 'L':
        gray = img.convert('L')
    else:
        gray = img

    # Convert to RGB if needed
    if img.mode in ('L', '1'):
        rgb = img.convert('RGB')
    else:
        rgb = img.convert('RGB')

    # Use inverted grayscale as alpha (255 - gray_value)
    # Dark pixels (low gray value) → high alpha (opaque)
    # White pixels (high gray value) → low alpha (transparent)
    rgb_array = np.array(rgb)
    gray_array = np.array(gray)

    # Invert grayscale to get alpha channel
    alpha_array = 255 - gray_array

    # Force light pixels (near-white) to fully transparent to avoid fringing
    alpha_array[gray_array > threshold] = 0

    # Create RGBA
    rgba_array = np.dstack((rgb_array, alpha_array))

    return Image.fromarray(rgba_array.astype('uint8'), 'RGBA')


def _boxes_overlap(box1: Dict, box2: Dict) -> bool:
    """Check if two boxes overlap at all."""
    # Boxes don't overlap if one is completely to the left/right/above/below the other
    if (box1["x1"] <= box2["x0"] or  # box1 is to the left of box2
        box1["x0"] >= box2["x1"] or  # box1 is to the right of box2
        box1["y1"] <= box2["y0"] or  # box1 is above box2
        box1["y0"] >= box2["y1"]):   # box1 is below box2
        return False
    return True


def _filter_overlapping_boxes(boxes: List[Dict]) -> List[Dict]:
    """Remove boxes that overlap with larger boxes, keeping only the largest.

    Args:
        boxes: List of boxes sorted by area (largest first)

    Returns:
        Filtered list with no overlapping boxes
    """
    if not boxes:
        return []

    kept = []
    for box in boxes:
        # Check if this box overlaps with any already-kept box
        overlaps = False
        for kept_box in kept:
            if _boxes_overlap(kept_box, box):
                overlaps = True
                break

        if not overlaps:
            kept.append(box)

    return kept


def detect_boxes(
    image_path: Path,
    blur: int = 5,
    min_area_ratio: float = 0.02,
    max_area_ratio: float = 0.99,
    min_width: int = 100,
    min_height: int = 100
) -> List[Dict[str, int]]:
    """Detect illustration bounding boxes using CV contour detection.

    Args:
        image_path: Path to page image
        blur: Gaussian blur kernel size (must be odd)
        min_area_ratio: Minimum box area as fraction of page area
        max_area_ratio: Maximum box area as fraction of page area
        min_width: Minimum box width in pixels
        min_height: Minimum box height in pixels

    Returns:
        List of bounding boxes {x0, y0, x1, y1} (non-overlapping)
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur_k = blur if blur % 2 == 1 else blur + 1
    gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morph open to drop specks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape[:2]
    img_area = w * h
    boxes = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area

        # Filter by area ratio
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue

        # Filter by minimum pixel dimensions (skip tiny decorative elements)
        if cw < min_width or ch < min_height:
            continue

        # Require reasonable aspect ratio (avoid text blocks and page-wide gutters)
        # Illustrations are typically square-ish (0.3 to 3.0 aspect ratio)
        aspect = cw / max(ch, 1)
        if aspect > 3.0 or aspect < 0.3:
            continue

        boxes.append({
            "x0": int(x),
            "y0": int(y),
            "x1": int(x + cw),
            "y1": int(y + ch),
            "width": int(cw),
            "height": int(ch),
            "area_ratio": round(ratio, 4)
        })

    # Sort by area (largest first)
    boxes.sort(key=lambda b: b["width"] * b["height"], reverse=True)

    # Remove overlapping boxes (keep only largest non-overlapping)
    boxes = _filter_overlapping_boxes(boxes)

    return boxes


def extract_illustrations(
    pages_manifest: str,
    output_dir: str,
    run_id: Optional[str] = None,
    transparency: bool = False,
    threshold: int = 230,
    blur: int = 5,
    min_area_ratio: float = 0.02,
    max_area_ratio: float = 0.99,
    min_width: int = 100,
    min_height: int = 100,
    topk: int = 5
) -> List[Dict[str, Any]]:
    """Extract illustrations from page images.

    Args:
        pages_manifest: Path to pages JSONL (with 'page' and 'image' fields)
        output_dir: Output directory for cropped images
        run_id: Optional run identifier
        transparency: Generate alpha versions for B&W images
        threshold: White threshold for transparency
        blur: Gaussian blur kernel size
        min_area_ratio: Min box area ratio
        max_area_ratio: Max box area ratio
        topk: Maximum boxes to extract per page

    Returns:
        List of manifest records for extracted illustrations
    """
    ensure_dir(output_dir)
    images_dir = os.path.join(output_dir, "images")
    ensure_dir(images_dir)

    pages = list(read_jsonl(pages_manifest))
    manifest = []

    _log(f"Processing {len(pages)} page images...")

    for page_rec in pages:
        page_num = page_rec.get("page", page_rec.get("page_number"))
        image_path = page_rec.get("image")

        if not image_path or not os.path.exists(image_path):
            _log(f"  Page {page_num}: Image not found, skipping")
            continue

        # Detect bounding boxes
        boxes = detect_boxes(
            Path(image_path),
            blur=blur,
            min_area_ratio=min_area_ratio,
            max_area_ratio=max_area_ratio,
            min_width=min_width,
            min_height=min_height
        )

        if not boxes:
            continue

        # Limit to topk boxes per page
        boxes = boxes[:topk]

        _log(f"  Page {page_num}: Found {len(boxes)} illustration(s)")

        # Crop and save each box
        page_img = Image.open(image_path)

        for box_idx, box in enumerate(boxes):
            # Crop illustration
            cropped = page_img.crop((box["x0"], box["y0"], box["x1"], box["y1"]))

            # Generate filename
            filename = f"page-{page_num:03d}-{box_idx:03d}.png"
            filepath = os.path.join(images_dir, filename)

            # Save original
            cropped.save(filepath, "PNG")

            # Generate alpha version if B&W and transparency enabled
            filename_alpha = None
            has_transparency = False

            if transparency and _is_bw_image(cropped):
                filename_alpha = f"page-{page_num:03d}-{box_idx:03d}-alpha.png"
                filepath_alpha = os.path.join(images_dir, filename_alpha)

                cropped_alpha = _make_transparent(cropped, threshold)
                cropped_alpha.save(filepath_alpha, "PNG")
                has_transparency = True

            # Build manifest record
            record = {
                "schema_version": "illustration_v1",
                "module_id": "extract_illustrations_v1",
                "run_id": run_id,
                "created_at": _utc(),
                "source_image": image_path,
                "source_page": page_num,
                "filename": filename,
                "filename_alpha": filename_alpha,
                "has_transparency": has_transparency,
                "bbox": {
                    "x0": box["x0"],
                    "y0": box["y0"],
                    "x1": box["x1"],
                    "y1": box["y1"]
                },
                "width": box["width"],
                "height": box["height"],
                "area_ratio": box["area_ratio"]
            }

            manifest.append(record)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Extract illustrations from page images using CV contour detection")
    parser.add_argument("--pages", required=True, help="Pages JSONL manifest (with page and image fields)")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--run-id", help="Run identifier")
    parser.add_argument("--transparency", action="store_true", help="Generate alpha versions for B&W images")
    parser.add_argument("--threshold", type=int, default=230, help="White threshold for transparency (default 230)")
    parser.add_argument("--blur", type=int, default=5, help="Gaussian blur kernel size")
    parser.add_argument("--min-area-ratio", type=float, default=0.02, help="Min box area ratio (default 0.02)")
    parser.add_argument("--max-area-ratio", type=float, default=0.99, help="Max box area ratio")
    parser.add_argument("--min-width", type=int, default=100, help="Min box width in pixels (default 100)")
    parser.add_argument("--min-height", type=int, default=100, help="Min box height in pixels (default 100)")
    parser.add_argument("--topk", type=int, default=5, help="Max boxes per page")

    args = parser.parse_args()

    # Extract illustrations
    manifest = extract_illustrations(
        pages_manifest=args.pages,
        output_dir=args.output_dir,
        run_id=args.run_id,
        transparency=args.transparency,
        threshold=args.threshold,
        blur=args.blur,
        min_area_ratio=args.min_area_ratio,
        max_area_ratio=args.max_area_ratio,
        min_width=args.min_width,
        min_height=args.min_height,
        topk=args.topk
    )

    # Save manifest
    manifest_path = os.path.join(args.output_dir, "illustration_manifest.jsonl")
    save_jsonl(manifest_path, manifest)

    _log(f"\nExtracted {len(manifest)} illustration(s)")
    _log(f"Manifest: {manifest_path}")
    _log(f"Images: {os.path.join(args.output_dir, 'images')}")


if __name__ == "__main__":
    main()
