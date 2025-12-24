#!/usr/bin/env python3
"""
Compare extracted vs rendered images for quality assessment.
"""

import argparse
import os
from PIL import Image
from pdf2image import convert_from_path

Image.MAX_IMAGE_PIXELS = None


def compare_methods(pdf_path: str, page_num: int, render_dpi: int):
    """Compare fast extraction vs rendering for a single page."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            print("Error: pypdf required")
            return

    import io

    def _resolve_obj(obj):
        try:
            return obj.get_object()
        except Exception:
            return obj

    def _extract_image(page):
        resources = page.get("/Resources") if hasattr(page, "get") else None
        if not resources or not hasattr(resources, "get"):
            return None
        xobject = resources.get("/XObject")
        if not xobject:
            return None

        for name, ref in xobject.items():
            obj = _resolve_obj(ref)
            subtype = obj.get("/Subtype") if hasattr(obj, "get") else None
            if subtype == "/Image":
                try:
                    if hasattr(obj, "get_data"):
                        data = obj.get_data()
                    elif hasattr(obj, "_data"):
                        data = obj._data
                    else:
                        continue
                    return Image.open(io.BytesIO(data)), len(data)
                except Exception as e:
                    print(f"Warning: {e}")
                    continue
        return None, None

    # Extract
    reader = PdfReader(pdf_path)
    page = reader.pages[page_num - 1]

    try:
        media_box = page.mediabox
        page_w_pts = float(media_box.width)
        page_h_pts = float(media_box.height)
        page_w_in = page_w_pts / 72.0
        page_h_in = page_h_pts / 72.0
    except Exception as e:
        print(f"Error reading MediaBox: {e}")
        return

    extracted_img, data_size = _extract_image(page)

    # Render
    rendered_imgs = convert_from_path(pdf_path, dpi=render_dpi, first_page=page_num, last_page=page_num)
    rendered_img = rendered_imgs[0] if rendered_imgs else None

    print(f"\n=== Page {page_num} Comparison ===")
    print(f"\nPage dimensions: {page_w_pts:.1f} × {page_h_pts:.1f} pts ({page_w_in:.2f} × {page_h_in:.2f} in)")

    if extracted_img:
        embedded_dpi_x = extracted_img.width / page_w_in
        embedded_dpi_y = extracted_img.height / page_h_in
        print(f"\nExtracted (embedded JPEG):")
        print(f"  Dimensions: {extracted_img.width} × {extracted_img.height}")
        print(f"  Embedded DPI: {embedded_dpi_x:.1f} × {embedded_dpi_y:.1f}")
        print(f"  Mode: {extracted_img.mode}")
        print(f"  Format: {extracted_img.format}")
        print(f"  Data size: {data_size / 1024:.1f} KB")
    else:
        print("\nExtracted: FAILED")

    if rendered_img:
        rendered_dpi_x = rendered_img.width / page_w_in
        rendered_dpi_y = rendered_img.height / page_h_in
        print(f"\nRendered @ {render_dpi} DPI:")
        print(f"  Dimensions: {rendered_img.width} × {rendered_img.height}")
        print(f"  Actual DPI: {rendered_dpi_x:.1f} × {rendered_dpi_y:.1f}")
        print(f"  Mode: {rendered_img.mode}")

        if extracted_img:
            size_ratio = (rendered_img.width * rendered_img.height) / (extracted_img.width * extracted_img.height)
            print(f"\nRendered image is {size_ratio:.2f}× larger (pixels)")
    else:
        print("\nRendered: FAILED")


def main():
    parser = argparse.ArgumentParser(description="Compare extraction vs rendering quality")
    parser.add_argument("--pdf", required=True, help="Path to PDF")
    parser.add_argument("--page", type=int, default=1, help="Page number")
    parser.add_argument("--dpi", type=int, default=120, help="Render DPI")
    args = parser.parse_args()

    compare_methods(args.pdf, args.page, args.dpi)


if __name__ == "__main__":
    main()
