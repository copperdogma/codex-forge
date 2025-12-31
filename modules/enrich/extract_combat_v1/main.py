import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from schemas import Combat, EnrichedPortion

# Common Fighting Fantasy combat patterns
# Stat block pattern: NAME followed by SKILL and STAMINA (sometimes on new lines)
STAT_BLOCK_PATTERN = re.compile(r"\b([A-Z][A-Z\s\-]{2,})\s+(?:SKILL|skill)\s*[:]?\s*(\d+)\s*(?:STAMINA|stamina)\s*[:]?\s*(\d+)", re.MULTILINE)
# Table-like or separated pattern
SEP_STAT_PATTERN = re.compile(r"(?:SKILL|skill)\s*[:]?\s*(\d+).*?(?:STAMINA|stamina)\s*[:]?\s*(\d+)", re.IGNORECASE | re.DOTALL)
WIN_PATTERN = re.compile(r"if\s+you\s+win,\s+turn\s+to\s+(\d+)", re.IGNORECASE)
LOSS_PATTERN = re.compile(r"if\s+you\s+lose,\s+turn\s+to\s+(\d+)", re.IGNORECASE)
ESCAPE_PATTERN = re.compile(r"if\s+you\s+wish\s+to\s+escape,\s+turn\s+to\s+(\d+)", re.IGNORECASE)
ESCAPE_FLEX_PATTERN = re.compile(r"\bescape\b.{0,80}?\bturn\s+to\s+(\d+)", re.IGNORECASE | re.DOTALL)
SPECIAL_RULE_PATTERN = re.compile(
    r"(reduce\s+your\s+(?:attack\s+strength|skill)\s+by\s+\d+[^.]*?)",
    re.IGNORECASE
)

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract combat encounter information from the provided text into a JSON list of enemies.
The text may contain multiple enemies, sometimes in a table-like format with columns for SKILL and STAMINA.

Each enemy object in the returned list MUST have:
- name: The creature's name (e.g., "ORC", "SKELETON", "First ORC")
- skill: SKILL score (integer)
- stamina: STAMINA score (integer)
- win_section: The section to turn to if the player wins (string, if mentioned)
- loss_section: The section to turn to if the player loses (string, if mentioned)
- escape_section: The section to turn to if the player escapes (string, if mentioned)
- special_rules: Any special combat rules mentioned (e.g., "Fight them one at a time", "-2 SKILL penalty")

Return a JSON object with a "combat" key containing the list:
{
  "combat": [
    {
      "name": "SKELETON WARRIOR",
      "skill": 8,
      "stamina": 6,
      "win_section": "71"
    }
  ]
}

If no combat is found, return {"combat": []}."""

def extract_combat_regex(text: str) -> List[Combat]:
    combats = []
    
    # Find all stat blocks
    matches = STAT_BLOCK_PATTERN.finditer(text)
    
    # Try to find common outcomes
    win_match = WIN_PATTERN.search(text)
    loss_match = LOSS_PATTERN.search(text)
    escape_match = ESCAPE_PATTERN.search(text) or ESCAPE_FLEX_PATTERN.search(text)
    special_rule_match = SPECIAL_RULE_PATTERN.search(text)
    special_rules = special_rule_match.group(1).strip() if special_rule_match else None
    
    win_section = win_match.group(1) if win_match else None
    loss_section = loss_match.group(1) if loss_match else None
    escape_section = escape_match.group(1) if escape_match else None
    
    for match in matches:
        enemy_name = match.group(1).strip()
        skill = int(match.group(2))
        stamina = int(match.group(3))
        
        combats.append(Combat(
            enemy=enemy_name,
            skill=skill,
            stamina=stamina,
            win_section=win_section,
            loss_section=loss_section,
            escape_section=escape_section,
            special_rules=special_rules,
            confidence=0.9
        ))
        
    if not combats:
        # Second pass: look for separated stats
        sep_matches = SEP_STAT_PATTERN.finditer(text)
        for match in sep_matches:
            # For separated stats, we might not have the name easily via regex
            # But we can capture the stats and let AI fill the rest if needed, 
            # or just mark as 'Unknown' for now to trigger AI escalation via validate_combat
            skill = int(match.group(1))
            stamina = int(match.group(2))
            combats.append(Combat(
                enemy="Unknown",
                skill=skill,
                stamina=stamina,
                win_section=win_section,
                loss_section=loss_section,
                escape_section=escape_section,
                special_rules=special_rules,
                confidence=0.5
            ))
            
    return combats

def extract_combat_llm(text: str, model: str, client: OpenAI) -> Tuple[List[Combat], Dict[str, Any]]:
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
        
        # Expecting a list under "combat" or just a list
        raw_list = data.get("combat") if isinstance(data, dict) and "combat" in data else data
        if not isinstance(raw_list, list):
            raw_list = []
            
        combats = []
        for item in raw_list:
            if ("name" in item or "enemy" in item) and "skill" in item and "stamina" in item:
                combats.append(Combat(
                    enemy=item.get("enemy") or item.get("name"),
                    skill=int(item.get("skill")),
                    stamina=int(item.get("stamina")),
                    win_section=str(item.get("win_section")) if item.get("win_section") else None,
                    loss_section=str(item.get("loss_section")) if item.get("loss_section") else None,
                    escape_section=str(item.get("escape_section")) if item.get("escape_section") else None,
                    special_rules=item.get("special_rules"),
                    confidence=0.95
                ))
        return combats, usage
    except Exception as e:
        print(f"LLM extraction error: {e}")
        return [], {}

# Normal ranges for Fighting Fantasy stats (generous to include bosses)
MIN_SKILL = 1
MAX_SKILL = 15
MIN_STAMINA = 1
MAX_STAMINA = 40

def validate_combat(combats: List[Combat]) -> bool:
    """Returns True if all extracted combats look realistic."""
    if not combats:
        return True # Empty is valid if no combat present
    
    for c in combats:
        if not c.enemy or not c.skill or not c.stamina:
            return False
        if not (MIN_SKILL <= c.skill <= MAX_SKILL):
            return False
        if not (MIN_STAMINA <= c.stamina <= MAX_STAMINA):
            return False
    return True

def main():
    parser = argparse.ArgumentParser(description="Extract combat encounters from enriched portions.")
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
    
    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text
        if not text and portion.raw_html:
            text = html_to_text(portion.raw_html)
        if not text:
            text = ""
        
        # 1. TRY: Regex attempt
        combats = extract_combat_regex(text)
        
        # 2. VALIDATE
        is_valid = validate_combat(combats)
        
        # 3. ESCALATE: LLM fallback if regex missed something, validation failed, 
        # or for complex cases (multiple enemies, special rules).
        
        needs_ai = False
        if not is_valid:
            needs_ai = True
        elif any(c.enemy == "Unknown" for c in combats):
            needs_ai = True
        elif not combats:
            # Check if text mentions SKILL or STAMINA but regex missed the block
            upper_text = text.upper()
            if "SKILL" in upper_text and "STAMINA" in upper_text:
                needs_ai = True
        elif len(combats) > 1 or "special" in text.lower() or "rules" in text.lower():
            # Multiple enemies or mentions of rules might need LLM to parse correctly
            needs_ai = True
            
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            # If plain text is empty or very short, use HTML for better context (tables)
            llm_input = text
            if len(text) < 50 and portion.raw_html:
                llm_input = f"HTML SOURCE:\n{portion.raw_html}\n\nPLAIN TEXT:\n{text}"
            
            combats_llm, usage = extract_combat_llm(llm_input, args.model, client)
            ai_calls += 1
            if combats_llm:
                combats = combats_llm
        
        portion.combat = combats
        out_portions.append(portion.model_dump(exclude_none=True))
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_combat", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    save_jsonl(args.out, out_portions)
    logger.log("extract_combat", "done", message=f"Extracted combat for {total_portions} portions. Total AI calls: {ai_calls}", artifact=args.out)

if __name__ == "__main__":
    main()
