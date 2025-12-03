import argparse
import json
from pathlib import Path

from modules.common.utils import read_jsonl, save_json


def load_page_text(path):
    page = json.load(open(path, "r", encoding="utf-8"))
    text = "\n".join([l.get("text", "") for l in page.get("lines", [])])
    return text


def main():
    ap = argparse.ArgumentParser(description="Flag pages with high divergence between OCR engines.")
    ap.add_argument("--ocr-index-a", required=True, help="pagelines_index.json for engine A")
    ap.add_argument("--ocr-index-b", required=True, help="pagelines_index.json for engine B")
    ap.add_argument("--out", required=True, help="JSON report path")
    ap.add_argument("--threshold", type=float, default=0.4, help="Jaccard threshold (lower means more divergent)")
    args = ap.parse_args()

    idx_a = json.load(open(args.ocr_index_a, "r", encoding="utf-8"))
    idx_b = json.load(open(args.ocr_index_b, "r", encoding="utf-8"))

    divergent = []
    for page in idx_a:
        if page not in idx_b:
            continue
        text_a = load_page_text(idx_a[str(page)])
        text_b = load_page_text(idx_b[str(page)])
        tokens_a = set(text_a.split())
        tokens_b = set(text_b.split())
        if not tokens_a or not tokens_b:
            continue
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        if jaccard < args.threshold:
            divergent.append({"page": int(page), "jaccard": jaccard})

    save_json(args.out, {"divergent_pages": sorted(divergent, key=lambda x: x["jaccard"])})
    print(f"Flagged {len(divergent)} divergent pages → {args.out}")


if __name__ == "__main__":
    main()
