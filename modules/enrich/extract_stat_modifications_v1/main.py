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
- stat: "skill", "stamina", or "luck" (normalized to lowercase).
- amount: The integer amount of change (positive for gains/restoration, negative for losses).
- permanent: Whether the change affects the INITIAL value (e.g., "reduce your initial Skill"). Default false.

Rules:
- Ignore narrative mentions that aren't modifications (e.g., "Your Skill is 12").
- "Restore" or "Gain" are positive. "Lose" or "Reduce" are negative.
- Handle implicit amounts (e.g., "Lose a Luck point" -> amount: -1).

Example output:
{
  "stat_modifications": [
    { "stat": "skill", "amount": -1, "permanent": false },
    { "stat": "stamina", "amount": 4, "permanent": false }
  ]
}

If no modifications are found, return {"stat_modifications": []}."""

AUDIT_SYSTEM_PROMPT = """You are a quality assurance auditor for a Fighting Fantasy gamebook extraction pipeline.
Review the list of extracted stat modifications.
Identify FALSE POSITIVES—entries that are NOT valid stat changes.

Common False Positives:
- Current state mentions: "Your Stamina is now 4".
- Conditional checks: "If your Stamina is 4 or less".
- Combat damage (already handled elsewhere): "The creature hits you for 2 Stamina".
- Abstract concepts: "Lose your nerve".

Return a JSON object with a "removals" key:
{
  "removals": [
    { "section_id": "1", "item_index": 0, "reason": "narrative mention" }
  ]
}
If everything is correct, return {"removals": []}."""

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

def audit_stat_modifications_batch(audit_list: List[Dict[str, Any]], model: str, client: OpenAI, run_id: str) -> List[Dict[str, Any]]:
    if not audit_list:
        return []
    
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
        
        data = json.loads(response.choices[0].message.content)
        return data.get("removals", [])
    except Exception as e:
        print(f"Global stat modification audit error: {e}")
        return []

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
        for i, m in enumerate(mods):
            audit_data.append({"section_id": sid, "item_index": i, "data": m.model_dump()})

        out_portions.append(portion)
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_stat_modifications", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    # 3. BATCH AUDIT (Global)
    if args.use_ai and audit_data:
        logger.log("extract_stat_modifications", "running", message=f"Performing global audit on {len(audit_data)} modifications...")
        removals = audit_stat_modifications_batch(audit_data, args.model, client, args.run_id)
        if removals:
            print(f"Global audit identified {len(removals)} false positives to remove.")
            removals_set = set()
            for r in removals:
                removals_set.add((str(r.get("section_id")), int(r.get("item_index"))))
            
            for p in out_portions:
                sid = str(p.section_id or p.portion_id)
                p.stat_modifications = [m for i, m in enumerate(p.stat_modifications) if (sid, i) not in removals_set]

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_stat_modifications", "done", message=f"Extracted stat modifications for {total_portions} portions. AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()
