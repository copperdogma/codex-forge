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


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _build_manifest_row(
    page: int,
    page_number: int,
    original_page_number: int,
    image_path: str,
    spread_side: str | None,
    run_id: str | None,
) -> Dict[str, Any]:
    return {
        "schema_version": "page_image_v1",
        "module_id": "split_pages_from_manifest_v1",
        "run_id": run_id,
        "created_at": _utc(),
        "page": page,
        "page_number": page_number,
        "original_page_number": original_page_number,
        "image": os.path.abspath(image_path),
        "spread_side": spread_side,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Split page images from a page_image_v1 manifest.")
    parser.add_argument("--pages", required=True, help="Path to page_image_v1 manifest JSONL")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--pdf", help="Ignored. Present for driver compatibility.")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--out", default="pages_split_manifest.jsonl", help="Output manifest filename")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    images_dir = os.path.join(args.outdir, "images")
    ensure_dir(images_dir)

    rows = list(read_jsonl(args.pages))
    image_paths = [row["image"] for row in rows]

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

    spread_decision = sample_spread_decision(image_paths, sample_size=min(5, len(image_paths)))
    is_spread_book = spread_decision["is_spread"]
    gutter_position = spread_decision["gutter_position"]
    total_progress = len(image_paths) * (2 if is_spread_book else 1)

    spread_log_path = os.path.join(args.outdir, "spread_decision.json")
    save_json(spread_log_path, spread_decision)
    logger.log(
        "extract",
        "running",
        current=0,
        total=total_progress,
        message=f"Spread mode: {is_spread_book}, gutter: {gutter_position:.3f}",
        artifact=spread_log_path,
        module_id="split_pages_from_manifest_v1",
        schema_version="page_image_v1",
        extra={"is_spread": is_spread_book, "gutter_position": gutter_position, "confidence": spread_decision["confidence"]},
    )

    output_page_number = 0
    manifest_rows: List[Dict[str, Any]] = []

    for row in rows:
        page_idx = row.get("page")
        original_page_number = row.get("original_page_number") or page_idx
        img_path = row["image"]
        pil_img = Image.open(img_path)

        if is_spread_book:
            page_gutter_frac, _, page_contrast, page_continuity = find_gutter_position(pil_img)
            min_contrast_threshold = 0.15
            min_continuity_threshold = 0.7
            min_center_distance = 0.02
            distance_from_center = abs(page_gutter_frac - 0.5)

            has_strong_seam = (
                page_contrast >= min_contrast_threshold
                and page_continuity >= min_continuity_threshold
                and distance_from_center >= min_center_distance
            )

            if has_strong_seam:
                actual_gutter = page_gutter_frac
                gutter_source = "per-page (strong seam)"
            elif distance_from_center < min_center_distance:
                actual_gutter = 0.5
                gutter_source = "center (detected too close)"
            else:
                actual_gutter = 0.5
                gutter_source = "center (weak signal)"

            w_px = pil_img.size[0]
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

            output_page_number += 1
            manifest_rows.append(
                _build_manifest_row(
                    page=page_idx,
                    page_number=output_page_number,
                    original_page_number=original_page_number,
                    image_path=left_path,
                    spread_side="L",
                    run_id=args.run_id,
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
                )
            )
        else:
            pil_img = deskew_image(pil_img)
            if should_apply_noise_reduction(pil_img):
                pil_img = reduce_noise(pil_img, method="morphological", kernel_size=2)
            out_path = os.path.join(images_dir, f"page-{page_idx:03d}.png")
            pil_img.save(out_path)

            output_page_number += 1
            manifest_rows.append(
                _build_manifest_row(
                    page=page_idx,
                    page_number=output_page_number,
                    original_page_number=original_page_number,
                    image_path=out_path,
                    spread_side=None,
                    run_id=args.run_id,
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
