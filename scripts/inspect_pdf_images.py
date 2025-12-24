#!/usr/bin/env python3
"""
Inspect PDF structure to determine if full-page embedded images exist.

This script checks:
1. How many XObject images exist per page
2. Image dimensions vs page dimensions
3. Whether images cover the full page
4. Image format and color space
"""

import argparse
import json
import sys
from typing import Dict, Any, List, Optional


def _resolve_obj(obj):
    """Resolve indirect PDF objects."""
    try:
        return obj.get_object()
    except Exception:
        return obj


def _extract_images_from_xobject(xobject, page_w_pts: float, page_h_pts: float) -> List[Dict[str, Any]]:
    """Extract image metadata from XObject resources."""
    images = []
    if not xobject:
        return images

    for name, ref in xobject.items():
        obj = _resolve_obj(ref)
        subtype = obj.get("/Subtype") if hasattr(obj, "get") else None

        if subtype == "/Image":
            width = obj.get("/Width")
            height = obj.get("/Height")
            color_space = obj.get("/ColorSpace")
            filter_type = obj.get("/Filter")

            # Calculate coverage percentage
            coverage_x = (width / page_w_pts) if page_w_pts > 0 else 0
            coverage_y = (height / page_h_pts) if page_h_pts > 0 else 0

            # Calculate DPI (assuming page dimensions are in points, 72 pts/inch)
            page_w_in = page_w_pts / 72.0
            page_h_in = page_h_pts / 72.0
            dpi_x = width / page_w_in if page_w_in > 0 else 0
            dpi_y = height / page_h_in if page_h_in > 0 else 0

            images.append({
                "name": str(name),
                "width": width,
                "height": height,
                "dpi_x": round(dpi_x, 2),
                "dpi_y": round(dpi_y, 2),
                "coverage_x": round(coverage_x, 2),
                "coverage_y": round(coverage_y, 2),
                "color_space": str(color_space) if color_space else None,
                "filter": str(filter_type) if filter_type else None,
                "is_full_page": coverage_x >= 0.95 and coverage_y >= 0.95,
            })
        elif subtype == "/Form":
            # Recurse into Form XObjects
            resources = obj.get("/Resources") if hasattr(obj, "get") else None
            nested = None
            if resources and hasattr(resources, "get"):
                nested = resources.get("/XObject")
            images.extend(_extract_images_from_xobject(nested, page_w_pts, page_h_pts))

    return images


def inspect_pdf(pdf_path: str, max_pages: Optional[int] = None) -> Dict[str, Any]:
    """Inspect a PDF for embedded images."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            print("Error: pypdf or PyPDF2 required", file=sys.stderr)
            sys.exit(1)

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    page_data = []
    full_page_image_count = 0
    multi_image_page_count = 0

    pages_to_check = min(total_pages, max_pages) if max_pages else total_pages

    for page_idx in range(pages_to_check):
        page = reader.pages[page_idx]

        try:
            media_box = page.mediabox
            page_w_pts = float(media_box.width)
            page_h_pts = float(media_box.height)
        except Exception as e:
            print(f"Warning: Could not read MediaBox for page {page_idx + 1}: {e}", file=sys.stderr)
            continue

        resources = page.get("/Resources") if hasattr(page, "get") else None
        xobject = None
        if resources and hasattr(resources, "get"):
            xobject = resources.get("/XObject")

        images = _extract_images_from_xobject(xobject, page_w_pts, page_h_pts)

        has_full_page_image = any(img["is_full_page"] for img in images)
        if has_full_page_image:
            full_page_image_count += 1
        if len(images) > 1:
            multi_image_page_count += 1

        page_data.append({
            "page": page_idx + 1,
            "page_width_pts": round(page_w_pts, 2),
            "page_height_pts": round(page_h_pts, 2),
            "image_count": len(images),
            "has_full_page_image": has_full_page_image,
            "images": images,
        })

    return {
        "pdf": pdf_path,
        "total_pages": total_pages,
        "pages_inspected": pages_to_check,
        "full_page_image_count": full_page_image_count,
        "multi_image_page_count": multi_image_page_count,
        "fast_extraction_viable": full_page_image_count == pages_to_check,
        "pages": page_data,
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect PDF for embedded images")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--max-pages", type=int, default=None, help="Maximum pages to inspect")
    parser.add_argument("--output", default=None, help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    result = inspect_pdf(args.pdf, args.max_pages)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
