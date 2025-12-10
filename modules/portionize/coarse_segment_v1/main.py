#!/usr/bin/env python3
"""
Coarse segmenter: LLM-first classification of frontmatter/gameplay/endmatter.

Takes elements_core.jsonl, reduces to compact per-page summaries, then uses a single
LLM call to classify macro sections (frontmatter/gameplay/endmatter) and output page ranges.
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from openai import OpenAI

from modules.common.utils import read_jsonl, save_json, log_llm_usage, ProgressLogger


def summarize_page(lines: List[Dict], page: int, max_lines: int = 10, max_len: int = 120) -> Dict:
    """Summarize a page's elements into compact snippets."""
    snippets = []
    numeric_flags = 0
    for ln in lines[:max_lines]:
        text = ln.get("text", "")
        if not text:
            continue
        if text.strip().isdigit():
            numeric_flags += 1
        if len(text) > max_len:
            text = text[:max_len] + "…"
        snippets.append(text)
    return {
        "page": page,
        "snippet_lines": snippets,
        "line_count": len(lines),
        "numeric_lines": numeric_flags,
    }


def reduce_elements(elements_path: str, max_lines: int = 8, max_len: int = 100) -> List[Dict]:
    """Reduce elements.jsonl to compact per-page summaries.
    
    Optimized for minimal data: only essential snippets, shorter lines, fewer per page.
    Works with full book output (226 pages from spread splitting).
    """
    pages = {}
    for row in read_jsonl(elements_path):
        # Handle element_core_v1 format (has 'page' directly as integer)
        pg = row.get("page")
        if pg is None:
            # Fallback to metadata if page not directly available
            pg = row.get("metadata", {}).get("page_number") or row.get("metadata", {}).get("page") or 0
        if pg == 0:
            continue  # Skip elements with no page
        pages.setdefault(pg, []).append(row)
    
    summaries = []
    for pg in sorted(pages.keys()):
        summaries.append(summarize_page(pages[pg], pg, max_lines, max_len))
    return summaries


def load_prompt(prompt_path: Optional[str] = None) -> str:
    """Load the coarse segmentation prompt."""
    if prompt_path and os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Default prompt (inline) - optimized for minimal data, full book processing
    return """You are analyzing the structure of a Fighting Fantasy gamebook to identify three macro sections.

INPUT: A JSON object with a "pages" array. Each page entry contains:
- page: page number (integer, 1-based)
- snippets: array of short text snippets from that page (up to 8 lines, ~100 chars each)
- line_count: total number of text lines on the page
- numeric: count of standalone numeric lines (potential section headers)

CRITICAL: You will receive ALL pages in the book (typically 100+ pages). You MUST analyze ALL pages to determine the correct boundaries.

TASK: Identify three contiguous page ranges:
1. frontmatter: Title pages, copyright, TOC, rules, instructions, adventure sheets (typically pages 1-15)
2. gameplay_sections: The numbered gameplay content starting with "BACKGROUND" or section "1" (typically pages 16-400+)
3. endmatter: Appendices, ads, previews, author bios (typically last 5-20 pages, may be null)

RULES:
- Frontmatter always starts at page 1
- Gameplay begins at the first page with "BACKGROUND", "INTRODUCTION", or numbered section headers
- Endmatter starts after gameplay clearly ends (no more numbered sections, or ads/previews appear)
- All three ranges must be contiguous (no gaps)
- If endmatter is absent, set it to null
- Use the page numbers from the input (do not invent page numbers)

OUTPUT JSON (exactly this format):
{
  "frontmatter_pages": [start_page, end_page],
  "gameplay_pages": [start_page, end_page],
  "endmatter_pages": [start_page, end_page] or null,
  "notes": "brief rationale citing distinguishing features"
}

Example for a 400-page book:
{
  "frontmatter_pages": [1, 15],
  "gameplay_pages": [16, 380],
  "endmatter_pages": [381, 400],
  "notes": "Frontmatter includes title, rules, adventure sheet. Gameplay starts at page 16 with BACKGROUND. Endmatter has ads and previews."
}"""


def call_llm_classify(client: OpenAI, model: str, pages: List[Dict], prompt: str) -> Dict:
    """Call LLM to classify macro sections."""
    # Optimize payload: only send essential fields, compact format
    optimized_pages = []
    for p in pages:
        optimized_pages.append({
            "page": p["page"],
            "snippets": p["snippet_lines"][:8],  # Max 8 lines (reduced from 10)
            "line_count": p["line_count"],
            "numeric": p["numeric_lines"],
        })
    # Add explicit instruction about total page count
    total_pages = len(optimized_pages)
    page_range_note = f"\n\nCRITICAL: This book has {total_pages} pages total (pages 1 through {total_pages}). You MUST examine ALL pages from 1 to {total_pages} to find where gameplay starts and ends. Do not stop at page 3 - continue analyzing through page {total_pages}.\n\n"
    user_content = prompt + page_range_note + json.dumps({"pages": optimized_pages}, indent=1)  # Compact indent
    
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": f"You are a book structure analyzer. This book has {total_pages} pages. You MUST analyze ALL {total_pages} pages from start to finish. Return only valid JSON."},
            {"role": "user", "content": user_content}
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
    """Validate the LLM output page ranges."""
    errors = []
    
    # Check required fields
    required = ["frontmatter_pages", "gameplay_pages", "endmatter_pages"]
    for field in required:
        if field not in result:
            errors.append(f"Missing field: {field}")
    
    # Validate frontmatter
    front = result.get("frontmatter_pages")
    if front is not None:
        if not isinstance(front, list) or len(front) != 2:
            errors.append("frontmatter_pages must be [start, end] or null")
        elif front[0] < 1 or front[1] > total_pages:
            errors.append(f"frontmatter_pages out of range: {front}")
        elif front[0] > front[1]:
            errors.append(f"frontmatter_pages invalid: start > end: {front}")
    
    # Validate gameplay
    gameplay = result.get("gameplay_pages")
    if gameplay is not None:
        if not isinstance(gameplay, list) or len(gameplay) != 2:
            errors.append("gameplay_pages must be [start, end] or null")
        elif gameplay[0] < 1 or gameplay[1] > total_pages:
            errors.append(f"gameplay_pages out of range: {gameplay}")
        elif gameplay[0] > gameplay[1]:
            errors.append(f"gameplay_pages invalid: start > end: {gameplay}")
    
    # Validate endmatter
    end = result.get("endmatter_pages")
    if end is not None:
        if not isinstance(end, list) or len(end) != 2:
            errors.append("endmatter_pages must be [start, end] or null")
        elif end[0] < 1 or end[1] > total_pages:
            errors.append(f"endmatter_pages out of range: {end}")
        elif end[0] > end[1]:
            errors.append(f"endmatter_pages invalid: start > end: {end}")
    
    # Check for overlaps/gaps
    ranges = []
    if front:
        ranges.append(("frontmatter", front))
    if gameplay:
        ranges.append(("gameplay", gameplay))
    if end:
        ranges.append(("endmatter", end))
    
    ranges.sort(key=lambda x: x[1][0])
    for i in range(len(ranges) - 1):
        curr_name, curr_range = ranges[i]
        next_name, next_range = ranges[i + 1]
        if curr_range[1] >= next_range[0]:
            errors.append(f"Overlap between {curr_name} and {next_name}")
        elif curr_range[1] + 1 < next_range[0]:
            errors.append(f"Gap between {curr_name} (ends {curr_range[1]}) and {next_name} (starts {next_range[0]})")
    
    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Coarse segmenter: LLM-first classification of macro sections")
    parser.add_argument("--elements", help="elements_core.jsonl path")
    parser.add_argument("--pages", help="Alias for --elements (driver compatibility)")
    parser.add_argument("--out", required=True, help="Output JSON with page ranges")
    parser.add_argument("--model", default="gpt-4.1-mini", help="LLM model to use")
    parser.add_argument("--max-lines", "--max_lines", type=int, default=8, dest="max_lines", help="Max lines per page in summary (optimized for minimal data)")
    parser.add_argument("--max-len", "--max_len", type=int, default=100, dest="max_len", help="Max length per line in summary (optimized for minimal data)")
    parser.add_argument("--prompt", help="Path to custom prompt file (optional)")
    parser.add_argument("--retry-model", "--retry_model", help="Model to use for retry if validation fails (default: same as --model)", dest="retry_model")
    parser.add_argument("--max-retries", "--max_retries", type=int, default=2, dest="max_retries", help="Max retries on validation failure")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    
    # Handle driver input aliases - prioritize --pages (from driver) over --elements (from params)
    elements_path = args.pages or args.elements
    if not elements_path:
        parser.error("Missing --elements (or --pages) input")
    
    # Resolve to absolute path if relative
    if not os.path.isabs(elements_path):
        # Try relative to current working directory first
        if os.path.exists(elements_path):
            elements_path = os.path.abspath(elements_path)
        else:
            # Try relative to current working directory
            cwd_path = os.path.join(os.getcwd(), elements_path)
            if os.path.exists(cwd_path):
                elements_path = os.path.abspath(cwd_path)
            else:
                raise SystemExit(f"Could not find elements file: {elements_path} (tried: {cwd_path})")
    else:
        # Already absolute, just verify it exists
        if not os.path.exists(elements_path):
            raise SystemExit(f"Elements file not found: {elements_path}")
    
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    # Step 1: Reduce elements to compact summaries
    logger.log("coarse_segment", "running", current=0, total=100,
               message="Reducing elements to compact summaries", artifact=args.out,
               module_id="coarse_segment_v1")
    
    pages = reduce_elements(elements_path, args.max_lines, args.max_len)
    total_pages = len(pages)
    
    logger.log("coarse_segment", "running", current=50, total=100,
               message=f"Reduced {total_pages} pages, calling LLM", artifact=args.out,
               module_id="coarse_segment_v1")
    
    # Step 2: Load prompt
    prompt = load_prompt(args.prompt)
    
    # Step 3: Call LLM with retry logic
    client = OpenAI()
    retry_model = args.retry_model or args.model
    result = None
    errors = []
    
    for attempt in range(args.max_retries + 1):
        model = retry_model if attempt > 0 else args.model
        try:
            result = call_llm_classify(client, model, pages, prompt)
            is_valid, errors = validate_ranges(result, total_pages)
            
            if is_valid:
                break
            
            if attempt < args.max_retries:
                logger.log("coarse_segment", "running", current=75, total=100,
                          message=f"Validation failed (attempt {attempt + 1}/{args.max_retries + 1}), retrying with {model}",
                          artifact=args.out, module_id="coarse_segment_v1")
        except Exception as e:
            errors = [f"LLM call failed: {str(e)}"]
            if attempt < args.max_retries:
                logger.log("coarse_segment", "running", current=75, total=100,
                          message=f"LLM error (attempt {attempt + 1}/{args.max_retries + 1}), retrying with {model}",
                          artifact=args.out, module_id="coarse_segment_v1")
            else:
                raise
    
    # Step 4: Save result
    if result is None:
        raise ValueError("Failed to get valid result from LLM after retries")
    
    output = {
        "schema_version": "coarse_segments_v1",
        "module_id": "coarse_segment_v1",
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
        logger.log("coarse_segment", "warning", current=100, total=100,
                  message=f"Completed with validation warnings: {', '.join(errors)}", artifact=args.out,
                  module_id="coarse_segment_v1")
        print(f"⚠️  Coarse segmentation completed with warnings: {', '.join(errors)}")
    else:
        logger.log("coarse_segment", "done", current=100, total=100,
                  message="Coarse segmentation completed successfully", artifact=args.out,
                  module_id="coarse_segment_v1")
    
    print(f"✅ Coarse segmentation → {args.out}")
    print(f"   Frontmatter: {output['frontmatter_pages']}")
    print(f"   Gameplay: {output['gameplay_pages']}")
    print(f"   Endmatter: {output['endmatter_pages']}")


if __name__ == "__main__":
    main()

