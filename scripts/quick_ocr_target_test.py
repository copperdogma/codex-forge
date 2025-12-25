#!/usr/bin/env python3
"""
Quick OCR quality test for different x-height targets.

This script extracts a few test pages at different target line heights
and runs minimal OCR tests to validate quality. Designed for fast iteration
during story-102 investigation.

Usage:
  python scripts/quick_ocr_target_test.py \
    --pdf "input/deathtrapdungeon00ian_jn9_1 - from internet archive.pdf" \
    --pages 13,16,32,50,69 \
    --targets 12,14,16,18,20,24,28 \
    --out-dir /tmp/ocr-target-test
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.extract.extract_pdf_images_fast_v1.main import (
    _estimate_line_height_px,
    _extract_image_from_xobject,
    _load_pdf_reader,
)


def extract_page_at_target(pdf_path: str, page: int, target_height: int, out_path: Path) -> dict:
    """Extract a page and scale to target line height."""
    reader = _load_pdf_reader(pdf_path)
    if reader is None:
        raise RuntimeError("Could not load PDF")

    page_obj = reader.pages[page - 1]

    # Get page dimensions
    media_box = page_obj.mediabox
    page_w_pts = float(media_box.width)
    page_h_pts = float(media_box.height)

    # Extract embedded image
    resources = page_obj.get("/Resources") if hasattr(page_obj, "get") else None
    xobject = None
    if resources and hasattr(resources, "get"):
        xobject = resources.get("/XObject")

    result = _extract_image_from_xobject(xobject, page_w_pts, page_h_pts)
    if result is None:
        raise RuntimeError(f"Could not extract page {page}")

    img, metadata = result

    # Measure native line height
    native_height = _estimate_line_height_px(img)

    # Calculate scale factor
    if native_height is None or native_height == 0:
        scale_factor = 1.0
        action = "no_measurement"
    elif native_height <= target_height:
        scale_factor = 1.0
        action = "no_upscale"
    else:
        scale_factor = target_height / native_height
        action = "downscale"

    # Apply scaling
    if scale_factor != 1.0:
        new_w = int(round(img.width * scale_factor))
        new_h = int(round(img.height * scale_factor))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=95)

    return {
        "page": page,
        "target_height": target_height,
        "native_height": native_height,
        "scale_factor": round(scale_factor, 4),
        "action": action,
        "native_size": f"{metadata['width']}x{metadata['height']}",
        "final_size": f"{img.width}x{img.height}",
        "file": str(out_path),
    }


def run_simple_ocr_test(image_path: Path, model: str = "gpt-4.1-mini") -> dict:
    """
    Run a simple OCR test using OpenAI's vision API.

    Returns basic metrics: char count, word count, has_html tags.
    """
    import base64
    import os

    import openai

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    # Read image
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Simple OCR prompt
    prompt = """Transcribe this page to clean HTML. Use semantic tags like <h1>, <h2>, <p>, <b>, <i>.
Return ONLY the HTML, no markdown fences."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                        },
                    },
                ],
            }
        ],
        max_tokens=4000,
    )

    text = response.choices[0].message.content
    usage = response.usage

    # Basic quality metrics
    char_count = len(text)
    word_count = len(text.split())
    has_html = "<" in text and ">" in text
    has_tags = any(tag in text for tag in ["<h1>", "<h2>", "<p>", "<b>", "<i>"])

    return {
        "text_length": char_count,
        "word_count": word_count,
        "has_html": has_html,
        "has_semantic_tags": has_tags,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "sample_text": text[:200] if text else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="Path to PDF")
    parser.add_argument("--pages", default="13,16,32,50,69", help="Comma-separated page numbers")
    parser.add_argument("--targets", default="12,14,16,18,20,24,28", help="Comma-separated target heights")
    parser.add_argument("--out-dir", default="/tmp/ocr-target-test", help="Output directory")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OCR model to use")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR tests (just extract images)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = [int(p.strip()) for p in args.pages.split(",")]
    targets = [int(t.strip()) for t in args.targets.split(",")]

    print(f"Testing {len(pages)} pages × {len(targets)} targets = {len(pages) * len(targets)} combinations")
    print(f"Pages: {pages}")
    print(f"Targets: {targets}")
    print(f"Output: {out_dir}")

    results = []

    for target in targets:
        target_dir = out_dir / f"target-{target:02d}"
        print(f"\n{'='*60}")
        print(f"Target height: {target}px")
        print(f"{'='*60}")

        for page in pages:
            img_path = target_dir / f"page-{page:03d}.jpg"

            # Extract at target
            print(f"  Page {page}: extracting...", end=" ")
            try:
                extract_meta = extract_page_at_target(args.pdf, page, target, img_path)
                print(f"{extract_meta['action']} (scale={extract_meta['scale_factor']})")
            except Exception as e:
                print(f"FAILED: {e}")
                continue

            # Run OCR test
            if not args.skip_ocr:
                print(f"           OCR testing...", end=" ")
                try:
                    ocr_meta = run_simple_ocr_test(img_path, args.model)
                    print(f"{ocr_meta['word_count']} words, {ocr_meta['total_tokens']} tokens")
                except Exception as e:
                    print(f"FAILED: {e}")
                    ocr_meta = {"error": str(e)}
            else:
                ocr_meta = {"skipped": True}

            results.append({
                **extract_meta,
                "ocr": ocr_meta,
            })

        # Save intermediate results
        results_path = target_dir / "results.json"
        with open(results_path, "w") as f:
            json.dump([r for r in results if r["target_height"] == target], f, indent=2)

    # Save overall results
    all_results_path = out_dir / "all_results.json"
    with open(all_results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Summary analysis
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    if args.skip_ocr:
        print("OCR tests skipped - only image extraction performed")
    else:
        # Group by target
        for target in targets:
            target_results = [r for r in results if r["target_height"] == target and "error" not in r.get("ocr", {})]
            if not target_results:
                continue

            word_counts = [r["ocr"]["word_count"] for r in target_results]
            token_counts = [r["ocr"]["total_tokens"] for r in target_results]

            print(f"\nTarget {target}px:")
            print(f"  Pages tested: {len(target_results)}")
            print(f"  Avg words: {np.mean(word_counts):.1f}")
            print(f"  Avg tokens: {np.mean(token_counts):.1f}")
            print(f"  Token range: {min(token_counts)}-{max(token_counts)}")

    print(f"\nResults saved to: {all_results_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
