#!/usr/bin/env python3
"""
derive_golden_boxes.py
======================
For each source page image in benchmarks/input/source-pages/, find all matching
golden crops in benchmarks/golden/crops/ using OpenCV template matching, and
output bounding-box annotations to benchmarks/golden/image-crops.json.

Run from the benchmarks/ directory:
    python scripts/derive_golden_boxes.py
"""

import json
import os
import re
import sys
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Paths (relative to the benchmarks/ directory)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BENCH_DIR = SCRIPT_DIR.parent  # benchmarks/

SOURCE_DIR = BENCH_DIR / "input" / "source-pages"
CROPS_DIR = BENCH_DIR / "golden" / "crops"
OUTPUT_JSON = BENCH_DIR / "golden" / "image-crops.json"

# Template-matching confidence threshold for flagging
CONFIDENCE_WARN_THRESHOLD = 0.80

# If the 1:1 match falls below this, try multi-scale matching
MULTISCALE_TRIGGER = 0.80


def gather_source_crop_map():
    """
    Build a mapping:  stem -> { source_file, crop_files[] }

    Source pages:    ImageXXX.jpg
    Numbered crops:  ImageXXX-NNN.jpg   (actual sub-image crops)
    Bare crops:      ImageXXX.jpg        (full-page copy -- same as source)
    """
    source_files = sorted(SOURCE_DIR.glob("*.jpg"))
    crop_files = sorted(CROPS_DIR.glob("*.jpg"))

    # Index source pages by stem
    sources_by_stem = {}
    for sf in source_files:
        stem = sf.stem  # e.g. "Image021"
        sources_by_stem[stem] = sf

    # Group numbered crops by their base stem
    # e.g. "Image021-001.jpg" -> base stem "Image021"
    crop_pattern = re.compile(r"^(.+?)-(\d+)\.jpg$")
    crop_map = {}  # stem -> list of crop file paths (numbered only)

    for cf in crop_files:
        m = crop_pattern.match(cf.name)
        if m:
            base_stem = m.group(1)
            crop_map.setdefault(base_stem, []).append(cf)

    # Also handle bare crops (ImageXXX.jpg in crops dir) -- these are
    # full-page duplicates.  We include them only if there are NO numbered
    # crops for that stem, meaning the entire page is the crop.
    for cf in crop_files:
        if crop_pattern.match(cf.name):
            continue  # skip numbered
        stem = cf.stem
        if stem not in crop_map:
            # Full-page crop with no sub-crops -- treat the bare file as the crop
            crop_map.setdefault(stem, []).append(cf)

    return sources_by_stem, crop_map


def match_crop_in_source(source_img, crop_img):
    """
    Use cv2.matchTemplate (TM_CCOEFF_NORMED) to locate crop_img inside
    source_img.  Returns (x0, y0, x1, y1, confidence, scale, method_note).

    If the initial 1:1 match confidence is below MULTISCALE_TRIGGER, a
    multi-scale search is performed (the crop may have been extracted from
    a different-resolution scan).
    """
    h, w = crop_img.shape[:2]
    src_h_px, src_w_px = source_img.shape[:2]

    # --- Pass 1: direct 1:1 template match (only if crop fits) ---
    max_val = -1.0
    max_loc = (0, 0)

    if h <= src_h_px and w <= src_w_px:
        result = cv2.matchTemplate(source_img, crop_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= MULTISCALE_TRIGGER:
            x0, y0 = max_loc
            return x0, y0, x0 + w, y0 + h, max_val, 1.0, "direct"

    # --- Pass 2: multi-scale fallback ---
    # Convert to grayscale for speed
    src_gray = cv2.cvtColor(source_img, cv2.COLOR_BGR2GRAY)
    crp_gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    src_h, src_w = src_gray.shape[:2]

    best_val = max_val
    best_loc = max_loc
    best_scale = 1.0

    # Coarse sweep: 50% to 600% in 10% steps
    for scale_pct in range(50, 601, 10):
        scale = scale_pct / 100.0
        new_w = int(w * scale)
        new_h = int(h * scale)
        if new_h > src_h or new_w > src_w or new_h < 10 or new_w < 10:
            continue
        scaled = cv2.resize(crp_gray, (new_w, new_h))
        res = cv2.matchTemplate(src_gray, scaled, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(res)
        if mv > best_val:
            best_val = mv
            best_loc = ml
            best_scale = scale

    # Fine sweep: +/- 10% around best in 1% steps
    lo = max(10, int(best_scale * 100) - 10)
    hi = min(600, int(best_scale * 100) + 11)
    for scale_pct in range(lo, hi):
        scale = scale_pct / 100.0
        new_w = int(w * scale)
        new_h = int(h * scale)
        if new_h > src_h or new_w > src_w or new_h < 10 or new_w < 10:
            continue
        scaled = cv2.resize(crp_gray, (new_w, new_h))
        res = cv2.matchTemplate(src_gray, scaled, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(res)
        if mv > best_val:
            best_val = mv
            best_loc = ml
            best_scale = scale

    final_w = int(w * best_scale)
    final_h = int(h * best_scale)
    x0, y0 = best_loc
    return x0, y0, x0 + final_w, y0 + final_h, best_val, best_scale, "multiscale"


def is_full_page(source_img, crop_img):
    """Check whether the crop has the same dimensions as the source."""
    return source_img.shape[:2] == crop_img.shape[:2]


def main():
    sources_by_stem, crop_map = gather_source_crop_map()

    results = {}
    warnings = []

    stems_with_crops = sorted(set(sources_by_stem.keys()) & set(crop_map.keys()))

    if not stems_with_crops:
        print("ERROR: No matching source/crop pairs found.", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(stems_with_crops)} source pages ...\n")
    print(f"{'Source':<14} {'Crop':<22} {'Bbox (px)':<32} {'Conf':<8} {'Scale':<8} {'Method':<12} {'Flag'}")
    print("-" * 110)

    for stem in stems_with_crops:
        source_path = sources_by_stem[stem]
        source_img = cv2.imread(str(source_path))
        if source_img is None:
            print(f"WARNING: Could not read source {source_path}", file=sys.stderr)
            continue

        src_h, src_w = source_img.shape[:2]

        entry = {
            "source": f"input/source-pages/{source_path.name}",
            "source_width": src_w,
            "source_height": src_h,
            "crops": [],
        }

        for crop_path in sorted(crop_map[stem]):
            crop_img = cv2.imread(str(crop_path))
            if crop_img is None:
                print(f"WARNING: Could not read crop {crop_path}", file=sys.stderr)
                continue

            crop_h, crop_w = crop_img.shape[:2]

            # Special case: crop is same size as source (full-page)
            if is_full_page(source_img, crop_img):
                x0, y0, x1, y1 = 0, 0, src_w, src_h
                confidence = 1.0
                scale = 1.0
                method = "full-page"
            else:
                # Ensure crop is not larger than source in either dimension
                # (only at 1:1 -- multi-scale handles scaling internally)
                if crop_h > src_h or crop_w > src_w:
                    # Still try multi-scale -- the crop might be from a
                    # higher-res scan and needs to be scaled down
                    x0, y0, x1, y1, confidence, scale, method = (
                        match_crop_in_source(source_img, crop_img)
                    )
                    if confidence < CONFIDENCE_WARN_THRESHOLD:
                        print(
                            f"WARNING: Crop {crop_path.name} is larger than source "
                            f"({crop_w}x{crop_h} vs {src_w}x{src_h}) and "
                            f"multi-scale confidence is low ({confidence:.4f})",
                            file=sys.stderr,
                        )
                else:
                    x0, y0, x1, y1, confidence, scale, method = (
                        match_crop_in_source(source_img, crop_img)
                    )

            # Normalized coordinates
            bbox = [int(x0), int(y0), int(x1), int(y1)]
            bbox_norm = [
                round(x0 / src_w, 6),
                round(y0 / src_h, 6),
                round(x1 / src_w, 6),
                round(y1 / src_h, 6),
            ]

            flag = ""
            if confidence < CONFIDENCE_WARN_THRESHOLD:
                flag = "** LOW **"
                warnings.append((stem, crop_path.name, confidence))

            print(
                f"{stem:<14} {crop_path.name:<22} {str(bbox):<32} {confidence:<8.4f} {scale:<8.2f} {method:<12} {flag}"
            )

            crop_entry = {
                "crop_file": crop_path.name,
                "bbox": bbox,
                "bbox_normalized": bbox_norm,
                "confidence": round(confidence, 4),
            }
            if scale != 1.0:
                crop_entry["match_scale"] = round(scale, 4)
            entry["crops"].append(crop_entry)

        results[stem] = entry

    # -----------------------------------------------------------------------
    # Write JSON output
    # -----------------------------------------------------------------------
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {OUTPUT_JSON}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    total_crops = sum(len(e["crops"]) for e in results.values())
    print(f"\nSummary: {len(results)} source pages, {total_crops} crop boxes total.")

    if warnings:
        print(f"\n*** {len(warnings)} LOW-CONFIDENCE MATCHES (< {CONFIDENCE_WARN_THRESHOLD}): ***")
        for stem, crop_name, conf in warnings:
            print(f"  {stem} / {crop_name}  confidence={conf:.4f}")
    else:
        print("All matches above confidence threshold.")


if __name__ == "__main__":
    main()
