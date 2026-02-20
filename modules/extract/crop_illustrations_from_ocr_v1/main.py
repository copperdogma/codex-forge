"""Crop illustrations from OCR bounding boxes.

Reads OCR output (page_html_v1 schema) containing illustration bounding boxes
and crops them from source images. Optionally generates transparent PNG versions
for B&W artwork.
"""

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

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


def _make_transparent(img: Image.Image, threshold: int = 230) -> Image.Image:
    """Convert white background to transparent for B&W artwork using grayscale as alpha.

    This creates smooth anti-aliased edges by using the inverted grayscale value
    as the alpha channel (dark = opaque, white = transparent). Light pixels above
    the threshold are forced to fully transparent to avoid white fringing.

    Args:
        img: Input image
        threshold: Grayscale value above which pixels become fully transparent (default 230)

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


def _normalize_output_format(output_format: Optional[str]) -> tuple[str, str]:
    fmt = (output_format or "png").strip().lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"png", "jpeg"}:
        raise ValueError(f"Unsupported output_format: {output_format}")
    ext = "png" if fmt == "png" else "jpg"
    return fmt, ext


def crop_illustrations(
    ocr_manifest: str,
    output_dir: str,
    run_id: Optional[str] = None,
    transparency: bool = False,
    threshold: int = 230,
    output_format: Optional[str] = None,
    jpeg_quality: int = 92
) -> List[Dict[str, Any]]:
    """Crop illustrations from OCR bounding boxes.

    Args:
        ocr_manifest: Path to OCR JSONL (page_html_v1 schema with illustrations field)
        output_dir: Output directory for cropped images
        run_id: Optional run identifier
        transparency: Generate alpha versions for B&W images
        threshold: White threshold for transparency
        output_format: Output image format (png or jpeg)
        jpeg_quality: JPEG quality when output_format=jpeg

    Returns:
        List of manifest records for cropped illustrations
    """
    ensure_dir(output_dir)
    images_dir = os.path.join(output_dir, "images")
    ensure_dir(images_dir)

    pages = list(read_jsonl(ocr_manifest))
    manifest = []

    fmt, ext = _normalize_output_format(output_format)
    if transparency and fmt == "jpeg":
        _log("  WARNING: transparency requested with JPEG output; disabling transparency.")
        transparency = False

    _log(f"Processing {len(pages)} OCR pages...")

    illustration_count = 0
    for page_rec in pages:
        page_num = page_rec.get("page_number")
        image_path = page_rec.get("image")
        illustrations = page_rec.get("illustrations", [])

        if not illustrations:
            continue

        if not image_path or not os.path.exists(image_path):
            _log(f"  Page {page_num}: Image not found, skipping")
            continue

        _log(f"  Page {page_num}: Found {len(illustrations)} illustration(s)")

        # Load source image once for this page
        page_img = Image.open(image_path)

        for illus_idx, illus in enumerate(illustrations):
            bbox = illus.get("bbox", {})
            alt = illus.get("alt", "")

            # Extract bbox coordinates
            x = bbox.get("x", 0)
            y = bbox.get("y", 0)
            width = bbox.get("width", 0)
            height = bbox.get("height", 0)

            if width == 0 or height == 0:
                _log(f"    Illustration {illus_idx}: Invalid bbox, skipping")
                continue

            # Crop illustration
            x1 = x + width
            y1 = y + height
            cropped = page_img.crop((x, y, x1, y1))

            # Generate filename
            filename = f"page-{page_num:03d}-{illus_idx:03d}.{ext}"
            filepath = os.path.join(images_dir, filename)

            # Save original
            if fmt == "jpeg":
                if cropped.mode not in ("RGB", "L"):
                    cropped = cropped.convert("RGB")
                cropped.save(filepath, "JPEG", quality=jpeg_quality, optimize=True)
            else:
                cropped.save(filepath, "PNG")

            # Generate alpha version if B&W and transparency enabled
            filename_alpha = None
            has_transparency = False

            if transparency and _is_bw_image(cropped):
                filename_alpha = f"page-{page_num:03d}-{illus_idx:03d}-alpha.png"
                filepath_alpha = os.path.join(images_dir, filename_alpha)

                cropped_alpha = _make_transparent(cropped, threshold)
                cropped_alpha.save(filepath_alpha, "PNG")
                has_transparency = True

            # Build manifest record
            record = {
                "schema_version": "illustration_v1",
                "module_id": "crop_illustrations_from_ocr_v1",
                "run_id": run_id,
                "created_at": _utc(),
                "source_image": image_path,
                "source_page": page_num,
                "filename": filename,
                "filename_alpha": filename_alpha,
                "has_transparency": has_transparency,
                "alt": alt,
                "bbox": {
                    "x": x,
                    "y": y,
                    "x1": x1,
                    "y1": y1,
                    "width": width,
                    "height": height
                }
            }

            manifest.append(record)
            illustration_count += 1

    _log(f"\nCropped {illustration_count} illustration(s) from {len(pages)} pages")
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Crop illustrations from OCR bounding boxes"
    )
    parser.add_argument(
        "--ocr-manifest",
        required=True,
        help="OCR JSONL manifest (page_html_v1 with illustrations field)"
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
        "--output-format",
        default="png",
        choices=["png", "jpeg", "jpg"],
        help="Output image format: png (default) or jpeg"
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=92,
        help="JPEG quality when output-format=jpeg (default 92)"
    )

    args = parser.parse_args()

    # Crop illustrations
    manifest = crop_illustrations(
        ocr_manifest=args.ocr_manifest,
        output_dir=args.output_dir,
        run_id=args.run_id,
        transparency=args.transparency,
        threshold=args.threshold,
        output_format=args.output_format,
        jpeg_quality=args.jpeg_quality
    )

    # Save manifest
    manifest_path = os.path.join(args.output_dir, "illustration_manifest.jsonl")
    save_jsonl(manifest_path, manifest)

    _log(f"Manifest: {manifest_path}")
    _log(f"Images: {os.path.join(args.output_dir, 'images')}")


if __name__ == "__main__":
    main()
