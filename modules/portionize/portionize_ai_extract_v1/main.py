import argparse
import json
import os
from pathlib import Path
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


def _resolve_images_dir(run_root: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    preferred = os.path.join(run_root, "01_extract_ocr_ensemble_v1", "images")
    if os.path.isdir(preferred):
        return preferred
    try:
        for name in os.listdir(run_root):
            cand = os.path.join(run_root, name, "images")
            if os.path.isdir(cand):
                return cand
    except Exception:
        return None
    return None


def _page_key_from_element(elem: Dict) -> Optional[tuple]:
    """
    Return (original_page_number, spread_side) for image lookup.
    Prefers explicit metadata fields; falls back to legacy element id parsing.
    """
    md = elem.get("metadata") or {}
    orig = md.get("original_page_number") or md.get("page_number") or elem.get("page")
    side = md.get("spread_side")
    if side not in (None, "L", "R"):
        side = None
    if isinstance(orig, int):
        return (orig, side)
    try:
        orig_int = int(orig)
        return (orig_int, side)
    except Exception:
        pass
    eid = elem.get("id") or ""
    if "-" in eid:
        page_part = eid.split("-", 1)[0]
        digits = ""
        suffix = ""
        for ch in page_part:
            if ch.isdigit():
                digits += ch
            else:
                suffix = page_part[len(digits):]
                break
        if digits:
            try:
                orig_int = int(digits)
            except Exception:
                return None
            legacy_side = None
            if suffix.startswith("L") or suffix.startswith("R"):
                legacy_side = suffix[0]
            return (orig_int, legacy_side)
    return None


def _sort_image_keys(keys: List[tuple]) -> List[tuple]:
    side_order = {"L": 0, "R": 1, None: 0}

    def key_fn(k: tuple):
        orig, side = k
        return (int(orig), side_order.get(side, 2))

    return sorted(keys, key=key_fn)


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
    parser.add_argument("--images-dir", "--images_dir", dest="images_dir",
                        help="Optional path to page images directory (defaults to run_root/*/images).")
    parser.add_argument("--escalation-cache-dir", dest="escalation_cache_dir",
                        help="Optional escalation cache dir (page_*.json) to override raw_text by section_id")
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
    parser.add_argument("--span-order", "--span_order", dest="span_order", choices=["numeric", "sequence"], default="numeric",
                        help="How to choose the next boundary for span end: numeric (default) or sequence order")
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

    # Sort boundaries by section_id (numeric) for processing order
    boundaries_sorted = sorted(boundaries, key=lambda b: int(b["section_id"]) if b["section_id"].isdigit() else 999999)

    # Compute end boundaries from the full list (so targeted re-runs still have correct spans)
    next_start_by_sid = {}
    if args.span_order == "sequence":
        # Use document order to define spans (prevents inverted spans when IDs are out of order)
        id_to_index = {eid: idx for idx, eid in enumerate(element_sequence)}
        boundaries_by_seq = sorted(
            [b for b in boundaries if b.get("start_element_id") in id_to_index],
            key=lambda b: id_to_index.get(b.get("start_element_id"), 999999),
        )
        for i, b in enumerate(boundaries_by_seq):
            sid = b.get("section_id")
            if not sid:
                continue
            next_start_by_sid[sid] = boundaries_by_seq[i + 1]["start_element_id"] if i + 1 < len(boundaries_by_seq) else None
    else:
        for i, b in enumerate(boundaries_sorted):
            sid = b.get("section_id")
            if not sid:
                continue
            next_start_by_sid[sid] = boundaries_sorted[i + 1]["start_element_id"] if i + 1 < len(boundaries_sorted) else None

    # Optional filter (process only a subset, but keep spans defined by full neighbor boundaries)
    allowed = None
    if args.section_filter:
        allowed = {s.strip() for s in args.section_filter.split(",") if s.strip()}
    boundaries_to_process = boundaries_sorted
    if allowed is not None:
        boundaries_to_process = [b for b in boundaries_sorted if b.get("section_id") in allowed]

    logger.log("portionize", "running", current=0, total=len(boundaries_to_process),
               message=f"Extracting {len(boundaries_to_process)} sections with AI",
               artifact=args.out, module_id="portionize_ai_extract_v1")

    # Load escalation cache if provided
    escalation_text = {}
    escalation_images = {}
    if args.escalation_cache_dir:
        cache_dir = Path(args.escalation_cache_dir)
        if cache_dir.exists():
            for cache_file in cache_dir.glob("page_*.json"):
                try:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                sections = data.get("sections", {}) or {}
                for sid, info in sections.items():
                    if sid and isinstance(info, dict):
                        text = info.get("text")
                        if text:
                            escalation_text[str(sid)] = text
                            escalation_images[str(sid)] = data.get("image_paths") or []
        else:
            logger.log("portionize", "warning", message=f"Escalation cache dir not found: {cache_dir}")

    # Prepare output directory
    ensure_dir(os.path.dirname(args.out) or ".")
    run_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(args.out)), os.pardir))
    images_dir = _resolve_images_dir(run_root=run_root, explicit=args.images_dir)

    # Process each boundary
    client = OpenAI()
    error_traces = []
    for idx, boundary in enumerate(tqdm(boundaries_to_process, desc="Extracting sections"), start=1):
        try:
            section_id = boundary["section_id"]
            start_element_id = boundary["start_element_id"]

            # Find end_element_id (start of next section, or None for last section)
            end_element_id = next_start_by_sid.get(section_id)

            # Extract text from elements (or use escalation cache override)
            source_images = []
            used_escalation = False
            if str(section_id) in escalation_text:
                raw_text = escalation_text[str(section_id)]
                element_ids = []
                source_images = escalation_images.get(str(section_id)) or []
                used_escalation = True
            else:
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

            parse_warnings: List[Dict[str, Any]] = []

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
                    try:
                        combat = Combat(
                            skill=int(combat_data["skill"]),
                            stamina=int(combat_data["stamina"]),
                            name=combat_data.get("name")
                        )
                    except Exception as e:
                        parse_warnings.append({
                            "kind": "combat_parse_failed",
                            "error": str(e),
                            "combat_data": combat_data,
                        })
                        combat = None

            test_luck = bool(gameplay_data.get("test_luck", False))

            item_effects = []
            for effect_data in gameplay_data.get("item_effects", []):
                if isinstance(effect_data, dict):
                    try:
                        item_effects.append(ItemEffect(**effect_data))
                    except Exception as e:
                        parse_warnings.append({
                            "kind": "item_effect_parse_failed",
                            "error": str(e),
                            "effect_data": effect_data,
                        })

            # Get page range from elements
            if used_escalation:
                page_start = int(boundary.get("start_page") or 1)
                page_end = page_start
            else:
                section_elements = [elements_by_id[eid] for eid in element_ids if eid in elements_by_id]
                page_numbers = []
                for e in section_elements:
                    md = e.get("metadata") or {}
                    pn = md.get("page_number") or e.get("page")
                    if pn is None:
                        continue
                    try:
                        page_numbers.append(int(pn))
                    except Exception:
                        continue
                page_start = min(page_numbers) if page_numbers else 1
                page_end = max(page_numbers) if page_numbers else 1

            # Create EnrichedPortion
            if not used_escalation:
                image_keys = []
                for eid in element_ids:
                    elem = elements_by_id.get(eid)
                    if not elem:
                        continue
                    key = _page_key_from_element(elem)
                    if key:
                        image_keys.append(key)
                # If we only have numeric page ranges, include both L/R images
                # so downstream multimodal repair can see the full spread.
                for pn in range(int(page_start), int(page_end) + 1):
                    image_keys.append((pn, "L"))
                    image_keys.append((pn, "R"))
                image_keys = _sort_image_keys(sorted(set(image_keys)))
                source_images = []
                if images_dir and image_keys:
                    for orig, side in image_keys:
                        if side in ("L", "R"):
                            filename = f"page-{orig:03d}{side}.png"
                        else:
                            filename = f"page-{orig:03d}.png"
                        cand = os.path.join(images_dir, filename)
                        if os.path.exists(cand):
                            source_images.append(cand)
            enriched = EnrichedPortion(
                portion_id=section_id,
                section_id=section_id,
                page_start=page_start,
                page_end=page_end,
                title=None,
                type="section",
                confidence=boundary.get("confidence", 0.0),
                source_images=source_images,
                raw_text=raw_text,
                choices=choices,
                combat=combat,
                test_luck=test_luck,
                item_effects=item_effects,
                targets=[c.target for c in choices],
                element_ids=element_ids,
                macro_section=boundary.get("macro_section"),
                module_id="portionize_ai_extract_v1",
                run_id=args.run_id,
                context_correction=(
                    {
                        "parse_warnings": parse_warnings,
                        "widened_span": widened,
                        "error": gameplay_data.get("error"),
                    }
                    if parse_warnings or gameplay_data.get("error") or widened
                    else None
                ),
            )

            append_jsonl(args.out, enriched.dict(by_alias=True, exclude_none=True))

            logger.log("portionize", "running", current=idx, total=len(boundaries_to_process),
                       message=f"Extracted section {section_id}",
                       artifact=args.out, module_id="portionize_ai_extract_v1")

        except Exception as e:
            # Always emit a schema-valid placeholder portion so downstream can diagnose/repair.
            section_id = str(boundary.get("section_id") or "")
            start_element_id = boundary.get("start_element_id")
            start_elem = elements_by_id.get(start_element_id) if start_element_id else None
            page = start_elem.get("metadata", {}).get("page_number") if start_elem else None
            if page is None and start_elem:
                page = start_elem.get("page")
            try:
                page_int = int(page) if page is not None else 0
            except Exception:
                page_int = 0
            source_images = []
            if images_dir and start_element_id:
                start_elem = elements_by_id.get(start_element_id)
                if start_elem:
                    key = _page_key_from_element(start_elem)
                    if key:
                        orig, side = key
                        if side in ("L", "R"):
                            filename = f"page-{orig:03d}{side}.png"
                        else:
                            filename = f"page-{orig:03d}.png"
                        cand = os.path.join(images_dir, filename)
                        if os.path.exists(cand):
                            source_images.append(cand)
            enriched = EnrichedPortion(
                portion_id=section_id or "unknown",
                section_id=section_id or None,
                page_start=page_int,
                page_end=page_int,
                title=None,
                type="section",
                confidence=0.0,
                source_images=source_images,
                raw_text="",
                choices=[],
                combat=None,
                test_luck=False,
                item_effects=[],
                targets=[],
                element_ids=[start_element_id] if start_element_id else None,
                macro_section=boundary.get("macro_section"),
                module_id="portionize_ai_extract_v1",
                run_id=args.run_id,
                context_correction={
                    "error": str(e),
                    "error_kind": "exception",
                    "boundary": {
                        "section_id": section_id,
                        "start_element_id": start_element_id,
                    },
                },
            )
            append_jsonl(args.out, enriched.dict(by_alias=True, exclude_none=True))
            logger.log("portionize", "running", current=idx, total=len(boundaries_to_process),
                       message=f"Error on section {boundary.get('section_id')}: {e}",
                       artifact=args.out, module_id="portionize_ai_extract_v1")

    logger.log("portionize", "done", current=len(boundaries_to_process), total=len(boundaries_to_process),
               message=f"Extracted {len(boundaries_to_process)} sections",
               artifact=args.out, module_id="portionize_ai_extract_v1",
               schema_version="enriched_portion_v1")

    if error_traces:
        err_path = args.out + ".errors.json"
        save_json(err_path, error_traces)
        print(f"[warn] {len(error_traces)} sections unresolved; trace → {err_path}")
        if args.fail_on_empty:
            raise SystemExit(f"Extraction unresolved for {len(error_traces)} sections (empty or parse errors)")

    print(f"Extracted {len(boundaries_to_process)} sections → {args.out}")


if __name__ == "__main__":
    main()
