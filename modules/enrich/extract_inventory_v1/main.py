import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from modules.common.turn_to_claims import merge_turn_to_claims
from schemas import EnrichedPortion, InventoryItem, InventoryCheck, InventoryEnrichment, InventoryState, TurnToLinkClaimInline

# --- Patterns ---

GAIN_PATTERNS = [
    re.compile(r"\byou\s+(?:find|take|pick\s+up|gain|receive|get)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\badd\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+to\s+your\s+backpack\b", re.IGNORECASE),
    re.compile(r"\b(.*?)\s+is\s+yours\b", re.IGNORECASE),
    re.compile(r"\bseize\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bput\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+in\s+your\s+pocket\b", re.IGNORECASE),
    re.compile(r"\bputting\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+in\s+your\s+pocket\b", re.IGNORECASE),
    re.compile(
        r"\b(?:cupboard|chest|box|bag|pouch|backpack|pack|sack|casket|cabinet|drawer|container)\s+contains\s+"
        r"(?:the\s+|a\s+|an\s+|some)?(.*?)(?:\.|$|\bturn\b)",
        re.IGNORECASE,
    ),
]

LOSE_PATTERNS = [
    re.compile(r"\byou\s+(?:lose|drop|discard|remove)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\byou\s+take\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+out\s+of\s+your\s+(?:backpack|pack|bag)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+taken\s+from\s+you\b", re.IGNORECASE),
]

USE_PATTERNS = [
    re.compile(r"\byou\s+(?:use|drink|eat)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\.|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\busing\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\s+to\b|\s+for\b|\.|$|\band\b|\bturn\b)", re.IGNORECASE),
]

CHECK_PATTERNS = [
    re.compile(r"\bif\s+you\s+(?:have|possess|are\s+carrying)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:,|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bif\s+you\s+(?:do\s+not\s+have|have\s+not)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:,|$|\bturn\b)", re.IGNORECASE),
    re.compile(r"\bif\s+(?:the\s+|a\s+|an\s+)?(.*?)\s+is\s+in\s+your\s+backpack\b", re.IGNORECASE),
]

QUANTITY_PATTERN = re.compile(r"^(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(.*)", re.IGNORECASE)

NUM_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
}

POSSESSIONS_LOSE_PATTERNS = [
    re.compile(r"\ball\s+your\s+possessions\s+(?:are\s+)?lost\b", re.IGNORECASE),
    re.compile(r"\byour\s+possessions\s+(?:are\s+)?lost\b", re.IGNORECASE),
    re.compile(r"\bstripped\s+of\s+(?:all\s+)?your\s+possessions\b", re.IGNORECASE),
    re.compile(r"\bdeprived\s+of\s+(?:all\s+)?your\s+possessions\b", re.IGNORECASE),
    re.compile(r"\b(?:all\s+)?your\s+possessions\s+(?:have\s+been\s+)?(?:taken|confiscated)\b", re.IGNORECASE),
]

POSSESSIONS_RESTORE_PATTERNS = [
    re.compile(r"\bthe\s+rest\s+of\s+your\s+possessions\s+are\s+here\b", re.IGNORECASE),
    re.compile(r"\ball\s+your\s+possessions\s+are\s+here\b", re.IGNORECASE),
    re.compile(r"\byour\s+possessions\s+are\s+here\b", re.IGNORECASE),
    re.compile(r"\byou\s+(?:recover|retrieve|regain|find|collect|gather|get\s+back)\s+(?:the\s+rest\s+of\s+|all\s+of\s+)?your\s+possessions\b", re.IGNORECASE),
    re.compile(r"\byour\s+possessions\s+(?:are\s+)?returned\b", re.IGNORECASE),
]


def _coerce_turn_to_claims(raw_claims: Optional[List[Any]]) -> List[TurnToLinkClaimInline]:
    if not raw_claims:
        return []
    return [
        TurnToLinkClaimInline(**c) if isinstance(c, dict) else c
        for c in raw_claims
    ]


def _extract_possessions_states(text: str) -> List[InventoryState]:
    if not text:
        return []
    lower = text.lower()
    if "possessions" not in lower:
        return []
    states: List[InventoryState] = []
    if any(p.search(text) for p in POSSESSIONS_LOSE_PATTERNS):
        states.append(InventoryState(action="lose_all", scope="possessions", confidence=0.8))
    if any(p.search(text) for p in POSSESSIONS_RESTORE_PATTERNS):
        states.append(InventoryState(action="restore_all", scope="possessions", confidence=0.8))
    return states


def _inventory_state_from_item(action: str, item_name: Optional[str], confidence: float = 0.7) -> Optional[InventoryState]:
    if not item_name:
        return None
    name = _clean_item_name(item_name).lower().strip()
    if name != "possessions":
        return None
    if action == "add":
        return InventoryState(action="restore_all", scope="possessions", confidence=confidence)
    if action == "remove":
        return InventoryState(action="lose_all", scope="possessions", confidence=confidence)
    return None

ADD_VERBS = [
    "find", "found", "take", "took", "pick up", "picked up", "pick", "grab", "grabbed", "seize", "seized",
    "collect", "collected", "receive", "received", "get", "got", "gain", "gained",
    "keep", "kept", "pocket", "put", "place", "add", "buy", "bought", "acquire", "acquired",
    "there is", "there are", "lying", "inside", "inside you find"
]
USE_VERBS = ["use", "using", "drink", "drank", "eat", "ate", "consume", "consumed", "quaff", "swallow"]
LOSE_VERBS = ["lose", "lost", "drop", "dropped", "discard", "discarded", "remove", "removed", "throw", "threw", "give", "gave", "leave", "left"]

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract inventory-related actions from the provided text into a JSON object.
Detect:
- items_gained: Items the player finds or receives.
- items_lost: Items the player loses, drops, or has taken away.
- items_used: Items the player uses or consumes (potions, keys).
- inventory_checks: Conditional checks on item possession.
- inventory_states: Whole-inventory events such as losing or restoring all Possessions.

IMPORTANT RULES:
- Only extract PHYSICAL objects (keys, potions, gold, weapons, etc.).
- DO NOT extract abstract concepts like "time", "aim", "balance", "luck", "yourself", "not done so already".
- DO NOT extract sentences or fragments like "not done so already", "any left", "if you have not".
- DO NOT extract phrases like "you find yourself in a chamber" or "you take a deep breath".
- Item names should be clean and concise (e.g., "Silver Key", not "the rusty silver key you found").
- quantity should be an integer or the string "all".
- Do NOT treat "Possessions" as a literal item. Instead, emit inventory_states with action "lose_all" or "restore_all".

Example output:
{
  "inventory": {
    "items_gained": [{"item": "Gold Pieces", "quantity": 10}],
    "items_lost": [{"item": "Rope", "quantity": 1}],
    "items_used": [{"item": "Potion of Strength", "quantity": 1}],
    "inventory_checks": [{"item": "Lantern", "condition": "if you have", "target_section": "43"}],
    "inventory_states": [{"action": "lose_all", "scope": "possessions"}]
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

def _clean_item_name(name: str) -> str:
    cleaned = name.strip()
    lowered = cleaned.lower()
    if lowered.startswith("of "):
        cleaned = cleaned[3:]
    for prefix in ("there is ", "there are "):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    for prefix in ("a ", "an ", "the ", "some ", "your ", "his ", "her ", "their ", "my ", "its "):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    cleaned = re.sub(r"^you\s+(?:recognize|see|notice|spot|find)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\w+'s\s+", "", cleaned).strip()
    cleaned = re.sub(r"\b(which|that)\s+you\s+may\s+take\s+with\s+you.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bwhich\s+you\s+(?:put|place|tuck)\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\b(which|that)\s+you\s+(?:start|begin|try|attempt|decide)\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bif\s+you\s+(?:wish|want).*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bmay be of use\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bmay be useful\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bout\s+of\s+(?:your|the)\s+(?:backpack|pack|bag).*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bin\s+(?:your|the)\s+(?:backpack|pack|bag).*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\blying\s+in.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bwith\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bby\b.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bis\s+hanging.*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\band\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bup\s+again\b$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\bagain\b$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.strip()


def _split_item_list(name: Optional[str]) -> List[str]:
    if not name:
        return []
    stop_verbs = {
        "search", "look", "open", "continue", "return", "head", "leave", "walk",
        "set", "go", "move", "follow", "decide", "turn", "throw", "tumble", "dive",
        "hurl", "aim", "grab", "press", "squeeze",
        "run", "rush", "hurry", "climb", "jump", "fight", "attack",
    }
    normalized = name.replace(" and ", ", ")
    parts = [p.strip() for p in normalized.split(",") if p.strip()]
    cleaned = []
    for part in parts:
        tokens = part.lower().split()
        if tokens and tokens[0] in stop_verbs:
            break
        cleaned.append(_clean_item_name(part))
    return [c for c in cleaned if c]

def _is_bad_item_name(name: Optional[str], action: Optional[str] = None) -> bool:
    if not name:
        return True
    lower = name.lower().strip(" .,?!()")
    if not lower or len(lower) < 3:
        return True
    bad_words = {
        "it", "them", "him", "her", "some", "none", "your", "his", "their", "my",
        "yourself", "himself", "herself", "not", "already", "any left", "one",
        "aim", "balance", "time", "luck", "note", "message", "done so already",
        "closer", "nearer", "farther"
    }
    if lower in bad_words:
        return True
    if "yourself" in lower:
        return True
    if "done so already" in lower:
        return True
    if re.search(r"\bpool\b", lower):
        return True
    if re.search(r"\bgrip\b", lower):
        return True
    if "crack in" in lower:
        return True
    if re.search(r"\bboulder\b", lower):
        return True
    if "off your" in lower or "off the" in lower:
        return True
    if "tear it" in lower or lower.startswith("tear "):
        return True
    if any(word in lower for word in ("stamina", "skill", "luck", "points")):
        return True
    if action == "add" and lower.startswith("broken "):
        return True
    if lower == "possessions":
        return True
    if any(phrase in lower for phrase in ("find yourself", "yourself in", "deep breath", "take a look", "quick look",
                                          "do not see", "see anybody", "tumble", "throw", "dive", "hurl", "aim",
                                          "which you put", "which you place", "which you tuck",
                                          "it is ", "it was ", "glued to", "up-river", "downriver")):
        return True
    if "danger" in lower:
        return True
    if re.search(r"\bfor\s+\d+\s+(?:day|days|hour|hours|week|weeks)\b", lower):
        return True
    if any(word in lower for word in ("until finally", "arrive", "journey", "passage")):
        return True
    if action == "add" and lower.startswith("your "):
        return True
    if "turn to" in lower or "?" in lower:
        return True
    return False

def _item_mentioned(text: str, item: str) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name in lower:
        return True
    if name.endswith("s") and name[:-1] in lower:
        return True
    if name.endswith("es") and name[:-2] in lower:
        return True
    return False


def _item_near_verbs(text: str, item: str, verbs: List[str]) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name not in lower:
        return False
    for m in re.finditer(re.escape(name), lower):
        window = lower[max(0, m.start() - 40):m.end() + 40]
        for v in verbs:
            pattern = r"\b" + re.escape(v).replace(r"\ ", r"\s+") + r"\b"
            if not re.search(pattern, window):
                continue
            if verbs is USE_VERBS and "using the other" in window:
                continue
            if verbs is USE_VERBS and "using your other" in window:
                continue
            if verbs is USE_VERBS and "using the other hand" in window:
                continue
            return True
    return False


def _item_in_choice_prompt(text: str, item: str) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name not in lower:
        return False
    for m in re.finditer(re.escape(name), lower):
        before = lower[max(0, m.start() - 80):m.start()]
        after = lower[m.end():m.end() + 80]
        window = before + after
        if "turn to" in window and ("?" in after):
            return True
        if "turn to" in window and ("if you wish" in before or "if you want" in before or "if you decide" in before or "if you choose" in before or "will you" in before):
            return True
    return False


def _item_optional_if_wish(text: str, item: str) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name not in lower:
        return False
    for m in re.finditer(re.escape(name), lower):
        before = lower[max(0, m.start() - 80):m.start()]
        if "inside" in before and "you find" in before:
            return False
        if "if you wish" in before or "if you want" in before or "if you would rather" in before:
            if any(verb in before for verb in ("take", "keep", "carry", "with you")):
                return True
        after = lower[m.end():m.end() + 80]
        if "if you wish" in after or "if you want" in after or "if you would rather" in after:
            if any(verb in after for verb in ("take", "keep", "carry", "with you")):
                return True
    return False


def _item_only_in_choice_prompt(text: str, item: str) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name not in lower:
        return False
    occurrences = list(re.finditer(re.escape(name), lower))
    if not occurrences:
        return False
    for match in occurrences:
        before = lower[max(0, match.start() - 80):match.start()]
        after = lower[match.end():match.end() + 80]
        window = before + after
        in_choice = (
            "turn to" in window
            and ("?" in after or "if you wish" in before or "if you want" in before or
                 "if you decide" in before or "if you choose" in before or "will you" in before)
        )
        if not in_choice:
            return False
    return True


def _item_given_without_storage(text: str, item: str) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name not in lower or "given" not in lower:
        return False
    for m in re.finditer(re.escape(name), lower):
        window = lower[max(0, m.start() - 80):m.end() + 80]
        if "given" not in window:
            continue
        if any(verb in window for verb in (
            "put it in your", "putting it in your", "put it into your",
            "place it in your", "tuck it in your", "pocket it",
            "add it to your backpack", "add it to your pack", "take it with you",
            "carry it", "keep it", "pack it away"
        )):
            return False
        return True
    return False


def _item_has_explicit_if(text: str, item: str) -> bool:
    lower = text.lower()
    name = item.lower().strip()
    if name not in lower:
        return False
    pattern = re.compile(
        rf"if you (?:have|have not|do not have|possess|are carrying)\s+(?:the|a|an|some|your)?\s*{re.escape(name)}",
        re.IGNORECASE,
    )
    return pattern.search(lower) is not None


def _is_allowed_check_condition(condition: Optional[str]) -> bool:
    if not condition:
        return True
    lower = condition.strip().lower()
    return lower.startswith(("if you have", "if you do not have", "if you possess", "if you are carrying", "is in your backpack"))


def _keep_removed_item(text: str, item: str, action: str) -> bool:
    if not text or not item:
        return False
    if action == "add":
        return (
            _item_mentioned(text, item)
            and _item_near_verbs(text, item, ADD_VERBS)
            and not _item_given_without_storage(text, item)
            and not _item_only_in_choice_prompt(text, item)
        )
    if action == "remove":
        return _item_near_verbs(text, item, LOSE_VERBS)
    if action == "use":
        return _item_near_verbs(text, item, USE_VERBS) and not _item_only_in_choice_prompt(text, item)
    if action == "check":
        return _item_has_explicit_if(text, item)
    return False


def _allow_audit_addition(text: str, item: str) -> bool:
    if not text or not item:
        return False
    return (
        _item_near_verbs(text, item, ADD_VERBS)
        and not _item_given_without_storage(text, item)
        and not _item_only_in_choice_prompt(text, item)
    )

def _parse_item_text(text: str) -> Tuple[Optional[str], int]:
    text = text.strip()
    if not text:
        return None, 1
    
    text_lower = text.lower()
    if text_lower in {
        "it", "them", "him", "her", "some", "none", "your", "his", "their", "my", 
        "yourself", "himself", "herself", "not", "not done so already", "already", "one",
        "possessions"
    }:
        return None, 1

    if text_lower.startswith("nothing except") or text_lower.startswith("nothing but"):
        parts = re.split(r"\bnothing\s+(?:except|but)\b", text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) > 1:
            text = parts[1].strip()
            text = re.sub(r"^for\s+", "", text, flags=re.IGNORECASE).strip()
            text_lower = text.lower()
        if not text:
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
            return _clean_item_name(item), int(qty_str)
        return _clean_item_name(item), NUM_MAP.get(qty_str, 1)
    return _clean_item_name(text), 1

def extract_inventory_regex(text: str) -> InventoryEnrichment:
    gained = []
    lost = []
    used = []
    checks = []
    inventory_states: List[InventoryState] = []

    STRICT_ITEMS = ["gold pieces", "provisions", "potion", "key", "rope", "spike", "mallet", "shield", "sword"]
    BAD_ITEM_WORDS = {"other", "message", "note"}
    KEYWORDS = [
        "backpack", "gold pieces", "potion", "item", "possess", "carrying",
        "you find", "you take", "you pick up", "you gain", "you receive", "you get",
        "you lose", "you drop", "you discard", "you remove", "you use", "you drink", "you eat",
        "if you have", "have you got", "seize", "putting", "put in your pocket", "pocket",
    ]
    lower_text = text.lower()
    if not any(k in lower_text for k in KEYWORDS):
        if not any(k in lower_text for k in STRICT_ITEMS):
            return InventoryEnrichment()

    inventory_states = _extract_possessions_states(text)

    for pattern in GAIN_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                if any(phrase in item_text.lower() for phrase in ("out of your backpack", "out of your pack", "out of your bag")):
                    continue
                name, qty = _parse_item_text(item_text)
                if name and name.lower().strip(" .,?!()") not in BAD_ITEM_WORDS and not _is_bad_item_name(name, "add"):
                    items = _split_item_list(name) or [name]
                    for idx, item_name in enumerate(items):
                        if not item_name or len(item_name) >= 40 or _is_bad_item_name(item_name, "add"):
                            continue
                        part_name, part_qty = _parse_item_text(item_name)
                        if not part_name or _is_bad_item_name(part_name, "add"):
                            continue
                        item_qty = part_qty if idx > 0 else qty if qty else part_qty
                        gained.append(InventoryItem(item=part_name, quantity=item_qty, confidence=0.7))

    for pattern in LOSE_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                name, qty = _parse_item_text(item_text)
                if name and name.lower().strip(" .,?!()") not in BAD_ITEM_WORDS and not _is_bad_item_name(name, "remove"):
                    items = _split_item_list(name) or [name]
                    for idx, item_name in enumerate(items):
                        if not item_name or len(item_name) >= 40 or _is_bad_item_name(item_name, "remove"):
                            continue
                        part_name, part_qty = _parse_item_text(item_name)
                        if not part_name or _is_bad_item_name(part_name, "remove"):
                            continue
                        item_qty = part_qty if idx > 0 else qty if qty else part_qty
                        lost.append(InventoryItem(item=part_name, quantity=item_qty, confidence=0.7))

    for pattern in USE_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                raw_match = match.group(0).lower()
                if "using the other" in raw_match or "using your other" in raw_match:
                    continue
                if "if you" in raw_match or "wish to" in raw_match or "if you wish" in raw_match:
                    continue
                name, qty = _parse_item_text(item_text)
                if name and name.lower().strip(" .,?!()") not in BAD_ITEM_WORDS and not _is_bad_item_name(name, "use"):
                    items = _split_item_list(name) or [name]
                    for idx, item_name in enumerate(items):
                        if not item_name or len(item_name) >= 40 or _is_bad_item_name(item_name, "use"):
                            continue
                        part_name, part_qty = _parse_item_text(item_name)
                        if not part_name or _is_bad_item_name(part_name, "use"):
                            continue
                        item_qty = part_qty if idx > 0 else qty if qty else part_qty
                        used.append(InventoryItem(item=part_name, quantity=item_qty, confidence=0.7))

    for pattern in CHECK_PATTERNS:
        for match in pattern.finditer(text):
            item_text = match.group(1)
            if item_text:
                raw_match = match.group(0).lower()
                if "do not have" in raw_match or "have not" in raw_match:
                    condition = "if you do not have"
                elif "if you have" in raw_match: condition = "if you have"
                elif "if you possess" in raw_match: condition = "if you possess"
                elif "if you are carrying" in raw_match: condition = "if you are carrying"
                elif "is in your backpack" in raw_match: condition = "is in your backpack"
                else: condition = "item check"
                tail = text[match.end():match.end() + 120]
                target_match = re.search(r"turn\s+to\s+(\d+)", tail, re.IGNORECASE)
                target_section = target_match.group(1) if target_match else None
                name, _ = _parse_item_text(item_text)
                if name:
                    if name.lower().startswith("not "):
                        name = name[4:].strip()
                if name and len(name) < 90 and not _is_bad_item_name(name):
                    checks.append(InventoryCheck(item=name, condition=condition, target_section=target_section, confidence=0.7))
    if checks:
        neg_match = re.search(r"if\s+you\s+(?:do\s+not\s+have|have\s+not)\b.*?turn\s+to\s+(\d+)", text, re.IGNORECASE | re.DOTALL)
        if neg_match and not any((c.condition or "").lower().startswith("if you do not have") for c in checks):
            checks.append(InventoryCheck(item=checks[0].item, condition="if you do not have", target_section=neg_match.group(1), confidence=0.7))
        else_match = re.search(r"\bif\s+you\s+do\s+not\b.*?turn\s+to\s+(\d+)", text, re.IGNORECASE | re.DOTALL)
        if else_match and not any((c.condition or "").lower().startswith("if you do not have") for c in checks):
            checks.append(InventoryCheck(item=checks[0].item, condition="if you do not have", target_section=else_match.group(1), confidence=0.7))
    question_match = re.search(r"\bhave\s+you\s+(?:got|have)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\?|\.|$)", text, re.IGNORECASE)
    question_item = None
    if question_match:
        q_item_text = question_match.group(1)
        q_name, _ = _parse_item_text(q_item_text)
        if q_name and not _is_bad_item_name(q_name):
            question_item = q_name
    verb_question_match = re.search(
        r"\bhave\s+you\s+(?:read|drunk|swallowed|used|eaten)\s+(?:the\s+|a\s+|an\s+)?(.*?)(?:\?|\.|$)",
        text,
        re.IGNORECASE,
    )
    if verb_question_match:
        q_item_text = verb_question_match.group(1)
        q_name, _ = _parse_item_text(q_item_text)
        if q_name and not _is_bad_item_name(q_name):
            if not question_item or len(q_name) > len(question_item):
                question_item = q_name
    pronoun_items = {
        "it", "them", "these", "those", "these items", "those items",
        "this book", "read this book", "this poem", "read this poem", "the poem",
        "drunk it", "swallowed this potion", "swallowed it", "this potion", "drunk this potion",
    }
    anchor_item = question_item
    if not anchor_item and checks:
        anchor_candidates = []
        for c in checks:
            item_lower = (c.item or "").lower()
            if "book" in item_lower or "potion" in item_lower:
                if len(item_lower) >= 12:
                    anchor_candidates.append(c.item)
        if anchor_candidates:
            anchor_item = max(anchor_candidates, key=len)
    if not anchor_item and checks:
        anchor_candidates = []
        for c in checks:
            item_lower = (c.item or "").lower().strip()
            if not item_lower or item_lower in pronoun_items:
                continue
            anchor_candidates.append(c.item)
        if anchor_candidates:
            anchor_item = max(anchor_candidates, key=len)
    if anchor_item:
        has_match = re.search(r"\bif\s+you\s+have\b(?!\s+not).*?turn\s+to\s+(\d+)", text, re.IGNORECASE | re.DOTALL)
        not_match = re.search(r"\bif\s+you\s+have\s+not\b.*?turn\s+to\s+(\d+)", text, re.IGNORECASE | re.DOTALL)
        if has_match:
            checks.append(InventoryCheck(item=anchor_item, condition="if you have", target_section=has_match.group(1), confidence=0.7))
        if not_match:
            checks.append(InventoryCheck(item=anchor_item, condition="if you do not have", target_section=not_match.group(1), confidence=0.7))
        for c in checks:
            item_lower = (c.item or "").lower().strip()
            if item_lower.startswith("not "):
                item_lower = item_lower[4:].strip()
            if item_lower in pronoun_items:
                c.item = anchor_item
    if checks:
        seen = set()
        deduped = []
        for c in checks:
            key = ((c.item or "").lower().strip(), c.condition, c.target_section)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        checks = deduped

    if gained:
        gained = [g for g in gained if not _item_only_in_choice_prompt(text, g.item) and not _item_optional_if_wish(text, g.item)]
    if lost:
        lost = [l for l in lost if not _item_only_in_choice_prompt(text, l.item)]

    if not gained and re.search(r"\bput\s+it\s+in\s+your\s+(?:backpack|pack|bag)\b", text, re.IGNORECASE):
        prior = text[:re.search(r"\bput\s+it\s+in\s+your\s+(?:backpack|pack|bag)\b", text, re.IGNORECASE).start()]
        noun_match = None
        for m in re.finditer(
            r"\b(?:prise|pry|pull|remove|take|lift|pick\s+up|pick|grab|retrieve|collect|extract|draw)\s+"
            r"(?:loose|out|free)?\s*"
            r"(?:the|a|an|\b\w+'s)\s+([A-Za-z][A-Za-z\-\' ]{2,60})",
            prior,
            re.IGNORECASE,
        ):
            noun_match = m
        if not noun_match:
            for m in re.finditer(r"(?:the|a|an|your|his|her|their|my|its|\b\w+'s)\s+([A-Za-z][A-Za-z\-\' ]{2,60})", prior, re.IGNORECASE):
                noun_match = m
        if noun_match:
            candidate = _clean_item_name(noun_match.group(1))
            if candidate and not _is_bad_item_name(candidate, "add"):
                gained.append(InventoryItem(item=candidate, quantity=1, confidence=0.6))
    if not gained and re.search(r"\bput\s+them\s+in\s+your\s+(?:backpack|pack|bag)\b", text, re.IGNORECASE):
        prior = text[:re.search(r"\bput\s+them\s+in\s+your\s+(?:backpack|pack|bag)\b", text, re.IGNORECASE).start()]
        noun_match = None
        for m in re.finditer(r"([A-Za-z][A-Za-z\- ]{1,40}eyes)", prior, re.IGNORECASE):
            noun_match = m
        if not noun_match:
            for m in re.finditer(r"(?:the|a|an|your|his|her|their|my|its|\b\w+'s)\s+([A-Za-z][A-Za-z\-\' ]{2,60})", prior, re.IGNORECASE):
                noun_match = m
        if noun_match:
            candidate = _clean_item_name(noun_match.group(1))
            if candidate and not _is_bad_item_name(candidate, "add"):
                gained.append(InventoryItem(item=candidate, quantity=1, confidence=0.6))
    
    if inventory_states:
        gained = [g for g in gained if g.item.lower().strip() != "possessions"]
        lost = [l for l in lost if l.item.lower().strip() != "possessions"]
        used = [u for u in used if u.item.lower().strip() != "possessions"]

    return InventoryEnrichment(
        items_gained=gained,
        items_lost=lost,
        items_used=used,
        inventory_checks=checks,
        inventory_states=inventory_states,
    )

def validate_inventory(inv: InventoryEnrichment) -> bool:
    """Returns True if the inventory data looks sane."""
    BLACK_LIST = {
        "time", "aim", "balance", "luck", "yourself", "not", "already", 
        "not done so already", "done so already", "any left", "one", 
        "some", "none", "not done so already)?", "it", "other", "message", "note"
    }
    
    all_items = inv.items_gained + inv.items_lost + inv.items_used
    for item in all_items:
        name_lower = item.item.lower().strip(" .,?!()")
        if not name_lower or len(name_lower) < 3:
            return False
        if name_lower in BLACK_LIST:
            return False
        if any(word in name_lower for word in ("stamina", "skill", "luck", "points")):
            return False
        if "turn to" in name_lower or "?" in name_lower:
            return False
        if name_lower == "possessions":
            return False
        if len(name_lower) > 50:
            return False
            
    for check in inv.inventory_checks:
        name_lower = check.item.lower().strip(" .,?!()")
        if not name_lower or len(name_lower) < 3:
            return False
        if name_lower in BLACK_LIST:
            return False
        if any(word in name_lower for word in ("stamina", "skill", "luck", "points")):
            return False
        if "turn to" in name_lower or "?" in name_lower:
            return False
        if name_lower == "possessions":
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
        def _maybe_possessions_state(item_name: Optional[str], action: str) -> Optional[InventoryState]:
            if not item_name:
                return None
            name = _clean_item_name(item_name).lower().strip()
            if name != "possessions":
                return None
            if action == "add":
                return InventoryState(action="restore_all", scope="possessions", confidence=0.95)
            if action == "remove":
                return InventoryState(action="lose_all", scope="possessions", confidence=0.95)
            return None

        inventory_states: List[InventoryState] = []

        gained = [
            InventoryItem(item=_clean_item_name(item.get("item")), quantity=parse_qty(item.get("quantity")), confidence=0.95)
            for item in inv_data.get("items_gained", [])
            if item.get("item")
            and not _is_bad_item_name(_clean_item_name(item.get("item")), "add")
            and _item_mentioned(text, item.get("item"))
            and _item_near_verbs(text, item.get("item"), ADD_VERBS)
            and not _item_given_without_storage(text, item.get("item"))
            and not _item_only_in_choice_prompt(text, item.get("item"))
            and not _item_optional_if_wish(text, item.get("item"))
        ]
        lost = [
            InventoryItem(item=_clean_item_name(item.get("item")), quantity=parse_qty(item.get("quantity")), confidence=0.95)
            for item in inv_data.get("items_lost", [])
            if item.get("item")
            and not _is_bad_item_name(_clean_item_name(item.get("item")), "remove")
            and _item_mentioned(text, item.get("item"))
            and _item_near_verbs(text, item.get("item"), LOSE_VERBS)
            and not _item_only_in_choice_prompt(text, item.get("item"))
        ]
        used = [
            InventoryItem(item=_clean_item_name(item.get("item")), quantity=parse_qty(item.get("quantity")), confidence=0.95)
            for item in inv_data.get("items_used", [])
            if item.get("item")
            and not _is_bad_item_name(_clean_item_name(item.get("item")), "use")
            and _item_mentioned(text, item.get("item"))
            and _item_near_verbs(text, item.get("item"), USE_VERBS)
            and not _item_only_in_choice_prompt(text, item.get("item"))
        ]
        checks = [
            InventoryCheck(
                item=_clean_item_name(item.get("item")), 
                condition=item.get("condition") or "if you have", 
                target_section=str(item.get("target_section")) if item.get("target_section") else None,
                confidence=0.95
            ) 
            for item in inv_data.get("inventory_checks", [])
            if item.get("item")
            and not _is_bad_item_name(_clean_item_name(item.get("item")))
            and _item_mentioned(text, item.get("item"))
            and _item_has_explicit_if(text, item.get("item"))
            and _is_allowed_check_condition(item.get("condition"))
        ]

        for state in inv_data.get("inventory_states", []):
            if not isinstance(state, dict):
                continue
            action = state.get("action")
            scope = state.get("scope") or "possessions"
            if action in {"lose_all", "restore_all"}:
                inventory_states.append(InventoryState(action=action, scope=scope, confidence=0.95))

        for item in inv_data.get("items_gained", []):
            state = _maybe_possessions_state(item.get("item"), "add")
            if state:
                inventory_states.append(state)
        for item in inv_data.get("items_lost", []):
            state = _maybe_possessions_state(item.get("item"), "remove")
            if state:
                inventory_states.append(state)

        gained = [g for g in gained if g.item.lower().strip() != "possessions"]
        lost = [l for l in lost if l.item.lower().strip() != "possessions"]
        used = [u for u in used if u.item.lower().strip() != "possessions"]

        return InventoryEnrichment(
            items_gained=gained,
            items_lost=lost,
            items_used=used,
            inventory_checks=checks,
            inventory_states=inventory_states,
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
    text_by_section: Dict[str, str] = {}
    
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
        text_by_section[str(sid)] = text

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
                    if key in corrections_map:
                        data = corrections_map.get(key)
                        if isinstance(data, dict) and data.get("item") and _item_mentioned(text_by_section.get(sid, ""), data.get("item")):
                            state = _inventory_state_from_item("add", data.get("item"), confidence=data.get("confidence", 0.7))
                            if state:
                                p.inventory.inventory_states.append(state)
                            else:
                                new_gained.append(InventoryItem(**data))
                        elif key not in removals_set:
                            new_gained.append(item)
                    elif key in removals_set:
                        text = text_by_section.get(sid, "")
                        if _keep_removed_item(text, item.item, "add"):
                            new_gained.append(item)
                    else:
                        new_gained.append(item)
                p.inventory.items_gained = new_gained

                new_lost = []
                for i, item in enumerate(p.inventory.items_lost):
                    key = (sid, "remove", i)
                    if key in corrections_map:
                        data = corrections_map.get(key)
                        text = text_by_section.get(sid, "")
                        if (
                            isinstance(data, dict)
                            and data.get("item")
                            and _item_mentioned(text, data.get("item"))
                            and _item_near_verbs(text, data.get("item"), LOSE_VERBS)
                        ):
                            state = _inventory_state_from_item("remove", data.get("item"), confidence=data.get("confidence", 0.7))
                            if state:
                                p.inventory.inventory_states.append(state)
                            else:
                                new_lost.append(InventoryItem(**data))
                        elif key not in removals_set:
                            new_lost.append(item)
                    elif key in removals_set:
                        text = text_by_section.get(sid, "")
                        if _keep_removed_item(text, item.item, "remove"):
                            new_lost.append(item)
                    else:
                        new_lost.append(item)
                p.inventory.items_lost = new_lost

                new_used = []
                for i, item in enumerate(p.inventory.items_used):
                    key = (sid, "use", i)
                    if key in corrections_map:
                        data = corrections_map.get(key)
                        text = text_by_section.get(sid, "")
                        if (
                            isinstance(data, dict)
                            and data.get("item")
                            and _item_mentioned(text, data.get("item"))
                            and _item_near_verbs(text, data.get("item"), USE_VERBS)
                        ):
                            new_used.append(InventoryItem(**data))
                        elif key not in removals_set:
                            new_used.append(item)
                    elif key in removals_set:
                        text = text_by_section.get(sid, "")
                        if _keep_removed_item(text, item.item, "use"):
                            new_used.append(item)
                    else:
                        new_used.append(item)
                p.inventory.items_used = new_used

                new_checks = []
                for i, item in enumerate(p.inventory.inventory_checks):
                    key = (sid, "check", i)
                    if key in corrections_map:
                        data = corrections_map.get(key)
                        if isinstance(data, dict) and data.get("item") and _item_mentioned(text_by_section.get(sid, ""), data.get("item")):
                            condition = data.get("condition") or item.condition
                            if _item_has_explicit_if(text_by_section.get(sid, ""), data.get("item")) and _is_allowed_check_condition(condition):
                                data["condition"] = condition
                                new_checks.append(InventoryCheck(**data))
                        elif key not in removals_set:
                            new_checks.append(item)
                    elif key in removals_set:
                        text = text_by_section.get(sid, "")
                        if _keep_removed_item(text, item.item, "check"):
                            new_checks.append(item)
                    else:
                        new_checks.append(item)
                p.inventory.inventory_checks = new_checks

                if sid in additions_map:
                    for a_data in additions_map[sid]:
                        if not isinstance(a_data, dict) or not a_data.get("item"):
                            continue
                        text = text_by_section.get(sid, "")
                        if not _item_mentioned(text, a_data.get("item")):
                            continue
                        action = a_data.pop("action", "add")
                        state = _inventory_state_from_item(action, a_data.get("item"), confidence=a_data.get("confidence", 0.7))
                        if state:
                            p.inventory.inventory_states.append(state)
                            continue
                        if _is_bad_item_name(a_data.get("item"), action):
                            continue
                        if action == "add":
                            if not _allow_audit_addition(text, a_data.get("item")):
                                continue
                            p.inventory.items_gained.append(InventoryItem(**a_data))
                        elif action == "remove":
                            if _item_near_verbs(text, a_data.get("item"), LOSE_VERBS):
                                p.inventory.items_lost.append(InventoryItem(**a_data))
                        elif action == "use":
                            if _item_near_verbs(text, a_data.get("item"), USE_VERBS):
                                p.inventory.items_used.append(InventoryItem(**a_data))
                        elif action == "check":
                            condition = a_data.get("condition") or "if you have"
                            if not _item_has_explicit_if(text, a_data.get("item")):
                                continue
                            if not _is_allowed_check_condition(condition):
                                continue
                            a_data["condition"] = condition
                            p.inventory.inventory_checks.append(InventoryCheck(**a_data))

                if p.inventory.inventory_checks:
                    filtered_checks = []
                    text = text_by_section.get(sid, "")
                    for item in p.inventory.inventory_checks:
                        condition = item.condition or "if you have"
                        if not _item_has_explicit_if(text, item.item):
                            continue
                        if not _is_allowed_check_condition(condition):
                            continue
                        filtered_checks.append(item)
                    p.inventory.inventory_checks = filtered_checks

    for p in out_portions:
        claims: List[Dict[str, Any]] = []
        inventory = p.inventory
        if inventory and inventory.inventory_checks:
            for idx, item in enumerate(inventory.inventory_checks):
                if item.target_section:
                    claims.append({
                        "target": str(item.target_section),
                        "claim_type": "inventory_check",
                        "module_id": "extract_inventory_v1",
                        "evidence_path": f"/inventory/inventory_checks/{idx}/target_section",
                    })
        p.turn_to_claims = merge_turn_to_claims(p.turn_to_claims, claims)
        p.turn_to_claims = _coerce_turn_to_claims(p.turn_to_claims)

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_inventory", "done", message=f"Extracted inventory for {total_portions} portions. Total AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()
