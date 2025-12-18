import argparse
import json
import os
from typing import List, Dict

from openai import OpenAI

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger, log_llm_usage
from schemas import SectionBoundary

SYSTEM_PROMPT = """You are analyzing a Fighting Fantasy gamebook to identify gameplay section boundaries.

Fighting Fantasy books contain:
- Numbered gameplay sections (typically 1-400)
- Each section starts with a bold number: "1", "42", "225", etc.
- Sections contain narrative text, choices like "Turn to 42", combat, luck tests, items
- NOT every number is a section (e.g., page numbers, dice rolls, stats, dates)

Context clues for REAL sections:
- Section numbers appear at the start of a paragraph or standalone
- They are often bold or emphasized in the text
- They are followed by narrative text describing a situation
- They may contain choices like "If you want to turn left, turn to 42"
- They appear in roughly sequential order (though PDF layout may shuffle)
- They are typically in the range 1-400
- **Elements tagged with Content:Section-header are strong candidates (especially if Num matches the section number)**

Context clues for FALSE positives (NOT sections):
- Page numbers (usually small, in headers/footers)
- **Elements tagged with Content:Page-header or Content:Page-footer should be ignored**
- **Elements tagged with Content:List-item are usually NOT section headers**
- Dice roll results ("Roll 2 dice, if you roll 7 or less...")
- Stat values (SKILL 7, STAMINA 12)
- Dates or years in narrative text
- Chapter numbers (usually words like "Chapter 1" not just "1")
- Numbers embedded in sentences without being section anchors

Your task:
1. Scan ALL elements in the document
2. For each element that STARTS a NEW gameplay section, identify:
   - The section number (e.g., "1", "2", "42", "225")
   - The element ID where this section begins
   - Your confidence (0.0-1.0) that this is a real section
   - Brief evidence explaining why this is a section boundary

Important:
- Only report section STARTS, not ends (ends will be inferred)
- Be conservative: when in doubt, prefer high confidence over catching everything
- If you see multiple elements that might be the same section, report only the first occurrence
- Section numbers should be in the range 1-400 for typical Fighting Fantasy books
- **Use Content tags to boost confidence: Section-header increases confidence, Page-header/Page-footer/List-item should be ignored**

Output format:
Return a JSON object with a "boundaries" array containing section boundary objects:
{
  "boundaries": [
    {
      "section_id": "1",
      "start_element_id": "abc123",
      "confidence": 0.95,
      "evidence": "Bold standalone '1' followed by narrative text 'You stand at the entrance...'"
    },
    ...
  ]
}

Return ONLY the JSON, no other text."""


def should_skip_element(elem: Dict) -> bool:
    """
    Pre-filter elements to reduce LLM prompt size and false positives.
    Returns True if element should be skipped.
    """
    content_type = elem.get("content_type")

    # Skip known false positive content types
    if content_type in ["Page-header", "Page-footer", "List-item"]:
        return True

    return False


def format_elements_for_scan(elements: List[Dict]) -> tuple[str, int]:
    """
    Format elements into a compact representation for AI scanning.
    Returns: (formatted_text, skipped_count)
    """
    lines = []
    skipped = 0

    for idx, elem in enumerate(elements):
        # Pre-filter obvious false positives
        if should_skip_element(elem):
            skipped += 1
            continue

        elem_id = elem.get("id", f"unknown_{idx}")
        elem_type = elem.get("type", "Unknown")
        text = elem.get("text", "").strip()
        page = elem.get("metadata", {}).get("page_number") or elem.get("page", "?")

        # Include content_type if available (helps LLM identify headers vs body text)
        content_type = elem.get("content_type")
        content_subtype = elem.get("content_subtype")

        # Truncate very long text to keep prompt size manageable
        if len(text) > 200:
            text = text[:200] + "..."

        # Format: [ID:abc123 | Type:Title | Page:5 | Content:Section-header] Text content here
        parts = [f"ID:{elem_id}", f"Type:{elem_type}", f"Page:{page}"]
        if content_type:
            parts.append(f"Content:{content_type}")
            if content_subtype and isinstance(content_subtype, dict) and "number" in content_subtype:
                parts.append(f"Num:{content_subtype['number']}")

        header = " | ".join(parts)
        lines.append(f"[{header}] {text}")

    return "\n".join(lines), skipped


def call_scan_llm(client: OpenAI, model: str, elements: List[Dict], max_tokens: int, retry_model: str = "gpt-5") -> tuple[List[Dict], int]:
    """
    Call AI to scan elements and identify section boundaries.
    Returns: (boundaries, skipped_count)
    """
    elements_text, skipped_count = format_elements_for_scan(elements)

    user_prompt = f"""Here are all the elements from the document:

{elements_text}

Please identify ALL Fighting Fantasy gameplay section boundaries."""

    def _once(selected_model: str):
        kwargs = dict(
            model=selected_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
        )
        # gpt-5 uses max_completion_tokens and may reject temperature overrides in this endpoint.
        if selected_model.startswith("gpt-5"):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = 0.0

        completion = client.chat.completions.create(**kwargs)

        usage = getattr(completion, "usage", None)
        pt = getattr(usage, "prompt_tokens", 0) if usage else 0
        ct = getattr(usage, "completion_tokens", 0) if usage else 0
        log_llm_usage(model=selected_model, prompt_tokens=pt, completion_tokens=ct, request_ms=None)
        return completion.choices[0].message.content or ""

    response_text = _once(model)
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"[ai_scan] JSON decode failed ({e}); retrying with {retry_model}")
        print(f"[ai_scan] First 300 chars: {response_text[:300]}")
        # Retry with stronger model; if it fails again, fall back to empty list
        try:
            response_text = _once(retry_model)
            payload = json.loads(response_text)
        except Exception as e2:
            print(f"[ai_scan] Retry failed: {e2}. Proceeding with empty boundaries.")
            return [], skipped_count

    # Extract boundaries array
    boundaries = []
    if isinstance(payload, dict) and "boundaries" in payload:
        boundaries = payload["boundaries"]
    elif isinstance(payload, list):
        boundaries = payload

    return boundaries, skipped_count


def main():
    parser = argparse.ArgumentParser(description="AI-powered section boundary detection for Fighting Fantasy books.")
    parser.add_argument("--pages", required=True, help="Path to elements.jsonl (uses --pages for driver compatibility)")
    parser.add_argument("--out", required=True, help="Path to section_boundaries.jsonl")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model to use")
    parser.add_argument("--max_tokens", type=int, default=2000, help="Max tokens (or max_completion_tokens) for AI response")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--retry-model", dest="retry_model", default="gpt-5",
                        help="Model to retry with if JSON parsing fails")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    # Read all elements
    logger.log("portionize", "running", current=0, total=1,
               message="Loading elements", artifact=args.out, module_id="portionize_ai_scan_v1")

    elements = list(read_jsonl(args.pages))
    if not elements:
        raise SystemExit("No elements found in input file")

    logger.log("portionize", "running", current=0, total=1,
               message=f"Scanning {len(elements)} elements with AI",
               artifact=args.out, module_id="portionize_ai_scan_v1")

    # Call AI to scan for boundaries
    client = OpenAI()
    boundaries_data, skipped_by_content_type = call_scan_llm(client, args.model, elements, args.max_tokens, retry_model=args.retry_model)

    if skipped_by_content_type > 0:
        logger.log("portionize", "running", current=0, total=1,
                   message=f"Skipped {skipped_by_content_type} elements by content_type filtering",
                   artifact=args.out, module_id="portionize_ai_scan_v1")

    # Convert to SectionBoundary schema
    boundaries = []
    for b in boundaries_data:
        boundary = SectionBoundary(
            section_id=str(b.get("section_id")),
            start_element_id=b.get("start_element_id"),
            end_element_id=None,  # Will be inferred later
            confidence=b.get("confidence", 0.0),
            evidence=b.get("evidence"),
            module_id="portionize_ai_scan_v1",
            run_id=args.run_id,
        )
        boundaries.append(boundary.dict(by_alias=True))

    # Save boundaries
    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, boundaries)

    logger.log("portionize", "done", current=1, total=1,
               message=f"Found {len(boundaries)} section boundaries",
               artifact=args.out, module_id="portionize_ai_scan_v1",
               schema_version="section_boundary_v1")

    print(f"Found {len(boundaries)} section boundaries → {args.out}")
    if skipped_by_content_type > 0:
        print(f"[ai_scan] skipped {skipped_by_content_type} elements by content_type filtering")


if __name__ == "__main__":
    main()
