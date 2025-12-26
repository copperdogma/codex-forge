import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from schemas import EnrichedPortion, InventoryItem, InventoryCheck, InventoryEnrichment

# --- Patterns ---

GAIN_PATTERNS = [
    re.compile(r"\byou\s+(?:find|take|pick\s+up|gain|receive|get)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
    re.compile(r"\badd\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+to\s+your\s+backpack\b", re.IGNORECASE),
    re.compile(r"\b(.*?)\s+is\s+yours\b", re.IGNORECASE),
]

LOSE_PATTERNS = [
    re.compile(r"\byou\s+(?:lose|drop|discard|remove)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+taken\s+from\s+you\b", re.IGNORECASE),
]

USE_PATTERNS = [
    re.compile(r"\byou\s+(?:use|drink|eat|read)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bwith\s+the\b\s+(.*?)(?:\.|$|\band\b|\bturn\b)", re.IGNORECASE),
]

CHECK_PATTERNS = [
    re.compile(r"\bif\s+you\s+(?:have|possess|are\s+carrying)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:,|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bif\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+is\s+in\s+your\s+backpack\b", re.IGNORECASE),
]

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

IMPORTANT RULES:
- Only extract PHYSICAL objects (keys, potions, gold, weapons, etc.).
- DO NOT extract abstract concepts like "time", "aim", "balance", "luck", "yourself", "not done so already".
- DO NOT extract sentences or fragments like "not done so already", "any left", "if you have not".
- Item names should be clean and concise (e.g., "Silver Key", not "the rusty silver key you found").
- quantity should be an integer or the string "all".

Example output:
{
  "inventory": {
    "items_gained": [{"item": "Gold Pieces", "quantity": 10}],
    "items_lost": [{"item": "Rope", "quantity": 1}],
    "items_used": [{"item": "Potion of Strength", "quantity": 1}],
    "inventory_checks": [{"item": "Lantern", "condition": "if you have", "target_section": "43"}]
  }
}

If no physical inventory actions are found, return {"inventory": {}}.
"""

AUDIT_SYSTEM_PROMPT = """You are a quality assurance auditor for a Fighting Fantasy gamebook extraction pipeline.
I will provide a list of inventory items extracted from various sections of the book along with the source text for each section.
Your job is to identify:
1. FALSE POSITIVES: Entries that are NOT physical items or valid game actions.
2. INCORRECT VALUES: Incorrect quantities or item names.
3. MISSING ITEMS: Items described in the text that were not in the extracted list.

Common False Positives to flag:
- Sentence fragments: "not done so already", "any left", "it is ours"
- Character states: "yourself", "dripping with sweat", "helplessly"
- Abstract concepts: "time", "luck", "aim", "balance"
- Non-item nouns: "officials", "Dwarf"
- Locations: "end of a tunnel", "large cavern"

For each section, review the items and tell me which ones to REMOVE, CORRECT, or ADD.
Return a JSON object with "removals", "corrections", and "additions".
{
  "removals": [
    { "section_id": "1", "type": "add", "item_index": 0, "reason": "not an item" }
  ],
  "corrections": [
    { "section_id": "42", "type": "add", "item_index": 0, "data": { "item": "Gold Pieces", "quantity": 10 } }
  ],
  "additions": [
    { "section_id": "100", "data": { "item": "Brass Key", "quantity": 1, "action": "add" } }
  ]
}
If everything is correct, return {"removals": [], "corrections": [], "additions": []}."""

# --- Logic ---

def _parse_item_text(text: str) -> Tuple[Optional[str], int]:
    text = text.strip()
    if not text:
        return None, 1
    
    text_lower = text.lower()
    if text_lower in {
        "it", "them", "him", "her", "some", "none", "your", "his", "their", "my", 
        "yourself", "himself", "herself", "not", "not done so already", "already"
    }:
        return None, 1
    
    for p in ["your ", "his ", "her ", "their ", "my ", "its ", "the ", "a ", "an "]:
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

    STRICT_ITEMS = ["gold pieces", "provisions", "potion", "key", "rope", "spike", "mallet", "shield", "sword"]
    lower_text = text.lower()
    if not any(k in lower_text for k in ["backpack", "gold pieces", "potion", "item", "possess", "carrying"]):
        if not any(k in lower_text for k in STRICT_ITEMS):
            return InventoryEnrichment()

    for pattern in GAIN_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and len(name) < 40:
                    gained.append(InventoryItem(item=name, quantity=qty, confidence=0.7))

    for pattern in LOSE_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and len(name) < 40:
                    lost.append(InventoryItem(item=name, quantity=qty, confidence=0.7))

    for pattern in USE_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and len(name) < 40:
                    used.append(InventoryItem(item=name, quantity=qty, confidence=0.7))

    for pattern in CHECK_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                raw_match = match.group(0).lower()
                if "if you have" in raw_match: condition = "if you have"
                elif "if you possess" in raw_match: condition = "if you possess"
                elif "if you are carrying" in raw_match: condition = "if you are carrying"
                elif "is in your backpack" in raw_match: condition = "is in your backpack"
                else: condition = "item check"
                
                name, _ = _parse_item_text(item_text)
                if name and len(name) < 40:
                    checks.append(InventoryCheck(item=name, condition=condition, confidence=0.7))
    
    return InventoryEnrichment(items_gained=gained, items_lost=lost, items_used=used, inventory_checks=checks)

def validate_inventory(inv: InventoryEnrichment) -> bool:
    """Returns True if the inventory data looks sane."""
    BLACK_LIST = {
        "time", "aim", "balance", "luck", "yourself", "not", "already", 
        "not done so already", "done so already", "any left", "one", 
        "some", "none", "not done so already)?", "it"
    }
    
    all_items = inv.items_gained + inv.items_lost + inv.items_used
    for item in all_items:
        name_lower = item.item.lower().strip(" .,?!()")
        if not name_lower or len(name_lower) < 3:
            return False
        if name_lower in BLACK_LIST:
            return False
        if "turn to" in name_lower or "?" in name_lower:
            return False
        if len(name_lower) > 50:
            return False
            
    for check in inv.inventory_checks:
        name_lower = check.item.lower().strip(" .,?!()")
        if not name_lower or len(name_lower) < 3:
            return False
        if name_lower in BLACK_LIST:
            return False
        if "turn to" in name_lower or "?" in name_lower:
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
        
        def parse_qty(q):
            if isinstance(q, int): return q
            if str(q).isdigit(): return int(q)
            if str(q).lower() == "all": return "all"
            return 1

        gained = [
            InventoryItem(item=item.get("item"), quantity=parse_qty(item.get("quantity")), confidence=0.95) 
            for item in inv_data.get("items_gained", [])
            if item.get("item")
        ]
        lost = [
            InventoryItem(item=item.get("item"), quantity=parse_qty(item.get("quantity")), confidence=0.95) 
            for item in inv_data.get("items_lost", [])
            if item.get("item")
        ]
        used = [
            InventoryItem(item=item.get("item"), quantity=parse_qty(item.get("quantity")), confidence=0.95) 
            for item in inv_data.get("items_used", [])
            if item.get("item")
        ]
        checks = [
            InventoryCheck(
                item=item.get("item"), 
                condition=item.get("condition") or "if you have", 
                target_section=str(item.get("target_section")) if item.get("target_section") else None,
                confidence=0.95
            ) 
            for item in inv_data.get("inventory_checks", [])
            if item.get("item")
        ]
        
        return InventoryEnrichment(
            items_gained=gained,
            items_lost=lost,
            items_used=used,
            inventory_checks=checks
        ), usage
    except Exception as e:
        print(f"LLM inventory extraction error: {e}")
        return InventoryEnrichment(), {}

def audit_inventory_batch(audit_list: List[Dict[str, Any]], model: str, client: OpenAI, run_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Performs a global audit over all extracted inventory items to prune debris."""
    if not audit_list:
        return {"removals": [], "corrections": [], "additions": []}
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
                {"role": "user", "content": f"AUDIT LIST:\n{json.dumps(audit_list, indent=2)}"}
            ],
            response_format={"type": "json_object"}
        )
        
        usage = {
            "model": model,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
        }
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Global inventory audit error: {e}")
        return {"removals": [], "corrections": [], "additions": []}

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
    audit_data = [] 
    
    INV_KEYWORDS = ["backpack", "gold pieces", "potion", "possess", "carrying", "you find", "you take", "you lose", "you drop", "if you have"]

    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text or html_to_text(portion.raw_html or "")
        
        inv = extract_inventory_regex(text)
        is_valid = validate_inventory(inv)
        
        needs_ai = False
        if not is_valid:
            needs_ai = True
        elif not inv.items_gained and not inv.items_lost and not inv.items_used and not inv.inventory_checks:
            if any(k in text.lower() for k in INV_KEYWORDS):
                needs_ai = True
        
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            llm_input = text
            if len(text) < 100 and portion.raw_html:
                llm_input = f"HTML SOURCE:\n{portion.raw_html}\n\nPLAIN TEXT:\n{text}"
            
            inv_llm, usage = extract_inventory_llm(llm_input, args.model, client)
            ai_calls += 1
            if inv_llm:
                inv = inv_llm
        
        portion.inventory = inv
        
        sid = portion.section_id or portion.portion_id
        section_items = []
        for i, item in enumerate(inv.items_gained): section_items.append({"item_index": i, "type": "add", "data": item.model_dump()})
        for i, item in enumerate(inv.items_lost): section_items.append({"item_index": i, "type": "remove", "data": item.model_dump()})
        for i, item in enumerate(inv.items_used): section_items.append({"item_index": i, "type": "use", "data": item.model_dump()})
        for i, item in enumerate(inv.inventory_checks): section_items.append({"item_index": i, "type": "check", "data": item.model_dump()})

        audit_data.append({
            "section_id": sid,
            "text": text[:500],
            "items": section_items
        })

        out_portions.append(portion)
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_inventory", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    if args.use_ai and audit_data:
        logger.log("extract_inventory", "running", message=f"Performing global audit on {len(audit_data)} sections...")
        audit_results = audit_inventory_batch(audit_data, args.model, client, args.run_id)
        
        removals = audit_results.get("removals", [])
        corrections = audit_results.get("corrections", [])
        additions = audit_results.get("additions", [])

        if removals or corrections or additions:
            print(f"Global audit identified {len(removals)} removals, {len(corrections)} corrections, and {len(additions)} additions.")
            
            removals_set = set()
            for r in removals:
                sid_r = r.get("section_id")
                idx_r = r.get("item_index")
                if sid_r is not None and idx_r is not None:
                    removals_set.add((str(sid_r), str(r.get("type")), int(idx_r)))
            
            corrections_map = {}
            for c in corrections:
                sid_c = c.get("section_id")
                idx_c = c.get("item_index")
                if sid_c is not None and idx_c is not None:
                    corrections_map[(str(sid_c), str(c.get("type")), int(idx_c))] = c.get("data")
            
            additions_map = {}
            for a in additions:
                sid_a = a.get("section_id")
                if sid_a is not None:
                    additions_map.setdefault(str(sid_a), []).append(a.get("data"))

            for p in out_portions:
                if not p.inventory:
                    p.inventory = InventoryEnrichment()
                
                sid = str(p.section_id or p.portion_id)
                
                new_gained = []
                for i, item in enumerate(p.inventory.items_gained):
                    key = (sid, "add", i)
                    if key in corrections_map: new_gained.append(InventoryItem(**corrections_map[key]))
                    elif key not in removals_set: new_gained.append(item)
                p.inventory.items_gained = new_gained

                new_lost = []
                for i, item in enumerate(p.inventory.items_lost):
                    key = (sid, "remove", i)
                    if key in corrections_map: new_lost.append(InventoryItem(**corrections_map[key]))
                    elif key not in removals_set: new_lost.append(item)
                p.inventory.items_lost = new_lost

                new_used = []
                for i, item in enumerate(p.inventory.items_used):
                    key = (sid, "use", i)
                    if key in corrections_map: new_used.append(InventoryItem(**corrections_map[key]))
                    elif key not in removals_set: new_used.append(item)
                p.inventory.items_used = new_used

                new_checks = []
                for i, item in enumerate(p.inventory.inventory_checks):
                    key = (sid, "check", i)
                    if key in corrections_map: new_checks.append(InventoryCheck(**corrections_map[key]))
                    elif key not in removals_set: new_checks.append(item)
                p.inventory.inventory_checks = new_checks

                if sid in additions_map:
                    for a_data in additions_map[sid]:
                        action = a_data.pop("action", "add")
                        if action == "add": p.inventory.items_gained.append(InventoryItem(**a_data))
                        elif action == "remove": p.inventory.items_lost.append(InventoryItem(**a_data))
                        elif action == "use": p.inventory.items_used.append(InventoryItem(**a_data))
                        elif action == "check": p.inventory.inventory_checks.append(InventoryCheck(**a_data))

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_inventory", "done", message=f"Extracted inventory for {total_portions} portions. Total AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()