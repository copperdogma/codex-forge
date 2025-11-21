import argparse
import json
import os
import sys
import pathlib

repo_root = pathlib.Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from utils import ensure_dir, save_jsonl
from ocr import render_pdf, run_ocr


def main():
    parser = argparse.ArgumentParser(description="Dump per-page OCR into pages_raw.jsonl")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--outdir", required=True, help="Base output directory")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--psm", type=int, default=4)
    parser.add_argument("--oem", type=int, default=3)
    parser.add_argument("--lang", default="eng")
    parser.add_argument("--tess", help="Path to tesseract binary")
    args = parser.parse_args()

    images_dir = os.path.join(args.outdir, "images")
    ocr_dir = os.path.join(args.outdir, "ocr")
    ensure_dir(images_dir)
    ensure_dir(ocr_dir)

    image_paths = render_pdf(args.pdf, images_dir, dpi=args.dpi,
                             start_page=args.start, end_page=args.end)

    pages = []
    for idx, img_path in enumerate(image_paths, start=args.start):
        text = run_ocr(img_path, lang=args.lang, psm=args.psm, oem=args.oem, tesseract_cmd=args.tess)
        ocr_path = os.path.join(ocr_dir, f"page-{idx:03d}.txt")
        with open(ocr_path, "w", encoding="utf-8") as f:
            f.write(text)
        pages.append({"page": idx, "image": os.path.abspath(img_path), "text": text})

    save_jsonl(os.path.join(args.outdir, "pages_raw.jsonl"), pages)
    print(f"Saved pages_raw.jsonl with {len(pages)} pages")


if __name__ == "__main__":
    main()
