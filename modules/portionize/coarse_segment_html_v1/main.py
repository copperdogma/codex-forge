#!/usr/bin/env python3
"""
Coarse segmenter (HTML blocks): LLM-first classification of frontmatter/gameplay/endmatter.

Consumes page_html_blocks_v1, reduces to compact per-page summaries, then uses a single
LLM call to classify macro sections and output page ranges.
"""
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from modules.common.utils import read_jsonl, save_json, log_llm_usage, ProgressLogger


def summarize_page(
    blocks: List[Dict],
    page_number: int,
    original_page_number: Optional[int],
    max_blocks: int = 8,
    max_len: int = 120,
) -> Dict:
    """Summarize a page's blocks into compact snippets."""
    snippets: List[str] = []
    numeric_flags = 0
    for block in blocks:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        block_type = block.get("block_type") or "p"
        if block_type == "h2" and text.isdigit():
            numeric_flags += 1
        if block_type in {"h1", "h2"}:
            snippet = f"{block_type.upper()}: {text}"
        elif block_type == "p" and (block.get("attrs") or {}).get("class"):
            cls = (block.get("attrs") or {}).get("class")
            snippet = f"P({cls}): {text}"
        else:
            snippet = text
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "…"
        snippets.append(snippet)
        if len(snippets) >= max_blocks:
            break
    return {
        "page_number": page_number,
        "original_page_number": original_page_number,
        "snippet_lines": snippets,
        "block_count": len(blocks),
        "numeric_headers": numeric_flags,
    }


def reduce_blocks(blocks_path: str, max_blocks: int = 8, max_len: int = 120) -> List[Dict]:
    pages: Dict[int, Dict[str, Optional[int] | List[Dict]]] = {}
    for row in read_jsonl(blocks_path):
        page_id = row.get("page_number")
        if page_id is None:
            page_id = row.get("page")
        if page_id is None:
            continue

        original_page_number = row.get("original_page_number")
        page_entry = pages.setdefault(
            page_id,
            {"blocks": [], "original_page_number": original_page_number},
        )
        if page_entry.get("original_page_number") is None and original_page_number is not None:
            page_entry["original_page_number"] = original_page_number

        blocks = row.get("blocks") or []
        page_entry["blocks"].extend(blocks)

    summaries = []
    for page_id in sorted(pages.keys()):
        page_entry = pages[page_id]
        summaries.append(
            summarize_page(
                page_entry["blocks"],
                page_id,
                page_entry.get("original_page_number"),
                max_blocks,
                max_len,
            )
        )
    return summaries


def load_prompt(prompt_path: Optional[str] = None) -> str:
    if prompt_path and os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    return """You are analyzing the structure of a Fighting Fantasy gamebook to identify three macro sections.

INPUT: A JSON object with a "pages" array. Each page entry contains:
- page_number: sequential page identifier (integer 1, 2, 3...)
- original_page_number: source document page index (integer, may repeat when a spread is split)
- snippets: array of short text snippets from that page (up to 8 items, ~120 chars each)
- block_count: total number of HTML blocks on the page
- numeric_headers: count of numeric <h2> headers (potential section headers)

CRITICAL: You will receive ALL pages in the book (typically 100+ pages). You MUST analyze ALL pages to determine the correct boundaries.

SPREAD-SPLIT PAGES: Some books split a single source page into multiple pipeline pages.
In that case, multiple entries will share the same original_page_number, but each will have its own page_number.
Treat each page_number as a separate page in your ranges.

TASK: Identify three contiguous page ranges:
1. frontmatter: Title pages, copyright, TOC, rules, instructions, adventure sheets (typically pages 1-15)
2. gameplay_sections: The numbered gameplay content starting with "BACKGROUND" or section "1" (typically pages 16-400+)
3. endmatter: Appendices, ads, previews, author bios (typically last 5-20 pages, may be null)

RULES:
- Frontmatter always starts at page 1
- Gameplay begins at the first page with "BACKGROUND", "INTRODUCTION", or numbered section headers (typically 1-400)
- Gameplay ends at the LAST page containing numbered sections (1-400), even if ads/previews also appear on that page
- Endmatter starts at the first page that contains ONLY ads/previews/appendices with NO numbered sections
- IMPORTANT: If a page has BOTH numbered sections AND ads, it is GAMEPLAY (the numbered sections take precedence)
- All three ranges must be contiguous (no gaps)
- If endmatter is absent, set it to null
- Use page_number values from the input (do not invent page numbers)

OUTPUT JSON (exactly this format):
{
  "frontmatter_pages": [start_page, end_page],
  "gameplay_pages": [start_page, end_page],
  "endmatter_pages": [start_page, end_page] or null,
  "notes": "brief rationale citing distinguishing features"
}
"""


def call_llm_classify(client: OpenAI, model: str, pages: List[Dict], prompt: str) -> Dict:
    optimized_pages = []
    for p in pages:
        optimized_pages.append({
            "page_number": p["page_number"],
            "original_page_number": p.get("original_page_number"),
            "snippets": p["snippet_lines"][:8],
            "block_count": p["block_count"],
            "numeric_headers": p["numeric_headers"],
        })
    total_pages = len(optimized_pages)
    page_range_note = (
        f"\n\nCRITICAL: This book has {total_pages} pages total (pages 1 through {total_pages}). "
        f"You MUST examine ALL pages from 1 to {total_pages} to find where gameplay starts and ends.\n\n"
    )
    user_content = prompt + page_range_note + json.dumps({"pages": optimized_pages}, indent=1)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": f"You are a book structure analyzer. This book has {total_pages} pages. You MUST analyze ALL {total_pages} pages from start to finish. Return only valid JSON."},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    usage = getattr(completion, "usage", None)
    if usage:
        log_llm_usage(
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    return json.loads(completion.choices[0].message.content)


def validate_ranges(result: Dict, total_pages: int) -> Tuple[bool, List[str]]:
    errors = []

    def parse_page_id(page_id):
        if isinstance(page_id, int):
            return page_id
        if page_id is None:
            return None
        digits = ""
        for ch in str(page_id):
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits:
            return int(digits)
        return None

    required = ["frontmatter_pages", "gameplay_pages", "endmatter_pages"]
    for field in required:
        if field not in result:
            errors.append(f"Missing field: {field}")

    front = result.get("frontmatter_pages")
    if front is not None:
        if not isinstance(front, list) or len(front) != 2:
            errors.append("frontmatter_pages must be [start, end] or null")
        else:
            start_num = parse_page_id(front[0])
            if start_num and start_num < 1:
                errors.append(f"frontmatter_pages start < 1: {front}")

    gameplay = result.get("gameplay_pages")
    if gameplay is not None:
        if not isinstance(gameplay, list) or len(gameplay) != 2:
            errors.append("gameplay_pages must be [start, end] or null")

    end = result.get("endmatter_pages")
    if end is not None:
        if not isinstance(end, list) or len(end) != 2:
            errors.append("endmatter_pages must be [start, end] or null")

    ranges = []
    if front:
        ranges.append(("frontmatter", front))
    if gameplay:
        ranges.append(("gameplay", gameplay))
    if end:
        ranges.append(("endmatter", end))

    for name, page_range in ranges:
        if page_range[0] is None or page_range[1] is None:
            errors.append(f"{name} has None page boundary: {page_range}")

    return len(errors) == 0, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Coarse segmenter for HTML block stream")
    parser.add_argument("--pages", help="page_html_blocks_v1 JSONL path")
    parser.add_argument("--inputs", nargs="*", help="Driver-provided inputs")
    parser.add_argument("--out", required=True, help="Output JSON with page ranges")
    parser.add_argument("--model", default="gpt-5.1", help="LLM model to use")
    parser.add_argument("--retry-model", dest="retry_model", help="Retry model (default: same as --model)")
    parser.add_argument("--retry_model", dest="retry_model", help="Retry model (default: same as --model)")
    parser.add_argument("--max-retries", dest="max_retries", type=int, default=2)
    parser.add_argument("--max_retries", dest="max_retries", type=int, default=2)
    parser.add_argument("--max-blocks", dest="max_blocks", type=int, default=8)
    parser.add_argument("--max_blocks", dest="max_blocks", type=int, default=8)
    parser.add_argument("--max-len", dest="max_len", type=int, default=120)
    parser.add_argument("--max_len", dest="max_len", type=int, default=120)
    parser.add_argument("--prompt", help="Path to custom prompt file (optional)")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages_path = args.pages or (args.inputs[0] if args.inputs else None)
    if not pages_path:
        parser.error("Missing --pages (or --inputs) input")
    if not os.path.isabs(pages_path):
        pages_path = os.path.abspath(pages_path)
    if not os.path.exists(pages_path):
        raise SystemExit(f"Blocks file not found: {pages_path}")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "coarse_segment",
        "running",
        current=0,
        total=100,
        message="Reducing HTML blocks to summaries",
        artifact=args.out,
        module_id="coarse_segment_html_v1",
    )

    pages = reduce_blocks(pages_path, args.max_blocks, args.max_len)
    total_pages = len(pages)

    logger.log(
        "coarse_segment",
        "running",
        current=50,
        total=100,
        message=f"Reduced {total_pages} pages, calling LLM",
        artifact=args.out,
        module_id="coarse_segment_html_v1",
    )

    prompt = load_prompt(args.prompt)
    client = OpenAI()
    retry_model = args.retry_model or args.model
    result = None
    errors: List[str] = []

    for attempt in range(args.max_retries + 1):
        model = retry_model if attempt > 0 else args.model
        try:
            result = call_llm_classify(client, model, pages, prompt)
            is_valid, errors = validate_ranges(result, total_pages)
            if is_valid:
                break
            if attempt < args.max_retries:
                logger.log(
                    "coarse_segment",
                    "running",
                    current=75,
                    total=100,
                    message=f"Validation failed (attempt {attempt + 1}/{args.max_retries + 1}), retrying with {model}",
                    artifact=args.out,
                    module_id="coarse_segment_html_v1",
                )
        except Exception as exc:
            errors = [f"LLM call failed: {str(exc)}"]
            if attempt < args.max_retries:
                logger.log(
                    "coarse_segment",
                    "running",
                    current=75,
                    total=100,
                    message=f"LLM error (attempt {attempt + 1}/{args.max_retries + 1}), retrying with {model}",
                    artifact=args.out,
                    module_id="coarse_segment_html_v1",
                )
            else:
                raise

    if result is None:
        raise ValueError("Failed to get valid result from LLM after retries")

    output = {
        "schema_version": "coarse_segments_v1",
        "module_id": "coarse_segment_html_v1",
        "run_id": args.run_id,
        "total_pages": total_pages,
        "frontmatter_pages": result.get("frontmatter_pages"),
        "gameplay_pages": result.get("gameplay_pages"),
        "endmatter_pages": result.get("endmatter_pages"),
        "notes": result.get("notes", ""),
        "validation_errors": errors if errors else None,
    }

    save_json(args.out, output)

    if errors:
        logger.log(
            "coarse_segment",
            "warning",
            current=100,
            total=100,
            message=f"Completed with validation warnings: {', '.join(errors)}",
            artifact=args.out,
            module_id="coarse_segment_html_v1",
        )
    else:
        logger.log(
            "coarse_segment",
            "done",
            current=100,
            total=100,
            message="Coarse segmentation completed successfully",
            artifact=args.out,
            module_id="coarse_segment_html_v1",
        )

    print(f"✅ Coarse segmentation → {args.out}")
    print(f"   Frontmatter: {output['frontmatter_pages']}")
    print(f"   Gameplay: {output['gameplay_pages']}")
    print(f"   Endmatter: {output['endmatter_pages']}")


if __name__ == "__main__":
    main()
