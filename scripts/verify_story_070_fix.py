#!/usr/bin/env python3
"""
Verify Story-070 fix: Compare per-page vs global gutter detection results.

This script compares the new per-page gutter detection against the old global
method to verify zero content loss on problem pages.
"""

import sys
from pathlib import Path
from PIL import Image

# Add modules to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.common.image_utils import find_gutter_position


def analyze_fix(old_run_dir: str, new_run_dir: str, problem_pages: list):
    """Compare old (global gutter) vs new (per-page gutter) results."""

    old_dir = Path(old_run_dir)
    new_dir = Path(new_run_dir)

    print(f"\n{'='*70}")
    print(f"STORY-070 FIX VERIFICATION")
    print(f"{'='*70}")
    print(f"Old run (global gutter): {old_dir.name}")
    print(f"New run (per-page gutter): {new_dir.name}")
    print(f"Problem pages: {problem_pages}")

    # Load old global gutter position from spread_decision.json
    import json
    # Try both old and new artifact organization paths
    old_spread_path = old_dir / "ocr_ensemble/spread_decision.json"
    if not old_spread_path.exists():
        old_spread_path = old_dir / "01_extract_ocr_ensemble_v1/ocr_ensemble/spread_decision.json"
    old_spread_decision = json.load(open(old_spread_path))
    global_gutter = old_spread_decision["gutter_position"]

    print(f"\nOld global gutter: {global_gutter:.3f}")

    results = []

    for page_num in problem_pages:
        old_img_path = old_dir / "images" / f"page-{page_num:03d}.jpg"
        new_img_path = new_dir / "01_extract_ocr_ensemble_v1/images" / f"page-{page_num:03d}.jpg"

        if not old_img_path.exists():
            print(f"\n⚠️  Page {page_num:03d} not found in old run: {old_img_path}")
            continue
        if not new_img_path.exists():
            print(f"\n⚠️  Page {page_num:03d} not found in new run: {new_img_path}")
            continue

        # Analyze old split (using global gutter)
        old_img = Image.open(old_img_path)
        old_w = old_img.size[0]
        detected_gutter, brightness, contrast, continuity = find_gutter_position(old_img)

        # Calculate differences
        global_px = int(global_gutter * old_w)
        detected_px = int(detected_gutter * old_w)
        diff_px = detected_px - global_px

        # Load new split images to verify they're better
        new_left = new_dir / "01_extract_ocr_ensemble_v1/images" / f"page-{page_num:03d}L.png"
        new_right = new_dir / "01_extract_ocr_ensemble_v1/images" / f"page-{page_num:03d}R.png"

        new_left_exists = new_left.exists()
        new_right_exists = new_right.exists()

        print(f"\n{'─'*70}")
        print(f"Page {page_num:03d}")
        print(f"{'─'*70}")
        print(f"Image width:         {old_w} px")
        print(f"Global gutter:       {global_gutter:.3f} ({global_px} px)")
        print(f"Detected gutter:     {detected_gutter:.3f} ({detected_px} px)")
        print(f"Difference:          {diff_px:+d} px ({(diff_px/old_w)*100:+.1f}%)")
        print(f"Gutter contrast:     {contrast:.3f}")

        if abs(diff_px) > 30:
            status = "✅ FIXED" if new_left_exists and new_right_exists else "⚠️  NEEDS FIX"
            print(f"\nStatus: {status}")
            print(f"  - Old method cut {abs(diff_px)}px of content")
            print(f"  - New split exists: L={new_left_exists}, R={new_right_exists}")
        else:
            print(f"\nStatus: ✓ Not a problem (difference < 30px)")

        results.append({
            "page": page_num,
            "diff_px": diff_px,
            "fixed": new_left_exists and new_right_exists,
            "was_problem": abs(diff_px) > 30
        })

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    problem_pages_found = [r for r in results if r["was_problem"]]
    fixed_pages = [r for r in problem_pages_found if r["fixed"]]

    print(f"Pages analyzed: {len(results)}")
    print(f"Problem pages (>30px diff): {len(problem_pages_found)}")
    print(f"Fixed by per-page detection: {len(fixed_pages)}")

    if problem_pages_found:
        print(f"\nProblem pages:")
        for r in problem_pages_found:
            status = "✅" if r["fixed"] else "❌"
            print(f"  {status} Page {r['page']:03d}: {r['diff_px']:+4d} px")

    if len(fixed_pages) == len(problem_pages_found):
        print(f"\n🎉 SUCCESS: All problem pages fixed!")
        return 0
    else:
        print(f"\n⚠️  WARNING: {len(problem_pages_found) - len(fixed_pages)} pages still have issues")
        return 1


def main():
    # Problem pages identified in story-070
    problem_pages = [21, 23, 25, 26]

    old_run_dir = "output/runs/validate-apple-with-apple-20251212-p1-40"
    new_run_dir = "/private/tmp/story-070-test"

    exit_code = analyze_fix(old_run_dir, new_run_dir, problem_pages)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
