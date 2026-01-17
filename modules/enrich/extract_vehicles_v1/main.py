import argparse
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from schemas import Vehicle, EnrichedPortion

# Patterns for parsing special abilities into structured rules
REDUCE_ENEMY_SKILL_PATTERN = re.compile(
    r"reduce\s+(?:the\s+)?(?:enemy\s+)?(?:SKILL|skill)\s+of\s+(?:any\s+)?(?:enemy\s+)?(\w+)?\s+by\s+(\d+)",
    re.IGNORECASE
)
REDUCE_ENEMY_SKILL_ALT_PATTERN = re.compile(
    r"reduce\s+(?:the\s+)?(?:SKILL|skill)\s+of\s+(?:any\s+)?(?:enemy\s+)?(\w+)?\s+by\s+(\d+)",
    re.IGNORECASE
)
# More flexible pattern that handles "any enemy X" or just "X"
REDUCE_ENEMY_SKILL_FLEX_PATTERN = re.compile(
    r"reduce\s+(?:the\s+)?(?:SKILL|skill)\s+of\s+(?:any\s+)?(?:enemy\s+)?(\w+)\s+by\s+(\d+)",
    re.IGNORECASE
)
REDUCE_ENEMY_STAT_PATTERN = re.compile(
    r"reduce\s+(?:the\s+)?(?:enemy\s+)?(\w+)\s+by\s+(\d+)",
    re.IGNORECASE
)
AUTO_WIN_ROUND_PATTERN = re.compile(
    r"(?:automatically\s+)?(?:wins?|win)\s+(?:the\s+)?(?:next\s+)?(?:combat\s+)?round",
    re.IGNORECASE
)
ATTACK_ROLL_DIFFERENCE_PATTERN = re.compile(
    r"(?:attack\s+roll|roll)\s+exceeds?\s+(?:its\s+foe'?s?\s+roll|foe'?s?\s+roll)\s+by\s+(\d+)\s+or\s+more",
    re.IGNORECASE
)
ESCAPE_OVERRIDE_PATTERN = re.compile(
    r"can\s+escape\s+from\s+any\s+opponent",
    re.IGNORECASE
)
COMBAT_BONUS_CONDITIONAL_PATTERN = re.compile(
    r"(?:combat\s+bonus|bonus)\s+of\s+([\+\-]?\d+).*?(?:against|when|if)\s+(\w+)",
    re.IGNORECASE
)
OPTIONAL_ATTACK_PATTERN = re.compile(
    r"(?:can\s+try\s+to\s+strike|optional\s+attack|clumsy\s+attack)\s*\(([\+\-]?\d+)\s+to\s+(?:your\s+)?roll\)",
    re.IGNORECASE
)
BONUS_DAMAGE_PATTERN = re.compile(
    r"(?:if\s+it\s+succeeds|on\s+success).*?(?:takes?|does?)\s+(\d+)\s+points?\s+of\s+damage",
    re.IGNORECASE
)
COIL_DAMAGE_PATTERN = re.compile(
    r"(?:coil\s+around|automatically\s+does?)\s+(\d+)\s+extra\s+points?\s+of\s+damage",
    re.IGNORECASE
)
ATTACK_ROLL_THRESHOLD_PATTERN = re.compile(
    r"attack\s+roll\s+is\s+(\d+)\s+or\s+better",
    re.IGNORECASE
)
CONDITIONAL_DISABLE_PATTERN = re.compile(
    r"(?:no\s+use|useless|does\s+not\s+apply)\s+against\s+(\w+)",
    re.IGNORECASE
)

# Vehicle/robot stat block patterns
# Pattern: NAME ARMOUR X SPEED Y COMBAT BONUS Z
# Name must be at least 3 chars, start with uppercase, and be on the same line as ARMOUR
VEHICLE_STAT_PATTERN = re.compile(
    r"^([A-Z][A-Z\s\-]{2,30})\s+ARMOUR\s+(\d+)\s+SPEED\s+([A-Za-z\s]+?)(?:\s+COMBAT\s+BONUS\s+([\+\-]?\d+))?(?:\s+SPECIAL\s+ABILITIES\s*[:]?\s*(.+?))?(?=\s*<|$|\n|</p>)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL
)

# Alternative pattern: NAME followed by stats on separate lines
VEHICLE_MULTILINE_PATTERN = re.compile(
    r"\b([A-Z][A-Z\s\-]{2,})\s+(?:ROBOT|FIGHTER|VEHICLE|MACHINE)\b.*?(?:ARMOUR|armour)\s*[:]?\s*(\d+).*?(?:SPEED|speed)\s*[:]?\s*([A-Za-z\s]+?)(?:\s+COMBAT\s+BONUS\s+([\+\-]?\d+))?",
    re.IGNORECASE | re.DOTALL
)

# Context cues that indicate this is a player-acquirable vehicle
PLAYER_VEHICLE_CUES = [
    re.compile(r"\b(?:you\s+may\s+take|you\s+can\s+take|if\s+you\s+do\s+not\s+have|if\s+you\s+already\s+have|you\s+take|take\s+one\s+of\s+these)\b", re.IGNORECASE),
    re.compile(r"\b(?:you\s+may\s+choose|you\s+can\s+choose|choose\s+which|pick\s+which)\b", re.IGNORECASE),
    re.compile(r"\b(?:your\s+robot|your\s+vehicle|your\s+craft)\b", re.IGNORECASE),
]

# Context cues that indicate this is an enemy vehicle (should be ignored)
# These must be very specific - only match when clearly fighting the vehicle itself as an enemy
ENEMY_VEHICLE_CUES = [
    re.compile(r"\b(?:enemy|attacking|attacks|foe|opponent)\b.*?\b(?:robot|vehicle|craft)\b", re.IGNORECASE),
    re.compile(r"\b(?:you\s+must\s+fight\s+(?:the|this|that)\s+(?:robot|vehicle|craft)|you\s+fight\s+(?:the|this|that)\s+(?:robot|vehicle|craft)|fight\s+(?:the|this|that)\s+(?:robot|vehicle|craft))\b", re.IGNORECASE),
    re.compile(r"\b(?:if\s+you\s+(?:defeat|kill|destroy)\s+(?:the|this|that)\s+(?:robot|vehicle|craft)|if\s+(?:the|this|that)\s+(?:robot|vehicle|craft)\s+(?:defeats|kills|destroys|attacks)\s+you)\b", re.IGNORECASE),
    re.compile(r"\b(?:you\s+cannot\s+escape|you\s+must\s+fight\s+to\s+the\s+finish)\b.*?\b(?:robot|vehicle|craft)\b", re.IGNORECASE),
]

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract player vehicle/robot information from the provided text into a JSON object.

A player vehicle/robot is a vehicle, robot, or mechanism that the player can acquire and use, with its own stat set (ARMOUR, FIREPOWER, SPEED, COMBAT BONUS) distinct from the player's primary stats.

Each vehicle object MUST have:
- name: The vehicle/robot name (e.g., "COWBOY ROBOT", "WASP FIGHTER")
- type: "robot", "vehicle", "mech", or similar

Optional fields when present in text:
- armour: Integer ARMOUR value
- firepower: Integer FIREPOWER value (if present)
- speed: String speed rating (e.g., "Slow", "Medium", "Fast", "Very Fast")
- combat_bonus: Integer combat bonus (may be positive or negative, e.g., +1, -2, 0)
- special_abilities: Text description of special abilities

Return a JSON object with a "vehicle" key:
{
  "vehicle": {
    "name": "COWBOY ROBOT",
    "type": "robot",
    "armour": 10,
    "speed": "Medium",
    "combat_bonus": 0,
    "special_abilities": null
  }
}

If no player vehicle is found, return {"vehicle": null}.

IMPORTANT: Only extract vehicles that the player can acquire/use. Do NOT extract enemy vehicles (those are handled by combat extraction). Look for context cues like "You may take", "If you do not have a robot", "You may choose", etc."""

def _is_player_vehicle(text: str) -> bool:
    """Check if text describes a player-acquirable vehicle (not an enemy)."""
    text_lower = text.lower()
    
    # Check for enemy vehicle cues first - if found, definitely not a player vehicle
    for pattern in ENEMY_VEHICLE_CUES:
        if pattern.search(text):
            return False
    
    # Check for explicit player vehicle cues
    for pattern in PLAYER_VEHICLE_CUES:
        if pattern.search(text):
            return True
    
    # If no enemy cues found and we have vehicle stats, check for implicit acquisition context
    # Look for phrases that suggest the player can use/acquire this vehicle
    implicit_cues = [
        re.compile(r"\b(?:you\s+must\s+choose|you\s+can|you\s+may|if\s+you\s+want|if\s+you\s+would\s+prefer)\b", re.IGNORECASE),
        re.compile(r"\b(?:turn\s+to.*?instead|change\s+your\s+mind)\b", re.IGNORECASE),  # "turn to X instead" suggests choice
    ]
    
    for pattern in implicit_cues:
        if pattern.search(text):
            return True
    
    # If we have vehicle stats and no enemy cues, and the text doesn't mention combat/fighting,
    # assume it's a player vehicle (default to extracting rather than missing)
    if "fight" not in text_lower and "combat" not in text_lower and "battle" not in text_lower:
        # Check if it's clearly not an enemy (no "you must fight" or "attacking" language)
        if not any(cue.search(text) for cue in ENEMY_VEHICLE_CUES):
            return True
    
    return False


def _parse_combat_bonus(bonus_str: Optional[str]) -> Optional[int]:
    """Parse combat bonus string like '+1', '-2', '0' into integer."""
    if not bonus_str:
        return None
    bonus_str = bonus_str.strip()
    if bonus_str.startswith('+'):
        try:
            return int(bonus_str[1:])
        except ValueError:
            return None
    try:
        return int(bonus_str)
    except ValueError:
        return None


def _extract_vehicle_regex(text: str, raw_html: Optional[str] = None) -> Optional[Vehicle]:
    """Extract vehicle stats using regex patterns."""
    # Try primary pattern first - search line by line for better accuracy
    # Create a pattern without the ^ anchor for line-by-line matching
    # Special abilities pattern should capture until end of paragraph or next stat/choice
    # Use non-greedy match but extend to end of paragraph
    line_pattern = re.compile(
        r"([A-Z][A-Z\s\-]{2,30})\s+ARMOUR\s+(\d+)\s+SPEED\s+([A-Za-z\s]+?)(?:\s+COMBAT\s+BONUS\s+([\+\-]?\d+))?(?:\s+SPECIAL\s+ABILITIES\s*[:]?\s*(.+?))?(?=\s*</p>|\s*<p>|\s*<a\s+href|$)",
        re.IGNORECASE | re.DOTALL
    )
    
    match = None
    for line in text.split('\n'):
        line_match = line_pattern.search(line)
        if line_match:
            # Verify the name starts at the beginning of the line or after whitespace
            name_start = line_match.start(1)
            line_before_name = line[:name_start].strip()
            # If there's significant text before the name, it might be a false match
            if len(line_before_name) > 10:
                continue
            match = line_match
            break
    
    if not match:
        # Try multiline pattern on full text
        match = VEHICLE_MULTILINE_PATTERN.search(text)
    
    if not match:
        return None
    
    name = match.group(1).strip()
    # Clean up name - remove any leading/trailing lowercase words that might have been captured
    # Split and take only words that are mostly uppercase
    name_words = name.split()
    cleaned_words = []
    for word in name_words:
        # Keep if it's mostly uppercase or is a known vehicle word
        word_upper_ratio = len([c for c in word if c.isupper()]) / len(word) if word else 0
        if word.isupper() or word_upper_ratio >= 0.5 or word.upper() in ['ROBOT', 'FIGHTER', 'VEHICLE', 'MODEL', 'D', 'VII', 'CRAB', 'TANK']:
            cleaned_words.append(word)
        elif not cleaned_words:
            # If we haven't started collecting, skip lowercase words
            continue
        else:
            # Once we've started, stop at first lowercase word
            break
    if cleaned_words:
        name = ' '.join(cleaned_words).strip()
    else:
        # If cleaning removed everything, use original but validate
        name = name.strip()
    armour = int(match.group(2)) if match.group(2) else None
    speed = match.group(3).strip() if match.group(3) else None
    combat_bonus_str = match.group(4) if len(match.groups()) > 3 and match.group(4) else None
    special_abilities = match.group(5).strip() if len(match.groups()) > 4 and match.group(5) else None
    
    combat_bonus = _parse_combat_bonus(combat_bonus_str)
    
    # Infer type from name
    vehicle_type = "robot"
    name_lower = name.lower()
    if "fighter" in name_lower or "flyer" in name_lower or "air" in name_lower:
        vehicle_type = "vehicle"
    elif "robot" in name_lower:
        vehicle_type = "robot"
    elif "vehicle" in name_lower or "car" in name_lower:
        vehicle_type = "vehicle"
    
    # Clean up special abilities - extract full text and remove narrative trailing text
    if special_abilities:
        # If we got special abilities from regex but it might be truncated, try to get full text from HTML
        if raw_html and len(special_abilities) < 150:
            # Likely truncated, try to extract full text from HTML
            from modules.common.html_utils import html_to_text
            html_text = html_to_text(raw_html)
            # Look for SPECIAL ABILITIES: and extract everything until next paragraph or end
            sa_full_pattern = re.compile(
                r'SPECIAL\s+ABILITIES\s*[:]?\s*(.+?)(?=\s*</p>|\s*<p>|\s*<a\s+href|$)',
                re.IGNORECASE | re.DOTALL
            )
            match_full = sa_full_pattern.search(html_text)
            if match_full:
                full_text = match_full.group(1).strip()
                # Remove any trailing narrative text that's not part of special abilities
                # Stop at common narrative transitions (these indicate end of special abilities)
                narrative_cues = [
                    r'\s*You may take.*$',
                    r'\s*If you (?:do not have|already have|want|would prefer|like).*$',
                    r'\s*Turn to \d+.*$',
                    r'\s*Return to \d+.*$',
                    r'\s*Now (?:you|turn to).*$',
                    r'\s*What will you do.*$',
                ]
                for cue in narrative_cues:
                    full_text = re.sub(cue, '', full_text, flags=re.IGNORECASE)
                if len(full_text.strip()) > len(special_abilities.strip()):
                    special_abilities = full_text.strip()
        
        # Clean up whitespace
        special_abilities = re.sub(r'\s+', ' ', special_abilities).strip()
        
        # Check if it's actually "None"
        if special_abilities.lower() in ("none", "n/a", "na", ""):
            special_abilities = None
        else:
            # Remove any trailing narrative that might have been captured
            # Look for sentence boundaries that indicate narrative start (but be careful not to remove valid special ability text)
            # Only remove if it's clearly narrative (e.g., "You may take", "Turn to", etc.)
            # Be very specific - don't remove sentences that are part of special abilities
            narrative_start = re.search(
                r'\.\s+(?:You may take|If you (?:do not have|already have|want|would prefer|like)|Turn to \d+|Return to \d+|Now (?:you|turn to)|What will you do)',
                special_abilities,
                re.IGNORECASE
            )
            if narrative_start:
                # Keep only up to the last complete sentence before narrative starts
                pos = narrative_start.start()
                # Find the last sentence boundary before this
                last_period = special_abilities.rfind('.', 0, pos)
                if last_period > 0:
                    # Only truncate if we're sure it's narrative, not part of special abilities
                    # Check if the text before the match looks like special ability continuation
                    before_match = special_abilities[max(0, pos-50):pos].lower()
                    # If it contains special ability keywords, don't truncate
                    if not any(word in before_match for word in ['weapon', 'robot', 'attack', 'damage', 'bonus', 'skill', 'armour', 'special', 'ability']):
                        special_abilities = special_abilities[:last_period + 1].strip()
    
    # Parse special abilities into structured rules and modifiers
    # Only parse if we have special abilities text
    rules, modifiers = _extract_vehicle_abilities(special_abilities) if special_abilities else ([], [])
    
    return Vehicle(
        name=name,
        type=vehicle_type,
        armour=armour,
        speed=speed,
        combat_bonus=combat_bonus,
        special_abilities=special_abilities,
        rules=rules if rules else None,  # Keep None for empty lists (schema allows None)
        modifiers=modifiers if modifiers else None,  # Keep None for empty lists (schema allows None)
        confidence=0.9
    )


def _extract_vehicle_llm(text: str, model: str, client: OpenAI) -> Tuple[Optional[Vehicle], Optional[Dict[str, Any]]]:
    """Extract vehicle using LLM."""
    if not client:
        return None, None
    
    prompt = f"{SYSTEM_PROMPT}\n\nText to analyze:\n{text}"
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        
        usage = {
            "model": model,
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        }
        
        content = response.choices[0].message.content
        if not content:
            return None, usage
        
        data = json.loads(content)
        vehicle_data = data.get("vehicle")
        
        if not vehicle_data:
            return None, usage
        
        return Vehicle(**vehicle_data), usage
        
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return None, None


def _extract_vehicle_abilities(special_abilities: Optional[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract structured rules and modifiers from vehicle special abilities text.
    Similar to _extract_combat_rules() in extract_combat_v1.
    
    Returns:
        Tuple of (rules, modifiers) where:
        - rules: List of structured rule objects (e.g., escape_override, auto_win_round)
        - modifiers: List of stat change modifiers (e.g., reduce enemy SKILL)
    """
    if not special_abilities:
        return [], []
    
    rules: List[Dict[str, Any]] = []
    modifiers: List[Dict[str, Any]] = []
    text = special_abilities.lower()
    
    # 1. Escape override rules
    if ESCAPE_OVERRIDE_PATTERN.search(special_abilities):
        rules.append({
            "kind": "escape_override",
            "allows_escape_from": ["Very Fast"]  # Can escape from faster opponents
        })
    
    # 2. Auto-win round conditions
    if AUTO_WIN_ROUND_PATTERN.search(special_abilities):
        # Check for attack roll difference condition
        diff_match = ATTACK_ROLL_DIFFERENCE_PATTERN.search(special_abilities)
        if diff_match:
            threshold = int(diff_match.group(1))
            rules.append({
                "kind": "auto_win_round",
                "condition": {
                    "kind": "attack_roll_difference",
                    "operator": "gte",
                    "value": threshold
                }
            })
        else:
            # Generic auto-win (may need more context)
            rules.append({
                "kind": "auto_win_round"
            })
        # Also check for "automatically wins the next combat round" - this is the effect
        if "automatically wins the next combat round" in special_abilities.lower():
            # This is already captured by auto_win_round, but we can add a note
            pass
    
    # 3. Stat modifications (reduce enemy SKILL/stat)
    # Try patterns in order, stop at first match to avoid duplicates
    skill_reduced = False
    for pattern in [REDUCE_ENEMY_SKILL_PATTERN, REDUCE_ENEMY_SKILL_ALT_PATTERN, REDUCE_ENEMY_SKILL_FLEX_PATTERN]:
        match = pattern.search(special_abilities)
        if match:
            enemy_type = match.group(1) if match.group(1) else None
            amount = int(match.group(2))
            modifier = {
                "kind": "stat_change",
                "stat": "enemy_skill",
                "amount": -amount,
                "scope": "combat",
                "reason": "vehicle special ability"
            }
            # Determine enemy type condition from context
            if enemy_type and enemy_type.lower() in ["dinosaur", "robot"]:
                modifier["condition"] = {"enemy_type": enemy_type.lower()}
            # Check for conditional text in the sentence
            elif "dinosaur" in special_abilities.lower() and "robot" in special_abilities.lower():
                # Check which one the reduction applies to - look at text around the match
                match_text = special_abilities[max(0, match.start()-30):match.end()+50].lower()
                if "dinosaur" in match_text:
                    modifier["condition"] = {"enemy_type": "dinosaur"}
                elif "robot" in match_text and "no use" not in match_text:
                    modifier["condition"] = {"enemy_type": "robot"}
            elif "dinosaur" in special_abilities.lower():
                modifier["condition"] = {"enemy_type": "dinosaur"}
            elif "robot" in special_abilities.lower() and "no use" in special_abilities.lower():
                # "no use against robots" means it doesn't apply to robots, so it applies to others
                # Don't add condition - applies to all non-robots
                pass
            modifiers.append(modifier)
            skill_reduced = True
            break  # Only match once
    
    # 4. Conditional combat bonus (e.g., "Against flying foes, COMBAT BONUS of +3")
    # First try "against X foes" pattern
    against_match = re.search(r"against\s+(\w+)\s+foes?.*?(?:combat\s+bonus|bonus)\s+of\s+([\+\-]?\d+)", special_abilities, re.IGNORECASE)
    if not against_match:
        # Try "COMBAT BONUS of X against Y" pattern
        bonus_match = COMBAT_BONUS_CONDITIONAL_PATTERN.search(special_abilities)
        if bonus_match:
            bonus_amount = _parse_combat_bonus(bonus_match.group(1))
            condition_type = bonus_match.group(2).lower() if bonus_match.group(2) else None
            if bonus_amount and condition_type:
                modifiers.append({
                    "kind": "stat_change",
                    "stat": "combat_bonus",
                    "amount": bonus_amount,
                    "scope": "combat",
                    "condition": {"enemy_type": condition_type},
                    "reason": "vehicle special ability"
                })
    else:
        condition_type = against_match.group(1).lower()
        bonus_amount = _parse_combat_bonus(against_match.group(2))
        if bonus_amount:
            modifiers.append({
                "kind": "stat_change",
                "stat": "combat_bonus",
                "amount": bonus_amount,
                "scope": "combat",
                "condition": {"enemy_type": condition_type},
                "reason": "vehicle special ability"
            })
    
    # 5. Optional attack with penalty/bonus damage
    opt_attack_match = OPTIONAL_ATTACK_PATTERN.search(special_abilities)
    if opt_attack_match:
        penalty = _parse_combat_bonus(opt_attack_match.group(1))
        damage_match = BONUS_DAMAGE_PATTERN.search(special_abilities)
        bonus_damage = int(damage_match.group(1)) if damage_match else None
        
        rules.append({
            "kind": "optional_attack",
            "modifier": penalty,
            "on_success": {"damage": bonus_damage} if bonus_damage else None
        })
    
    # 6. Coil/automatic damage (Serpent VII pattern)
    coil_match = COIL_DAMAGE_PATTERN.search(special_abilities)
    if coil_match:
        damage = int(coil_match.group(1))
        threshold_match = ATTACK_ROLL_THRESHOLD_PATTERN.search(special_abilities)
        threshold = int(threshold_match.group(1)) if threshold_match else None
        
        rule = {
            "kind": "automatic_damage",
            "damage": damage,
        }
        if threshold:
            rule["condition"] = {
                "kind": "attack_roll_threshold",
                "operator": "gte",
                "value": threshold
            }
        # Check for "does not apply to flying foes"
        if "does not apply" in special_abilities.lower() or "flying" in special_abilities.lower():
            if "flying" in special_abilities.lower():
                rule["condition"] = rule.get("condition", {})
                rule["condition"]["exclude_enemy_type"] = "flying"
        rules.append(rule)
    
    # 7. Conditional disable (no use against certain types)
    disable_match = CONDITIONAL_DISABLE_PATTERN.search(special_abilities)
    if disable_match:
        disabled_against = disable_match.group(1).lower() if disable_match.group(1) else None
        if disabled_against and disabled_against not in ["other", "others"]:
            rules.append({
                "kind": "conditional_disable",
                "condition": {"enemy_type": disabled_against},
                "effect": "disabled"
            })
    
    return rules, modifiers


def _validate_vehicle(vehicle: Optional[Vehicle]) -> bool:
    """Validate extracted vehicle data."""
    if not vehicle:
        return True  # No vehicle is valid
    
    # Must have a name
    if not vehicle.name or len(vehicle.name.strip()) < 3:
        return False
    
    # Reject names that look like sentence fragments (contain common words at start)
    name_lower = vehicle.name.lower().strip()
    bad_start_words = ['you', 'see', 'it', 'is', 'actually', 'but', 'willing', 'try', 'turn', 'aside', 
                      'leave', 'your', 'own', 'best', 'have', 'been', 'able', 'find', 'battered', 'old',
                      'farm', 'the', 'a', 'an', 'this', 'that', 'these', 'those', 'if', 'when']
    # Check if name starts with a bad word or contains multiple bad words (likely a fragment)
    words = name_lower.split()
    if words and words[0] in bad_start_words:
        return False
    if len([w for w in words if w in bad_start_words]) > 2:
        return False
    
    # Name should be mostly uppercase or have proper capitalization (not all lowercase)
    if name_lower == vehicle.name.lower() and len([c for c in vehicle.name if c.isupper()]) < 2:
        return False
    
    # Should have at least one stat
    if not any([vehicle.armour is not None, vehicle.firepower is not None, vehicle.speed]):
        return False
    
    # Armour should be reasonable (1-50)
    if vehicle.armour is not None and (vehicle.armour < 1 or vehicle.armour > 50):
        return False
    
    # Firepower should be reasonable (1-20)
    if vehicle.firepower is not None and (vehicle.firepower < 1 or vehicle.firepower > 20):
        return False
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Extract player vehicles/robots from enriched portions.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--out", required=True, help="Output enriched_portion_v1 JSONL")
    parser.add_argument("--pages", help="Input page_html_blocks_v1 JSONL (for driver compatibility; not used)")
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
    
    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text
        if not text and portion.raw_html:
            text = html_to_text(portion.raw_html)
        if not text:
            text = ""
        
        vehicle = None
        
        # 1. TRY: Regex attempt
        if text:
            vehicle = _extract_vehicle_regex(text, portion.raw_html)
        
        # 2. VALIDATE: Check if this is a player vehicle (not enemy)
        if vehicle:
            # Reject if text has SKILL stat (enemies have SKILL, player vehicles don't)
            if "SKILL" in text.upper() and ("ARMOUR" in text.upper() or "STAMINA" in text.upper()):
                # This is likely an enemy, not a player vehicle
                vehicle = None
            elif not _is_player_vehicle(text):
                vehicle = None  # Likely an enemy vehicle, skip it
        
        # 3. VALIDATE: Check data quality
        is_valid = _validate_vehicle(vehicle)
        
        # 4. ESCALATE: LLM fallback if regex missed something or validation failed
        needs_ai = False
        if not is_valid:
            needs_ai = True
        elif not vehicle:
            # Check if text mentions vehicle stats but regex missed the block
            upper_text = text.upper()
            if "ARMOUR" in upper_text and "SPEED" in upper_text:
                # Check if it's a player vehicle context
                if _is_player_vehicle(text):
                    needs_ai = True
        
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            vehicle_llm, usage = _extract_vehicle_llm(text, args.model, client)
            ai_calls += 1
            if vehicle_llm and _validate_vehicle(vehicle_llm):
                # Parse special abilities for LLM-extracted vehicle too
                if vehicle_llm.special_abilities:
                    llm_rules, llm_modifiers = _extract_vehicle_abilities(vehicle_llm.special_abilities)
                    vehicle_llm.rules = llm_rules if llm_rules else None
                    vehicle_llm.modifiers = llm_modifiers if llm_modifiers else None
                vehicle = vehicle_llm
        
        portion.vehicle = vehicle
        out_portions.append(portion.model_dump(exclude_none=True))

        if (idx + 1) % 50 == 0:
            logger.log("extract_vehicles", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    save_jsonl(args.out, out_portions)
    logger.log("extract_vehicles", "done", message=f"Extracted vehicles for {total_portions} portions. Total AI calls: {ai_calls}", artifact=args.out)

if __name__ == "__main__":
    main()
