#!/usr/bin/env python3
"""
Header Classification Module v1

Classifies elements_core.jsonl to identify candidate section headers (macro + game sections)
using batched AI calls. Performs forward/backward passes for redundancy and aggregates results.
"""

import argparse
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple

from openai import OpenAI

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger, log_llm_usage
from schemas import ElementCore, HeaderCandidate

# CYOA Document Profile
CYOA_PROFILE = {
    "doc_type": "cyoa_gamebook",
    "expected_macro_sections": [
        "cover",
        "title_page",
        "publishing_info",
        "toc",
        "character_sheet",
        "rules",
        "introduction",
        "game_sections"
    ],
    "game_section_hint": {
        "numeric_range": [1, 400],
        "typical_layout": [
            "centered number alone on a line, followed by text",
            "image, then centered number alone on a line, followed by text"
        ]
    }
}

# Helper function to detect numeric-only lines (safety net for high recall)
def is_numeric_only_line(text: str, min_val: int = 1, max_val: int = 400) -> Optional[int]:
    """
    Detect if text is a numeric-only line (just digits 1-400).
    Returns the number if it matches, None otherwise.
    
    This is a code-based detection for high recall - we don't want to miss
    numeric lines just because the AI didn't notice them.
    """
    if not text:
        return None
    
    # Strip whitespace - numeric headers are usually just "1", "42", "225"
    stripped = text.strip()
    
    # Match: just digits (1-3 digits for 1-400)
    match = re.match(r'^(\d{1,3})$', stripped)
    if match:
        num = int(match.group(1))
        if min_val <= num <= max_val:
            return num
    
    return None


def sanitize_section_number(value: Any) -> Optional[int]:
    """
    Sanitize claimed_section_number to ensure it's a valid integer 1-400.
    
    Handles:
    - Integer values
    - String integers ("1", "42")
    - Invalid formats (ranges "86-88", non-numeric) → None
    """
    if value is None:
        return None
    
    # If already an integer
    if isinstance(value, int):
        if 1 <= value <= 400:
            return value
        return None
    
    # If string, try to parse
    if isinstance(value, str):
        # Try to extract first number from string (handles "86-88" → 86)
        match = re.match(r'^(\d{1,3})', value.strip())
        if match:
            num = int(match.group(1))
            if 1 <= num <= 400:
                return num
    
    return None


def boost_numeric_candidates(batch_elements: List[Dict[str, Any]], 
                             ai_results: List[Dict[str, Any]],
                             all_elements: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Post-process AI results to boost numeric-only lines as candidates (safety net).
    
    For any element that is a numeric-only line 1-400 and AI didn't mark it as a candidate,
    we boost it to candidate status with moderate confidence (0.7).
    
    This ensures high recall: we don't miss numeric headers just because AI was conservative.
    
    Args:
        batch_elements: Elements in the current batch
        ai_results: AI classification results for the batch
        all_elements: Optional full element list for context checking (for rules detection)
    """
    # Create lookup of AI results by seq
    ai_by_seq = {r.get("seq"): r.copy() for r in ai_results if "seq" in r}
    
    # Create lookup of all elements by seq for context checking
    elements_by_seq = {}
    if all_elements:
        elements_by_seq = {e.get("seq"): e for e in all_elements}
    else:
        # Fallback: use batch elements only
        elements_by_seq = {e.get("seq"): e for e in batch_elements}
    
    boosted = []
    for elem in batch_elements:
        seq = elem.get("seq")
        text = elem.get("text", "")
        
        # Check if this is a numeric-only line
        numeric_val = is_numeric_only_line(text)
        
        if numeric_val and seq in ai_by_seq:
            ai_result = ai_by_seq[seq]
            
            # If AI didn't mark it as a game section header candidate, boost it
            if not ai_result.get("game_section_header", False):
                # Check if it's clearly in rules (previous element mentions dice, combat, etc.)
                prev_text = ""
                if seq > 0 and (seq - 1) in elements_by_seq:
                    prev_elem = elements_by_seq[seq - 1]
                    prev_text = prev_elem.get("text", "").lower()
                
                rules_keywords = ["dice", "roll", "skill", "stamina", "luck", "combat", "battle", 
                                 "equipment", "adventure sheet", "provisions"]
                is_likely_rules = any(keyword in prev_text for keyword in rules_keywords)
                
                if not is_likely_rules:
                    # Boost to candidate
                    ai_result["game_section_header"] = True
                    ai_result["claimed_section_number"] = numeric_val
                    # Set confidence to moderate (0.7) if AI had very low confidence
                    if ai_result.get("confidence", 0.0) < 0.5:
                        ai_result["confidence"] = 0.7
                    boosted.append(seq)
                    ai_by_seq[seq] = ai_result
    
    if boosted:
        print(f"  🔍 Boosted {len(boosted)} numeric-only lines to candidates (safety net for high recall)", flush=True)
    
    return list(ai_by_seq.values())


SYSTEM_PROMPT = """You are identifying headers in a Fighting Fantasy gamebook. These books have a standard structure:

1. Front matter: Cover, title page, table of contents, publishing info
2. Rules section: Instructions on how to play, combat, equipment, etc.
3. Introduction: Transition text like "YOU ARE THE HERO" or "YOUR ADVENTURE BEGINS"
4. Gameplay sections: Numbered sections (typically 1-400) that contain the actual adventure

Your task: For each element, identify if it's a header and what type:
- Macro headers: Cover, title page, rules section titles, introduction text
- Game section headers: Standalone numbers (1, 42, 225, etc.) that mark the start of gameplay sections
- Non-headers: Regular narrative text, dialogue, body content

IMPORTANT: This is candidate detection - mark anything that could be a header. A later stage will refine this. Better to include uncertain cases than to miss real headers.

For game sections: Look for standalone numbers (just "1", "42", ":10", etc.) that appear before gameplay narrative. These are section headers. Numbers in rules instructions or lists are NOT section headers."""


def create_batch_prompt(elements: List[Dict[str, Any]], cyoa_profile: Dict) -> str:
    """Create user prompt for a batch of elements."""
    # Compact profile - just the essentials
    macro_sections = ", ".join(cyoa_profile["expected_macro_sections"][:-1])  # Skip "game_sections"
    section_range = f"{cyoa_profile['game_section_hint']['numeric_range'][0]}-{cyoa_profile['game_section_hint']['numeric_range'][1]}"
    
    # Compact JSON for elements (no indentation)
    elements_json = json.dumps(elements, separators=(',', ':'))
    
    num_elements = len(elements)
    prompt = f"""Analyze {num_elements} elements from a Fighting Fantasy gamebook and identify headers.

Document structure: Front matter (cover, title, TOC) → Rules section → Introduction → Numbered gameplay sections (1-{section_range.split('-')[1]})

For each element, classify:
- macro_header: "cover", "title_page", "toc", "rules", "introduction", or "none"
- game_section_header: true if this is a numbered gameplay section header (standalone number like "1", "42", ":10")
- claimed_section_number: the section number if it's a game section header, null otherwise
- confidence: how confident you are (0.0-1.0)

Return JSON with "elements" array containing exactly {num_elements} objects:

{{
  "elements": [
    {{"seq": 0, "macro_header": "cover", "game_section_header": false, "claimed_section_number": null, "confidence": 0.9}},
    {{"seq": 133, "macro_header": "none", "game_section_header": true, "claimed_section_number": 1, "confidence": 0.9}},
    {{"seq": 180, "macro_header": "none", "game_section_header": true, "claimed_section_number": 2, "confidence": 0.85}}
  ]
}}

Key points:
- Standalone numbers (1-{section_range.split('-')[1]}) in the gameplay portion are section headers
- Numbers in rules instructions are NOT section headers
- Use context to distinguish rules from gameplay
- Mark uncertain cases as candidates - better to include than miss

Elements ({num_elements} total):
{elements_json}"""
    
    return prompt


def call_classify_llm(client: OpenAI, model: str, elements: List[Dict[str, Any]], 
                      cyoa_profile: Dict, max_tokens: int) -> List[Dict[str, Any]]:
    """Call AI to classify a batch of elements."""
    prompt = create_batch_prompt(elements, cyoa_profile)
    
    # Calculate reasonable max_tokens: ~50 tokens per element for JSON response
    # Use the provided max_tokens as an upper bound, but calculate a reasonable lower bound
    num_elements = len(elements)
    calculated_max = min(max_tokens, max(200, num_elements * 50 + 100))  # At least 200, or 50 per element + buffer
    
    try:
        kwargs = dict(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
        )
        # gpt-5 requires max_completion_tokens and does not allow temperature=0
        if model.startswith("gpt-5"):
            kwargs["max_completion_tokens"] = calculated_max
            kwargs["temperature"] = 1
        else:
            kwargs["max_tokens"] = calculated_max
            kwargs["temperature"] = 0.0

        completion = client.chat.completions.create(**kwargs)
        
        # Log usage
        usage = getattr(completion, "usage", None)
        pt = getattr(usage, "prompt_tokens", 0) if usage else 0
        ct = getattr(usage, "completion_tokens", 0) if usage else 0
        log_llm_usage(
            model=model,
            prompt_tokens=pt,
            completion_tokens=ct,
            request_ms=None,
        )
        
        # Parse response
        response_text = completion.choices[0].message.content
        payload = json.loads(response_text)
        
        # Extract elements array
        if isinstance(payload, dict) and "elements" in payload:
            return payload["elements"]
        else:
            return []
            
    except Exception as e:
        print(f"Error calling LLM for batch: {e}")
        # Return empty classifications for this batch
        return [
            {
                "seq": elem["seq"],
                "macro_header": "none",
                "game_section_header": False,
                "claimed_section_number": None,
                "confidence": 0.0
            }
            for elem in elements
        ]


def batch_elements(elements: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
    """Split elements into batches of specified size."""
    batches = []
    for i in range(0, len(elements), batch_size):
        batch = elements[i:i + batch_size]
        batches.append(batch)
    return batches


def aggregate_results(results_forward: List[Dict], results_backward: List[Dict]) -> Dict[int, Dict]:
    """
    Aggregate forward and backward pass results by seq number.
    
    Uses majority vote for categorical labels, average for confidence.
    """
    aggregated = {}
    
    # Combine results from both passes
    all_results_by_seq = defaultdict(list)
    for result in results_forward + results_backward:
        seq = result.get("seq")
        if seq is not None:
            all_results_by_seq[seq].append(result)
    
    # Aggregate each seq
    for seq, results in all_results_by_seq.items():
        if not results:
            continue
        
        # Majority vote for macro_header
        macro_headers = [r.get("macro_header", "none") for r in results]
        macro_header_counts = defaultdict(int)
        for h in macro_headers:
            macro_header_counts[h] += 1
        macro_header = max(macro_header_counts.items(), key=lambda x: x[1])[0]
        
        # Majority vote for game_section_header
        game_section_flags = [r.get("game_section_header", False) for r in results]
        game_section_header = sum(game_section_flags) > len(game_section_flags) / 2
        
        # Average confidence
        confidences = [r.get("confidence", 0.0) for r in results if isinstance(r.get("confidence"), (int, float))]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # For claimed_section_number, use the value from results where game_section_header is true
        claimed_section_number = None
        if game_section_header:
            # Get section numbers from results where game_section_header is true
            section_numbers = [r.get("claimed_section_number") for r in results 
                             if r.get("game_section_header") and r.get("claimed_section_number") is not None]
            if section_numbers:
                # Use most common section number
                section_number_counts = defaultdict(int)
                for sn in section_numbers:
                    section_number_counts[sn] += 1
                claimed_section_number = max(section_number_counts.items(), key=lambda x: x[1])[0]
        
        aggregated[seq] = {
            "seq": seq,
            "macro_header": macro_header,
            "game_section_header": game_section_header,
            "claimed_section_number": claimed_section_number,
            "confidence": round(avg_confidence, 3),
        }
    
    return aggregated


def main():
    parser = argparse.ArgumentParser(
        description="Classify element-level headers using batched AI calls"
    )
    parser.add_argument("--pages", required=True,
                       help="Input elements_core.jsonl path (uses --pages for driver compatibility)")
    parser.add_argument("--out", required=True,
                       help="Output header_candidates.jsonl path")
    parser.add_argument("--model", default="gpt-4.1-nano",
                       help="OpenAI model to use (gpt-4.1-nano is fastest and cheapest for this task)")
    parser.add_argument("--batch_size", type=int, default=75,
                       help="Number of elements per batch (50-100 recommended). Smaller sizes create too many API calls and are very slow.")
    parser.add_argument("--max_tokens", type=int, default=4000,
                       help="Max tokens for AI response")
    parser.add_argument("--redundancy", default="forward_backward",
                       choices=["none", "forward_backward", "multiple_calls"],
                       help="Redundancy strategy")
    parser.add_argument("--skip-ai", "--skip_ai", action="store_true", dest="skip_ai",
                       help="Skip AI calls and copy stub output instead")
    parser.add_argument("--stub",
                       help="Stub header_candidates.jsonl to use when --skip-ai is set")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id,
    )
    
    ensure_dir(os.path.dirname(args.out) or ".")

    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for classify_headers_v1")
        stub_rows = list(read_jsonl(args.stub))
        save_jsonl(args.out, stub_rows)
        print(f"[skip-ai] classify_headers_v1 copied stubs → {args.out}")
        logger.log("portionize", "done", current=len(stub_rows), total=len(stub_rows),
                   message="Loaded header_candidates stubs", artifact=args.out, module_id="classify_headers_v1")
        return
    
    # Read input elements
    logger.log(
        "portionize",
        "running",
        current=0,
        total=None,
        message="Loading elements_core.jsonl",
        module_id="classify_headers_v1",
    )
    
    elements = []
    for elem_dict in read_jsonl(args.pages):
        # Validate ElementCore schema (but we'll work with dict for flexibility)
        elem = ElementCore(**elem_dict)
        elements.append(elem_dict)
    
    total_elements = len(elements)
    
    # Initialize OpenAI client with timeout
    client = OpenAI(timeout=60.0)  # 60 second timeout per request
    
    # Batch elements
    batches = batch_elements(elements, args.batch_size)
    total_batches = len(batches)

    logger.log(
        "portionize",
        "running",
        current=0,
        total=total_elements,
        message=f"Loaded {total_elements} elements, starting classification",
        module_id="classify_headers_v1",
        extra={"action": "start", "phase": "forward", "total_batches": total_batches},
    )
    
    print(f"Processing {total_elements} elements in {total_batches} batches of ~{args.batch_size}")
    print(f"Estimated time: ~{total_batches * 6} seconds for forward pass", flush=True)
    
    # Forward pass
    forward_results = []
    for batch_idx, batch in enumerate(batches):
        print(f"\n[Forward] Batch {batch_idx + 1}/{total_batches} ({len(batch)} elements)...", flush=True)
        logger.log(
            "portionize",
            "running",
            current=batch_idx * args.batch_size,
            total=total_elements,
            message=f"Forward pass: batch {batch_idx + 1}/{total_batches}",
            module_id="classify_headers_v1",
            extra={
                "action": "start",
                "phase": "forward",
                "batch": batch_idx + 1,
                "total_batches": total_batches,
                "batch_size": len(batch),
            },
        )
        
        import time
        start_time = time.time()
        batch_results = call_classify_llm(
            client, args.model, batch, CYOA_PROFILE, args.max_tokens
        )
        
        # Post-process: boost numeric-only lines as candidates (safety net for high recall)
        # Pass all elements for context checking (to detect rules sections)
        batch_results = boost_numeric_candidates(batch, batch_results, all_elements=elements)
        
        elapsed = time.time() - start_time
        forward_results.extend(batch_results)
        
        print(f"  ✓ Batch {batch_idx + 1}/{total_batches}: classified {len(batch_results)} elements in {elapsed:.1f}s", flush=True)
        logger.log(
            "portionize",
            "running",
            current=(batch_idx + 1) * args.batch_size,
            total=total_elements,
            message=f"Forward batch {batch_idx + 1}/{total_batches} done",
            module_id="classify_headers_v1",
            extra={
                "action": "finish",
                "phase": "forward",
                "batch": batch_idx + 1,
                "total_batches": total_batches,
                "batch_size": len(batch),
                "output_count": len(batch_results),
                "duration_ms": int(elapsed * 1000),
            },
        )
    
    # Backward pass (if redundancy enabled)
    backward_results = []
    if args.redundancy in ["forward_backward", "multiple_calls"]:
        print(f"Running backward pass for redundancy...")
        # Reverse batches and elements within each batch
        reversed_batches = [list(reversed(batch)) for batch in reversed(batches)]
        
        for batch_idx, batch in enumerate(reversed_batches):
            logger.log(
                "portionize",
                "running",
                current=total_elements,
                total=total_elements,
                message=f"Backward pass: batch {batch_idx + 1}/{total_batches}",
                module_id="classify_headers_v1",
                extra={
                    "action": "start",
                    "phase": "backward",
                    "batch": batch_idx + 1,
                    "total_batches": total_batches,
                    "batch_size": len(batch),
                },
            )
            
            import time
            start_time = time.time()
            batch_results = call_classify_llm(
                client, args.model, batch, CYOA_PROFILE, args.max_tokens
            )
            
            # Post-process: boost numeric-only lines as candidates (safety net for high recall)
            # Pass all elements for context checking (to detect rules sections)
            batch_results = boost_numeric_candidates(batch, batch_results, all_elements=elements)
            
            # Reverse results back to original order
            batch_results_reversed = list(reversed(batch_results))
            backward_results.extend(batch_results_reversed)
            elapsed = time.time() - start_time
            print(f"  Backward batch {batch_idx + 1}/{total_batches}: classified {len(batch_results)} elements")
            logger.log(
                "portionize",
                "running",
                current=total_elements,
                total=total_elements,
                message=f"Backward batch {batch_idx + 1}/{total_batches} done",
                module_id="classify_headers_v1",
                extra={
                    "action": "finish",
                    "phase": "backward",
                    "batch": batch_idx + 1,
                    "total_batches": total_batches,
                    "batch_size": len(batch),
                    "output_count": len(batch_results),
                    "duration_ms": int(elapsed * 1000),
                },
            )
    else:
        # No redundancy - use forward results as-is
        backward_results = forward_results
    
    # Aggregate results
    logger.log(
        "portionize",
        "running",
        current=total_elements,
        total=total_elements,
        message="Aggregating forward/backward results",
        module_id="classify_headers_v1",
    )
    
    aggregated = aggregate_results(forward_results, backward_results)
    
    # Create header candidates for all elements (including negatives)
    header_candidates = []
    for elem in elements:
        seq = elem["seq"]
        page = elem["page"]
        
        if seq in aggregated:
            result = aggregated[seq]
            # Sanitize claimed_section_number before creating HeaderCandidate
            claimed_section_number = sanitize_section_number(result.get("claimed_section_number"))
            
            # Don't include text in AI output - will merge separately
            candidate = HeaderCandidate(
                seq=seq,
                page=page,
                macro_header=result["macro_header"],
                game_section_header=result["game_section_header"],
                claimed_section_number=claimed_section_number,
                confidence=result["confidence"],
            )
        else:
            # Default classification (shouldn't happen, but be safe)
            candidate = HeaderCandidate(
                seq=seq,
                page=page,
                macro_header="none",
                game_section_header=False,
                claimed_section_number=None,
                confidence=0.0,
            )
        
        header_candidates.append(candidate.model_dump(exclude_none=True))
    
    # Post-process: Merge with elements to add text for verification
    # Create lookup of elements by seq
    elements_by_seq = {elem["seq"]: elem for elem in elements}
    
    # Enrich candidates with text from elements_core (after AI returns, merge text)
    enriched_candidates = []
    for candidate in header_candidates:
        enriched = candidate.copy()  # Don't mutate original
        seq = candidate["seq"]
        if seq in elements_by_seq:
            enriched["text"] = elements_by_seq[seq].get("text", "")
        enriched_candidates.append(enriched)
    
    # Write enriched output (AI results + merged text)
    save_jsonl(args.out, enriched_candidates)
    
    # Count positives
    game_section_count = sum(1 for c in enriched_candidates if c.get("game_section_header"))
    macro_header_count = sum(1 for c in enriched_candidates if c.get("macro_header") != "none")
    
    logger.log(
        "portionize",
        "done",
        current=total_elements,
        total=total_elements,
        message=f"Classified {total_elements} elements: {game_section_count} game sections, {macro_header_count} macro headers",
        module_id="classify_headers_v1",
        artifact=args.out,
    )
    
    print(f"Classified {total_elements} elements → {args.out}")
    print(f"  Game section headers: {game_section_count}")
    print(f"  Macro headers: {macro_header_count}")


if __name__ == "__main__":
    main()
