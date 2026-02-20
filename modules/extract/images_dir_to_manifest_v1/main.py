#!/usr/bin/env python3
"""
Build a page_image_v1 manifest from a directory of scanned page images.
"""
import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from modules.common.utils import ensure_dir, save_jsonl, ProgressLogger


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_numbers(name: str) -> List[int]:
    return [int(m) for m in re.findall(r"\d+", name)]


def _sort_key(path: Path) -> Tuple[int, List[int], str]:
    numbers = _extract_numbers(path.name)
    has_numbers = 0 if numbers else 1
    return (has_numbers, numbers, path.name.lower())


def _iter_images(input_dir: Path) -> List[Path]:
    images = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    return sorted(images, key=_sort_key)


def build_manifest(
    input_dir: Path,
    outdir: Path,
    out: str,
    run_id: Optional[str],
    start: Optional[int],
    end: Optional[int],
) -> Path:
    images = _iter_images(input_dir)
    if not images:
        raise SystemExit(f"No images found in {input_dir}")

    rows = []
    for idx, img_path in enumerate(images, start=1):
        if start is not None and idx < start:
            continue
        if end is not None and idx > end:
            continue
        rows.append({
            "schema_version": "page_image_v1",
            "module_id": "images_dir_to_manifest_v1",
            "run_id": run_id,
            "source": [str(input_dir.resolve())],
            "created_at": _utc_now(),
            "page": idx,
            "page_number": idx,
            "original_page_number": idx,
            "image": str(img_path.resolve()),
            "spread_side": None,
        })

    ensure_dir(outdir)
    out_path = outdir / out
    save_jsonl(str(out_path), rows)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build page_image_v1 manifest from an image directory"
    )
    parser.add_argument("--input_dir", "--input-dir", dest="input_dir", required=False,
                        help="Directory containing page images")
    parser.add_argument("--images", dest="images", required=False,
                        help="Alias for --input_dir (driver passes --images for extract stages)")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--out", default="pages_images_manifest.jsonl", help="Output manifest filename")
    parser.add_argument("--run_id", "--run-id", dest="run_id", default=None,
                        help="Optional run ID for manifest metadata")
    parser.add_argument("--state-file", dest="state_file", default=None,
                        help="Ignored (driver compatibility)")
    parser.add_argument("--progress-file", dest="progress_file", default=None,
                        help="Ignored (driver compatibility)")
    parser.add_argument("--start", type=int, default=None, help="1-based start index (inclusive)")
    parser.add_argument("--end", type=int, default=None, help="1-based end index (inclusive)")

    args = parser.parse_args()
    input_dir_value = args.input_dir or args.images
    if not input_dir_value:
        raise SystemExit("Must provide --input_dir/--input-dir or --images")
    input_dir = Path(input_dir_value)
    if not input_dir.exists():
        raise SystemExit(f"Input dir not found: {input_dir}")
    if not input_dir.is_dir():
        raise SystemExit(f"Input path is not a directory: {input_dir}")

    logger = ProgressLogger("images_dir_to_manifest_v1")
    logger.log("build_manifest", "running", message=f"Reading images from {input_dir}")
    out_path = build_manifest(
        input_dir=input_dir,
        outdir=Path(args.outdir),
        out=args.out,
        run_id=args.run_id,
        start=args.start,
        end=args.end,
    )
    logger.log("build_manifest", "done", message=f"Wrote manifest: {out_path}")


if __name__ == "__main__":
    main()
