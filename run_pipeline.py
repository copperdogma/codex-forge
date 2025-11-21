import argparse
import glob
import json
import os
import sys
from typing import List, Optional
from openai import OpenAI
from tqdm import tqdm

from utils import load_settings, ensure_dir, save_json
from ocr import render_pdf, run_ocr
from llm_clean import clean_page
from validate import validate_pages, ValidationError
from schemas import PageResult, Paragraph


def gather_images(images_dir: str, start: int, end: Optional[int]) -> List[str]:
    paths = sorted(glob.glob(os.path.join(images_dir, "page-*.jpg")))
    if not paths:
        raise FileNotFoundError(f"No images found in {images_dir}")
    if end:
        return paths[start - 1:end]
    return paths[start - 1:]


def main():
    parser = argparse.ArgumentParser(description="Full PDF→OCR→LLM clean→data.json pipeline.")
    parser.add_argument("--settings", default="settings.example.yaml")
    parser.add_argument("--pdf", help="Path to source PDF")
    parser.add_argument("--images", help="Directory of pre-rendered page-*.jpg")
    parser.add_argument("--out", default="output", help="Output directory")
    parser.add_argument("--pstart", type=int, help="First page to process (1-based). Overrides settings.")
    parser.add_argument("--pend", type=int, help="Last page to process (inclusive). Overrides settings.")
    parser.add_argument("--lenient", action="store_true",
                        help="Allow choice targets outside the processed page range (useful for partial runs).")
    args = parser.parse_args()

    settings = load_settings(args.settings)
    model = settings.get("model", "gpt-4o-mini")
    temperature = settings.get("temperature", 0.2)
    max_retries = settings.get("max_retries", 3)
    dpi = settings.get("render", {}).get("dpi", 300)
    psm = settings.get("ocr", {}).get("psm", 4)
    oem = settings.get("ocr", {}).get("oem", 3)
    lang = settings.get("ocr", {}).get("lang", "eng")
    tess_cmd = settings.get("paths", {}).get("tesseract_cmd")
    start_page = args.pstart or settings.get("range", {}).get("start_page", 1)
    end_page = args.pend or settings.get("range", {}).get("end_page")

    out_dir = os.path.join("pipeline", args.out) if not args.out.startswith("/") else args.out
    ensure_dir(out_dir)

    # Optional pipeline state tracking per output folder
    state_path = os.path.join(out_dir, "pipeline_state.json")
    state = {"images_extracted": False, "ocr_done_pages": [], "clean_done_pages": []}
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state.update(json.load(f))
        except Exception:
            pass
    images_out = os.path.join(out_dir, "images")
    ocr_out = os.path.join(out_dir, "ocr")
    clean_out = os.path.join(out_dir, "pages_clean")
    ensure_dir(ocr_out)
    ensure_dir(clean_out)

    # Step 1: images
    if args.images:
        image_paths = gather_images(args.images, start_page, end_page)
        state["images_extracted"] = True
    else:
        pdf_path = args.pdf or settings["paths"].get("pdf")
        if not pdf_path:
            print("Error: provide --pdf or images dir", file=sys.stderr)
            sys.exit(1)
        image_paths = render_pdf(pdf_path, images_out, dpi=dpi,
                                 start_page=start_page, end_page=end_page)
        state["images_extracted"] = True

    # Step 2/3: OCR + LLM clean
    if "OPENAI_API_KEY" not in os.environ:
        print("Error: OPENAI_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    paragraphs: List[Paragraph] = []

    for idx, image_path in enumerate(tqdm(image_paths, desc="Pages")):
        page_num = start_page + idx

        ocr_text = run_ocr(image_path, lang=lang, psm=psm, oem=oem, tesseract_cmd=tess_cmd)
        ocr_path = os.path.join(ocr_out, f"page-{page_num:03d}.txt")
        with open(ocr_path, "w", encoding="utf-8") as f:
            f.write(ocr_text)
        state["ocr_done_pages"].append(page_num)

        attempt = 0
        last_err = None
        page_result: Optional[PageResult] = None
        while attempt < max_retries:
            attempt += 1
            try:
                page_result = clean_page(client, model, ocr_text, image_path)
                # attach page number to each paragraph
                for p in page_result.paragraphs:
                    p.page = page_num
                    if not p.images:
                        p.images = [os.path.basename(image_path)]
                break
            except Exception as e:  # validation/parsing issues
                last_err = e
        if page_result is None:
            raise RuntimeError(f"Failed to process page {page_num}: {last_err}")

        save_json(os.path.join(clean_out, f"page-{page_num:03d}.json"),
                  page_result.dict())
        paragraphs.extend(page_result.paragraphs)
        state["clean_done_pages"].append(page_num)

    # Optional heuristic: drop preamble pages until the first "turn to" pattern
    opts = settings.get("options", {})
    drop_until_turn = opts.get("drop_until_turn", True)
    if drop_until_turn:
        start_idx = 0
        for i, p in enumerate(paragraphs):
            if "turn to" in p.text.lower():
                start_idx = i
                break
        if start_idx > 0:
            paragraphs = paragraphs[start_idx:]

    # Optional heuristic: deduplicate paragraph IDs by first occurrence (helps remove intro tables)
    if opts.get("dedupe_ids", True):
        seen = {}
        for p in paragraphs:
            if p.id not in seen:
                seen[p.id] = p
        paragraphs = list(seen.values())

    # Step 4: global validation
    try:
        validate_pages(paragraphs, strict=not args.lenient)
    except ValidationError as e:
        print(f"Global validation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 5: merge
    merged = {p.id: p.dict() for p in paragraphs}
    save_json(os.path.join(out_dir, "data.json"), merged)
    save_json(state_path, state)
    print(f"Done. data.json written to {out_dir}")


if __name__ == "__main__":
    main()
