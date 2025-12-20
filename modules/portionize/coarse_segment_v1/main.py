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


def summarize_page(
    lines: List[Dict],
    page_number: int,
    original_page_number: Optional[int],
    max_lines: int = 10,
    max_len: int = 120,
) -> Dict:
    """Summarize a page's elements into compact snippets.

    Args:
        page_number: Sequential page identifier used throughout the pipeline
        original_page_number: Source document page index (may be shared by split pages)
    """
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
        "page_number": page_number,
        "original_page_number": original_page_number,
        "snippet_lines": snippets,
        "line_count": len(lines),
        "numeric_lines": numeric_flags,
    }


def reduce_elements(elements_path: str, max_lines: int = 8, max_len: int = 100) -> List[Dict]:
    """Reduce elements.jsonl to compact per-page summaries.

    Optimized for minimal data: only essential snippets, shorter lines, fewer per page.
    Works with full book output (226 pages from spread splitting).

    CRITICAL: Prefer sequential page_number when available. Legacy L/R element IDs
    are supported as a fallback only.
    """
    pages: Dict[int, Dict[str, Optional[int] | List[Dict]]] = {}
    for row in read_jsonl(elements_path):
        # Prefer canonical page_number when available
        page_id = row.get("page_number")
        if page_id is None:
            page_id = row.get("page")
        if page_id is None:
            page_id = row.get("metadata", {}).get("page_number") or row.get("metadata", {}).get("page")
        if page_id is None:
            # Legacy fallback: extract from element id prefix
            elem_id = row.get("id", "")
            if "-" in elem_id:
                page_id = elem_id.split("-")[0]
        if page_id is None:
            continue  # Skip elements with no page

        original_page_number = row.get("original_page_number")
        if original_page_number is None:
            original_page_number = row.get("metadata", {}).get("original_page_number")
        page_entry = pages.setdefault(
            page_id,
            {"rows": [], "original_page_number": original_page_number},
        )
        if page_entry.get("original_page_number") is None and original_page_number is not None:
            page_entry["original_page_number"] = original_page_number
        page_entry["rows"].append(row)

    summaries = []
    # Sort page IDs: numeric pages first (1, 2, ...), then legacy L/R pages if present
    def page_sort_key(page_id):
        if isinstance(page_id, int):
            return (0, page_id, "")
        digits = ""
        suffix = ""
        for ch in str(page_id):
            if ch.isdigit():
                digits += ch
            else:
                suffix = str(page_id)[len(digits):]
                break
        if digits:
            side_order = {"L": 0, "R": 1}
            return (0, int(digits), side_order.get(suffix[:1], 2))
        return (1, str(page_id), "")

    for page_id in sorted(pages.keys(), key=page_sort_key):
        page_entry = pages[page_id]
        summaries.append(
            summarize_page(
                page_entry["rows"],
                page_id,
                page_entry.get("original_page_number"),
                max_lines,
                max_len,
            )
        )
    return summaries


def load_prompt(prompt_path: Optional[str] = None) -> str:
    """Load the coarse segmentation prompt."""
    if prompt_path and os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Default prompt (inline) - optimized for minimal data, full book processing
    return """You are analyzing the structure of a Fighting Fantasy gamebook to identify three macro sections.

INPUT: A JSON object with a "pages" array. Each page entry contains:
- page_number: sequential page identifier (integer 1, 2, 3...)
- original_page_number: source document page index (integer, may repeat when a spread is split)
- snippets: array of short text snippets from that page (up to 8 lines, ~100 chars each)
- line_count: total number of text lines on the page
- numeric: count of standalone numeric lines (potential section headers)

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

Example for a 400-page book:
{
  "frontmatter_pages": [1, 11],
  "gameplay_pages": [12, 402],
  "endmatter_pages": [403, 410],
  "notes": "Frontmatter (pp.1-11) includes title, copyright, rules. Gameplay starts at page 12 with BACKGROUND and ends at page 402 (contains section 400). Endmatter starts at page 403 (ads/previews begin)."
}
"""


def call_llm_classify(client: OpenAI, model: str, pages: List[Dict], prompt: str) -> Dict:
    """Call LLM to classify macro sections."""
    # Optimize payload: only send essential fields, compact format
    optimized_pages = []
    for p in pages:
        optimized_pages.append({
            "page_number": p["page_number"],
            "original_page_number": p.get("original_page_number"),
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
    """Validate the LLM output page ranges.

    Handles both integer page IDs (1, 2, 3...) and string page IDs ("111L", "111R").
    """
    errors = []

    def parse_page_id(page_id):
        """Extract numeric portion from page ID for validation."""
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
        else:
            # For string page IDs, just check format, not numeric range
            start_num = parse_page_id(front[0])
            end_num = parse_page_id(front[1])
            if start_num and start_num < 1:
                errors.append(f"frontmatter_pages start < 1: {front}")

    # Validate gameplay
    gameplay = result.get("gameplay_pages")
    if gameplay is not None:
        if not isinstance(gameplay, list) or len(gameplay) != 2:
            errors.append("gameplay_pages must be [start, end] or null")
        # Light validation - just check format is reasonable

    # Validate endmatter
    end = result.get("endmatter_pages")
    if end is not None:
        if not isinstance(end, list) or len(end) != 2:
            errors.append("endmatter_pages must be [start, end] or null")
    
    # Check for overlaps/gaps
    # NOTE: With string page IDs (e.g., "111L", "111R"), we skip numeric gap/overlap checks
    # The AI is responsible for ensuring contiguity
    ranges = []
    if front:
        ranges.append(("frontmatter", front))
    if gameplay:
        ranges.append(("gameplay", gameplay))
    if end:
        ranges.append(("endmatter", end))

    # Light validation: just check that all page IDs are present (no None values)
    for name, page_range in ranges:
        if page_range[0] is None or page_range[1] is None:
            errors.append(f"{name} has None page boundary: {page_range}")

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
