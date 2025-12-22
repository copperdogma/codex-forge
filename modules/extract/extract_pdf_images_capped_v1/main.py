import argparse
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
from PIL import Image
from pdf2image import convert_from_path

from modules.common import ensure_dir, save_json, save_jsonl, ProgressLogger

Image.MAX_IMAGE_PIXELS = None


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_pdf_reader(pdf_path: str):
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
    try:
        return obj.get_object()
    except Exception:
        return obj


def _extract_max_image_dpi_from_xobject(xobject, page_w_in: float, page_h_in: float) -> Optional[float]:
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


def _build_manifest_row(page: int, page_number: int, image_path: str, run_id: Optional[str]) -> Dict[str, Any]:
    return {
        "schema_version": "page_image_v1",
        "module_id": "extract_pdf_images_capped_v1",
        "run_id": run_id,
        "created_at": _utc(),
        "page": page,
        "page_number": page_number,
        "original_page_number": page,
        "image": os.path.abspath(image_path),
        "spread_side": None,
    }


def _choose_render_dpi(max_source_dpi: Optional[float], dpi_cap: Optional[int]) -> int:
    if max_source_dpi is None:
        return dpi_cap or 0
    try:
        dpi = int(max_source_dpi)
    except Exception:
        return dpi_cap or 0
    if dpi <= 0:
        return dpi_cap or 0
    if dpi_cap and dpi_cap > 0:
        return min(dpi, dpi_cap)
    return dpi


def _estimate_line_height_px(image: Image.Image) -> Optional[float]:
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
    if page_count <= 0:
        return []
    if sample_count <= 0:
        return []
    if sample_count >= page_count:
        return list(range(1, page_count + 1))
    step = (page_count - 1) / float(sample_count - 1)
    return sorted({int(round(1 + i * step)) for i in range(sample_count)})


def _choose_target_dpi(
    baseline_dpi: int,
    target_line_height: int,
    line_heights: List[float],
    dpi_cap: Optional[int],
    min_dpi: int,
) -> int:
    if not line_heights:
        fallback = baseline_dpi
        if dpi_cap and dpi_cap > 0:
            fallback = min(fallback, dpi_cap)
        return max(min_dpi, fallback)
    observed = float(np.median(line_heights))
    if observed <= 0:
        fallback = baseline_dpi
        if dpi_cap and dpi_cap > 0:
            fallback = min(fallback, dpi_cap)
        return max(min_dpi, fallback)
    scale = float(target_line_height) / observed
    desired = int(round(baseline_dpi * scale))
    if dpi_cap and dpi_cap > 0:
        desired = min(desired, dpi_cap)
    return max(min_dpi, desired)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render PDF pages at max available DPI capped at a specified limit."
    )
    parser.add_argument("--pdf", required=True, help="Path to input PDF")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--dpi-cap", dest="dpi_cap", type=int, default=None, help="Maximum render DPI (optional)")
    parser.add_argument("--dpi_cap", dest="dpi_cap", type=int, default=None, help="Alias for --dpi-cap")
    parser.add_argument("--baseline-dpi", dest="baseline_dpi", type=int, default=72, help="DPI for sampling line height")
    parser.add_argument("--baseline_dpi", dest="baseline_dpi", type=int, default=72, help="Alias for --baseline-dpi")
    parser.add_argument("--target-line-height", dest="target_line_height", type=int, default=28,
                        help="Target median line height in pixels for OCR")
    parser.add_argument("--target_line_height", dest="target_line_height", type=int, default=28,
                        help="Alias for --target-line-height")
    parser.add_argument("--min-dpi", dest="min_dpi", type=int, default=72,
                        help="Minimum render DPI (floors the computed target)")
    parser.add_argument("--min_dpi", dest="min_dpi", type=int, default=72,
                        help="Alias for --min-dpi")
    parser.add_argument("--sample-count", dest="sample_count", type=int, default=5,
                        help="Number of pages to sample for line-height estimation")
    parser.add_argument("--sample_count", dest="sample_count", type=int, default=5,
                        help="Alias for --sample-count")
    parser.add_argument("--sweep-line-heights", dest="sweep_line_heights", default=None,
                        help="Comma-separated line heights (px) to sweep and auto-pick")
    parser.add_argument("--sweep_line_heights", dest="sweep_line_heights", default=None,
                        help="Alias for --sweep-line-heights")
    parser.add_argument("--sweep-report", dest="sweep_report", default="line_height_sweep.json",
                        help="Output JSON report for line-height sweep")
    parser.add_argument("--sweep_report", dest="sweep_report", default="line_height_sweep.json",
                        help="Alias for --sweep-report")
    parser.add_argument("--max-mp", dest="max_mp", type=float, default=None,
                        help="Optional max megapixels cap per page (off by default)")
    parser.add_argument("--max_mp", dest="max_mp", type=float, default=None,
                        help="Alias for --max-mp")
    parser.add_argument("--start", type=int, default=1, help="Start page (1-based)")
    parser.add_argument("--end", type=int, default=None, help="End page (1-based)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--out", default="pages_rendered_manifest.jsonl", help="Output manifest filename")
    parser.add_argument("--report", default="render_dpi_report.jsonl", help="Per-page DPI report filename")
    args = parser.parse_args()

    dpi_cap = args.dpi_cap
    baseline_dpi = args.baseline_dpi
    target_line_height = args.target_line_height
    min_dpi = args.min_dpi
    sample_count = args.sample_count
    max_mp = args.max_mp
    sweep_line_heights = args.sweep_line_heights
    sweep_report = args.sweep_report

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    images_dir = os.path.join(args.outdir, "images")
    ensure_dir(images_dir)

    reader = _load_pdf_reader(args.pdf)
    if reader is None:
        logger.log(
            "extract",
            "warning",
            message="pypdf/PyPDF2 not available; defaulting to DPI cap for all pages.",
            module_id="extract_pdf_images_capped_v1",
            schema_version="page_image_v1",
        )

    total_pages = len(reader.pages) if reader else None
    start_page = args.start
    end_page = args.end or total_pages or args.start
    if total_pages and end_page > total_pages:
        end_page = total_pages

    total = max(0, end_page - start_page + 1)

    sampled_pages: List[int] = []
    line_heights: List[float] = []
    sample_meta: List[Dict[str, Any]] = []
    if total_pages:
        sampled_pages = _sample_pages(total_pages, sample_count)
        for page_idx in sampled_pages:
            page_obj = reader.pages[page_idx - 1] if reader else None
            max_source_dpi = _page_max_image_dpi(page_obj) if page_obj else None
            area_in2 = None
            if page_obj is not None:
                try:
                    media_box = page_obj.mediabox
                    area_in2 = (float(media_box.width) / 72.0) * (float(media_box.height) / 72.0)
                except Exception:
                    area_in2 = None
            sample_dpi = min(baseline_dpi, int(max_source_dpi)) if max_source_dpi else baseline_dpi
            images = convert_from_path(args.pdf, dpi=sample_dpi, first_page=page_idx, last_page=page_idx)
            if not images:
                continue
            estimate = _estimate_line_height_px(images[0])
            if estimate:
                # Normalize line height to baseline DPI for consistent scaling.
                normalized = estimate * (float(baseline_dpi) / float(sample_dpi))
                line_heights.append(normalized)
                sample_meta.append({
                    "page": page_idx,
                    "line_height_px": normalized,
                    "max_source_dpi": max_source_dpi,
                    "area_in2": area_in2,
                })

    target_dpi = _choose_target_dpi(
        baseline_dpi=baseline_dpi,
        target_line_height=target_line_height,
        line_heights=line_heights,
        dpi_cap=dpi_cap,
        min_dpi=min_dpi,
    )

    sweep_results = []
    if sweep_line_heights:
        candidates = []
        for raw in str(sweep_line_heights).split(","):
            try:
                candidates.append(int(raw.strip()))
            except Exception:
                continue
        for candidate in candidates:
            applied_dpis = []
            effective_line_heights = []
            for meta in sample_meta:
                line_height = meta["line_height_px"]
                if not line_height:
                    continue
                desired = baseline_dpi * (float(candidate) / float(line_height))
                dpi = desired
                if dpi_cap and dpi_cap > 0:
                    dpi = min(dpi, dpi_cap)
                if meta.get("max_source_dpi"):
                    dpi = min(dpi, float(meta["max_source_dpi"]))
                if max_mp and meta.get("area_in2"):
                    max_dpi_by_mp = (max_mp * 1_000_000.0 / float(meta["area_in2"])) ** 0.5
                    dpi = min(dpi, max_dpi_by_mp)
                dpi = max(dpi, min_dpi)
                applied_dpis.append(dpi)
                effective_line_heights.append(line_height * (dpi / float(baseline_dpi)))
            if not applied_dpis:
                continue
            median_dpi = float(np.median(applied_dpis))
            median_line = float(np.median(effective_line_heights))
            sweep_results.append({
                "candidate_line_height_px": candidate,
                "median_applied_dpi": median_dpi,
                "median_effective_line_height_px": median_line,
                "median_error_px": abs(candidate - median_line),
            })

        if sweep_results:
            sweep_results.sort(key=lambda r: (r["median_error_px"], r["median_applied_dpi"]))
            best = sweep_results[0]
            target_line_height = int(best["candidate_line_height_px"])
            target_dpi = _choose_target_dpi(
                baseline_dpi=baseline_dpi,
                target_line_height=target_line_height,
                line_heights=line_heights,
                dpi_cap=dpi_cap,
                min_dpi=min_dpi,
            )

    logger.log(
        "extract",
        "running",
        current=0,
        total=total,
        message=(
            f"Rendering pages {start_page}-{end_page} at max available DPI (cap={dpi_cap}); "
            f"target_dpi={target_dpi} (baseline={baseline_dpi}, target_line_height={target_line_height}px)"
        ),
        module_id="extract_pdf_images_capped_v1",
        schema_version="page_image_v1",
        extra={
            "baseline_dpi": baseline_dpi,
            "target_line_height_px": target_line_height,
            "sample_count": sample_count,
            "sampled_pages": sampled_pages,
            "line_heights_px": line_heights,
            "sweep_candidates": sweep_results,
            "target_dpi": target_dpi,
            "max_mp": max_mp,
        },
    )

    manifest_rows: List[Dict[str, Any]] = []
    report_rows: List[Dict[str, Any]] = []

    page_number = 0
    for page_idx in range(start_page, end_page + 1):
        max_source_dpi = None
        area_in2 = None
        if reader is not None and 0 <= page_idx - 1 < len(reader.pages):
            page_obj = reader.pages[page_idx - 1]
            max_source_dpi = _page_max_image_dpi(page_obj)
            try:
                media_box = page_obj.mediabox
                area_in2 = (float(media_box.width) / 72.0) * (float(media_box.height) / 72.0)
            except Exception:
                area_in2 = None

        render_dpi = _choose_render_dpi(max_source_dpi, dpi_cap)
        if target_dpi:
            render_dpi = min(render_dpi, target_dpi)
        if max_mp and area_in2:
            max_dpi_by_mp = (max_mp * 1_000_000.0 / float(area_in2)) ** 0.5
            render_dpi = min(render_dpi, max_dpi_by_mp)
        render_dpi = max(render_dpi, min_dpi)
        images = convert_from_path(args.pdf, dpi=render_dpi, first_page=page_idx, last_page=page_idx)
        if not images:
            logger.log(
                "extract",
                "warning",
                current=page_idx - start_page,
                total=total,
                message=f"No image rendered for page {page_idx}",
                module_id="extract_pdf_images_capped_v1",
                schema_version="page_image_v1",
            )
            continue

        out_path = os.path.join(images_dir, f"page-{page_idx:03d}.jpg")
        images[0].save(out_path, "JPEG")

        page_number += 1
        manifest_rows.append(_build_manifest_row(page_idx, page_number, out_path, args.run_id))
        report_rows.append({
            "page": page_idx,
            "render_dpi": render_dpi,
            "dpi_cap": dpi_cap,
            "target_dpi": target_dpi,
            "baseline_dpi": baseline_dpi,
            "target_line_height_px": target_line_height,
            "min_dpi": min_dpi,
            "max_mp": max_mp,
            "max_source_dpi": None if max_source_dpi is None else float(max_source_dpi),
        })

        logger.log(
            "extract",
            "running",
            current=page_number,
            total=total,
            message=f"Rendered page {page_idx} at {render_dpi} DPI",
            module_id="extract_pdf_images_capped_v1",
            schema_version="page_image_v1",
            extra={"render_dpi": render_dpi, "max_source_dpi": max_source_dpi, "dpi_cap": dpi_cap},
        )

    out_path = os.path.join(args.outdir, args.out)
    report_path = os.path.join(args.outdir, args.report)
    save_jsonl(out_path, manifest_rows)
    save_jsonl(report_path, report_rows)

    logger.log(
        "extract",
        "done",
        current=page_number,
        total=total,
        message="Capped render complete",
        artifact=out_path,
        module_id="extract_pdf_images_capped_v1",
        schema_version="page_image_v1",
    )
    save_json(os.path.join(args.outdir, "render_dpi_summary.json"), {
        "pdf": os.path.abspath(args.pdf),
        "start": start_page,
        "end": end_page,
        "dpi_cap": dpi_cap,
        "baseline_dpi": baseline_dpi,
        "target_line_height_px": target_line_height,
        "min_dpi": min_dpi,
        "sample_count": sample_count,
        "sampled_pages": sampled_pages,
        "line_heights_px": line_heights,
        "target_dpi": target_dpi,
        "max_mp": max_mp,
        "sweep_results": sweep_results,
        "pages_rendered": page_number,
        "report": os.path.abspath(report_path),
    })
    if sweep_results:
        save_json(os.path.join(args.outdir, sweep_report), sweep_results)


if __name__ == "__main__":
    main()
