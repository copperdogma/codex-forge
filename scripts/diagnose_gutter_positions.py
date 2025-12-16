#!/usr/bin/env python3
"""
Diagnostic tool to analyze per-page gutter positions for problem pages.

This script analyzes the gutter position for specific pages to understand
why the global gutter position causes bad splits.
"""

import sys
from pathlib import Path
from PIL import Image

# Add modules to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.common.image_utils import find_gutter_position


def analyze_page_gutter(image_path: str, page_num: int, global_gutter: float):
    """Analyze gutter position for a single page."""
    img = Image.open(image_path)
    w, h = img.size

    # Detect per-page gutter
    gutter_frac, brightness, contrast, continuity = find_gutter_position(img)

    # Calculate pixel positions
    global_px = int(global_gutter * w)
    detected_px = int(gutter_frac * w)
    diff_px = detected_px - global_px
    diff_pct = (gutter_frac - global_gutter) * 100

    print(f"\n{'='*60}")
    print(f"Page {page_num:03d}: {Path(image_path).name}")
    print(f"{'='*60}")
    print(f"Image size:        {w} x {h} px")
    print(f"Global gutter:     {global_gutter:.3f} ({global_px} px)")
    print(f"Detected gutter:   {gutter_frac:.3f} ({detected_px} px)")
    print(f"Difference:        {diff_pct:+.1f}% ({diff_px:+d} px)")
    print(f"Gutter brightness: {brightness:.1f}")
    print(f"Gutter contrast:   {contrast:.3f}")

    if abs(diff_px) > 50:
        direction = "right" if diff_px > 0 else "left"
        print(f"\n⚠️  WARNING: Per-page gutter is {abs(diff_px)}px to the {direction}")
        print(f"   Using global position would cut content!")

    return {
        "page": page_num,
        "width": w,
        "height": h,
        "global_gutter": global_gutter,
        "detected_gutter": gutter_frac,
        "diff_px": diff_px,
        "diff_pct": diff_pct,
        "brightness": brightness,
        "contrast": contrast,
    }


def main():
    # Problem pages identified in story-070
    problem_pages = [21, 23, 25, 26, 71, 74, 76, 91]

    # Run directory
    run_dir = Path("output/runs/validate-apple-with-apple-20251212-p1-40")
    images_dir = run_dir / "images"

    # Global gutter position from spread_decision.json
    global_gutter = 0.487

    print(f"\n{'='*60}")
    print(f"GUTTER POSITION DIAGNOSTIC")
    print(f"{'='*60}")
    print(f"Run: {run_dir.name}")
    print(f"Global gutter: {global_gutter:.3f}")
    print(f"Problem pages: {problem_pages}")

    results = []

    # Analyze each problem page
    for page_num in problem_pages:
        image_path = images_dir / f"page-{page_num:03d}.jpg"

        if not image_path.exists():
            print(f"\n⚠️  Page {page_num:03d} not found: {image_path}")
            continue

        result = analyze_page_gutter(str(image_path), page_num, global_gutter)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Pages analyzed: {len(results)}/{len(problem_pages)}")

    if results:
        avg_diff = sum(r["diff_px"] for r in results) / len(results)
        max_diff = max(results, key=lambda r: abs(r["diff_px"]))

        print(f"Average difference: {avg_diff:+.0f} px")
        print(f"Max difference: {max_diff['diff_px']:+d} px (page {max_diff['page']:03d})")

        # Pages with significant deviation
        significant = [r for r in results if abs(r["diff_px"]) > 50]
        if significant:
            print(f"\nPages with >50px deviation: {len(significant)}")
            for r in significant:
                print(f"  - Page {r['page']:03d}: {r['diff_px']:+4d} px ({r['diff_pct']:+.1f}%)")


if __name__ == "__main__":
    main()
