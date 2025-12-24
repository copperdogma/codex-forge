#!/usr/bin/env python3
"""
Benchmark PDF extraction: fast (direct) vs render (pdf2image).
"""

import argparse
import os
import shutil
import tempfile
import time
from typing import Dict, Any

from PIL import Image
from pdf2image import convert_from_path

Image.MAX_IMAGE_PIXELS = None


def benchmark_render(pdf_path: str, start: int, end: int, dpi: int) -> Dict[str, Any]:
    """Benchmark pdf2image rendering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        results = []
        total_time = 0.0

        for page_num in range(start, end + 1):
            t0 = time.time()
            images = convert_from_path(pdf_path, dpi=dpi, first_page=page_num, last_page=page_num)
            render_time = time.time() - t0
            total_time += render_time

            if images:
                img = images[0]
                results.append({
                    "page": page_num,
                    "time_sec": round(render_time, 4),
                    "width": img.width,
                    "height": img.height,
                })
                print(f"  Page {page_num}: rendered {img.width}×{img.height} @ {dpi} DPI in {render_time:.3f}s")
            else:
                results.append({"page": page_num, "error": "No image rendered"})

        return {
            "method": "render",
            "dpi": dpi,
            "pages": len(results),
            "total_time_sec": round(total_time, 3),
            "avg_time_per_page_sec": round(total_time / len(results), 4) if results else 0,
            "results": results,
        }


def benchmark_fast_extract(pdf_path: str, start: int, end: int) -> Dict[str, Any]:
    """Benchmark fast extraction."""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return {"error": "pypdf not available"}

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
                    return Image.open(io.BytesIO(data))
                except Exception:
                    continue
        return None

    reader = PdfReader(pdf_path)
    results = []
    total_time = 0.0

    for page_num in range(start, end + 1):
        t0 = time.time()
        page = reader.pages[page_num - 1]
        img = _extract_image(page)
        extract_time = time.time() - t0
        total_time += extract_time

        if img:
            results.append({
                "page": page_num,
                "time_sec": round(extract_time, 4),
                "width": img.width,
                "height": img.height,
            })
            print(f"  Page {page_num}: extracted {img.width}×{img.height} in {extract_time:.3f}s")
        else:
            results.append({"page": page_num, "error": "No image extracted"})

    return {
        "method": "fast_extract",
        "pages": len(results),
        "total_time_sec": round(total_time, 3),
        "avg_time_per_page_sec": round(total_time / len(results), 4) if results else 0,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark PDF extraction methods")
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument("--start", type=int, default=1, help="Start page")
    parser.add_argument("--end", type=int, default=5, help="End page")
    parser.add_argument("--dpi", type=int, default=150, help="Render DPI for comparison")
    args = parser.parse_args()

    print(f"\n=== Benchmarking: {os.path.basename(args.pdf)} ===")
    print(f"Pages: {args.start}-{args.end}\n")

    print("Method 1: Fast extraction (direct from PDF)")
    fast_result = benchmark_fast_extract(args.pdf, args.start, args.end)

    print(f"\nMethod 2: Rendering (pdf2image @ {args.dpi} DPI)")
    render_result = benchmark_render(args.pdf, args.start, args.end, args.dpi)

    print("\n=== Summary ===")
    print(f"Fast extraction:  {fast_result['total_time_sec']:.3f}s total, {fast_result['avg_time_per_page_sec']:.4f}s/page")
    print(f"Rendering @ {args.dpi} DPI: {render_result['total_time_sec']:.3f}s total, {render_result['avg_time_per_page_sec']:.4f}s/page")

    if fast_result['total_time_sec'] > 0:
        speedup = render_result['total_time_sec'] / fast_result['total_time_sec']
        print(f"Speedup: {speedup:.1f}× faster")


if __name__ == "__main__":
    main()
