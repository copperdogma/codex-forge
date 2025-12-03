import argparse
import json
import os
from pathlib import Path

from modules.portionize.portionize_headers_numeric_v1.main import clean_lines, NUM_TOKEN_RE


def load_pages(path):
    pages = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            pages[int(obj["page"])] = obj
    return pages


def load_headers(path):
    headers = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            sid = obj.get("portion_id")
            pg = obj.get("page_start")
            headers.setdefault(pg, []).append(sid)
    return headers


def detect_inline_numbers(lines):
    found = []
    for line in lines:
        trimmed = line.strip()
        for m in NUM_TOKEN_RE.finditer(trimmed):
            sid = m.group(1)
            if sid.isdigit() and 1 <= int(sid) <= 400:
                found.append((sid, trimmed))
    return found


def main():
    ap = argparse.ArgumentParser(description="Inspect a page: image path, raw/clean text, headers on page.")
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--pages", required=True, help="pages_clean.jsonl")
    ap.add_argument("--headers", required=False, help="window_hypotheses.jsonl")
    ap.add_argument("--image-root", required=False, help="root folder for images (optional)")
    args = ap.parse_args()

    pages = load_pages(args.pages)
    page = pages.get(args.page)
    if not page:
        raise SystemExit(f"Page {args.page} not found in {args.pages}")

    headers = load_headers(args.headers) if args.headers else {}
    clean_text = page.get("clean_text") or page.get("raw_text") or ""
    raw_lines = clean_lines(clean_text)
    inline_nums = detect_inline_numbers(raw_lines)

    print(f"Page: {args.page}")
    if page.get("image"):
        img = page["image"]
        if args.image_root and not os.path.isabs(img):
            img = os.path.join(args.image_root, os.path.basename(img))
        print(f"Image: {img}")
    print("\n=== Clean lines ===")
    for ln in raw_lines:
        print(ln)
    print("\n=== Inline numeric tokens (1-400) ===")
    for sid, ln in inline_nums:
        print(f"{sid}: {ln}")
    if headers:
        print("\n=== Detected headers on this page ===")
        for sid in sorted(set(headers.get(args.page, [])), key=lambda x: int(x) if str(x).isdigit() else str(x)):
            print(sid)


if __name__ == "__main__":
    main()
