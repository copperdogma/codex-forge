import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger, log_llm_usage
from modules.common.html_utils import html_to_text
from schemas import EnrichedPortion, StatCheck, TestLuck

# --- Patterns ---

# Test Your Luck: "Test your Luck", "if you are lucky", "if you are unlucky"
LUCK_PATTERN = re.compile(r"\bTest\s+your\s+Luck\b", re.IGNORECASE)
LUCKY_PATTERN = re.compile(r"\bif\s+you\s+are\s+lucky\b.*?\bturn\s+to\s+(\d+)\b", re.IGNORECASE)
UNLUCKY_PATTERN = re.compile(r"\bif\s+you\s+are\s+unlucky\b.*?\bturn\s+to\s+(\d+)\b", re.IGNORECASE)

# Numeric word map
NUM_MAP = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract stat check mechanics and "Test Your Luck" instructions from the provided text into a JSON object.

Detect:
- stat_checks: Dice rolls compared against a stat (SKILL, LUCK, STAMINA) or specific ranges.
- test_your_luck: The standard "Test Your Luck" mechanic (lucky vs unlucky outcomes).

Rules:
- stat: The stat being checked (SKILL, LUCK, STAMINA) or null for a plain dice roll.
- dice_roll: String like "2d6" or "1d6".
- pass_condition: Logic for success (e.g., "total <= SKILL", "1-3").
- pass_section: The section ID to turn to on success.
- fail_section: The section ID to turn to on failure.

Example output:
{
  "stat_checks": [
    {
      "stat": "SKILL",
      "dice_roll": "2d6",
      "pass_condition": "total <= SKILL",
      "pass_section": "55",
      "fail_section": "202"
    }
  ],
  "test_your_luck": [
    {
      "lucky_section": "100",
      "unlucky_section": "200"
    }
  ]
}

If no mechanics are found, return {"stat_checks": [], "test_your_luck": []}."""

AUDIT_SYSTEM_PROMPT = """You are a quality assurance auditor for a Fighting Fantasy gamebook extraction pipeline.
Review the list of extracted stat checks and "Test Your Luck" mechanics.
Identify FALSE POSITIVES or logical errors (e.g., pass/fail sections reversed, non-mechanic text).

Common False Positives to flag:
- Narrative text about stats that isn't a check: "Your SKILL is 12", "Restore 2 STAMINA".
- Ambiguous dice rolls that aren't checks: "The Dwarf rolls two dice and laughs."
- Character states: "You feel lucky."

Return a JSON object with a "removals" key:
{
  "removals": [
    { "section_id": "1", "item_index": 0, "type": "stat_check", "reason": "not a check" }
  ]
}
If everything is correct, return {"removals": []}."""

# --- Logic ---

def extract_stat_checks_regex(text: str) -> Tuple[List[StatCheck], List[TestLuck]]:
    checks = []
    luck_tests = []
    
    # 1. Test Your Luck
    if LUCK_PATTERN.search(text):
        lucky_match = LUCKY_PATTERN.search(text)
        unlucky_match = UNLUCKY_PATTERN.search(text)
        if lucky_match and unlucky_match:
            luck_tests.append(TestLuck(
                lucky_section=lucky_match.group(1),
                unlucky_section=unlucky_match.group(1),
                confidence=0.7
            ))
            
    return checks, luck_tests

def extract_stat_checks_llm(text: str, model: str, client: OpenAI) -> Tuple[List[StatCheck], List[TestLuck], Dict[str, Any]]:
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
        
        checks = [StatCheck(**item, confidence=0.95) for item in data.get("stat_checks", [])]
        luck_tests = [TestLuck(**item, confidence=0.95) for item in data.get("test_your_luck", [])]
        
        return checks, luck_tests, usage
    except Exception as e:
        print(f"LLM stat check extraction error: {e}")
        return [], [], {}

def audit_stat_checks_batch(audit_list: List[Dict[str, Any]], model: str, client: OpenAI) -> List[Dict[str, Any]]:
    """Performs a global audit over all extracted stat checks to prune debris."""
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
        log_llm_usage("global_audit", "stat_check_audit", usage)
        
        data = json.loads(response.choices[0].message.content)
        return data.get("removals", [])
    except Exception as e:
        print(f"Global stat check audit error: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Extract stat checks from enriched portions.")
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
    
    CHECK_KEYWORDS = ["roll", "dice", "SKILL", "LUCK", "STAMINA", "lucky", "unlucky"]

    for idx, row in enumerate(portions):
        portion = EnrichedPortion(**row)
        text = portion.raw_text or html_to_text(portion.raw_html or "")
        
        checks, luck_tests = extract_stat_checks_regex(text)
        
        needs_ai = False
        if not checks and not luck_tests:
            if any(k.lower() in text.lower() for k in CHECK_KEYWORDS):
                needs_ai = True
        
        if needs_ai and args.use_ai and ai_calls < args.max_ai_calls:
            llm_input = text
            if len(text) < 100 and portion.raw_html:
                llm_input = f"HTML SOURCE:\n{portion.raw_html}\n\nPLAIN TEXT:\n{text}"
            
            c_ai, l_ai, usage = extract_stat_checks_llm(llm_input, args.model, client)
            ai_calls += 1
            log_llm_usage(args.run_id, "extract_stat_checks", usage)
            if c_ai or l_ai:
                checks, luck_tests = c_ai, l_ai
        
        portion.stat_checks = checks
        portion.test_luck = luck_tests
        
        sid = portion.section_id or portion.portion_id
        for i, c in enumerate(checks):
            audit_data.append({"section_id": sid, "item_index": i, "type": "stat_check", "data": c.model_dump()})
        for i, l in enumerate(luck_tests):
            audit_data.append({"section_id": sid, "item_index": i, "type": "test_luck", "data": l.model_dump()})

        out_portions.append(portion)
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_stat_checks", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    if args.use_ai and audit_data:
        logger.log("extract_stat_checks", "running", message=f"Performing global audit on {len(audit_data)} mechanics...")
        removals = audit_stat_checks_batch(audit_data, args.model, client)
        if removals:
            print(f"Global audit identified {len(removals)} false positives to remove.")
            removals_set = set() 
            for r in removals:
                removals_set.add((str(r.get("section_id")), str(r.get("type")), int(r.get("item_index"))))
            
            for p in out_portions:
                sid = str(p.section_id or p.portion_id)
                p.stat_checks = [c for i, c in enumerate(p.stat_checks) if (sid, "stat_check", i) not in removals_set]
                p.test_luck = [l for i, l in enumerate(p.test_luck) if (sid, "test_luck", i) not in removals_set]

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_stat_checks", "done", message=f"Extracted stat checks for {total_portions} portions. Total AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()