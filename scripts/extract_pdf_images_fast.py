#!/usr/bin/env python3
"""
Fast extraction of embedded PDF images without rendering.

Uses pypdf to extract JPEG/PNG streams directly from PDF XObjects.
"""

import argparse
import io
import os
import time
from typing import Dict, Any, List, Optional, Tuple

from PIL import Image


def _resolve_obj(obj):
    """Resolve indirect PDF objects."""
    try:
        return obj.get_object()
    except Exception:
        return obj


def _extract_image_from_xobject(xobject, page_w_pts: float, page_h_pts: float) -> Optional[Tuple[Image.Image, Dict[str, Any]]]:
    """
    Extract the largest image from XObject resources.

    Returns (PIL.Image, metadata) or None if no suitable image found.
    """
    if not xobject:
        return None

    candidates = []

    for name, ref in xobject.items():
        obj = _resolve_obj(ref)
        subtype = obj.get("/Subtype") if hasattr(obj, "get") else None

        if subtype == "/Image":
            width = obj.get("/Width")
            height = obj.get("/Height")
            if not width or not height:
                continue

            # Calculate coverage
            coverage_x = width / page_w_pts if page_w_pts > 0 else 0
            coverage_y = height / page_h_pts if page_h_pts > 0 else 0
            is_full_page = coverage_x >= 0.95 and coverage_y >= 0.95

            candidates.append({
                "name": str(name),
                "obj": obj,
                "width": width,
                "height": height,
                "area": width * height,
                "coverage_x": coverage_x,
                "coverage_y": coverage_y,
                "is_full_page": is_full_page,
            })
        elif subtype == "/Form":
            # Recurse into Form XObjects
            resources = obj.get("/Resources") if hasattr(obj, "get") else None
            nested = None
            if resources and hasattr(resources, "get"):
                nested = resources.get("/XObject")
            result = _extract_image_from_xobject(nested, page_w_pts, page_h_pts)
            if result:
                return result

    if not candidates:
        return None

    # Pick the largest image (by area)
    candidates.sort(key=lambda c: c["area"], reverse=True)
    best = candidates[0]

    # Try to extract the image data
    obj = best["obj"]

    try:
        # Try to get raw image data
        # pypdf v3+ has .get_data(), older versions have ._data
        if hasattr(obj, "get_data"):
            data = obj.get_data()
        elif hasattr(obj, "_data"):
            data = obj._data
        else:
            return None

        # Try to decode as image
        img = Image.open(io.BytesIO(data))

        metadata = {
            "name": best["name"],
            "width": best["width"],
            "height": best["height"],
            "is_full_page": best["is_full_page"],
            "coverage_x": round(best["coverage_x"], 3),
            "coverage_y": round(best["coverage_y"], 3),
            "format": img.format,
            "mode": img.mode,
        }

        return (img, metadata)

    except Exception as e:
        print(f"Warning: Could not extract image {best['name']}: {e}")
        return None


def extract_pdf_images_fast(
    pdf_path: str,
    output_dir: str,
    start_page: int = 1,
    end_page: Optional[int] = None,
    format: str = "JPEG",
) -> Dict[str, Any]:
    """
    Extract embedded images from PDF without rendering.

    Returns timing and metadata for each extracted page.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError("pypdf or PyPDF2 required")

    os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    end_page = min(end_page or total_pages, total_pages)

    results = []
    total_extract_time = 0.0

    for page_idx in range(start_page - 1, end_page):
        page_num = page_idx + 1
        t0 = time.time()

        page = reader.pages[page_idx]

        try:
            media_box = page.mediabox
            page_w_pts = float(media_box.width)
            page_h_pts = float(media_box.height)
        except Exception as e:
            print(f"Warning: Could not read MediaBox for page {page_num}: {e}")
            continue

        resources = page.get("/Resources") if hasattr(page, "get") else None
        xobject = None
        if resources and hasattr(resources, "get"):
            xobject = resources.get("/XObject")

        result = _extract_image_from_xobject(xobject, page_w_pts, page_h_pts)

        if result:
            img, metadata = result

            # Save image
            out_path = os.path.join(output_dir, f"page-{page_num:03d}.{format.lower()}")
            if format.upper() == "JPEG":
                # Convert RGBA to RGB for JPEG
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(out_path, "JPEG", quality=95)
            else:
                img.save(out_path, format)

            extract_time = time.time() - t0
            total_extract_time += extract_time

            results.append({
                "page": page_num,
                "success": True,
                "output_path": out_path,
                "extract_time_sec": round(extract_time, 4),
                "image_width": img.width,
                "image_height": img.height,
                **metadata,
            })

            print(f"Page {page_num}: extracted {img.width}×{img.height} in {extract_time:.3f}s")
        else:
            results.append({
                "page": page_num,
                "success": False,
                "error": "No extractable image found",
            })
            print(f"Page {page_num}: no extractable image")

    return {
        "pdf": pdf_path,
        "start_page": start_page,
        "end_page": end_page,
        "pages_processed": len(results),
        "pages_extracted": sum(1 for r in results if r.get("success")),
        "total_extract_time_sec": round(total_extract_time, 3),
        "avg_time_per_page_sec": round(total_extract_time / len(results), 4) if results else 0,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Fast-extract embedded PDF images")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--outdir", required=True, help="Output directory for images")
    parser.add_argument("--start", type=int, default=1, help="Start page (1-based)")
    parser.add_argument("--end", type=int, default=None, help="End page (1-based)")
    parser.add_argument("--format", default="JPEG", choices=["JPEG", "PNG"], help="Output format")
    args = parser.parse_args()

    import json

    result = extract_pdf_images_fast(
        args.pdf,
        args.outdir,
        start_page=args.start,
        end_page=args.end,
        format=args.format,
    )

    # Save report
    report_path = os.path.join(args.outdir, "extract_report.json")
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nExtraction complete:")
    print(f"  Pages extracted: {result['pages_extracted']}/{result['pages_processed']}")
    print(f"  Total time: {result['total_extract_time_sec']:.3f}s")
    print(f"  Avg time/page: {result['avg_time_per_page_sec']:.4f}s")
    print(f"  Report: {report_path}")


if __name__ == "__main__":
    main()
