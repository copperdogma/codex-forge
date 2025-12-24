import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger, log_llm_usage
from modules.common.html_utils import html_to_text
from schemas import EnrichedPortion, InventoryItem, InventoryCheck, InventoryEnrichment

# --- Patterns ---

GAIN_PATTERNS = [
    re.compile(r"\byou\s+(?:find|take|pick\s+up|gain|receive|get)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
    re.compile(r"\badd\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+to\s+your\s+backpack\b", re.IGNORECASE),
    re.compile(r"\b(.*?)\s+is\s+yours\b", re.IGNORECASE),
]

# Losing: "you lose", "you drop", "is taken", "remove"
LOSE_PATTERNS = [
    re.compile(r"\byou\s+(?:lose|drop|discard|remove)\s+(?:a\b|the\b|an\b)?\s*(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+taken\s+from\s+you\b", re.IGNORECASE),
]

# Using: "you use", "you drink", "you eat", "using the"
USE_PATTERNS = [
    re.compile(r"\byou\s+(?:use|drink|eat|read)\s+(?:the\b|a\b|an\b)?\s*(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bwith\s+the\b\s+(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
]

# Checks: "if you have", "if you possess", "is in your backpack"
CHECK_PATTERNS = [
    re.compile(r"\bif\s+you\s+(?:have|possess|are\s+carrying)\s+(?:the\b|a\b|an\b)?\s*(.*?)(?:,|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bif\s+(?:the\b|a\b|an\b)?\s*(.*?)\s+is\s+in\s+your\s+backpack\b", re.IGNORECASE),
]

# Quantity: try to extract a leading number
QUANTITY_PATTERN = re.compile(r"^(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(.*)", re.IGNORECASE)

NUM_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
}

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract inventory-related actions from the provided text into a JSON object.
Detect:
- items_gained: Items the player finds or receives.
- items_lost: Items the player loses, drops, or has taken away.
- items_used: Items the player uses or consumes (potions, keys).
- inventory_checks: Conditional checks on item possession.

For each item, include:
- item: The clean name of the item.
- quantity: Number of items (default 1).
- condition: (For checks only) The condition phrase like "if you have".
- target_section: (For checks only) The section to turn to if the check passes.

Example output:
{
  "inventory": {
    "items_gained": [{"item": "Gold Pieces", "quantity": 10}],
    "items_lost": [{"item": "Rope", "quantity": 1}],
    "items_used": [{"item": "Potion of Strength", "quantity": 1}],
    "inventory_checks": [{"item": "Lantern", "condition": "if you have", "target_section": "43"}]
  }
}

If no inventory actions are found, return {"inventory": {}}.
"""

# --- Logic ---

def _parse_item_text(text: str) -> Tuple[Optional[str], int]:
    text = text.strip()
    if not text:
        return None, 1
    
    # Filter out common pronouns and articles that might be captured by loose regex
    text_lower = text.lower()
    if text_lower in {"it", "them", "him", "her", "some", "none", "your", "his", "their", "my"}:
        return None, 1
    
    # Strip leading "your " etc
    for p in ["your ", "his ", "her ", "their ", "my ", "its "]:
        if text_lower.startswith(p):
            text = text[len(p):].strip()
            text_lower = text.lower()
            break

    match = QUANTITY_PATTERN.match(text)
    if match:
        qty_str = match.group(1).lower()
        item = match.group(2).strip()
        if qty_str.isdigit():
            return item, int(qty_str)
        return item, NUM_MAP.get(qty_str, 1)
    return text, 1

def extract_inventory_regex(text: str) -> InventoryEnrichment:
    gained = []
    lost = []
    used = []
    checks = []

    # This is a very naive regex implementation.
    # It will likely have many false positives and misses.
    # In a real scenario, we'd refine these patterns or rely more on LLM.
    
    # We only apply regex if we see strong keywords to minimize false positives
    if not any(k in text.lower() for k in ["backpack", "gold pieces", "potion", "item", "possess", "carrying", "find", "take", "lose", "drop", "have"]):
        return InventoryEnrichment()

    for pattern in GAIN_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and len(name) < 50:
                    gained.append(InventoryItem(item=name, quantity=qty, confidence=0.7))

    for pattern in LOSE_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and len(name) < 50:
                    lost.append(InventoryItem(item=name, quantity=qty, confidence=0.7))

    for pattern in USE_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and len(name) < 50:
                    used.append(InventoryItem(item=name, quantity=qty, confidence=0.7))

    for pattern in CHECK_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                # Capture the specific condition keyword(s)
                raw_match = match.group(0).lower()
                if "if you have" in raw_match: condition = "if you have"
                elif "if you possess" in raw_match: condition = "if you possess"
                elif "if you are carrying" in raw_match: condition = "if you are carrying"
                elif "is in your backpack" in raw_match: condition = "is in your backpack"
                else: condition = "item check"
                
                name, _ = _parse_item_text(item_text)
                if name and len(name) < 50:
                    checks.append(InventoryCheck(item=name, condition=condition, confidence=0.7))
    
    return InventoryEnrichment(items_gained=gained, items_lost=lost, items_used=used, inventory_checks=checks)

def validate_inventory(inv: InventoryEnrichment) -> bool:
    """Returns True if the inventory data looks sane."""
    # Basic sanity: no empty item names, reasonable quantities
    all_items = inv.items_gained + inv.items_lost + inv.items_used
    for item in all_items:
        if not item.item or len(item.item) < 2:
            return False
        if item.quantity <= 0 or item.quantity > 1000:
            return False
        # Check for obvious garbage
        if "turn to" in item.item.lower() or "turn over" in item.item.lower():
            return False
            
    for check in inv.inventory_checks:
        if not check.item or len(check.item) < 2:
            return False
        if "turn to" in check.item.lower():
            return False
            
    return True

def extract_inventory_llm(text: str, model: str, client: OpenAI) -> Tuple[InventoryEnrichment, Dict[str, Any]]:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        
        usage = {
            "model": model,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }
        
        content = response.choices[0].message.content
        data = json.loads(content)
        inv_data = data.get("inventory", {})
        
        gained = [InventoryItem(**item, confidence=0.95) for item in inv_data.get("items_gained", [])]
        lost = [InventoryItem(**item, confidence=0.95) for item in inv_data.get("items_lost", [])]
        used = [InventoryItem(**item, confidence=0.95) for item in inv_data.get("items_used", [])]
        checks = [InventoryCheck(**item, confidence=0.95) for item in inv_data.get("inventory_checks", [])]
        
        return InventoryEnrichment(
            items_gained=gained,
            items_lost=lost,
            items_used=used,
            inventory_checks=checks
        ), usage
    except Exception as e:
        print(f"LLM inventory extraction error: {e}")
        return InventoryEnrichment(), {}

def main():
    parser = argparse.ArgumentParser(description="Extract inventory actions from enriched portions.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--pages", help="Input page_html_blocks_v1 JSONL (for driver compatibility)")
    parser.add_argument("--out", required=True, help="Output enriched_portion_v1 JSONL")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--use-ai", "--use_ai", action="store_true", default=True)
    parser.add_argument("--no-ai", "--no_ai", dest="use_ai", action="store_false")
    parser.add_argument("--max-ai-calls", "--max_ai_calls", type=int, default=50)
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    
    portions = list(read_jsonl(args.portions))
    total_portions = len(portions)
    
    client = OpenAI() if args.use_ai else None
    ai_calls = 0
    
    out_portions = []
    
    # High-signal keywords that strongly suggest inventory actions
    INV_KEYWORDS = ["backpack", "gold pieces", "potion", "possess", "carrying", "you find", "you take", "you lose", "you drop", "if you have"]

    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text
        if not text and portion.raw_html:
            text = html_to_text(portion.raw_html)
        if not text:
            text = ""
        
        # 1. TRY: Regex attempt (only for gains for now as a spike)
        inv = extract_inventory_regex(text)
        
        # 2. VALIDATE
        is_valid = validate_inventory(inv)
        
        # 3. ESCALATE
        needs_ai = False
        if not is_valid:
            needs_ai = True
        elif not inv.items_gained and not inv.items_lost and not inv.items_used and not inv.inventory_checks:
            # If regex found nothing, check if we should escalate based on keywords
            if any(k in text.lower() for k in INV_KEYWORDS):
                needs_ai = True
        
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            # print(f"DEBUG: Triggering AI inventory extraction for section {portion.section_id}")
            llm_input = text
            if len(text) < 100 and portion.raw_html:
                llm_input = f"HTML SOURCE:\n{portion.raw_html}\n\nPLAIN TEXT:\n{text}"
            
            inv_llm, usage = extract_inventory_llm(llm_input, args.model, client)
            ai_calls += 1
            log_llm_usage(args.run_id, "extract_inventory", usage)
            if inv_llm:
                inv = inv_llm
        
        portion.inventory = inv
        out_portions.append(portion.model_dump(exclude_none=True))
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_inventory", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    save_jsonl(args.out, out_portions)
    logger.log("extract_inventory", "done", message=f"Extracted inventory for {total_portions} portions. Total AI calls: {ai_calls}", artifact=args.out)

if __name__ == "__main__":
    main()
