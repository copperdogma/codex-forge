"""Evaluate image-gate accuracy: which method best identifies pages with illustrations?

Tests multiple gate strategies on the Onward book pages and scores against golden truth.
Reports recall (don't miss image pages), precision (don't waste detector calls),
and estimated cost per 1000 pages.
"""

import base64
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def load_golden_pages():
    """Return set of page numbers that have golden crops."""
    with open("benchmarks/golden/image-crops.json") as f:
        golden = json.load(f)
    # ImageNNN -> page NNN+1
    return {int(k.replace("Image", "")) + 1 for k in golden.keys()}


def load_ocr_manifest(path):
    """Return dict of page_number -> html from OCR manifest."""
    pages = {}
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            pn = rec.get("page_number")
            html = rec.get("html", "")
            pages[pn] = html
    return pages


def gate_ocr_img_tags(ocr_pages):
    """Gate: page has images if OCR HTML contains <img tags."""
    return {pn for pn, html in ocr_pages.items() if "<img" in html.lower()}


def gate_vlm_yesno(image_dir, model, pages_to_check=None):
    """Gate: ask a cheap VLM 'does this page have illustrations?' yes/no."""
    from google.genai import Client
    client = Client(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))

    prompt = """Look at this scanned book page. Does it contain any photographs, illustrations, drawings, logos, seals, or other non-text visual elements?

Answer with ONLY a JSON object: {"has_images": true} or {"has_images": false}

Do NOT count decorative borders, horizontal rules, or text formatting as images.
Only count actual visual content like photos, drawings, logos, seals, signatures."""

    flagged = set()
    total_input_tokens = 0
    total_output_tokens = 0

    image_files = sorted(Path(image_dir).glob("*.jpg")) + sorted(Path(image_dir).glob("*.png"))
    if not image_files:
        image_files = sorted(Path(image_dir).glob("*.tif")) + sorted(Path(image_dir).glob("*.tiff"))

    for i, img_path in enumerate(image_files):
        page_num = i + 1
        if pages_to_check and page_num not in pages_to_check:
            continue

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
                total_input_tokens += resp.usage_metadata.prompt_token_count or 0
                total_output_tokens += resp.usage_metadata.candidates_token_count or 0

            if '"has_images": true' in text.lower() or '"has_images":true' in text.lower():
                flagged.add(page_num)
        except Exception as e:
            print(f"  Error on page {page_num}: {e}", file=sys.stderr)

        # Rate limiting
        if (i + 1) % 10 == 0:
            print(f"  {model}: processed {i+1}/{len(image_files)} pages...", file=sys.stderr)

    return flagged, total_input_tokens, total_output_tokens


def score_gate(flagged_pages, golden_pages, total_pages):
    """Score a gate method: recall, precision, F1."""
    tp = len(flagged_pages & golden_pages)
    fp = len(flagged_pages - golden_pages)
    fn = len(golden_pages - flagged_pages)
    tn = total_pages - tp - fp - fn

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "flagged": len(flagged_pages),
        "missed": sorted(golden_pages - flagged_pages),
    }


def main():
    golden_pages = load_golden_pages()
    print(f"Golden image pages ({len(golden_pages)}): {sorted(golden_pages)}")

    # We know from previous pipeline run that these additional pages also have images
    # (29 pages with 41 crops from story-126 run). But we only score against golden.

    image_dir = "input/onward-to-the-unknown-images"
    total_pages = len(list(Path(image_dir).glob("*")))
    print(f"Total pages: {total_pages}")

    ocr_path = "output/runs/onward-canonical/01_load_artifact_v1/pages_html.jsonl"

    results = {}

    # --- Gate 1: OCR img tags ---
    print("\n=== Gate: OCR <img> tags ===")
    ocr_pages = load_ocr_manifest(ocr_path)
    ocr_flagged = gate_ocr_img_tags(ocr_pages)
    score = score_gate(ocr_flagged, golden_pages, total_pages)
    results["OCR <img> tags"] = {**score, "cost_per_1k": 0.0, "input_tokens": 0, "output_tokens": 0}
    print(f"  Flagged: {score['flagged']} pages | Recall: {score['recall']:.1%} | Precision: {score['precision']:.1%}")
    print(f"  Missed golden pages: {score['missed']}")
    print(f"  Cost: $0 (already computed)")

    # --- Gate 2-4: VLM yes/no ---
    vlm_models = [
        ("gemini-2.5-flash", 0.15, 0.60),      # input $/M, output $/M
        ("gemini-3-flash-preview", 0.15, 0.60),  # estimated same tier
        ("gemini-3.1-flash-lite-preview", 0.075, 0.30),  # cheapest
    ]

    for model, input_price, output_price in vlm_models:
        print(f"\n=== Gate: {model} yes/no ===")
        flagged, in_tok, out_tok = gate_vlm_yesno(image_dir, model)
        score = score_gate(flagged, golden_pages, total_pages)
        cost_per_page = (in_tok * input_price + out_tok * output_price) / 1_000_000 / total_pages if total_pages > 0 else 0
        cost_per_1k = cost_per_page * 1000
        results[f"{model} yes/no"] = {
            **score,
            "cost_per_1k": cost_per_1k,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
        }
        print(f"  Flagged: {score['flagged']} pages | Recall: {score['recall']:.1%} | Precision: {score['precision']:.1%}")
        print(f"  Missed golden pages: {score['missed']}")
        print(f"  Tokens: {in_tok:,} in / {out_tok:,} out | Cost/1k pages: ${cost_per_1k:.4f}")

    # --- Gate 5: No gate (all pages) ---
    print(f"\n=== Gate: No gate (all pages) ===")
    all_pages = set(range(1, total_pages + 1))
    score = score_gate(all_pages, golden_pages, total_pages)
    results["No gate (all pages)"] = {**score, "cost_per_1k": 0.0, "input_tokens": 0, "output_tokens": 0}
    print(f"  Flagged: {score['flagged']} pages | Recall: {score['recall']:.1%} | Precision: {score['precision']:.1%}")

    # --- Summary table ---
    print("\n" + "=" * 90)
    print(f"{'Gate Method':<35} {'Recall':>8} {'Precision':>10} {'Flagged':>8} {'Missed':>8} {'Gate $/1k':>10}")
    print("-" * 90)
    for name, r in results.items():
        print(f"{name:<35} {r['recall']:>7.1%} {r['precision']:>9.1%} {r['flagged']:>8} {len(r['missed']):>8} ${r['cost_per_1k']:>9.4f}")

    # Save results
    out_path = "benchmarks/results/gate-eval-results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
