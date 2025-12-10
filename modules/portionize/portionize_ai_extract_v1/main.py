import argparse
import json
import os
from typing import List, Dict, Optional
from collections import defaultdict

from openai import OpenAI
from tqdm import tqdm

from modules.common.utils import read_jsonl, append_jsonl, ensure_dir, ProgressLogger, log_llm_usage, save_jsonl, save_json
from schemas import EnrichedPortion, Choice, Combat, ItemEffect

SYSTEM_PROMPT = """You are analyzing a Fighting Fantasy gamebook section to extract gameplay data.

Your task is to parse the section text and identify:

1. **Choices**: Navigation options that send the player to other sections
   - Look for phrases like "Turn to 42", "Go to 123", "If you want to X, turn to Y"
   - Extract the target section number and the choice text
   - Example: "If you want to open the door, turn to 42" → choice: {target: "42", text: "Open the door"}

2. **Combat**: Enemy encounters with stats
   - Look for enemy stat blocks like "SKILL 7 STAMINA 9"
   - Extract enemy name, SKILL value, STAMINA value
   - Example: "You must fight the ORC SKILL 7 STAMINA 9" → combat: {name: "ORC", skill: 7, stamina: 9}

3. **Luck Tests**: Sections that require testing your luck
   - Look for phrases like "Test your Luck", "you must test your luck"
   - Mark as true if present
   - Example: "You must Test your Luck" → test_luck: true

4. **Item Effects**: Items gained/lost, gold/provisions changes
   - Look for phrases about gaining/losing items, gold, provisions
   - Extract what changed
   - Examples:
     - "Take 3 Gold Pieces" → item_effects: [{delta_gold: 3}]
     - "You find a Magic Sword" → item_effects: [{add_item: "Magic Sword"}]
     - "Lose 2 Provisions" → item_effects: [{delta_provisions: -2}]

Output JSON format:
{
  "choices": [
    {"target": "42", "text": "Open the door"},
    {"target": "123", "text": "Walk away"}
  ],
  "combat": {
    "name": "ORC",
    "skill": 7,
    "stamina": 9
  },
  "test_luck": true,
  "item_effects": [
    {"delta_gold": 3},
    {"add_item": "Magic Sword"}
  ]
}

Important:
- Return ONLY the JSON, no other text
- If no choices found, return empty array: "choices": []
- If no combat, omit "combat" field or set to null
- If no luck test, set "test_luck": false or omit
- If no item effects, return empty array: "item_effects": []
- Be conservative: only extract clear, unambiguous gameplay elements
"""


def extract_text_from_elements(
    elements_by_id: Dict[str, Dict],
    element_sequence: List[str],
    start_element_id: str,
    end_element_id: Optional[str]
) -> tuple:
    """
    Extract text from elements between start_element_id and end_element_id.

    Returns (text, element_ids)
    """
    # Find start and end indices in the sequence
    try:
        start_idx = element_sequence.index(start_element_id)
    except ValueError:
        return "", []

    if end_element_id:
        try:
            end_idx = element_sequence.index(end_element_id)
        except ValueError:
            end_idx = len(element_sequence)
    else:
        end_idx = len(element_sequence)

    # Extract elements in range [start_idx, end_idx)
    section_element_ids = element_sequence[start_idx:end_idx]
    section_elements = [elements_by_id[eid] for eid in section_element_ids if eid in elements_by_id]

    # Filter out headers/footers and extract text
    text_parts = []
    for elem in section_elements:
        if elem.get("type") in ("Header", "Footer", "PageBreak"):
            continue
        text = elem.get("text", "").strip()
        if text:
            text_parts.append(text)

    return "\n\n".join(text_parts), section_element_ids


def extract_with_window(
    elements_by_id: Dict[str, Dict],
    element_sequence: List[str],
    start_element_id: str,
    window: int = 6,
) -> tuple:
    """
    Fallback extractor: grab a fixed window of elements starting at start_element_id.
    Useful when the boundary span is too tight and yields empty text.
    """
    if start_element_id not in element_sequence:
        return "", []
    start_idx = element_sequence.index(start_element_id)
    end_idx = min(len(element_sequence), start_idx + window)
    section_element_ids = element_sequence[start_idx:end_idx]
    text_parts = []
    for eid in section_element_ids:
        elem = elements_by_id.get(eid)
        if not elem:
            continue
        if elem.get("type") in ("Header", "Footer", "PageBreak"):
            continue
        text = (elem.get("text") or "").strip()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts), section_element_ids


def call_extract_llm(client: OpenAI, model: str, section_text: str, max_tokens: int) -> Dict:
    """Call AI to extract gameplay data from section text."""
    user_prompt = f"""Here is the section text:

{section_text}

Please extract all gameplay data (choices, combat, luck tests, item effects)."""

    create_kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
    )
    if model.startswith("gpt-5"):
        create_kwargs["max_completion_tokens"] = max_tokens
    else:
        create_kwargs["max_tokens"] = max_tokens

    completion = client.chat.completions.create(**create_kwargs)

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
    return json.loads(response_text)


def main():
    parser = argparse.ArgumentParser(description="AI-powered section content extraction for Fighting Fantasy books.")
    parser.add_argument("--pages", required=True, help="Path to elements.jsonl (uses --pages for driver compatibility)")
    parser.add_argument("--boundaries", required=True, help="Path to section_boundaries.jsonl")
    parser.add_argument("--out", required=True, help="Path to portions_enriched.jsonl")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model to use")
    parser.add_argument("--max_tokens", type=int, default=2000, help="Max tokens for AI response")
    parser.add_argument("--fallback-window", type=int, default=6,
                        help="Number of elements to include when widening empty spans")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--skip-ai", "--skip_ai", action="store_true", dest="skip_ai",
                        help="Bypass AI extraction and load stub portions")
    parser.add_argument("--stub", help="Stub enriched portions jsonl to use when --skip-ai")
    parser.add_argument("--retry-count", type=int, default=1, dest="retry_count",
                        help="Number of retries on LLM errors per section")
    parser.add_argument("--retry-model", default="gpt-5", dest="retry_model",
                        help="Model to use on retry attempts")
    parser.add_argument("--fail-on-empty", action="store_true", dest="fail_on_empty",
                        help="Fail the stage if any section text remains empty after retries/widening")
    parser.add_argument("--section-filter", help="Comma-separated list of section_ids to process (others skipped)")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    if args.skip_ai:
        if not args.stub:
            raise SystemExit("--skip-ai set but no --stub provided for portionize_ai_extract_v1")
        stub_rows = list(read_jsonl(args.stub))
        ensure_dir(os.path.dirname(args.out) or ".")
        save_jsonl(args.out, stub_rows)
        logger.log("portionize", "done", current=len(stub_rows), total=len(stub_rows),
                   message="Loaded portion stubs", artifact=args.out, module_id="portionize_ai_extract_v1")
        print(f"[skip-ai] portionize_ai_extract_v1 copied stubs → {args.out}")
        return

    # Read elements and build index
    logger.log("portionize", "running", current=0, total=1,
               message="Loading elements", artifact=args.out, module_id="portionize_ai_extract_v1")

    elements = list(read_jsonl(args.pages))
    if not elements:
        raise SystemExit("No elements found in input file")

    # Build element index by ID and preserve sequence
    elements_by_id = {e["id"]: e for e in elements}
    element_sequence = [e["id"] for e in elements]

    # Read section boundaries
    boundaries = list(read_jsonl(args.boundaries))
    if not boundaries:
        raise SystemExit("No section boundaries found in input file")

    # Optional filter
    allowed = None
    if args.section_filter:
        allowed = set([s.strip() for s in args.section_filter.split(",") if s.strip()])

    # Sort boundaries by section_id (numeric)
    boundaries_sorted = sorted(boundaries, key=lambda b: int(b["section_id"]) if b["section_id"].isdigit() else 999999)
    if allowed is not None:
        boundaries_sorted = [b for b in boundaries_sorted if b.get("section_id") in allowed]

    logger.log("portionize", "running", current=0, total=len(boundaries_sorted),
               message=f"Extracting {len(boundaries_sorted)} sections with AI",
               artifact=args.out, module_id="portionize_ai_extract_v1")

    # Prepare output directory
    ensure_dir(os.path.dirname(args.out) or ".")

    # Process each boundary
    client = OpenAI()
    error_traces = []
    for idx, boundary in enumerate(tqdm(boundaries_sorted, desc="Extracting sections"), start=1):
        try:
            section_id = boundary["section_id"]
            start_element_id = boundary["start_element_id"]

            # Find end_element_id (start of next section, or None for last section)
            end_element_id = None
            if idx < len(boundaries_sorted):
                end_element_id = boundaries_sorted[idx]["start_element_id"]

            # Extract text from elements
            raw_text, element_ids = extract_text_from_elements(
                elements_by_id,
                element_sequence,
                start_element_id,
                end_element_id
            )

            gameplay_data = None
            widened = False
            if not raw_text:
                raw_text, element_ids = extract_with_window(
                    elements_by_id,
                    element_sequence,
                    start_element_id,
                    args.fallback_window
                )
                widened = True

            if not raw_text:
                # Unresolved empty text
                gameplay_data = {
                    "choices": [],
                    "combat": None,
                    "test_luck": False,
                    "item_effects": [],
                    "error": "empty_text"
                }
                error_traces.append({
                    "section_id": section_id,
                    "error": "empty_text",
                    "start_element_id": start_element_id,
                    "widened": widened,
                    "run_id": args.run_id,
                    "model_first": args.model,
                    "model_retry": args.retry_model,
                })
            else:
                attempts = args.retry_count + 1
                last_err = None
                for attempt in range(attempts):
                    try:
                        model_used = args.model if attempt == 0 else args.retry_model
                        gameplay_data = call_extract_llm(client, model_used, raw_text, args.max_tokens)
                        break
                    except Exception as e:
                        last_err = e
                if gameplay_data is None:
                    print(f"[warn] section {section_id}: LLM parse failed after retries: {last_err}")
                    error_traces.append({
                        "section_id": section_id,
                        "error": str(last_err),
                        "start_element_id": start_element_id,
                        "run_id": args.run_id,
                        "model_first": args.model,
                        "model_retry": args.retry_model,
                    })
                    gameplay_data = {
                        "choices": [],
                        "combat": None,
                        "test_luck": False,
                        "item_effects": [],
                        "error": str(last_err) if last_err else "unknown_error"
                    }

            # Parse gameplay data into schema objects
            choices = []
            for choice_data in gameplay_data.get("choices", []):
                if isinstance(choice_data, dict) and "target" in choice_data:
                    choices.append(Choice(
                        target=str(choice_data["target"]),
                        text=choice_data.get("text")
                    ))

            combat = None
            combat_data = gameplay_data.get("combat")
            if combat_data and isinstance(combat_data, dict):
                if "skill" in combat_data and "stamina" in combat_data:
                    combat = Combat(
                        skill=int(combat_data["skill"]),
                        stamina=int(combat_data["stamina"]),
                        name=combat_data.get("name")
                    )

            test_luck = bool(gameplay_data.get("test_luck", False))

            item_effects = []
            for effect_data in gameplay_data.get("item_effects", []):
                if isinstance(effect_data, dict):
                    item_effects.append(ItemEffect(**effect_data))

            # Get page range from elements
            section_elements = [elements_by_id[eid] for eid in element_ids if eid in elements_by_id]
            page_numbers = [
                e.get("metadata", {}).get("page_number")
                for e in section_elements
                if e.get("metadata", {}).get("page_number")
            ]
            page_start = min(page_numbers) if page_numbers else 1
            page_end = max(page_numbers) if page_numbers else 1

            # Create EnrichedPortion
            enriched = EnrichedPortion(
                portion_id=section_id,
                section_id=section_id,
                page_start=page_start,
                page_end=page_end,
                title=None,
                type="section",
                confidence=boundary.get("confidence", 0.0),
                source_images=[],
                raw_text=raw_text,
                choices=choices,
                combat=combat,
                test_luck=test_luck,
                item_effects=item_effects,
                targets=[c.target for c in choices],
                element_ids=element_ids,
                module_id="portionize_ai_extract_v1",
                run_id=args.run_id,
            )

            append_jsonl(args.out, enriched.dict(by_alias=True, exclude_none=True))

            logger.log("portionize", "running", current=idx, total=len(boundaries_sorted),
                       message=f"Extracted section {section_id}",
                       artifact=args.out, module_id="portionize_ai_extract_v1")

        except Exception as e:
            # Log error but continue processing
            error_record = {
                "error": str(e),
                "section_id": boundary.get("section_id"),
                "start_element_id": boundary.get("start_element_id")
            }
            append_jsonl(args.out, error_record)
            logger.log("portionize", "running", current=idx, total=len(boundaries_sorted),
                       message=f"Error on section {boundary.get('section_id')}: {e}",
                       artifact=args.out, module_id="portionize_ai_extract_v1")

    logger.log("portionize", "done", current=len(boundaries_sorted), total=len(boundaries_sorted),
               message=f"Extracted {len(boundaries_sorted)} sections",
               artifact=args.out, module_id="portionize_ai_extract_v1",
               schema_version="enriched_portion_v1")

    if error_traces:
        err_path = args.out + ".errors.json"
        save_json(err_path, error_traces)
        print(f"[warn] {len(error_traces)} sections unresolved; trace → {err_path}")
        if args.fail_on_empty:
            raise SystemExit(f"Extraction unresolved for {len(error_traces)} sections (empty or parse errors)")

    print(f"Extracted {len(boundaries_sorted)} sections → {args.out}")


if __name__ == "__main__":
    main()
