import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger, log_llm_usage
from modules.common.html_utils import html_to_text
from schemas import EnrichedPortion, StatModification

# --- Patterns ---

# Loose patterns to detect potential stat changes and trigger AI
MOD_KEYWORDS = ["lose", "gain", "reduce", "increase", "restore", "add", "deduct", "subtract", "SKILL", "STAMINA", "LUCK"]

# Specific regex for common deterministic cases
REDUCE_PATTERN = re.compile(r"\b(?:lose|reduce|deduct|subtract)\s+(?:your\s+)?(.*?)\s+by\s+(\d+)\b", re.IGNORECASE)
LOSE_PATTERN = re.compile(r"\b(?:lose|deduct)\s+(\d+)\s+(.*?)\b", re.IGNORECASE)
GAIN_PATTERN = re.compile(r"\b(?:gain|increase|restore|add)\s+(?:your\s+)?(.*?)\s+by\s+(\d+)\b", re.IGNORECASE)
GAIN_VAL_PATTERN = re.compile(r"\b(?:gain|restore|add)\s+(\d+)\s+(.*?)\b", re.IGNORECASE)

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract stat modifications (SKILL, STAMINA, LUCK) from the provided text into a JSON object.

Detect:
- stat: \"skill\", \"stamina\", or \"luck\" (normalized to lowercase).
- amount: The integer amount of change (positive for gains/restoration, negative for losses).
- permanent: Whether the change affects the INITIAL value (e.g., \"reduce your initial Skill\"). Default false.

Rules:
- Ignore narrative mentions that aren't modifications (e.g., \"Your Skill is 12\").
- \"Restore\" or \"Gain\" are positive. \"Lose\" or \"Reduce\" are negative.
- Handle implicit amounts (e.g., \"Lose a Luck point\" -> amount: -1).

Example output:
{
  \"stat_modifications\": [
    { \"stat\": \"skill\", \"amount\": -1, \"permanent\": false },
    { \"stat\": \"stamina\", \"amount\": 4, \"permanent\": false }
  ]
}

If no modifications are found, return {\"stat_modifications\": []}."""

AUDIT_SYSTEM_PROMPT = """You are a quality assurance auditor for a Fighting Fantasy gamebook extraction pipeline.
I will provide a list of extracted stat modifications along with the source text for each section.
Your job is to:
1. Identify FALSE POSITIVES (narrative text that isn't a stat change).
2. Identify INCORRECT VALUES (e.g., text says \"reduce by 1d6 + 1\" but extraction says \"-1\").
3. Identify MISSING modifications that were in the text but not the list.

Common Issues:
- Text says \"Roll one die, add 1... reduce STAMINA by total\" -> amount should be \"-(1d6+1)\".
- Narrative mentions like \"Your Stamina is now 4\" are NOT modifications.

Return a JSON object with \"removals\" (to delete), \"corrections\" (to update), and \"additions\" (to add).
{
  \"removals\": [
    { \"section_id\": \"1\", \"item_index\": 0, \"reason\": \"narrative mention\" }
  ],
  \"corrections\": [
    { \"section_id\": \"16\", \"item_index\": 0, \"data\": { \"stat\": \"stamina\", \"amount\": \"-(1d6+1)\", \"permanent\": false } }
  ],
  \"additions\": []
}
If everything is correct, return {\"removals\": [], \"corrections\": [], \"additions\": []}."""

# --- Logic ---

def normalize_stat(name: str) -> Optional[str]:
    name = name.lower()
    if "skill" in name: return "skill"
    if "stamina" in name: return "stamina"
    if "luck" in name: return "luck"
    return None

def extract_stat_modifications_regex(text: str) -> List[StatModification]:
    mods = []
    # Very simple regex attempt; most extraction will rely on AI due to phrasing variety
    for match in REDUCE_PATTERN.finditer(text):
        stat = normalize_stat(match.group(1))
        if stat:
            mods.append(StatModification(stat=stat, amount=-int(match.group(2)), confidence=0.7))
            
    for match in LOSE_PATTERN.finditer(text):
        stat = normalize_stat(match.group(2))
        if stat:
            mods.append(StatModification(stat=stat, amount=-int(match.group(1)), confidence=0.7))
            
    return mods

def extract_stat_modifications_llm(text: str, model: str, client: OpenAI) -> Tuple[List[StatModification], Dict[str, Any]]:
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
        
        data = json.loads(response.choices[0].message.content)
        mods = [StatModification(**item, confidence=0.95) for item in data.get("stat_modifications", [])]
        
        return mods, usage
    except Exception as e:
        print(f"LLM stat modification extraction error: {e}")
        return [], {}

def audit_stat_modifications_batch(audit_list: List[Dict[str, Any]], model: str, client: OpenAI, run_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Performs a global audit over all extracted stat modifications to prune debris."""
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
        log_llm_usage(run_id, "stat_mod_audit", usage)
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Global stat modification audit error: {e}")
        return {"removals": [], "corrections": [], "additions": []}

def main():
    parser = argparse.ArgumentParser(description="Extract stat modifications from enriched portions.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--pages", help="Input page_html_blocks_v1 JSONL")
    parser.add_argument("--out", required=True, help="Output enriched_portion_v1 JSONL")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--use-ai", "--use_ai", action="store_true", default=True)
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

    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text or html_to_text(portion.raw_html or "")
        
        # 1. TRY: Regex
        mods = extract_stat_modifications_regex(text)
        
        # 2. ESCALATE
        needs_ai = False
        if not mods:
            if any(k.lower() in text.lower() for k in MOD_KEYWORDS):
                needs_ai = True
        
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            llm_input = text
            if len(text) < 100 and portion.raw_html:
                llm_input = f"HTML SOURCE:\n{portion.raw_html}\n\nPLAIN TEXT:\n{text}"
            
            m_ai, usage = extract_stat_modifications_llm(llm_input, args.model, client)
            ai_calls += 1
            log_llm_usage(args.run_id, "extract_stat_modifications", usage)
            if m_ai:
                mods = m_ai
        
        portion.stat_modifications = mods
        
        sid = portion.section_id or portion.portion_id
        # Include text in audit data for context!
        audit_data.append({
            "section_id": sid, 
            "text": text[:500], # Provide snippet for context
            "mods": [m.model_dump() for m in mods]
        })

        out_portions.append(portion)
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_stat_modifications", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    # 3. BATCH AUDIT (Global)
    if args.use_ai and audit_data:
        logger.log("extract_stat_modifications", "running", message=f"Performing global audit on {len(audit_data)} sections...")
        audit_results = audit_stat_modifications_batch(audit_data, args.model, client, args.run_id)
        
        removals = audit_results.get("removals", [])
        corrections = audit_results.get("corrections", [])
        additions = audit_results.get("additions", [])

        if removals or corrections or additions:
            print(f"Global audit identified {len(removals)} removals, {len(corrections)} corrections, and {len(additions)} additions.")
            
            # Map by section ID for easy access
            removals_map = {}
            for r in removals:
                removals_map.setdefault(str(r.get("section_id")), set()).add(int(r.get("item_index")))
            
            corrections_map = {}
            for c in corrections:
                corrections_map.setdefault(str(c.get("section_id")), {})[int(c.get("item_index"))] = c.get("data")
            
            additions_map = {}
            for a in additions:
                additions_map.setdefault(str(a.get("section_id")), []).append(a.get("data"))

            for p in out_portions:
                sid = str(p.section_id or p.portion_id)
                # Apply corrections
                if sid in corrections_map:
                    for idx, new_data in corrections_map[sid].items():
                        if idx < len(p.stat_modifications):
                            p.stat_modifications[idx] = StatModification(**new_data)
                
                # Apply removals
                if sid in removals_map:
                    p.stat_modifications = [m for i, m in enumerate(p.stat_modifications) if i not in removals_map[sid]]
                
                # Apply additions
                if sid in additions_map:
                    if not p.stat_modifications:
                        p.stat_modifications = []
                    for a_data in additions_map[sid]:
                        p.stat_modifications.append(StatModification(**a_data))

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_stat_modifications", "done", message=f"Extracted stat modifications for {total_portions} portions. AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()