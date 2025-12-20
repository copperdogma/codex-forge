#!/usr/bin/env python3
"""
Fine segmenter for frontmatter: Divides frontmatter section into logical portions.

Takes elements_core.jsonl and coarse_segments.json, filters to frontmatter pages,
then uses LLM to identify logical portions (title, copyright, TOC, rules, etc.).
"""

import argparse
import json
import os
from typing import List, Dict, Optional

from openai import OpenAI

from modules.common.utils import read_jsonl, save_json, log_llm_usage, ProgressLogger


def filter_frontmatter_elements(elements_path: str, frontmatter_pages: List[int]) -> List[Dict]:
    """Filter elements to only frontmatter pages."""
    elements = list(read_jsonl(elements_path))
    frontmatter_set = set(frontmatter_pages)
    
    filtered = []
    for elem in elements:
        page = elem.get("page") or elem.get("metadata", {}).get("page_number")
        if page in frontmatter_set:
            filtered.append(elem)
    
    return filtered


def _page_num(value: Optional[object]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            digits = "".join(ch for ch in value if ch.isdigit())
            return int(digits) if digits else None
        except Exception:
            return None
    return None


def reduce_elements(elements: List[Dict], max_lines: int = 10, max_len: int = 120) -> List[Dict]:
    """Reduce elements to compact per-page summaries."""
    # Group by page
    pages: Dict[int, List[Dict]] = {}
    for elem in elements:
        page = elem.get("page") or elem.get("metadata", {}).get("page_number")
        if page:
            pages.setdefault(page, []).append(elem)
    
    summaries = []
    for page_num in sorted(pages.keys()):
        page_elems = pages[page_num]
        snippets = []
        for elem in page_elems[:max_lines]:
            text = elem.get("text", "")
            if not text:
                continue
            if len(text) > max_len:
                text = text[:max_len] + "…"
            snippets.append(text)
        
        summaries.append({
            "page": page_num,
            "snippets": snippets,
            "line_count": len(page_elems),
        })
    
    return summaries


def load_prompt(prompt_path: Optional[str] = None) -> str:
    """Load the frontmatter fine segmentation prompt."""
    if prompt_path and os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    
    # Default prompt
    return """You are analyzing the frontmatter section of a Fighting Fantasy gamebook to identify logical portions.

INPUT: A JSON object with a "pages" array. Each page entry contains:
- page: page number (integer)
- snippets: array of short text snippets from that page (up to 10 lines, ~120 chars each)
- line_count: total number of text lines on the page

TASK: Identify logical portions within the frontmatter. Typical portions include:
1. Title page (book title, author, publisher)
2. Copyright page (copyright notice, ISBN, publication info)
3. Table of contents (TOC)
4. Rules/How to play (gameplay instructions)
5. Equipment/Items (lists of equipment, weapons, etc.)
6. Adventure sheet (character sheet template)
7. Other frontmatter (dedications, acknowledgements, etc.)

OUTPUT JSON (exactly this format):
{
  "portions": [
    {
      "portion_id": "frontmatter_title",
      "name": "Title Page",
      "page_range": [start_page, end_page],
      "description": "Brief description of this portion"
    },
    {
      "portion_id": "frontmatter_copyright",
      "name": "Copyright",
      "page_range": [start_page, end_page],
      "description": "Copyright notice and publication info"
    },
    ...
  ],
  "notes": "Brief rationale for the segmentation"
}

RULES:
- Each portion must have a contiguous page range
- Portions should not overlap
- Use descriptive portion_id (e.g., "frontmatter_title", "frontmatter_toc", "frontmatter_rules")
- If a portion spans multiple pages, use [start, end]. If single page, use [page, page]
- All frontmatter pages must be covered (no gaps)
"""


def call_llm_segment(client: OpenAI, model: str, pages: List[Dict], prompt: str) -> Dict:
    """Call LLM to segment frontmatter into portions."""
    user_content = prompt + "\n\n" + json.dumps({"pages": pages}, indent=1)
    
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a book structure analyzer. Return only valid JSON."},
            {"role": "user", "content": user_content}
        ],
        response_format={"type": "json_object"},
    )
    
    response_text = completion.choices[0].message.content
    usage = getattr(completion, "usage", None)
    if usage is not None:
        pt = getattr(usage, "prompt_tokens", None)
        ct = getattr(usage, "completion_tokens", None)
        if pt is not None and ct is not None:
            log_llm_usage(model=model, prompt_tokens=pt, completion_tokens=ct,
                          stage_id="fine_segment_frontmatter_v1")
    
    try:
        result = json.loads(response_text)
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nResponse: {response_text[:500]}")


def validate_portions(result: Dict, frontmatter_pages: List[int]) -> tuple[bool, List[str]]:
    """Validate the LLM's output portions."""
    errors = []
    
    if "portions" not in result:
        errors.append("Missing 'portions' field in LLM response")
        return False, errors
    
    portions = result.get("portions", [])
    if not portions:
        errors.append("No portions returned")
        return False, errors
    
    frontmatter_set = set(frontmatter_pages)
    covered_pages = set()
    
    for i, portion in enumerate(portions):
        if "portion_id" not in portion:
            errors.append(f"Portion {i} missing 'portion_id'")
        if "page_range" not in portion:
            errors.append(f"Portion {i} missing 'page_range'")
            continue
        
        page_range = portion["page_range"]
        if not isinstance(page_range, list) or len(page_range) != 2:
            errors.append(f"Portion {i} has invalid page_range (expected [start, end])")
            continue
        
        start, end = page_range
        if start > end:
            errors.append(f"Portion {i} has invalid range: start ({start}) > end ({end})")
            continue
        
        # Check all pages in range are in frontmatter
        for page in range(start, end + 1):
            if page not in frontmatter_set:
                errors.append(f"Portion {i} includes page {page} which is not in frontmatter range")
            covered_pages.add(page)
    
    # Check coverage (allow page 1 to be missing if it's a cover/blank)
    missing = frontmatter_set - covered_pages
    if missing:
        # Page 1 is often a cover/blank page - warn but don't fail
        if missing == {1}:
            errors.append(f"Page 1 not covered (likely cover/blank page - acceptable)")
        else:
            errors.append(f"Pages not covered by any portion: {sorted(missing)}")
    
    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Fine segmenter for frontmatter: divides frontmatter into logical portions")
    parser.add_argument("--elements", help="elements_core.jsonl path")
    parser.add_argument("--pages", help="Alias for --elements (driver compatibility)")
    parser.add_argument("--coarse-segments", required=True, help="coarse_segments.json path")
    parser.add_argument("--out", required=True, help="Output JSON with frontmatter portions")
    parser.add_argument("--model", default="gpt-4.1-mini", help="LLM model to use")
    parser.add_argument("--max-lines", "--max_lines", type=int, default=10, dest="max_lines", help="Max lines per page in summary")
    parser.add_argument("--max-len", "--max_len", type=int, default=120, dest="max_len", help="Max length per line in summary")
    parser.add_argument("--prompt", help="Path to custom prompt file (optional)")
    parser.add_argument("--retry-model", "--retry_model", help="Model to use for retry if validation fails", dest="retry_model")
    parser.add_argument("--max-retries", "--max_retries", type=int, default=2, dest="max_retries", help="Max retries on validation failure")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    
    # Handle driver input aliases
    elements_path = args.pages or args.elements
    if not elements_path:
        parser.error("Missing --elements (or --pages) input")
    
    # Resolve to absolute path if relative
    if not os.path.isabs(elements_path):
        if os.path.exists(elements_path):
            elements_path = os.path.abspath(elements_path)
        else:
            cwd_path = os.path.join(os.getcwd(), elements_path)
            if os.path.exists(cwd_path):
                elements_path = os.path.abspath(cwd_path)
            else:
                raise SystemExit(f"Could not find elements file: {elements_path}")
    
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    # Load coarse segments
    logger.log("fine_segment_frontmatter", "running", current=0, total=100,
               message="Loading coarse segments", artifact=args.out,
               module_id="fine_segment_frontmatter_v1")
    
    with open(args.coarse_segments, "r", encoding="utf-8") as f:
        coarse = json.load(f)
    
    fm_range = coarse.get("frontmatter_pages") or []
    if not isinstance(fm_range, list) or len(fm_range) < 2:
        raise SystemExit("coarse_segments.frontmatter_pages missing or invalid")
    fm_start = _page_num(fm_range[0])
    fm_end = _page_num(fm_range[1])
    if fm_start is None or fm_end is None:
        raise SystemExit(f"Invalid frontmatter_pages values: {fm_range}")
    if fm_start > fm_end:
        fm_start, fm_end = fm_end, fm_start
    frontmatter_pages = list(range(fm_start, fm_end + 1))
    
    # Filter and reduce elements
    logger.log("fine_segment_frontmatter", "running", current=25, total=100,
               message=f"Filtering {len(frontmatter_pages)} frontmatter pages", artifact=args.out,
               module_id="fine_segment_frontmatter_v1")
    
    elements = filter_frontmatter_elements(elements_path, frontmatter_pages)
    pages = reduce_elements(elements, args.max_lines, args.max_len)
    
    logger.log("fine_segment_frontmatter", "running", current=50, total=100,
               message=f"Reduced to {len(pages)} page summaries, calling LLM", artifact=args.out,
               module_id="fine_segment_frontmatter_v1")
    
    # Load prompt
    prompt = load_prompt(args.prompt)
    
    # Call LLM with retry logic
    client = OpenAI()
    retry_model = args.retry_model or args.model
    result = None
    errors = []
    
    for attempt in range(args.max_retries + 1):
        model = retry_model if attempt > 0 else args.model
        try:
            result = call_llm_segment(client, model, pages, prompt)
            is_valid, errors = validate_portions(result, frontmatter_pages)
            
            if is_valid:
                break
            
            if attempt < args.max_retries:
                logger.log("fine_segment_frontmatter", "running", current=75, total=100,
                          message=f"Validation failed (attempt {attempt + 1}/{args.max_retries + 1}), retrying with {model}",
                          artifact=args.out, module_id="fine_segment_frontmatter_v1")
        except Exception as e:
            errors = [f"LLM call failed: {str(e)}"]
            if attempt < args.max_retries:
                logger.log("fine_segment_frontmatter", "running", current=75, total=100,
                          message=f"LLM error (attempt {attempt + 1}/{args.max_retries + 1}), retrying with {model}",
                          artifact=args.out, module_id="fine_segment_frontmatter_v1")
            else:
                raise
    
    if not result:
        raise ValueError("Failed to get valid result from LLM after retries")
    
    # Save result
    output = {
        "schema_version": "fine_segments_frontmatter_v1",
        "module_id": "fine_segment_frontmatter_v1",
        "run_id": args.run_id,
        "frontmatter_pages": frontmatter_pages,
        "portions": result.get("portions", []),
        "notes": result.get("notes", ""),
        "validation_errors": errors if errors else None,
    }
    
    save_json(args.out, output)
    
    if errors:
        logger.log("fine_segment_frontmatter", "done", current=100, total=100,
                  message=f"Completed with validation warnings: {', '.join(errors)}", artifact=args.out,
                  module_id="fine_segment_frontmatter_v1")
        print(f"⚠️  Frontmatter fine segmentation completed with warnings: {', '.join(errors)}")
    else:
        logger.log("fine_segment_frontmatter", "done", current=100, total=100,
                  message="Frontmatter fine segmentation completed successfully", artifact=args.out,
                  module_id="fine_segment_frontmatter_v1")
    
    print(f"✅ Frontmatter fine segmentation → {args.out}")
    print(f"   Found {len(output['portions'])} portions:")
    for portion in output['portions']:
        page_range = portion.get('page_range', [])
        print(f"     • {portion.get('name', 'N/A')}: pages {page_range[0]}-{page_range[1]}")


if __name__ == "__main__":
    main()
