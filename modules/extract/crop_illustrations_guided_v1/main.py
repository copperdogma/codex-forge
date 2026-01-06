"""Guided illustration cropping using OCR metadata + CV contour detection.

Two-pass approach:
1. OCR identifies pages with images (alt text + count)
2. This module runs CV detection ONLY on those pages, extracting N largest contours

This works because:
- We KNOW which pages have images (high confidence from GPT-5.1)
- CV just needs to find N largest non-text regions (not distinguish text from art)
- Falls back to vision model for edge cases
"""

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

import re

from modules.common import ensure_dir, save_jsonl, read_jsonl

Image.MAX_IMAGE_PIXELS = None


def _extract_images_from_html(html: str) -> List[Dict[str, Any]]:
    """Extract image metadata from HTML img tags (fallback for older OCR output)."""
    images = []
    pattern_with_count = r'<img\s+alt="([^"]*)"\s+data-count="(\d+)">'
    pattern_simple = r'<img\s+alt="([^"]*)"(?:\s*/)?>'

    found_positions = set()
    for match in re.finditer(pattern_with_count, html):
        alt = match.group(1)
        count = int(match.group(2))
        images.append({"alt": alt, "count": count})
        found_positions.add(match.start())

    for match in re.finditer(pattern_simple, html):
        if match.start() not in found_positions:
            full_match = html[match.start():match.start()+150]
            if 'data-count=' not in full_match:
                alt = match.group(1)
                images.append({"alt": alt, "count": 1})

    return images


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _log(message: str):
    """Simple logging function."""
    print(message, flush=True)


def _is_bw_image(img: Image.Image) -> bool:
    """Check if image is black & white (grayscale or near-grayscale).
    
    Handles beige/cream paper backgrounds by checking both color variance
    and saturation levels. Desaturated images (low saturation) are treated
    as B&W even if they have slight color variance from aged paper.
    """
    if img.mode in ('L', '1'):
        return True

    if img.mode == 'RGB' or img.mode == 'RGBA':
        img_array = np.array(img)
        if img.mode == 'RGBA':
            rgb = img_array[:, :, :3]
        else:
            rgb = img_array

        # Method 1: Check color variance (strict)
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        color_variance = np.std([np.mean(r), np.mean(g), np.mean(b)])
        if color_variance < 5:
            return True
        
        # Method 2: Check saturation (handles beige/cream backgrounds)
        # Convert to normalized RGB for saturation calculation
        rgb_norm = rgb.astype(np.float32) / 255.0
        max_val = np.max(rgb_norm, axis=2)
        min_val = np.min(rgb_norm, axis=2)
        delta = max_val - min_val
        
        # Calculate mean saturation (0.0 = grayscale, 1.0 = fully saturated)
        mean_saturation = np.mean(delta)
        
        # If saturation is very low (< 0.25), treat as B&W even with color variance
        # This handles beige/cream paper that has slight R/G/B differences but is effectively grayscale
        if mean_saturation < 0.25:
            return True
        
        # Fallback: if color variance is moderate (< 20) and saturation is low (< 0.30)
        if color_variance < 20 and mean_saturation < 0.30:
            return True

    return False


def _make_transparent(img: Image.Image, threshold: int = 230) -> Image.Image:
    """Convert white background to transparent for B&W artwork.
    
    First converts the image to proper grayscale to remove any beige/cream
    tint, then generates alpha channel from the grayscale values.
    """
    # Convert to proper grayscale first (removes beige/cream tint)
    # This ensures consistent black/white values regardless of paper color
    if img.mode != 'L':
        gray = img.convert('L')
    else:
        gray = img
    
    # Use the grayscale image for both RGB and alpha calculations
    # This ensures the final image is truly black & white (not beige-tinted)
    gray_array = np.array(gray)
    
    # Convert grayscale to RGB (single channel repeated for R, G, B)
    rgb_array = np.stack([gray_array, gray_array, gray_array], axis=2)

    # Invert grayscale to get alpha (dark = opaque, white/light = transparent)
    alpha_array = 255 - gray_array

    # Force near-white pixels fully transparent
    alpha_array[gray_array > threshold] = 0

    rgba_array = np.dstack((rgb_array, alpha_array))
    return Image.fromarray(rgba_array.astype('uint8'), 'RGBA')


def detect_contours_cv(
    image_path: Path,
    expected_count: int = 1,
    blur: int = 7,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.99,
    min_width: int = 50,
    min_height: int = 50,
    padding_percent: float = 0.05
) -> List[Dict[str, int]]:
    """Detect illustration bounding boxes using CV contour detection.

    Args:
        image_path: Path to page image
        expected_count: Number of illustrations expected on this page
        blur: Gaussian blur kernel size
        min_area_ratio: Minimum box area as fraction of page area
        max_area_ratio: Maximum box area as fraction of page area
        min_width: Minimum box width in pixels
        min_height: Minimum box height in pixels
        padding_percent: Percentage padding to add around detected boxes (default 0.15 = 15%)

    Returns:
        List of bounding boxes {x0, y0, x1, y1, width, height}
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
    candidates = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        ratio = area / img_area

        # Filter by area ratio
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue

        # Filter by minimum pixel dimensions
        if cw < min_width or ch < min_height:
            continue

        # Looser aspect ratio for guided detection (we know it's an image)
        aspect = cw / max(ch, 1)
        if aspect > 5.0 or aspect < 0.2:
            continue

        candidates.append({
            "x0": int(x),
            "y0": int(y),
            "x1": int(x + cw),
            "y1": int(y + ch),
            "width": int(cw),
            "height": int(ch),
            "area": area,
            "area_ratio": round(ratio, 4)
        })

    # Sort by area (largest first)
    candidates.sort(key=lambda b: b["area"], reverse=True)

    # Take top N non-overlapping candidates
    selected = []
    for candidate in candidates:
        if len(selected) >= expected_count:
            break

        # Check for overlap with already selected boxes
        overlaps = False
        for sel in selected:
            if _boxes_overlap(candidate, sel):
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

    # Add padding to selected boxes to capture lighter elements around main subject
    padded = []
    for box in selected:
        # Calculate padding in pixels
        pad_w = int(box["width"] * padding_percent)
        pad_h = int(box["height"] * padding_percent)

        # Expand box with padding, clamped to image boundaries
        x0 = max(0, box["x0"] - pad_w)
        y0 = max(0, box["y0"] - pad_h)
        x1 = min(w, box["x1"] + pad_w)
        y1 = min(h, box["y1"] + pad_h)

        padded.append({
            "x0": int(x0),
            "y0": int(y0),
            "x1": int(x1),
            "y1": int(y1),
            "width": int(x1 - x0),
            "height": int(y1 - y0),
            "area": int((x1 - x0) * (y1 - y0)),
            "area_ratio": round(((x1 - x0) * (y1 - y0)) / img_area, 4)
        })

    return padded


def _boxes_overlap(box1: Dict, box2: Dict) -> bool:
    """Check if two boxes overlap."""
    if (box1["x1"] <= box2["x0"] or box1["x0"] >= box2["x1"] or
        box1["y1"] <= box2["y0"] or box1["y0"] >= box2["y1"]):
        return False
    return True


def crop_illustrations_guided(
    ocr_manifest: str,
    output_dir: str,
    run_id: Optional[str] = None,
    transparency: bool = False,
    threshold: int = 230,
    blur: int = 7,
    min_area_ratio: float = 0.01,
    max_area_ratio: float = 0.99,
    min_width: int = 50,
    min_height: int = 50,
    highres_manifest: Optional[str] = None,
    padding_percent: float = 0.05
) -> List[Dict[str, Any]]:
    """Crop illustrations from pages identified by OCR.

    Args:
        ocr_manifest: Path to OCR JSONL (page_html_v1 schema with images field)
        output_dir: Output directory for cropped images
        run_id: Optional run identifier
        transparency: Generate alpha versions for B&W images
        threshold: White threshold for transparency
        blur: Gaussian blur kernel size for CV
        min_area_ratio: Min box area ratio for CV
        max_area_ratio: Max box area ratio for CV
        min_width: Min box width in pixels
        min_height: Min box height in pixels
        highres_manifest: Optional path to high-res page images manifest (for better quality crops)
        padding_percent: Percentage padding around detected boxes (default 0.05 = 5%)

    Returns:
        List of manifest records for cropped illustrations
    """
    ensure_dir(output_dir)
    images_dir = os.path.join(output_dir, "images")
    ensure_dir(images_dir)

    pages = list(read_jsonl(ocr_manifest))
    manifest = []

    # Build high-res page map from highres_manifest OR from image_native fields
    highres_page_map = {}

    # First, check if pages have image_native field (preferred)
    native_count = 0
    for page in pages:
        page_num = page.get("page_number")
        image_native = page.get("image_native")
        if page_num and image_native and os.path.exists(image_native):
            highres_page_map[page_num] = image_native
            native_count += 1

    if native_count > 0:
        _log(f"Using image_native from manifest for {native_count} pages")

    # If highres_manifest provided, override/supplement with those
    if highres_manifest:
        _log(f"Loading additional high-res images from {highres_manifest}")
        highres_pages = list(read_jsonl(highres_manifest))
        external_count = 0
        for hr_page in highres_pages:
            page_num = hr_page.get("page_number")
            # Check both image and image_native from external manifest
            image_path = hr_page.get("image_native") or hr_page.get("image")
            if page_num and image_path and os.path.exists(image_path):
                highres_page_map[page_num] = image_path
                external_count += 1
        _log(f"Loaded {external_count} high-res images from external manifest")

    # Filter to pages with images (check images field or extract from HTML)
    pages_with_images = []
    for p in pages:
        if p.get("images"):
            pages_with_images.append(p)
        elif p.get("html") and "<img" in p.get("html", ""):
            # Fallback: extract from HTML for older OCR output
            extracted = _extract_images_from_html(p.get("html", ""))
            if extracted:
                p["images"] = extracted
                pages_with_images.append(p)

    _log(f"Found {len(pages_with_images)} pages with images out of {len(pages)} total")

    for page_rec in pages_with_images:
        page_num = page_rec.get("page_number")
        image_path = page_rec.get("image")
        ocr_images = page_rec.get("images", [])

        # Use high-res image if available, otherwise use OCR image
        source_image_path = highres_page_map.get(page_num, image_path)

        if not source_image_path or not os.path.exists(source_image_path):
            _log(f"  Page {page_num}: Image not found, skipping")
            continue

        # Calculate expected count (sum of all image counts on this page)
        expected_count = sum(img.get("count", 1) for img in ocr_images)

        using_highres = source_image_path != image_path
        resolution_label = "high-res" if using_highres else "OCR-res"
        _log(f"  Page {page_num}: Expecting {expected_count} illustration(s) [{resolution_label}]")

        # Run CV detection with expected count
        boxes = detect_contours_cv(
            Path(source_image_path),
            expected_count=expected_count,
            blur=blur,
            min_area_ratio=min_area_ratio,
            max_area_ratio=max_area_ratio,
            min_width=min_width,
            min_height=min_height,
            padding_percent=padding_percent
        )

        if not boxes:
            _log(f"    CV detection found 0 boxes (expected {expected_count})")
            continue

        if len(boxes) < expected_count:
            _log(f"    CV detection found {len(boxes)} boxes (expected {expected_count})")

        # Load page image for cropping
        page_img = Image.open(source_image_path)

        # Match boxes with OCR image descriptions (by order/position)
        # Sort boxes by y-position to match reading order
        boxes_sorted = sorted(boxes, key=lambda b: (b["y0"], b["x0"]))

        # Flatten OCR image list (expand counts)
        ocr_descriptions = []
        for img in ocr_images:
            count = img.get("count", 1)
            for _ in range(count):
                ocr_descriptions.append(img.get("alt", ""))

        for box_idx, box in enumerate(boxes_sorted):
            # Get description from OCR if available
            alt = ""
            if box_idx < len(ocr_descriptions):
                alt = ocr_descriptions[box_idx]

            # Crop illustration
            cropped = page_img.crop((box["x0"], box["y0"], box["x1"], box["y1"]))

            # Generate filename
            filename = f"page-{page_num:03d}-{box_idx:03d}.png"
            filepath = os.path.join(images_dir, filename)

            # Save original
            cropped.save(filepath, "PNG")

            # Detect if image is color or B&W
            is_bw = _is_bw_image(cropped)
            is_color = not is_bw

            # Generate alpha version if B&W and transparency enabled
            filename_alpha = None
            has_transparency = False

            if transparency and is_bw:
                filename_alpha = f"page-{page_num:03d}-{box_idx:03d}-alpha.png"
                filepath_alpha = os.path.join(images_dir, filename_alpha)

                cropped_alpha = _make_transparent(cropped, threshold)
                cropped_alpha.save(filepath_alpha, "PNG")
                has_transparency = True

            # Build manifest record
            record = {
                "schema_version": "illustration_v1",
                "module_id": "crop_illustrations_guided_v1",
                "run_id": run_id,
                "created_at": _utc(),
                "source_image": image_path,
                "source_page": page_num,
                "filename": filename,
                "filename_alpha": filename_alpha,
                "has_transparency": has_transparency,
                "is_color": is_color,
                "alt": alt,
                "bbox": {
                    "x0": box["x0"],
                    "y0": box["y0"],
                    "x1": box["x1"],
                    "y1": box["y1"],
                    "width": box["width"],
                    "height": box["height"]
                },
                "area_ratio": box["area_ratio"],
                "detection_method": "cv_guided"
            }

            manifest.append(record)

    # Count color vs B&W illustrations
    color_count = sum(1 for m in manifest if m.get("is_color", False))
    bw_count = len(manifest) - color_count

    _log(f"\nCropped {len(manifest)} illustration(s) from {len(pages_with_images)} pages")
    _log(f"  Color: {color_count}, B&W: {bw_count}")
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Crop illustrations using OCR metadata + CV detection"
    )
    parser.add_argument(
        "--ocr-manifest",
        required=True,
        help="OCR JSONL manifest (page_html_v1 with images field)"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory"
    )
    parser.add_argument(
        "--run-id",
        help="Run identifier"
    )
    parser.add_argument(
        "--transparency",
        action="store_true",
        help="Generate alpha versions for B&W images"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=230,
        help="White threshold for transparency (default 230)"
    )
    parser.add_argument(
        "--blur",
        type=int,
        default=7,
        help="Gaussian blur kernel size for CV (default 7)"
    )
    parser.add_argument(
        "--min-area-ratio",
        type=float,
        default=0.01,
        help="Min box area ratio (default 0.01)"
    )
    parser.add_argument(
        "--max-area-ratio",
        type=float,
        default=0.99,
        help="Max box area ratio (default 0.99)"
    )
    parser.add_argument(
        "--min-width",
        type=int,
        default=50,
        help="Min box width in pixels (default 50)"
    )
    parser.add_argument(
        "--min-height",
        type=int,
        default=50,
        help="Min box height in pixels (default 50)"
    )
    parser.add_argument(
        "--highres-manifest",
        help="Optional high-res page images manifest (for better quality crops)"
    )
    parser.add_argument(
        "--padding-percent",
        type=float,
        default=0.05,
        help="Percentage padding around detected boxes (default 0.05 = 5%%)"
    )

    args = parser.parse_args()

    manifest = crop_illustrations_guided(
        ocr_manifest=args.ocr_manifest,
        output_dir=args.output_dir,
        run_id=args.run_id,
        transparency=args.transparency,
        threshold=args.threshold,
        blur=args.blur,
        min_area_ratio=args.min_area_ratio,
        max_area_ratio=args.max_area_ratio,
        min_width=args.min_width,
        min_height=args.min_height,
        highres_manifest=args.highres_manifest,
        padding_percent=args.padding_percent
    )

    # Save manifest
    manifest_path = os.path.join(args.output_dir, "illustration_manifest.jsonl")
    save_jsonl(manifest_path, manifest)

    _log(f"Manifest: {manifest_path}")
    _log(f"Images: {os.path.join(args.output_dir, 'images')}")


if __name__ == "__main__":
    main()
