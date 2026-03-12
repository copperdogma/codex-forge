"""Test permissive gate prompts — optimize for recall over precision."""

import base64
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def load_golden_pages():
    with open("benchmarks/golden/image-crops.json") as f:
        golden = json.load(f)
    return {int(k.replace("Image", "")) + 1 for k in golden.keys()}


PERMISSIVE_PROMPT = """Look at this scanned book page. Could this page contain ANY visual elements beyond plain text?

Answer YES if you see ANY of these, even if you're not sure:
- Photographs or parts of photographs
- Illustrations, drawings, or sketches
- Logos, seals, stamps, or emblems
- Signatures or handwritten marks
- Decorative graphics (NOT simple horizontal lines)
- Maps, diagrams, or charts
- Any non-text visual content whatsoever

When in doubt, answer YES. It's better to flag a page that might have images than to miss one.

Answer with ONLY: {"has_images": true} or {"has_images": false}"""

AGGRESSIVE_PROMPT = """Scan this book page. Does it have ANYTHING other than printed text and page numbers?

If there is ANY mark, graphic, photo, drawing, seal, logo, signature, or visual element — even partially visible, even tiny, even faded — answer true.

Only answer false if the page is PURELY typeset text with no visual elements at all.

{"has_images": true} or {"has_images": false}"""


def run_gate(image_dir, model, prompt, label):
    from google.genai import Client
    client = Client(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))

    flagged = set()
    total_in = 0
    total_out = 0

    image_files = sorted(Path(image_dir).glob("*.jpg")) + sorted(Path(image_dir).glob("*.png"))
    if not image_files:
        image_files = sorted(Path(image_dir).glob("*.tif")) + sorted(Path(image_dir).glob("*.tiff"))

    for i, img_path in enumerate(image_files):
        page_num = i + 1
        with open(img_path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.standard_b64encode(img_bytes).decode()
        ext = img_path.suffix.lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png" if ext == ".png" else "image/tiff"

        try:
            resp = client.models.generate_content(
                model=model,
                contents=[{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime, "data": b64}},
                    ]
                }],
                config={"temperature": 0, "max_output_tokens": 50},
            )
            text = resp.text or ""
            if resp.usage_metadata:
                total_in += resp.usage_metadata.prompt_token_count or 0
                total_out += resp.usage_metadata.candidates_token_count or 0

            # More permissive parsing — also catch "true" without JSON wrapper
            text_lower = text.lower().strip()
            if "true" in text_lower or "yes" in text_lower:
                flagged.add(page_num)
        except Exception as e:
            print(f"  Error on page {page_num} ({model}/{label}): {e}", file=sys.stderr)
            # On error, flag it (permissive)
            flagged.add(page_num)

        if (i + 1) % 20 == 0:
            print(f"  {model}/{label}: {i+1}/{len(image_files)}", file=sys.stderr)

    return flagged, total_in, total_out


def score_gate(flagged, golden, total):
    tp = len(flagged & golden)
    fp = len(flagged - golden)
    fn = len(golden - flagged)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    return {
        "recall": recall, "precision": precision,
        "tp": tp, "fp": fp, "fn": fn,
        "flagged": len(flagged),
        "missed": sorted(golden - flagged),
    }


def main():
    golden = load_golden_pages()
    image_dir = "input/onward-to-the-unknown-images"
    total = len(list(Path(image_dir).glob("*")))
    print(f"Golden: {sorted(golden)} | Total pages: {total}")

    configs = [
        # (model, prompt, label)
        ("gemini-2.5-flash", PERMISSIVE_PROMPT, "2.5-flash/permissive"),
        ("gemini-2.5-flash", AGGRESSIVE_PROMPT, "2.5-flash/aggressive"),
        ("gemini-3.1-flash-lite-preview", PERMISSIVE_PROMPT, "3.1-lite/permissive"),
        ("gemini-3.1-flash-lite-preview", AGGRESSIVE_PROMPT, "3.1-lite/aggressive"),
        ("gemini-3-flash-preview", PERMISSIVE_PROMPT, "3-flash/permissive"),
        ("gemini-3-flash-preview", AGGRESSIVE_PROMPT, "3-flash/aggressive"),
    ]

    results = {}
    for model, prompt, label in configs:
        print(f"\n=== {label} ===", file=sys.stderr)
        flagged, in_tok, out_tok = run_gate(image_dir, model, prompt, label)
        s = score_gate(flagged, golden, total)

        # Cost estimate (flash-tier pricing)
        if "2.5" in model:
            cost = (in_tok * 0.15 + out_tok * 0.60) / 1_000_000
        else:
            cost = (in_tok * 0.075 + out_tok * 0.30) / 1_000_000  # lite tier estimate

        results[label] = {**s, "in_tok": in_tok, "out_tok": out_tok, "cost": cost}

    # Summary
    print(f"\n{'Config':<30} {'Recall':>7} {'Prec':>7} {'Flagged':>8} {'Missed':>7} {'Cost':>8}")
    print("-" * 75)
    for label, r in results.items():
        print(f"{label:<30} {r['recall']:>6.1%} {r['precision']:>6.1%} {r['flagged']:>8} {len(r['missed']):>7} ${r['cost']:>7.4f}")
        if r['missed']:
            print(f"  {'':30} missed: {r['missed']}")

    # Save
    with open("benchmarks/results/permissive-gate-eval.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to benchmarks/results/permissive-gate-eval.json")


if __name__ == "__main__":
    main()
