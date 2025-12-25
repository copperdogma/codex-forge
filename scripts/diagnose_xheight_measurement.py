#!/usr/bin/env python3
"""
Diagnostic tool to visualize and understand x-height measurement.

This script:
1. Extracts a page from a PDF at native resolution
2. Runs _estimate_line_height_px to get the system measurement
3. Visualizes the measurement process (ink detection, row density, runs)
4. Provides manual measurement guidance for comparison
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pdf2image import convert_from_path
from pypdf import PdfReader

# Import the measurement function
sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.extract.extract_pdf_images_fast_v1.main import (
    _estimate_line_height_px,
    _page_max_image_dpi,
)


def visualize_measurement(
    image: Image.Image, out_dir: Path, prefix: str = "debug"
) -> Tuple[Optional[float], dict]:
    """
    Visualize the x-height measurement process.

    Returns (estimated_line_height, debug_info)
    """
    gray = np.array(image.convert("L"))
    height, width = gray.shape

    # Step 1: Ink detection
    mean = float(gray.mean())
    std = float(gray.std())
    threshold = max(0.0, min(255.0, mean - (0.5 * std)))
    ink = gray < threshold

    # Step 2: Row-wise ink density
    row_ink = ink.sum(axis=1)
    row_ink_ratio = row_ink / float(width)

    # Step 3: Calculate percentiles and density range
    nonzero = row_ink_ratio[row_ink_ratio > 0]
    if nonzero.size == 0:
        return None, {"error": "No ink detected"}

    p20 = float(np.percentile(nonzero, 20))
    p80 = float(np.percentile(nonzero, 80))
    min_ratio = max(0.005, p20 * 0.5)
    max_ratio = min(0.35, p80 * 1.5)

    # Step 4: Find runs
    runs: List[int] = []
    current = 0
    run_positions = []  # Track where runs start/end for visualization

    for i, ratio in enumerate(row_ink_ratio):
        if min_ratio <= ratio <= max_ratio:
            if current == 0:
                run_start = i
            current += 1
        elif current:
            if 3 <= current <= 80:
                runs.append(current)
                run_positions.append((run_start, i - 1, current))
            current = 0

    if 3 <= current <= 80:
        runs.append(current)
        run_positions.append((run_start, len(row_ink_ratio) - 1, current))

    if not runs:
        return None, {"error": "No valid runs found"}

    estimate = float(np.median(runs))

    # Debug info
    debug_info = {
        "image_size": f"{width}x{height}",
        "gray_mean": round(mean, 2),
        "gray_std": round(std, 2),
        "threshold": round(threshold, 2),
        "ink_pixels": int(ink.sum()),
        "p20_density": round(p20, 4),
        "p80_density": round(p80, 4),
        "min_density": round(min_ratio, 4),
        "max_density": round(max_ratio, 4),
        "run_count": len(runs),
        "runs": sorted(runs),
        "run_stats": {
            "min": int(min(runs)),
            "max": int(max(runs)),
            "median": round(estimate, 2),
            "mean": round(np.mean(runs), 2),
        },
        "run_positions": run_positions[:10],  # First 10 for brevity
    }

    # Visualization 1: Ink detection
    ink_vis = np.zeros((height, width, 3), dtype=np.uint8)
    ink_vis[ink] = [255, 0, 0]  # Red for ink
    ink_vis[~ink] = [240, 240, 240]  # Light gray for background
    Image.fromarray(ink_vis).save(out_dir / f"{prefix}_01_ink_detection.png")

    # Visualization 2: Row density plot
    plot_height = 800
    plot_width = 400
    plot = Image.new("RGB", (plot_width, plot_height), "white")
    draw = ImageDraw.Draw(plot)

    # Scale densities to plot width
    max_density_plot = max(row_ink_ratio.max(), max_ratio * 1.2)

    for i, ratio in enumerate(row_ink_ratio):
        y = int((i / height) * plot_height)
        x = int((ratio / max_density_plot) * (plot_width - 50))

        # Color code: green if in range, gray otherwise
        if min_ratio <= ratio <= max_ratio:
            color = (0, 200, 0)
        else:
            color = (200, 200, 200)

        draw.line([(0, y), (x, y)], fill=color, width=1)

    # Draw threshold lines
    min_x = int((min_ratio / max_density_plot) * (plot_width - 50))
    max_x = int((max_ratio / max_density_plot) * (plot_width - 50))
    draw.line([(min_x, 0), (min_x, plot_height)], fill="blue", width=2)
    draw.line([(max_x, 0), (max_x, plot_height)], fill="red", width=2)

    plot.save(out_dir / f"{prefix}_02_row_density.png")

    # Visualization 3: Runs highlighted on original image
    run_vis = image.convert("RGB")
    draw = ImageDraw.Draw(run_vis)

    # Draw the first 20 runs
    for i, (start, end, length) in enumerate(run_positions[:20]):
        # Alternate colors for visibility
        color = (255, 0, 0) if i % 2 == 0 else (0, 255, 0)
        draw.rectangle([(0, start), (width, end)], outline=color, width=3)
        # Draw length annotation
        mid_y = (start + end) // 2
        draw.text((10, mid_y), f"{length}px", fill=color)

    run_vis.save(out_dir / f"{prefix}_03_runs_highlighted.png")

    return estimate, debug_info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose x-height measurement discrepancies"
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF")
    parser.add_argument("--page", type=int, default=1, help="Page to analyze (1-based)")
    parser.add_argument("--dpi", type=int, default=None, help="Render DPI (default: native max)")
    parser.add_argument("--out-dir", default="/tmp/xheight-diagnostic", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing {args.pdf}, page {args.page}...")

    # Get native DPI from PDF
    reader = PdfReader(args.pdf)
    if args.page > len(reader.pages):
        print(f"Error: Page {args.page} out of range (PDF has {len(reader.pages)} pages)")
        return 1

    page_obj = reader.pages[args.page - 1]
    max_source_dpi = _page_max_image_dpi(page_obj)

    render_dpi = args.dpi
    if render_dpi is None:
        render_dpi = int(max_source_dpi) if max_source_dpi else 300

    print(f"Native max DPI: {max_source_dpi}")
    print(f"Render DPI: {render_dpi}")

    # Render page
    images = convert_from_path(
        args.pdf, dpi=render_dpi, first_page=args.page, last_page=args.page
    )

    if not images:
        print("Error: Failed to render page")
        return 1

    img = images[0]
    print(f"Image size: {img.width}x{img.height}")

    # Save original
    img.save(out_dir / "00_original.png")

    # Run diagnostic visualization
    print("\nRunning measurement diagnostic...")
    estimate, debug_info = visualize_measurement(img, out_dir)

    # Also run the actual function for comparison
    actual_estimate = _estimate_line_height_px(img)

    print("\n" + "=" * 60)
    print("MEASUREMENT RESULTS")
    print("=" * 60)

    if estimate is None:
        print(f"ERROR: {debug_info.get('error', 'Unknown error')}")
        return 1

    print(f"Estimated line height: {estimate:.2f} px")
    print(f"Actual function result: {actual_estimate:.2f} px")
    print(f"\nImage dimensions: {debug_info['image_size']}")
    print(f"Grayscale mean: {debug_info['gray_mean']}")
    print(f"Grayscale std: {debug_info['gray_std']}")
    print(f"Ink threshold: {debug_info['threshold']}")
    print(f"Ink pixels: {debug_info['ink_pixels']:,}")

    print(f"\nRow density range:")
    print(f"  p20={debug_info['p20_density']:.4f}, p80={debug_info['p80_density']:.4f}")
    print(f"  Filter range: [{debug_info['min_density']:.4f}, {debug_info['max_density']:.4f}]")

    print(f"\nRuns found: {debug_info['run_count']}")
    print(f"  Min: {debug_info['run_stats']['min']} px")
    print(f"  Max: {debug_info['run_stats']['max']} px")
    print(f"  Median: {debug_info['run_stats']['median']} px")
    print(f"  Mean: {debug_info['run_stats']['mean']} px")

    print(f"\nFirst 10 run lengths: {debug_info['runs'][:10]}")

    print("\n" + "=" * 60)
    print("MANUAL MEASUREMENT GUIDE")
    print("=" * 60)
    print("To manually measure x-height:")
    print("1. Open: 00_original.png in an image editor (Photoshop, GIMP, etc.)")
    print("2. Find a lowercase letter (e.g., 'x', 'a', 'e', 'w')")
    print("3. Measure the height from:")
    print("   - Baseline (bottom of letter, excluding descenders)")
    print("   - To midline (top of lowercase letter, excluding ascenders)")
    print("4. Record the pixel height")
    print("\nTo measure line height (baseline-to-baseline):")
    print("1. Find two consecutive lines of text")
    print("2. Measure from baseline of first line to baseline of second line")
    print("3. Record the pixel height")

    print("\n" + "=" * 60)
    print("WHAT THE ALGORITHM MEASURES")
    print("=" * 60)
    print("The algorithm measures:")
    print("- CONSECUTIVE RUNS of rows with consistent ink density")
    print("- Returns the MEDIAN run length")
    print("\nThis is NOT the same as:")
    print("- X-height (baseline to midline of lowercase)")
    print("- Line height (baseline to baseline)")
    print("- Font size (point size)")
    print("\nIt's more like the typical vertical extent of ink")
    print("in regions with moderate density (likely individual")
    print("characters or character strokes).")

    # Save debug info
    with open(out_dir / "debug_info.json", "w") as f:
        # Convert run_positions to serializable format
        debug_info["run_positions"] = [
            {"start": s, "end": e, "length": l}
            for s, e, l in debug_info["run_positions"]
        ]
        json.dump(debug_info, f, indent=2)

    print(f"\nOutputs saved to: {out_dir}")
    print("  00_original.png - Original rendered page")
    print("  01_ink_detection.png - Ink pixels (red)")
    print("  02_row_density.png - Row-wise ink density plot")
    print("  03_runs_highlighted.png - Detected runs overlaid")
    print("  debug_info.json - Detailed measurement data")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
