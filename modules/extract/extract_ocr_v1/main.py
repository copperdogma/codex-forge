import argparse
import json
import os

from modules.common import render_pdf, run_ocr
from modules.common.utils import ensure_dir, save_jsonl, ProgressLogger


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
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    images_dir = os.path.join(args.outdir, "images")
    ocr_dir = os.path.join(args.outdir, "ocr")
    ensure_dir(images_dir)
    ensure_dir(ocr_dir)

    image_paths = render_pdf(args.pdf, images_dir, dpi=args.dpi,
                             start_page=args.start, end_page=args.end)

    pages = []
    total = len(image_paths)
    for idx, img_path in enumerate(image_paths, start=args.start):
        text = run_ocr(img_path, lang=args.lang, psm=args.psm, oem=args.oem, tesseract_cmd=args.tess)
        ocr_path = os.path.join(ocr_dir, f"page-{idx:03d}.txt")
        with open(ocr_path, "w", encoding="utf-8") as f:
            f.write(text)
        pages.append({"page": idx, "image": os.path.abspath(img_path), "text": text})
        logger.log("extract", "running", current=len(pages), total=total,
                   message=f"OCR page {idx}", artifact=os.path.join(args.outdir, "pages_raw.jsonl"))

    save_jsonl(os.path.join(args.outdir, "pages_raw.jsonl"), pages)
    logger.log("extract", "done", current=total, total=total,
               message="OCR complete", artifact=os.path.join(args.outdir, "pages_raw.jsonl"))
    print(f"Saved pages_raw.jsonl with {len(pages)} pages")


if __name__ == "__main__":
    main()
