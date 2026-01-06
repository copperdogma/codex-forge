import argparse
import os
from datetime import datetime
from typing import List, Dict, Any

from PIL import Image

from modules.common import ensure_dir, save_json, save_jsonl, read_jsonl, ProgressLogger
from modules.common.image_utils import (
    sample_spread_decision,
    split_spread_at_gutter,
    find_gutter_position,
    deskew_image,
    should_apply_noise_reduction,
    reduce_noise,
)


def _bucket_size(value: int, bucket: int) -> int:
    return int(round(value / bucket) * bucket)


def _size_group_key(width: int, height: int, ratio_bucket: float, size_bucket: int) -> tuple:
    ratio = width / max(height, 1)
    ratio_key = round(ratio / ratio_bucket) * ratio_bucket
    return (_bucket_size(width, size_bucket), _bucket_size(height, size_bucket), round(ratio_key, 3))


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _build_manifest_row(
    page: int,
    page_number: int,
    original_page_number: int,
    image_path: str,
    spread_side: str | None,
    run_id: str | None,
    source: Any | None,
    image_native: str | None = None,
) -> Dict[str, Any]:
    row = {
        "schema_version": "page_image_v1",
        "module_id": "split_pages_from_manifest_v1",
        "run_id": run_id,
        "source": source,
        "created_at": _utc(),
        "page": page,
        "page_number": page_number,
        "original_page_number": original_page_number,
        "image": os.path.abspath(image_path),
        "spread_side": spread_side,
    }
    if image_native:
        row["image_native"] = os.path.abspath(image_native)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Split page images from a page_image_v1 manifest.")
    parser.add_argument("--pages", required=True, help="Path to page_image_v1 manifest JSONL")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--pdf", help="Ignored. Present for driver compatibility.")
    parser.add_argument("--ratio-bucket", dest="ratio_bucket", type=float, default=0.05, help="Bucket size for aspect ratio grouping")
    parser.add_argument("--size-bucket", dest="size_bucket", type=int, default=50, help="Bucket size in pixels for width/height grouping")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--out", default="pages_split_manifest.jsonl", help="Output manifest filename")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    images_dir = os.path.join(args.outdir, "images")
    ensure_dir(images_dir)

    # Create native images directory if any input rows have image_native
    rows = list(read_jsonl(args.pages))
    has_native = any(row.get("image_native") for row in rows)
    images_native_dir = None
    if has_native:
        images_native_dir = os.path.join(args.outdir, "images_native")
        ensure_dir(images_native_dir)
    image_paths = [row["image"] for row in rows]
    row_by_path = {row["image"]: row for row in rows if row.get("image")}

    if not image_paths:
        logger.log(
            "extract",
            "done",
            current=0,
            total=0,
            message="No pages provided",
            module_id="split_pages_from_manifest_v1",
            schema_version="page_image_v1",
        )
        return

    # Group by size + aspect ratio to handle mixed-layout PDFs (spreads + single pages).
    size_groups: Dict[tuple, List[str]] = {}
    page_sizes: Dict[str, tuple] = {}
    for path in image_paths:
        img = Image.open(path)
        w, h = img.size
        page_sizes[path] = (w, h)
        key = _size_group_key(w, h, args.ratio_bucket, args.size_bucket)
        size_groups.setdefault(key, []).append(path)

    group_decisions: Dict[tuple, Dict[str, Any]] = {}
    for key, paths in size_groups.items():
        decision = sample_spread_decision(paths, sample_size=min(5, len(paths)))
        group_decisions[key] = decision

    split_diagnostics = {
        "group_count": len(size_groups),
        "ratio_bucket": args.ratio_bucket,
        "size_bucket": args.size_bucket,
        "groups": [],
    }
    for key, paths in size_groups.items():
        decision = group_decisions[key]
        split_diagnostics["groups"].append({
            "group_key": key,
            "count": len(paths),
            "decision": decision,
        })

    total_progress = len(image_paths) * 2

    split_log_path = os.path.join(args.outdir, "split_decisions.json")
    save_json(split_log_path, split_diagnostics)
    logger.log(
        "extract",
        "running",
        current=0,
        total=len(image_paths),
        message=f"Split groups: {len(size_groups)}",
        artifact=split_log_path,
        module_id="split_pages_from_manifest_v1",
        schema_version="page_image_v1",
        extra={"group_count": len(size_groups)},
    )

    output_page_number = 0
    manifest_rows: List[Dict[str, Any]] = []

    for row in rows:
        page_idx = row.get("page")
        original_page_number = row.get("original_page_number") or page_idx
        img_path = row["image"]
        img_native_path = row.get("image_native")
        pil_img = Image.open(img_path)
        pil_img_native = Image.open(img_native_path) if img_native_path and os.path.exists(img_native_path) else None

        group_key = _size_group_key(pil_img.size[0], pil_img.size[1], args.ratio_bucket, args.size_bucket)
        group_decision = group_decisions.get(group_key) or {"is_spread": False, "gutter_position": 0.5, "confidence": 0.0}
        is_spread_group = group_decision.get("is_spread", False)
        gutter_position = group_decision.get("gutter_position", 0.5)

        w_px, h_px = pil_img.size
        is_landscape = (w_px / max(h_px, 1)) > 1.1

        source = row_by_path.get(img_path, {}).get("source")
        if is_spread_group and is_landscape:
            page_gutter_frac, _, page_contrast, page_continuity = find_gutter_position(pil_img)
            min_contrast_threshold = 0.15
            min_continuity_threshold = 0.7
            has_strong_seam = (
                page_contrast >= min_contrast_threshold
                and page_continuity >= min_continuity_threshold
            )

            if has_strong_seam:
                actual_gutter = page_gutter_frac
                gutter_source = "per-page (strong seam)"
            else:
                # Use group gutter when per-page signal is weak/ambiguous.
                actual_gutter = gutter_position
                gutter_source = "group (weak signal)"

            center_px = int(0.5 * w_px)
            actual_px = int(actual_gutter * w_px)
            diff_from_center_px = actual_px - center_px

            logger.log(
                "extract",
                "running",
                current=output_page_number,
                total=total_progress,
                message=(
                    f"Page {page_idx} gutter: {actual_gutter:.3f} ({gutter_source}), "
                    f"detected: {page_gutter_frac:.3f} (contrast: {page_contrast:.3f}, "
                    f"continuity: {page_continuity:.3f}), center diff: {diff_from_center_px:+d}px"
                ),
            )

            left_img, right_img = split_spread_at_gutter(pil_img, actual_gutter)
            left_img = deskew_image(left_img)
            right_img = deskew_image(right_img)
            if should_apply_noise_reduction(left_img):
                left_img = reduce_noise(left_img, method="morphological", kernel_size=2)
            if should_apply_noise_reduction(right_img):
                right_img = reduce_noise(right_img, method="morphological", kernel_size=2)

            left_path = os.path.join(images_dir, f"page-{page_idx:03d}L.png")
            right_path = os.path.join(images_dir, f"page-{page_idx:03d}R.png")
            left_img.save(left_path)
            right_img.save(right_path)

            # Split native image if available
            left_native_path = None
            right_native_path = None
            if pil_img_native and images_native_dir:
                left_native, right_native = split_spread_at_gutter(pil_img_native, actual_gutter)
                left_native = deskew_image(left_native)
                right_native = deskew_image(right_native)
                if should_apply_noise_reduction(left_native):
                    left_native = reduce_noise(left_native, method="morphological", kernel_size=2)
                if should_apply_noise_reduction(right_native):
                    right_native = reduce_noise(right_native, method="morphological", kernel_size=2)

                left_native_path = os.path.join(images_native_dir, f"page-{page_idx:03d}L.png")
                right_native_path = os.path.join(images_native_dir, f"page-{page_idx:03d}R.png")
                left_native.save(left_native_path)
                right_native.save(right_native_path)

            output_page_number += 1
            manifest_rows.append(
                _build_manifest_row(
                    page=page_idx,
                    page_number=output_page_number,
                    original_page_number=original_page_number,
                    image_path=left_path,
                    spread_side="L",
                    run_id=args.run_id,
                    source=source,
                    image_native=left_native_path,
                )
            )
            output_page_number += 1
            manifest_rows.append(
                _build_manifest_row(
                    page=page_idx,
                    page_number=output_page_number,
                    original_page_number=original_page_number,
                    image_path=right_path,
                    spread_side="R",
                    run_id=args.run_id,
                    source=source,
                    image_native=right_native_path,
                )
            )
        else:
            pil_img = deskew_image(pil_img)
            if should_apply_noise_reduction(pil_img):
                pil_img = reduce_noise(pil_img, method="morphological", kernel_size=2)
            out_path = os.path.join(images_dir, f"page-{page_idx:03d}.png")
            pil_img.save(out_path)

            # Process native image if available
            out_native_path = None
            if pil_img_native and images_native_dir:
                pil_img_native = deskew_image(pil_img_native)
                if should_apply_noise_reduction(pil_img_native):
                    pil_img_native = reduce_noise(pil_img_native, method="morphological", kernel_size=2)
                out_native_path = os.path.join(images_native_dir, f"page-{page_idx:03d}.png")
                pil_img_native.save(out_native_path)

            output_page_number += 1
            manifest_rows.append(
                _build_manifest_row(
                    page=page_idx,
                    page_number=output_page_number,
                    original_page_number=original_page_number,
                    image_path=out_path,
                    spread_side=None,
                    run_id=args.run_id,
                    source=source,
                    image_native=out_native_path,
                )
            )

        logger.log(
            "extract",
            "running",
            current=output_page_number,
            total=total_progress,
            message=f"Page {page_idx} split complete",
            module_id="split_pages_from_manifest_v1",
            schema_version="page_image_v1",
        )

    out_path = os.path.join(args.outdir, args.out)
    save_jsonl(out_path, manifest_rows)
    logger.log(
        "extract",
        "done",
        current=output_page_number,
        total=total_progress,
        message="Split run complete",
        artifact=out_path,
        module_id="split_pages_from_manifest_v1",
        schema_version="page_image_v1",
    )


if __name__ == "__main__":
    main()
