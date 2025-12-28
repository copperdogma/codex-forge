import argparse
import io
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
from PIL import Image

from modules.common import ensure_dir, save_json, save_jsonl, ProgressLogger

Image.MAX_IMAGE_PIXELS = None


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _measure_xheight_tesseract(image: Image.Image) -> Optional[float]:
    """
    Measure x-height using Tesseract OCR.

    Returns the robust median x_size from Tesseract HOCR output.
    Note: Tesseract reports ~2× true x-height, correction applied in caller.
    """
    try:
        import pytesseract

        # Get HOCR output from Tesseract
        hocr = pytesseract.image_to_pdf_or_hocr(image, extension='hocr')
        hocr_str = hocr.decode('utf-8')

        # Extract all x_size values from HOCR
        # Format: bbox x0 y0 x1 y1; x_size 20; x_descenders 5; x_ascenders 8
        pattern = r'x_size\s+([0-9.]+)'
        matches = re.findall(pattern, hocr_str)

        if not matches:
            return None

        x_sizes = [float(m) for m in matches]

        # Calculate robust median (exclude line-level outliers)
        arr = np.array(x_sizes)
        median = np.median(arr)
        std = np.std(arr)
        typical = arr[arr <= median + 2 * std]

        return float(np.median(typical))

    except ImportError:
        # Tesseract not available, return None
        return None
    except Exception:
        # Any other error, return None
        return None


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
    image_xobject_count = 0

    for name, ref in xobject.items():
        obj = _resolve_obj(ref)
        subtype = obj.get("/Subtype") if hasattr(obj, "get") else None

        if subtype == "/Image":
            image_xobject_count += 1
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
            "coverage_min": round(min(best["coverage_x"], best["coverage_y"]), 3),
            "candidates_count": len(candidates),
            "image_xobject_count": image_xobject_count,
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


def _build_manifest_row(page: int, page_number: int, image_path: str, run_id: Optional[str], source_pdf: Optional[str]) -> Dict[str, Any]:
    return {
        "schema_version": "page_image_v1",
        "module_id": "extract_pdf_images_fast_v1",
        "run_id": run_id,
        "source": [source_pdf] if source_pdf else None,
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
    parser.add_argument("--min-coverage", "--min_coverage", dest="min_coverage", type=float, default=0.93,
                        help="Minimum coverage for fast-extracted image before forcing render fallback")
    parser.add_argument("--require-full-page", "--require_full_page", dest="require_full_page", action="store_true", default=True,
                        help="Force render fallback when extracted image is below min-coverage (default: True)")
    parser.add_argument("--allow-partial", dest="require_full_page", action="store_false",
                        help="Allow partial fast-extracted images (disable coverage fallback)")
    parser.add_argument("--max-xobject-images", "--max_xobject_images", dest="max_xobject_images", type=int, default=1,
                        help="Maximum number of image XObjects allowed before forcing render fallback")
    parser.add_argument("--target-line-height", "--target_line_height", dest="target_line_height", type=int, default=20,
                        help="Target text height in pixels for OCR normalization (default: 20). Global scale applied uniformly to all pages based on Tesseract-measured x-height. Never upscales.")
    parser.add_argument("--baseline-dpi", "--baseline_dpi", dest="baseline_dpi", type=int, default=72,
                        help="[DEPRECATED] Baseline DPI is no longer used. Kept for compatibility but ignored.")
    parser.add_argument("--sample-count", "--sample_count", dest="sample_count", type=int, default=5,
                        help="[DEPRECATED] Sampling no longer used (per-page scaling). Kept for compatibility but ignored.")
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
        fallback_reason = None

        if result and args.require_full_page:
            _, meta = result
            coverage_min = meta.get("coverage_min", 1.0)
            image_xobject_count = meta.get("image_xobject_count", 1)
            if image_xobject_count > args.max_xobject_images:
                result = None
                fallback_reason = f"xobjects>{args.max_xobject_images}"
            elif coverage_min < args.min_coverage:
                result = None
                fallback_reason = f"coverage<{args.min_coverage}"

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
                if fallback_reason:
                    metadata["fallback_reason"] = fallback_reason
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

    # Tesseract-based robust global x-height measurement and scaling
    # Strategy: Sample ~10 pages, measure with Tesseract, discard outliers,
    # apply 2.0× correction factor, calculate uniform global scale.
    # Tesseract is accurate and consistent (validated against manual measurement).
    global_scale_factor = 1.0
    robust_median = None
    tesseract_robust_median = None
    sample_pages_list = []
    outlier_samples = []
    sample_measurements = {}  # page_idx -> tesseract_xheight

    if args.normalize and extracted_images and args.target_line_height > 0:
        # Sample pages for measurement
        page_indices = sorted(extracted_images.keys())
        sample_pages_list = _sample_pages(len(page_indices), args.sample_count)

        logger.log(
            "extract",
            "running",
            current=page_number,
            total=total,
            message=f"Sampling {len(sample_pages_list)} pages for Tesseract x-height measurement (target={args.target_line_height}px)...",
            module_id="extract_pdf_images_fast_v1",
            schema_version="page_image_v1",
        )

        # Measure sampled pages with Tesseract
        all_measurements = []

        for sample_idx in sample_pages_list:
            # Map sample index (1-based) to page_idx
            if sample_idx < 1 or sample_idx > len(page_indices):
                continue

            page_idx = page_indices[sample_idx - 1]
            img, metadata = extracted_images[page_idx]

            tesseract_xheight = _measure_xheight_tesseract(img)

            if tesseract_xheight is not None and tesseract_xheight >= 3:
                all_measurements.append(tesseract_xheight)
                sample_measurements[page_idx] = tesseract_xheight

        if all_measurements:
            # Robust statistics on Tesseract measurements
            measurements_array = np.array(all_measurements)
            median = float(np.median(measurements_array))
            std = float(np.std(measurements_array))
            outlier_threshold = median + 2 * std

            # Discard outliers
            typical_measurements = measurements_array[measurements_array <= outlier_threshold]
            tesseract_robust_median = float(np.median(typical_measurements))
            tesseract_robust_mean = float(np.mean(typical_measurements))

            # Apply 2.0× correction factor (Tesseract reports ~2× true x-height)
            TESSERACT_CORRECTION_FACTOR = 2.0
            robust_median = tesseract_robust_median / TESSERACT_CORRECTION_FACTOR

            # Identify outlier samples
            for page_idx, height in sample_measurements.items():
                if height > outlier_threshold:
                    outlier_samples.append({"page": page_idx, "tesseract_xheight": height, "threshold": outlier_threshold})

            # Calculate global scale
            if robust_median > args.target_line_height:
                global_scale_factor = float(args.target_line_height) / robust_median
            else:
                global_scale_factor = 1.0  # Never upscale

            logger.log(
                "extract",
                "running",
                current=page_number,
                total=total,
                message=f"Tesseract measurements: raw_median={tesseract_robust_median:.1f}px, corrected={robust_median:.1f}px, outliers={len(outlier_samples)}, global_scale={global_scale_factor:.4f}",
                module_id="extract_pdf_images_fast_v1",
                schema_version="page_image_v1",
            )
        else:
            logger.log(
                "extract",
                "warning",
                current=page_number,
                total=total,
                message="Tesseract measurements failed on all samples, skipping normalization",
                module_id="extract_pdf_images_fast_v1",
                schema_version="page_image_v1",
            )

    # Save images with global scaling and build manifest
    page_number = 0
    for page_idx in sorted(extracted_images.keys()):
        img, metadata = extracted_images[page_idx]
        extraction_method = metadata["extraction_method"]
        original_size = (img.width, img.height)

        # Apply global scaling
        if args.normalize and global_scale_factor != 1.0:
            # Record metadata
            tesseract_xheight = sample_measurements.get(page_idx)
            if tesseract_xheight:
                metadata["tesseract_xheight"] = round(tesseract_xheight, 1)
                metadata["is_sample_outlier"] = page_idx in [o["page"] for o in outlier_samples]
            metadata["global_scale_applied"] = round(global_scale_factor, 4)
            metadata["target_height"] = args.target_line_height
            metadata["true_xheight_robust_median"] = round(robust_median, 1) if robust_median else None
            metadata["tesseract_robust_median"] = round(tesseract_robust_median, 1) if tesseract_robust_median else None

            # Resize
            new_width = int(round(img.width * global_scale_factor))
            new_height = int(round(img.height * global_scale_factor))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            metadata["original_size"] = f"{original_size[0]}x{original_size[1]}"
            metadata["scaled"] = True
        else:
            # No scaling
            if args.normalize:
                tesseract_xheight = sample_measurements.get(page_idx)
                if tesseract_xheight:
                    metadata["tesseract_xheight"] = round(tesseract_xheight, 1)
                    metadata["is_sample_outlier"] = page_idx in [o["page"] for o in outlier_samples]
                metadata["global_scale_applied"] = 1.0
                metadata["true_xheight_robust_median"] = round(robust_median, 1) if robust_median else None
                metadata["tesseract_robust_median"] = round(tesseract_robust_median, 1) if tesseract_robust_median else None
            metadata["scaled"] = False

        metadata["final_size"] = f"{img.width}x{img.height}"
        
        # Save image
        out_path = os.path.join(images_dir, f"page-{page_idx:03d}.jpg")
        img.save(out_path, "JPEG", quality=95)

        page_number += 1
        manifest_rows.append(_build_manifest_row(page_idx, page_number, out_path, args.run_id, os.path.abspath(args.pdf)))
        report_rows.append({
            "page": page_idx,
            **metadata,
        })

        # Build status message
        status_parts = [f"{extraction_method}", f"{img.width}×{img.height}"]
        if args.normalize:
            if metadata.get("native_text_height"):
                text_h = metadata["native_text_height"]
                status_parts.append(f"text={text_h:.1f}px")
                if metadata.get("is_outlier"):
                    status_parts.append("(outlier)")
            if metadata.get("scaled"):
                status_parts.append(f"global_scale={global_scale_factor:.3f}")

        logger.log(
            "extract",
            "running",
            current=page_number,
            total=total,
            message=f"Page {page_idx}: {', '.join(status_parts)}",
            module_id="extract_pdf_images_fast_v1",
            schema_version="page_image_v1",
            extra={"method": extraction_method, "dpi": metadata.get("max_source_dpi"), "text_height": metadata.get("native_text_height")},
        )

    # Save outputs
    manifest_path = os.path.join(args.outdir, args.out)
    report_path = os.path.join(args.outdir, args.report)
    save_jsonl(manifest_path, manifest_rows)
    save_jsonl(report_path, report_rows)

    # Build summary with per-page statistics
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
        "manifest": os.path.abspath(manifest_path),
        "report": os.path.abspath(report_path),
    }

    # Add Tesseract-based robust global scaling statistics if normalization was enabled
    if args.normalize and robust_median is not None:
        summary["scaling_strategy"] = "tesseract_robust_global"
        summary["measurement_method"] = "tesseract"
        summary["sample_pages"] = sample_pages_list
        summary["sample_measurements_count"] = len(sample_pages_list)
        summary["measurements_valid"] = len(sample_measurements)
        summary["measurements_discarded"] = len(outlier_samples)
        summary["tesseract_robust_median"] = round(tesseract_robust_median, 2) if tesseract_robust_median else None
        summary["true_xheight_robust_median"] = round(robust_median, 2)
        summary["global_scale_factor"] = round(global_scale_factor, 4)
        summary["outlier_samples"] = outlier_samples
    save_json(os.path.join(args.outdir, "extraction_summary.json"), summary)

    # Build completion message with scaling stats
    msg_parts = [f"{extraction_count} fast, {fallback_count} fallback, {failed_count} failed"]
    if args.normalize and robust_median is not None:
        msg_parts.append(f"Tesseract scaling: true_xheight={robust_median:.1f}px, global_scale={global_scale_factor:.3f}, outliers={len(outlier_samples)}")

    logger.log(
        "extract",
        "done",
        current=page_number,
        total=total,
        message=f"Fast extraction complete: {', '.join(msg_parts)}",
        artifact=manifest_path,
        module_id="extract_pdf_images_fast_v1",
        schema_version="page_image_v1",
        extra=summary,
    )


if __name__ == "__main__":
    main()
