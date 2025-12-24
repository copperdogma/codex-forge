import argparse
import io
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
from PIL import Image

from modules.common import ensure_dir, save_json, save_jsonl, ProgressLogger

Image.MAX_IMAGE_PIXELS = None


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _estimate_line_height_px(image: Image.Image) -> Optional[float]:
    """Estimate median line height in pixels from a grayscale image."""
    gray = np.array(image.convert("L"))
    mean = float(gray.mean())
    std = float(gray.std())
    threshold = max(0.0, min(255.0, mean - (0.5 * std)))
    ink = gray < threshold
    row_ink = ink.sum(axis=1)
    row_ink_ratio = row_ink / float(gray.shape[1])

    nonzero = row_ink_ratio[row_ink_ratio > 0]
    if nonzero.size == 0:
        return None

    p20 = float(np.percentile(nonzero, 20))
    p80 = float(np.percentile(nonzero, 80))
    min_ratio = max(0.005, p20 * 0.5)
    max_ratio = min(0.35, p80 * 1.5)

    runs: List[int] = []
    current = 0
    for ratio in row_ink_ratio:
        if min_ratio <= ratio <= max_ratio:
            current += 1
        elif current:
            if 3 <= current <= 80:
                runs.append(current)
            current = 0
    if 3 <= current <= 80:
        runs.append(current)

    if not runs:
        return None
    return float(np.median(runs))


def _sample_pages(page_count: int, sample_count: int) -> List[int]:
    """Select evenly distributed page indices for sampling."""
    if page_count <= 0 or sample_count <= 0:
        return []
    if sample_count >= page_count:
        return list(range(1, page_count + 1))
    step = float(page_count - 1) / float(sample_count - 1)
    return sorted({int(round(1 + i * step)) for i in range(sample_count)})


def _load_pdf_reader(pdf_path: str):
    """Load PDF reader (pypdf or PyPDF2)."""
    try:
        from pypdf import PdfReader
        return PdfReader(pdf_path)
    except Exception:
        try:
            from PyPDF2 import PdfReader
            return PdfReader(pdf_path)
        except Exception:
            return None


def _resolve_obj(obj):
    """Resolve indirect PDF objects."""
    try:
        return obj.get_object()
    except Exception:
        return obj


def _extract_max_image_dpi_from_xobject(xobject, page_w_in: float, page_h_in: float) -> Optional[float]:
    """Extract maximum image DPI from XObject resources."""
    max_dpi = None
    if not xobject:
        return None

    for _, ref in xobject.items():
        obj = _resolve_obj(ref)
        subtype = obj.get("/Subtype") if hasattr(obj, "get") else None

        if subtype == "/Image":
            width = obj.get("/Width")
            height = obj.get("/Height")
            if not width or not height or page_w_in <= 0 or page_h_in <= 0:
                continue
            dpi_x = float(width) / page_w_in
            dpi_y = float(height) / page_h_in
            img_dpi = max(dpi_x, dpi_y)
            if max_dpi is None or img_dpi > max_dpi:
                max_dpi = img_dpi
        elif subtype == "/Form":
            resources = obj.get("/Resources") if hasattr(obj, "get") else None
            nested = None
            if resources and hasattr(resources, "get"):
                nested = resources.get("/XObject")
            nested_dpi = _extract_max_image_dpi_from_xobject(nested, page_w_in, page_h_in)
            if nested_dpi is not None and (max_dpi is None or nested_dpi > max_dpi):
                max_dpi = nested_dpi

    return max_dpi


def _page_max_image_dpi(page) -> Optional[float]:
    """Get maximum embedded image DPI for a page."""
    try:
        media_box = page.mediabox
        page_w_in = float(media_box.width) / 72.0
        page_h_in = float(media_box.height) / 72.0
    except Exception:
        return None

    resources = page.get("/Resources") if hasattr(page, "get") else None
    xobject = None
    if resources and hasattr(resources, "get"):
        xobject = resources.get("/XObject")

    return _extract_max_image_dpi_from_xobject(xobject, page_w_in, page_h_in)


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

    except Exception:
        return None


def _render_page_fallback(pdf_path: str, page_num: int, dpi: int) -> Optional[Image.Image]:
    """Fallback: render page using pdf2image."""
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=dpi, first_page=page_num, last_page=page_num)
        return images[0] if images else None
    except Exception:
        return None


def _build_manifest_row(page: int, page_number: int, image_path: str, run_id: Optional[str]) -> Dict[str, Any]:
    return {
        "schema_version": "page_image_v1",
        "module_id": "extract_pdf_images_fast_v1",
        "run_id": run_id,
        "created_at": _utc(),
        "page": page,
        "page_number": page_number,
        "original_page_number": page,
        "image": os.path.abspath(image_path),
        "spread_side": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast extraction of embedded PDF images with rendering fallback and x-height normalization."
    )
    parser.add_argument("--pdf", required=True, help="Path to input PDF")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--start", type=int, default=1, help="Start page (1-based)")
    parser.add_argument("--end", type=int, default=None, help="End page (1-based)")
    parser.add_argument("--fallback-to-render", "--fallback_to_render", dest="fallback_to_render", action="store_true", default=True,
                        help="Fall back to rendering if extraction fails (default: True)")
    parser.add_argument("--no-fallback", dest="fallback_to_render", action="store_false",
                        help="Disable rendering fallback")
    parser.add_argument("--fallback-dpi", "--fallback_dpi", dest="fallback_dpi", type=int, default=300,
                        help="DPI for rendering fallback (default: 300)")
    parser.add_argument("--target-line-height", "--target_line_height", dest="target_line_height", type=int, default=24,
                        help="Target x-height in pixels for OCR normalization (default: 24). Images with larger x-height will be downscaled to this target. Never upscales.")
    parser.add_argument("--baseline-dpi", "--baseline_dpi", dest="baseline_dpi", type=int, default=72,
                        help="[DEPRECATED] Baseline DPI is no longer used. Kept for compatibility but ignored.")
    parser.add_argument("--sample-count", "--sample_count", dest="sample_count", type=int, default=5,
                        help="Number of pages to sample for line-height estimation (default: 5)")
    parser.add_argument("--no-normalize", "--no_normalize", dest="normalize", action="store_false", default=True,
                        help="Disable x-height normalization (extract at native size)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--out", default="pages_rendered_manifest.jsonl", help="Output manifest filename")
    parser.add_argument("--report", default="extraction_report.jsonl", help="Per-page report filename")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    images_dir = os.path.join(args.outdir, "images")
    ensure_dir(images_dir)

    reader = _load_pdf_reader(args.pdf)
    if reader is None:
        logger.log(
            "extract",
            "error",
            message="pypdf/PyPDF2 not available; cannot perform fast extraction.",
            module_id="extract_pdf_images_fast_v1",
            schema_version="page_image_v1",
        )
        return

    total_pages = len(reader.pages)
    start_page = args.start
    end_page = args.end or total_pages
    if end_page > total_pages:
        end_page = total_pages

    total = max(0, end_page - start_page + 1)

    logger.log(
        "extract",
        "running",
        current=0,
        total=total,
        message=f"Fast extraction: pages {start_page}-{end_page} (fallback={'enabled' if args.fallback_to_render else 'disabled'})",
        module_id="extract_pdf_images_fast_v1",
        schema_version="page_image_v1",
    )

    manifest_rows: List[Dict[str, Any]] = []
    report_rows: List[Dict[str, Any]] = []
    extraction_count = 0
    fallback_count = 0
    failed_count = 0

    # Extract all images first
    extracted_images: Dict[int, Tuple[Image.Image, Dict[str, Any]]] = {}
    page_number = 0
    for page_idx in range(start_page, end_page + 1):
        t0 = time.time()
        page_obj = reader.pages[page_idx - 1]

        # Get page dimensions
        try:
            media_box = page_obj.mediabox
            page_w_pts = float(media_box.width)
            page_h_pts = float(media_box.height)
        except Exception:
            page_w_pts = None
            page_h_pts = None

        # Get embedded image DPI
        max_source_dpi = _page_max_image_dpi(page_obj)

        # Attempt fast extraction
        resources = page_obj.get("/Resources") if hasattr(page_obj, "get") else None
        xobject = None
        if resources and hasattr(resources, "get"):
            xobject = resources.get("/XObject")

        result = _extract_image_from_xobject(xobject, page_w_pts, page_h_pts) if page_w_pts and page_h_pts else None

        extraction_method = None
        img = None
        metadata = {}

        if result:
            # Fast extraction succeeded
            img, metadata = result
            extraction_method = "fast_extract"
            extraction_count += 1
        elif args.fallback_to_render:
            # Fall back to rendering
            img = _render_page_fallback(args.pdf, page_idx, args.fallback_dpi)
            if img:
                extraction_method = "render_fallback"
                fallback_count += 1
                metadata = {
                    "render_dpi": args.fallback_dpi,
                    "width": img.width,
                    "height": img.height,
                }
            else:
                failed_count += 1
        else:
            failed_count += 1

        extract_time = time.time() - t0

        if img:
            # Store image for potential normalization
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            extracted_images[page_idx] = (img, {
                "extraction_method": extraction_method,
                "extract_time_sec": round(extract_time, 4),
                "max_source_dpi": None if max_source_dpi is None else float(max_source_dpi),
                **metadata,
            })
            page_number += 1
        else:
            logger.log(
                "extract",
                "warning",
                current=page_number,
                total=total,
                message=f"Page {page_idx}: extraction failed",
                module_id="extract_pdf_images_fast_v1",
                schema_version="page_image_v1",
            )

    # X-height normalization: sample pages, measure line height, calculate scale factor
    # For OCR, only pixel x-height matters, not DPI. We measure native pixel x-height
    # and scale to target (24px) if needed. Never upscale (scale_factor <= 1.0).
    scale_factor = 1.0
    if args.normalize and extracted_images and args.target_line_height > 0:
        logger.log(
            "extract",
            "running",
            current=page_number,
            total=total,
            message=f"Sampling {args.sample_count} pages for x-height normalization...",
            module_id="extract_pdf_images_fast_v1",
            schema_version="page_image_v1",
        )
        
        # Sample from extracted pages (keys are page indices)
        extracted_page_indices = sorted(extracted_images.keys())
        if len(extracted_page_indices) > 0:
            sampled_indices = _sample_pages(len(extracted_page_indices), args.sample_count)
            # Map sampled indices (1-based position) to actual page indices
            sampled_pages = [extracted_page_indices[i - 1] for i in sampled_indices if 1 <= i <= len(extracted_page_indices)]
        else:
            sampled_pages = []
        
        line_heights: List[float] = []
        
        for page_idx in sampled_pages:
            if page_idx not in extracted_images:
                continue
            img, metadata = extracted_images[page_idx]
            line_height = _estimate_line_height_px(img)
            if line_height:
                # Measure native pixel x-height (DPI doesn't matter for OCR)
                line_heights.append(line_height)
        
        if line_heights:
            observed_xheight = float(np.median(line_heights))
            if observed_xheight > 0:
                # Simple logic: if x-height < target, can't upscale (scale = 1.0)
                # If x-height > target, downscale to target
                if observed_xheight < args.target_line_height:
                    # Can't upscale - images are already smaller than target
                    scale_factor = 1.0
                    logger.log(
                        "extract",
                        "running",
                        current=page_number,
                        total=total,
                        message=f"X-height normalization: observed={observed_xheight:.1f}px, target={args.target_line_height}px (no upscaling, scale=1.0)",
                        module_id="extract_pdf_images_fast_v1",
                        schema_version="page_image_v1",
                    )
                else:
                    # Downscale to target x-height
                    scale_factor = float(args.target_line_height) / observed_xheight
                    logger.log(
                        "extract",
                        "running",
                        current=page_number,
                        total=total,
                        message=f"X-height normalization: observed={observed_xheight:.1f}px, target={args.target_line_height}px, scale={scale_factor:.3f} (downscaling)",
                        module_id="extract_pdf_images_fast_v1",
                        schema_version="page_image_v1",
                    )
            else:
                logger.log(
                    "extract",
                    "warning",
                    current=page_number,
                    total=total,
                    message="Could not estimate x-height, skipping normalization",
                    module_id="extract_pdf_images_fast_v1",
                    schema_version="page_image_v1",
                )
        else:
            logger.log(
                "extract",
                "warning",
                current=page_number,
                total=total,
                message="No line heights measured, skipping normalization",
                module_id="extract_pdf_images_fast_v1",
                schema_version="page_image_v1",
            )

    # Save normalized images and build manifest
    page_number = 0
    for page_idx in sorted(extracted_images.keys()):
        img, metadata = extracted_images[page_idx]
        extraction_method = metadata["extraction_method"]
        
        # Apply normalization if enabled
        if args.normalize:
            # Mark as normalized even if scale_factor == 1.0 (normalization was attempted)
            metadata["normalized"] = True
            metadata["scale_factor"] = round(scale_factor, 4)
            metadata["target_line_height"] = args.target_line_height
            
            if scale_factor != 1.0:
                # Actually resize the image
                original_size = (img.width, img.height)
                new_width = int(round(img.width * scale_factor))
                new_height = int(round(img.height * scale_factor))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                metadata["original_width"] = original_size[0]
                metadata["original_height"] = original_size[1]
        else:
            metadata["normalized"] = False
        
        # Save image
        out_path = os.path.join(images_dir, f"page-{page_idx:03d}.jpg")
        img.save(out_path, "JPEG", quality=95)

        page_number += 1
        manifest_rows.append(_build_manifest_row(page_idx, page_number, out_path, args.run_id))
        report_rows.append({
            "page": page_idx,
            **metadata,
        })

        logger.log(
            "extract",
            "running",
            current=page_number,
            total=total,
            message=f"Page {page_idx}: {extraction_method} ({img.width}×{img.height})" + 
                   (f" normalized (scale={scale_factor:.3f})" if args.normalize and scale_factor != 1.0 else ""),
            module_id="extract_pdf_images_fast_v1",
            schema_version="page_image_v1",
            extra={"method": extraction_method, "dpi": metadata.get("max_source_dpi")},
        )

    # Save outputs
    manifest_path = os.path.join(args.outdir, args.out)
    report_path = os.path.join(args.outdir, args.report)
    save_jsonl(manifest_path, manifest_rows)
    save_jsonl(report_path, report_rows)

    summary = {
        "pdf": os.path.abspath(args.pdf),
        "start": start_page,
        "end": end_page,
        "pages_processed": total,
        "pages_extracted": page_number,
        "extraction_count": extraction_count,
        "fallback_count": fallback_count,
        "failed_count": failed_count,
        "fallback_enabled": args.fallback_to_render,
        "fallback_dpi": args.fallback_dpi if args.fallback_to_render else None,
        "normalization_enabled": args.normalize,
        "target_line_height": args.target_line_height if args.normalize else None,
        "scale_factor": round(scale_factor, 4) if args.normalize else None,
        "manifest": os.path.abspath(manifest_path),
        "report": os.path.abspath(report_path),
    }
    save_json(os.path.join(args.outdir, "extraction_summary.json"), summary)

    logger.log(
        "extract",
        "done",
        current=page_number,
        total=total,
        message=f"Fast extraction complete: {extraction_count} fast, {fallback_count} fallback, {failed_count} failed",
        artifact=manifest_path,
        module_id="extract_pdf_images_fast_v1",
        schema_version="page_image_v1",
        extra=summary,
    )


if __name__ == "__main__":
    main()
