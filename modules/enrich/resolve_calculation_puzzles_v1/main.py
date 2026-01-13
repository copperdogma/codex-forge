"""
Resolve Calculation Puzzles Module

Detects sections with calculation/puzzle instructions (e.g., "count the letters,
multiply by 10, turn to that reference") and uses AI to resolve them by reasoning
with extracted game context (items, state values, codes).

Creates conditional links to target sections with provenance metadata, making
calculation puzzles navigable in the game engine.
"""
import argparse
import json
import os
import re
from typing import Dict, List, Any, Optional, Set

from modules.common.openai_client import OpenAI
from modules.common.utils import save_json, ProgressLogger


def detect_calculation_patterns(text: str) -> bool:
    """
    Detect if section contains calculation/puzzle instructions.

    Patterns:
    - "add X to Y and turn to"
    - "multiply by X and turn to"
    - "count the letters"
    - "model number" + "turn to that"
    - "turn to the number of"
    - "turn to that reference/paragraph"
    """
    text_lower = text.lower()

    patterns = [
        r'add\s+\d+\s+to.*turn to',
        r'multiply.*by.*turn to',
        r'count\s+the\s+(letter|word)',
        r'model\s+number.*turn to',
        r'turn to\s+the\s+number\s+of',
        r'turn to\s+that\s+(reference|paragraph|section)',
        r'if you know.*turn to\s+\w+',
    ]

    for pattern in patterns:
        if re.search(pattern, text_lower):
            return True

    return False


def gather_game_context(gamebook: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gather all items, state values, and contextual information from gamebook.

    Returns dict with:
    - items: List of all item names mentioned
    - state_values: List of all state values (codes, passwords, etc.)
    - sections_with_items: Mapping of section_id to items gained there
    - model_numbers: Dict of item/object -> model number (extracted from text)
    - codes_and_passwords: Dict of code/password names -> values
    """
    items = set()
    state_values = {}
    sections_with_items = {}
    model_numbers = {}
    codes_and_passwords = {}

    sections = gamebook.get("sections", {})

    for section_id, section in sections.items():
        section_items = []

        # Extract items from sequence
        sequence = section.get("sequence", [])
        for event in sequence:
            if event.get("kind") == "item":
                action = event.get("action")
                item_name = event.get("name")
                if item_name:
                    items.add(item_name)
                    if action == "add":
                        section_items.append(item_name)

            # Extract state values (passwords, codes, etc.)
            if event.get("kind") == "state_value":
                key = event.get("key")
                value = event.get("value")
                if key and value:
                    state_values[key] = value

        if section_items:
            sections_with_items[section_id] = section_items

        # Extract model numbers and codes from text
        text = section.get("presentation_html", "")

        # Pattern: "Model X" or "Model number X"
        # Note: This is a basic pattern - complex cases are handled by full-book AI escalation
        model_pattern = re.finditer(r'Model\s+(\d+)', text, re.IGNORECASE)
        for match in model_pattern:
            # We don't know the item name from this pattern alone
            # Store with a generic key that includes context
            model_numbers[f"model_{match.group(1)}"] = match.group(1)

        # Pattern: countersign/password with value
        password_pattern = re.finditer(r'(?:countersign|password|code)\s+(?:is\s+)?[\'"]?([A-Za-z]+|[0-9]+)[\'"]?', text, re.IGNORECASE)
        for match in password_pattern:
            value = match.group(1)
            # Store as "countersign" or similar
            codes_and_passwords["countersign"] = value

    return {
        "items": sorted(list(items)),
        "state_values": state_values,
        "sections_with_items": sections_with_items,
        "model_numbers": model_numbers,
        "codes_and_passwords": codes_and_passwords
    }


def resolve_puzzle_with_ai(
    client: OpenAI,
    section_id: str,
    section_text: str,
    game_context: Dict[str, Any],
    gamebook: Dict[str, Any],
    model: str = "gpt-4o-mini",
    max_verification_turns: int = 2
) -> Optional[Dict[str, Any]]:
    """
    Use AI to resolve calculation puzzle with two-part verification.

    Phase 1: AI calculates target section(s) from puzzle instruction
    Phase 2: AI verifies each target by reading the target section text
             and checking if it makes narrative sense

    Returns dict with:
    - targets: List of {targetSection, requiredItem, calculation, confidence, verified}
    """
    items = game_context["items"]
    state_values = game_context["state_values"]
    model_numbers = game_context["model_numbers"]
    codes_and_passwords = game_context["codes_and_passwords"]

    # Phase 1: Initial calculation
    initial_prompt = f"""You are analyzing a Fighting Fantasy gamebook section that contains a calculation or puzzle instruction.

Section {section_id} text:
{section_text}

Available items in the game:
{json.dumps(items, indent=2)}

Model numbers found in game text:
{json.dumps(model_numbers, indent=2)}

Codes and passwords found in game:
{json.dumps(codes_and_passwords, indent=2)}

State values:
{json.dumps(state_values, indent=2)}

This section tells the player to calculate a section number and turn to it. Your task:
1. Identify what calculation the player must perform
2. Determine which items or state values are needed
3. Calculate the target section number(s)
4. Explain your reasoning step by step, including counting letters if applicable

Return a JSON object with this structure:
{{
  "targets": [
    {{
      "targetSection": "100",
      "requiredItem": "Blue Potion",
      "calculation": "Blue (4 letters) + Potion (6 letters) = 10 letters, 10 × 10 = 100",
      "confidence": 0.95
    }}
  ]
}}

If no calculation can be resolved, return: {{"targets": []}}

IMPORTANT: Only return the JSON object, no other text."""

    try:
        messages = [{"role": "user", "content": initial_prompt}]

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1000
        )

        content = completion.choices[0].message.content
        result = json.loads(content)

        if not result.get("targets"):
            return {"targets": []}

        # Phase 2: Verify each target by showing the target section text
        messages.append({"role": "assistant", "content": content})

        verified_targets = []
        sections = gamebook.get("sections", {})

        for target in result["targets"]:
            target_section_id = str(target.get("targetSection"))
            target_section = sections.get(target_section_id)

            if not target_section:
                # Target section doesn't exist, skip
                print(f"    Warning: Target section {target_section_id} not found in gamebook")
                continue

            target_text = target_section.get("presentation_html", "")[:500]

            # Verification prompt
            verify_prompt = f"""Now let's verify your calculation. Here is the text of section {target_section_id} that you calculated:

Section {target_section_id} text:
{target_text}

Based on your calculation for "{target.get('requiredItem', 'the item')}" leading to section {target_section_id}:
- Does this section text make narrative sense as the result of that calculation?
- Does it seem like the logical continuation for a player who has that item?

Return a JSON object:
{{
  "verified": true/false,
  "reason": "brief explanation",
  "correctedTarget": null or "new_section_number" if you want to correct,
  "correctedCalculation": null or "corrected calculation explanation"
}}"""

            messages.append({"role": "user", "content": verify_prompt})

            verify_completion = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=500
            )

            verify_content = verify_completion.choices[0].message.content
            verify_result = json.loads(verify_content)

            messages.append({"role": "assistant", "content": verify_content})

            if verify_result.get("verified"):
                # Verification passed
                target["verified"] = True
                target["verificationReason"] = verify_result.get("reason", "")
                verified_targets.append(target)
                print(f"    ✓ Verified: {target_section_id} ({verify_result.get('reason', '')})")
            elif verify_result.get("correctedTarget"):
                # AI wants to correct the calculation
                corrected_id = str(verify_result["correctedTarget"])
                corrected_section = sections.get(corrected_id)

                if corrected_section:
                    corrected_target = {
                        "targetSection": corrected_id,
                        "requiredItem": target.get("requiredItem"),
                        "calculation": verify_result.get("correctedCalculation", target.get("calculation")),
                        "confidence": target.get("confidence", 0.8),
                        "verified": True,
                        "verificationReason": f"Corrected from {target_section_id}: {verify_result.get('reason', '')}"
                    }
                    verified_targets.append(corrected_target)
                    print(f"    → Corrected: {target_section_id} → {corrected_id}")
            else:
                # Verification failed, no correction
                print(f"    ✗ Rejected: {target_section_id} ({verify_result.get('reason', '')})")

        return {"targets": verified_targets}

    except Exception as e:
        print(f"Error resolving puzzle for section {section_id}: {e}")
        return {"targets": []}


def build_reverse_graph(gamebook: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Build a reverse graph: for each section, which sections link TO it?
    """
    reverse = {}
    sections = gamebook.get("sections", {})

    for section_id, section in sections.items():
        for event in section.get("sequence", []):
            targets = []

            # Extract all possible targets from any event type
            if event.get("targetSection"):
                targets.append(event["targetSection"])
            for key in ["has", "hasnt", "missing", "pass", "fail", "lucky", "unlucky"]:
                if event.get(key) and event[key].get("targetSection"):
                    targets.append(event[key]["targetSection"])
            outcomes = event.get("outcomes", {})
            for outcome in outcomes.values():
                if isinstance(outcome, dict) and outcome.get("targetSection"):
                    targets.append(outcome["targetSection"])
            for choice in event.get("choices", []):
                if choice.get("targetSection"):
                    targets.append(choice["targetSection"])

            for target in targets:
                if target not in reverse:
                    reverse[target] = []
                reverse[target].append(section_id)

    return reverse


def find_path_to_section(gamebook: Dict[str, Any], target_section: str, max_depth: int = 20) -> Set[str]:
    """
    Find all sections that could lead to target_section via BFS backwards.

    Returns set of section IDs that are on paths leading to this section.
    """
    from collections import deque

    reverse = build_reverse_graph(gamebook)
    visited = set()
    queue = deque([(target_section, 0)])

    while queue:
        section_id, depth = queue.popleft()
        if section_id in visited or depth > max_depth:
            continue
        visited.add(section_id)

        # Add all sections that link to this one
        for source in reverse.get(section_id, []):
            if source not in visited:
                queue.append((source, depth + 1))

    return visited


def extract_relevant_section_text(gamebook: Dict[str, Any], relevant_sections: Set[str], max_chars: int = 50000) -> str:
    """
    Extract text only from relevant sections (those on paths to the puzzle).
    """
    sections = gamebook.get("sections", {})
    lines = []
    total_chars = 0

    # Sort for consistent ordering
    for section_id in sorted(relevant_sections, key=lambda x: (x.isdigit(), int(x) if x.isdigit() else 0, x)):
        if section_id not in sections:
            continue
        section = sections[section_id]
        text = section.get("presentation_html", "")

        # Strip HTML tags
        clean_text = re.sub(r'<[^>]+>', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        if not clean_text:
            continue

        line = f"[Section {section_id}]: {clean_text[:500]}"

        if total_chars + len(line) > max_chars:
            lines.append(f"... (truncated at {len(lines)} sections)")
            break

        lines.append(line)
        total_chars += len(line) + 1

    return "\n".join(lines)


def extract_keywords_from_puzzle(puzzle_text: str) -> List[str]:
    """
    Extract likely item/device names from puzzle text.

    Looks for capitalized words that might be item names, excluding common words.
    """
    # Strip HTML
    clean = re.sub(r'<[^>]+>', ' ', puzzle_text)

    # Common words to exclude
    stop_words = {
        'if', 'you', 'know', 'the', 'turn', 'to', 'that', 'reference', 'number',
        'model', 'add', 'multiply', 'count', 'letters', 'and', 'or', 'not',
        'section', 'paragraph', 'what', 'its', 'your', 'have', 'has', 'been',
        'where', 'would', 'like', 'go', 'city', 'of', 'note', 'cannot', 'until'
    }

    # Find capitalized words/phrases that might be item names
    keywords = []

    # Pattern for capitalized words (potential item names)
    words = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', clean)
    for word in words:
        if word.lower() not in stop_words and len(word) > 2:
            keywords.append(word)

    # Also extract key nouns from the puzzle
    # e.g., "Wasp Fighter's model number" -> "Wasp", "Fighter"
    noun_pattern = re.findall(r"(\w+)(?:'s|s')?\s+(?:model|number|code)", clean, re.IGNORECASE)
    for noun in noun_pattern:
        if noun.lower() not in stop_words and len(noun) > 2:
            keywords.append(noun)

    return list(set(keywords))


def filter_sections_by_keywords(
    gamebook: Dict[str, Any],
    section_ids: Set[str],
    keywords: List[str]
) -> Set[str]:
    """
    Filter sections to only those containing any of the keywords.
    """
    if not keywords:
        return section_ids

    sections = gamebook.get("sections", {})
    matching = set()

    for sid in section_ids:
        if sid not in sections:
            continue
        text = sections[sid].get("presentation_html", "").lower()
        for kw in keywords:
            if kw.lower() in text:
                matching.add(sid)
                break

    return matching


def resolve_puzzle_with_full_book(
    client: OpenAI,
    section_id: str,
    section_text: str,
    gamebook: Dict[str, Any],
    model: str = "gpt-4o-mini"
) -> Optional[Dict[str, Any]]:
    """
    Escalation: Use keyword-filtered path-based context to resolve puzzle.

    1. Find sections on paths leading to this puzzle
    2. Extract keywords from puzzle (item/device names)
    3. Filter to only sections mentioning those keywords
    4. This focuses AI on the most relevant context
    """
    print(f"    Escalating to keyword-filtered context for section {section_id}...")

    # Extract keywords from the puzzle
    keywords = extract_keywords_from_puzzle(section_text)
    print(f"    Keywords from puzzle: {keywords}")

    # Find sections on paths leading to this puzzle
    path_sections = find_path_to_section(gamebook, section_id)

    # Filter to sections containing the keywords
    relevant_sections = filter_sections_by_keywords(gamebook, path_sections, keywords)
    print(f"    Filtered from {len(path_sections)} to {len(relevant_sections)} sections")

    # If filtering was too aggressive, fall back to full path
    if len(relevant_sections) < 5:
        print(f"    Too few matches, using full path context")
        relevant_sections = path_sections

    # Extract text from relevant sections only
    context_text = extract_relevant_section_text(gamebook, relevant_sections)
    sections = gamebook.get("sections", {})

    # Phase 1: Initial calculation
    calc_prompt = f"""You are solving a calculation puzzle in a Fighting Fantasy gamebook.

PUZZLE (Section {section_id}):
{section_text}

The player reached this section through one of the paths below. Somewhere along the way, they learned information needed to solve this puzzle.

SECTIONS THE PLAYER COULD HAVE VISITED:
{context_text}

YOUR TASK:
1. Read the puzzle carefully - what SPECIFIC item/device/vehicle is mentioned?
2. Search the sections above for that EXACT thing
3. Find the relevant number (model number, code, letter count, etc.)
4. Model numbers can appear as:
   - "Model X" or "Model number X"
   - Numbers embedded in names (e.g., "Wasp 200 Fighter" means model number is 200)
5. Apply any calculation mentioned in the puzzle (add, multiply, etc.)
6. If the puzzle says "turn to that reference/model number" with no math, the number IS the target

CRITICAL: The targetSection is the NUMBER you calculated, NOT the section where you found the info.
Example: If you find "Wasp 200 Fighter" in section 221, and the puzzle says "turn to the model number", then:
  - foundIn = "221" (where you found the info)
  - targetSection = "200" (the model number to turn to)

Return JSON:
{{
  "targetSection": "THE NUMBER TO TURN TO (result of calculation)",
  "itemMentioned": "the exact item/device from the puzzle",
  "foundIn": "which section you found the info",
  "foundText": "the exact text snippet with the number",
  "calculation": "step by step calculation",
  "confidence": 0.0 to 1.0
}}

If you cannot solve it: {{"targetSection": null, "reason": "explanation"}}"""

    try:
        messages = [{"role": "user", "content": calc_prompt}]

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=1000
        )

        content = completion.choices[0].message.content
        result = json.loads(content)

        if not result.get("targetSection"):
            print(f"    Could not resolve: {result.get('reason', 'unknown')}")
            return {"targets": []}

        target_id = str(result["targetSection"])
        print(f"    Initial calculation: {target_id} ({result.get('calculation', 'N/A')[:60]})")

        # Phase 2: Verification - does the target section make narrative sense?
        if target_id not in sections:
            print(f"    ✗ Target {target_id} doesn't exist in gamebook")
            return {"targets": []}

        target_section = sections[target_id]
        target_text = target_section.get("presentation_html", "")
        clean_target = re.sub(r'<[^>]+>', ' ', target_text)
        clean_target = re.sub(r'\s+', ' ', clean_target).strip()[:500]

        messages.append({"role": "assistant", "content": content})

        verify_prompt = f"""Now verify your calculation. Here is section {target_id}:

Section {target_id}:
{clean_target}

This section is the REWARD for knowing about "{result.get('itemMentioned', 'the item')}".

Verification criteria (answer YES if ANY of these are true):
- Does the section acknowledge prior knowledge/experience with the item?
- Does the section give an advantage that makes sense for someone who knows the item?
- Does the section continue the story in a way that rewards knowing the info?
- Is there ANY indirect connection (e.g., "arcade game" connects to "Wasp 200 Fighter")?

The connection does NOT need to be explicit - indirect narrative links count.

Return JSON:
{{
  "verified": true or false,
  "reason": "brief explanation",
  "alternativeTarget": null or "different section number if you think you made an error"
}}"""

        messages.append({"role": "user", "content": verify_prompt})

        verify_completion = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=500
        )

        verify_result = json.loads(verify_completion.choices[0].message.content)

        if verify_result.get("verified"):
            print(f"    ✓ Verified: {target_id} ({verify_result.get('reason', '')[:60]})")
            return {"targets": [{
                "targetSection": target_id,
                "requiredItem": result.get("itemMentioned"),
                "calculation": result.get("calculation"),
                "confidence": result.get("confidence", 0.9),
                "sourceSection": result.get("foundIn"),
                "verified": True,
                "fullBookEscalation": True
            }]}
        elif verify_result.get("alternativeTarget"):
            alt_id = str(verify_result["alternativeTarget"])
            if alt_id in sections:
                print(f"    → Corrected to: {alt_id} ({verify_result.get('reason', '')})")
                return {"targets": [{
                    "targetSection": alt_id,
                    "requiredItem": result.get("itemMentioned"),
                    "calculation": f"Corrected from {target_id}: {verify_result.get('reason', '')}",
                    "confidence": 0.85,
                    "verified": True,
                    "fullBookEscalation": True
                }]}

        print(f"    ✗ Verification failed: {verify_result.get('reason', 'unknown')}")
        return {"targets": []}

    except Exception as e:
        print(f"    Path-based escalation error: {e}")
        return {"targets": []}


def inject_calculated_links(
    gamebook: Dict[str, Any],
    section_id: str,
    targets: List[Dict[str, Any]]
) -> int:
    """
    Inject conditional links for calculated targets into section's sequence.

    Returns number of links injected.
    """
    sections = gamebook.get("sections", {})
    section = sections.get(section_id)

    if not section:
        return 0

    sequence = section.get("sequence", [])
    injected = 0

    for target in targets:
        target_section = target.get("targetSection")
        required_item = target.get("requiredItem")
        calculation = target.get("calculation")
        confidence = target.get("confidence", 0.0)

        if not target_section:
            continue

        # Create conditional link
        link_event = {
            "kind": "item_check",
            "item": required_item if required_item else "unknown",
            "has": {
                "targetSection": target_section
            },
            "metadata": {
                "resolvedByPuzzleSolver": True,
                "calculation": calculation,
                "confidence": confidence
            }
        }

        # If no required item, create simple choice
        if not required_item:
            link_event = {
                "kind": "choice",
                "targetSection": target_section,
                "choiceText": f"Turn to {target_section} (calculated)",
                "metadata": {
                    "resolvedByPuzzleSolver": True,
                    "calculation": calculation,
                    "confidence": confidence
                }
            }

        sequence.append(link_event)
        injected += 1

    section["sequence"] = sequence
    return injected


def main():
    parser = argparse.ArgumentParser(description="Resolve calculation puzzles using AI")
    parser.add_argument("--gamebook", required=True, help="Path to gamebook.json")
    parser.add_argument("--out", required=True, help="Path to output gamebook.json")
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--confidence-threshold", dest="confidence_threshold", type=float, default=0.8, help="Minimum confidence to inject links")
    parser.add_argument("--progress-file", dest="progress_file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", dest="state_file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", dest="run_id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(
        state_path=args.state_file,
        progress_path=args.progress_file,
        run_id=args.run_id
    )

    logger.log(
        "resolve_puzzles", "running", current=0, total=4,
        message="Loading gamebook", artifact=args.out, module_id="resolve_calculation_puzzles_v1"
    )

    # Load gamebook
    with open(args.gamebook, 'r', encoding='utf-8') as f:
        gamebook = json.load(f)

    sections = gamebook.get("sections", {})

    logger.log(
        "resolve_puzzles", "running", current=1, total=4,
        message="Detecting calculation puzzles", artifact=args.out
    )

    # Phase 1: Detect calculation puzzle sections
    puzzle_sections = []
    for section_id, section in sections.items():
        text = section.get("presentation_html", "")
        if detect_calculation_patterns(text):
            puzzle_sections.append((section_id, text))

    print(f"Detected {len(puzzle_sections)} sections with calculation patterns")

    if not puzzle_sections:
        print("No calculation puzzles detected, saving unmodified gamebook")
        save_json(args.out, gamebook)
        logger.log(
            "resolve_puzzles", "done", current=4, total=4,
            message="No puzzles to resolve", artifact=args.out
        )
        return

    logger.log(
        "resolve_puzzles", "running", current=2, total=4,
        message=f"Gathering game context from {len(sections)} sections", artifact=args.out
    )

    # Phase 2: Gather game context
    game_context = gather_game_context(gamebook)
    print(f"Found {len(game_context['items'])} items, {len(game_context['model_numbers'])} model numbers, {len(game_context['codes_and_passwords'])} codes/passwords")

    logger.log(
        "resolve_puzzles", "running", current=3, total=4,
        message=f"Resolving {len(puzzle_sections)} puzzles with AI", artifact=args.out
    )

    # Phase 3: Resolve puzzles with AI and inject links
    total_links = 0
    resolved_sections = []

    # Create OpenAI client
    client = OpenAI()

    for section_id, section_text in puzzle_sections:
        print(f"\nResolving puzzle in section {section_id}...")

        # Phase 1: Try standard approach with extracted context
        result = resolve_puzzle_with_ai(client, section_id, section_text, game_context, gamebook, args.model)

        # Filter by confidence threshold
        targets = []
        if result and result.get("targets"):
            targets = [
                t for t in result["targets"]
                if t.get("confidence", 0.0) >= args.confidence_threshold
            ]

        # Phase 2: If standard approach failed, escalate to full-book mode
        if not targets:
            print(f"  Standard approach failed, trying full-book escalation...")
            full_book_result = resolve_puzzle_with_full_book(client, section_id, section_text, gamebook, args.model)

            if full_book_result and full_book_result.get("targets"):
                targets = [
                    t for t in full_book_result["targets"]
                    if t.get("confidence", 0.0) >= args.confidence_threshold
                ]

        if not targets:
            print(f"  No targets resolved for section {section_id} (even with full-book)")
            continue

        # Inject links
        injected = inject_calculated_links(gamebook, section_id, targets)
        total_links += injected
        resolved_sections.append(section_id)

        for target in targets:
            escalation_note = " [full-book]" if target.get("fullBookEscalation") else ""
            print(f"  → {target['targetSection']}: {target.get('calculation', 'N/A')[:80]} (conf: {target.get('confidence', 0.0):.2f}){escalation_note}")

    print(f"\n✓ Resolved {len(resolved_sections)} puzzles, injected {total_links} links")
    print(f"  Sections: {', '.join(resolved_sections)}")

    # Save enhanced gamebook
    save_json(args.out, gamebook)

    logger.log(
        "resolve_puzzles", "done", current=4, total=4,
        message=f"Resolved {len(resolved_sections)} puzzles", artifact=args.out
    )


if __name__ == "__main__":
    main()
