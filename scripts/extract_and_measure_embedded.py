#!/usr/bin/env python3
"""Extract embedded images and measure them directly."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.extract.extract_pdf_images_fast_v1.main import (
    _estimate_line_height_px,
    _extract_image_from_xobject,
    _page_max_image_dpi,
    _load_pdf_reader,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--out-dir", default="/tmp/embedded-extract")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reader = _load_pdf_reader(args.pdf)
    if reader is None:
        print("Error: Could not load PDF")
        return 1

    if args.page > len(reader.pages):
        print(f"Error: Page {args.page} out of range")
        return 1

    page_obj = reader.pages[args.page - 1]

    # Get page info
    try:
        media_box = page_obj.mediabox
        page_w_pts = float(media_box.width)
        page_h_pts = float(media_box.height)
    except Exception as e:
        print(f"Error getting page dimensions: {e}")
        return 1

    max_source_dpi = _page_max_image_dpi(page_obj)
    print(f"Page {args.page}:")
    print(f"  Dimensions: {page_w_pts:.1f} x {page_h_pts:.1f} pts")
    print(f"  Max source DPI: {max_source_dpi}")

    # Extract embedded image
    resources = page_obj.get("/Resources") if hasattr(page_obj, "get") else None
    xobject = None
    if resources and hasattr(resources, "get"):
        xobject = resources.get("/XObject")

    result = _extract_image_from_xobject(xobject, page_w_pts, page_h_pts)

    if result is None:
        print("Error: Could not extract embedded image")
        return 1

    img, metadata = result
    print(f"\nExtracted image:")
    print(f"  Size: {img.width} x {img.height}")
    print(f"  Mode: {img.mode}")
    print(f"  Format: {metadata.get('format')}")
    print(f"  Coverage: {metadata.get('coverage_x'):.3f} x {metadata.get('coverage_y'):.3f}")
    print(f"  Is full page: {metadata.get('is_full_page')}")

    # Calculate effective DPI
    effective_dpi_x = img.width / (page_w_pts / 72.0)
    effective_dpi_y = img.height / (page_h_pts / 72.0)
    print(f"  Effective DPI: {effective_dpi_x:.1f} x {effective_dpi_y:.1f}")

    # Save extracted image
    img_path = out_dir / f"embedded_page{args.page:03d}.png"
    img.save(img_path)
    print(f"\nSaved to: {img_path}")

    # Measure line height
    line_height = _estimate_line_height_px(img)
    print(f"\nMeasured line height: {line_height:.2f} px")

    # Compare to what we'd get at different DPIs
    print(f"\nScaling comparison:")
    print(f"  At 72 DPI: {line_height * (72 / effective_dpi_x):.2f} px")
    print(f"  At 150 DPI: {line_height * (150 / effective_dpi_x):.2f} px")
    print(f"  At 300 DPI: {line_height * (300 / effective_dpi_x):.2f} px")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
