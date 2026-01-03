import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from modules.common.turn_to_claims import merge_turn_to_claims
from schemas import EnrichedPortion, StatCheck, TestLuck, TurnToLinkClaimInline

# --- Patterns ---

# Test Your Luck: "Test your Luck", "if you are lucky", "if you are unlucky"
LUCK_PATTERN = re.compile(r"\bTest\s+your\s+Luck\b", re.IGNORECASE)
LUCKY_PATTERN = re.compile(r"\bif\s+you\s+are\s+lucky\b.*?\bturn\s+to\s+(\d+)\b", re.IGNORECASE)
UNLUCKY_PATTERN = re.compile(r"\bif\s+you\s+are\s+unlucky\b.*?\bturn\s+to\s+(\d+)\b", re.IGNORECASE)

# Numeric word map
NUM_MAP = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}

ROLL_CHECK_PATTERN = re.compile(
    r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die(?:s)?|dice)"
    r".{0,160}?\b(skill|stamina|luck)\b"
    r".{0,80}?turn\s+to\s+(\d+)"
    r".{0,160}?(?:greater\s+than|more\s+than)"
    r".{0,80}?turn\s+to\s+(\d+)",
    re.IGNORECASE | re.DOTALL,
)

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
I will provide a list of extracted stat checks and "Test Your Luck" mechanics along with the source text for each section.
Your job is to identify:
1. FALSE POSITIVES: Entries that are NOT valid stat checks or mechanics.
2. INCORRECT VALUES: Incorrect pass/fail sections, stats, or conditions.
3. MISSING MECHANICS: Mechanics described in the text that were not extracted.

Common Issues to flag:
- Narrative text about stats that isn't a check: "Your SKILL is 12".
- Ambiguous dice rolls that aren't checks: "The Dwarf rolls two dice and laughs."
- Character states: "You feel lucky."

For each section, review the items and tell me which ones to REMOVE, CORRECT, or ADD.
Return a JSON object with "removals", "corrections", and "additions".
{
  "removals": [
    { "section_id": "1", "type": "stat_check", "item_index": 0, "reason": "not a check" }
  ],
  "corrections": [
    { "section_id": "18", "type": "stat_check", "item_index": 0, "data": { "stat": "SKILL", "pass_section": "55" } }
  ],
  "additions": []
}
If everything is correct, return {"removals": [], "corrections": [], "additions": []}."""

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

    roll_match = ROLL_CHECK_PATTERN.search(text)
    if roll_match:
        dice_word = roll_match.group(1).lower()
        dice_count = NUM_MAP.get(dice_word, None)
        if dice_count is None:
            dice_count = int(dice_word) if dice_word.isdigit() else 2
        stat = roll_match.group(2).upper()
        pass_section = roll_match.group(3)
        fail_section = roll_match.group(4)
        dice_roll = f"{dice_count}d6"
        checks.append(StatCheck(
            stat=stat,
            dice_roll=dice_roll,
            dice_count=dice_count,
            dice_sides=6,
            pass_condition=f"total <= {stat}",
            pass_section=pass_section,
            fail_condition=f"total > {stat}",
            fail_section=fail_section,
            confidence=0.7
        ))
            
    return checks, luck_tests

def ensure_test_luck(text: str, luck_tests: List[TestLuck]) -> List[TestLuck]:
    if luck_tests:
        return luck_tests
    if not LUCK_PATTERN.search(text):
        return luck_tests
    lucky_match = LUCKY_PATTERN.search(text)
    unlucky_match = UNLUCKY_PATTERN.search(text)
    if lucky_match and unlucky_match:
        return [TestLuck(
            lucky_section=lucky_match.group(1),
            unlucky_section=unlucky_match.group(1),
            confidence=0.7
        )]
    lower = text.lower()
    idx = lower.find("test your luck")
    if idx != -1:
        tail = text[idx:]
        turn_idx = tail.lower().find("turn to")
        if turn_idx != -1:
            window = tail[turn_idx:turn_idx + 160]
            numbers = re.findall(r"\b(\d+)\b", window)
            if len(numbers) >= 2:
                return [TestLuck(
                    lucky_section=numbers[0],
                    unlucky_section=numbers[1],
                    confidence=0.5
                )]
    return luck_tests

def _filter_stat_checks(text: str, checks: List[StatCheck]) -> List[StatCheck]:
    lower = text.lower()
    has_roll = any(k in lower for k in ("roll", "dice", "die"))
    has_test = any(k in lower for k in ("test your skill", "test your luck", "test your stamina"))
    if not (has_roll or has_test):
        return []
    return checks

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

def audit_stat_checks_batch(audit_list: List[Dict[str, Any]], model: str, client: OpenAI, run_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Performs a global audit over all extracted stat checks to prune debris."""
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
        print(f"Global stat check audit error: {e}")
        return {"removals": [], "corrections": [], "additions": []}

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
            if c_ai or l_ai:
                checks, luck_tests = c_ai, l_ai
        checks = _filter_stat_checks(text, checks)
        
        portion.stat_checks = checks
        portion.test_luck = luck_tests
        
        sid = portion.section_id or portion.portion_id
        section_mechanics = []
        for i, c in enumerate(checks): section_mechanics.append({"item_index": i, "type": "stat_check", "data": c.model_dump()})
        for i, l in enumerate(luck_tests): section_mechanics.append({"item_index": i, "type": "test_luck", "data": l.model_dump()})

        audit_data.append({
            "section_id": sid,
            "text": text[:500],
            "mechanics": section_mechanics
        })

        out_portions.append(portion)
        
        if (idx + 1) % 50 == 0:
            logger.log("extract_stat_checks", "running", current=idx+1, total=total_portions, 
                       message=f"Processed {idx+1}/{total_portions} portions (AI calls: {ai_calls})")

    if args.use_ai and audit_data:
        logger.log("extract_stat_checks", "running", message=f"Performing global audit on {len(audit_data)} sections...")
        audit_results = audit_stat_checks_batch(audit_data, args.model, client, args.run_id)
        
        removals = audit_results.get("removals", [])
        corrections = audit_results.get("corrections", [])
        additions = audit_results.get("additions", [])

        if removals or corrections or additions:
            print(f"Global audit identified {len(removals)} removals, {len(corrections)} corrections, and {len(additions)} additions.")
            
            removals_set = set()
            removals_map = {}
            for r in removals:
                item_index = r.get("item_index")
                if item_index is not None:
                    sid_r = str(r.get("section_id"))
                    removals_set.add((sid_r, str(r.get("type")), int(item_index)))
                    removals_map.setdefault(sid_r, set()).add(int(item_index))
            
            corrections_map = {}
            for c in corrections:
                item_index = c.get("item_index")
                if item_index is not None:
                    corrections_map.setdefault(str(c.get("section_id")), {})[int(item_index)] = c.get("data")
            
            additions_map = {}
            for a in additions:
                additions_map.setdefault(str(a.get("section_id")), []).append(a.get("data"))

            def _valid_str(val):
                return isinstance(val, str) and val.strip()

            def _sanitize_test_luck(data):
                if not _valid_str(data.get("lucky_section")):
                    return None
                if not _valid_str(data.get("unlucky_section")):
                    return None
                return data

            def _sanitize_stat_check(data):
                if not _valid_str(data.get("pass_section")):
                    return None
                return data

            for p in out_portions:
                sid = str(p.section_id or p.portion_id)
                
                # Apply corrections
                if sid in corrections_map:
                    for idx, new_data in corrections_map[sid].items():
                        if idx < len(p.stat_checks):
                            merged = p.stat_checks[idx].model_dump()
                            merged.update(new_data)
                            # Filter out None values for required fields before validation
                            merged = {k: v for k, v in merged.items() if v is not None or k in ["fail_section"]}
                            try:
                                p.stat_checks[idx] = StatCheck(**merged)
                            except Exception as e:
                                # Skip invalid corrections
                                print(f"Warning: Skipping invalid correction for section {sid}, index {idx}: {e}")
                                continue
                        elif idx < (len(p.stat_checks) + len(p.test_luck)):
                            l_idx = idx - len(p.stat_checks)
                            merged = p.test_luck[l_idx].model_dump()
                            merged.update(new_data)
                            merged = _sanitize_test_luck(merged)
                            if merged is None:
                                print(f"Warning: Skipping invalid luck correction for section {sid}, index {l_idx}")
                                continue
                            try:
                                p.test_luck[l_idx] = TestLuck(**merged)
                            except Exception as e:
                                print(f"Warning: Skipping invalid luck correction for section {sid}, index {l_idx}: {e}")
                                continue
                
                # Apply removals
                if sid in removals_map:
                    p.stat_checks = [m for i, m in enumerate(p.stat_checks) if (sid, "stat_check", i) not in removals_set]
                    p.test_luck = [l for i, l in enumerate(p.test_luck) if (sid, "test_luck", i) not in removals_set]
                
                # Apply additions
                if sid in additions_map:
                    for a_data in additions_map[sid]:
                        if not isinstance(a_data, dict):
                            print(f"Warning: Skipping invalid addition for section {sid}: {a_data}")
                            continue
                        is_luck = "lucky_section" in a_data and "unlucky_section" in a_data
                        if is_luck:
                            clean = _sanitize_test_luck(a_data)
                            if clean is None:
                                print(f"Warning: Skipping invalid luck addition for section {sid}")
                                continue
                            try:
                                p.test_luck.append(TestLuck(**clean))
                            except Exception as e:
                                print(f"Warning: Skipping invalid luck addition for section {sid}: {e}")
                                continue
                        elif "pass_section" in a_data:
                            clean = _sanitize_stat_check(a_data)
                            if clean is None:
                                print(f"Warning: Skipping invalid stat check addition for section {sid}")
                                continue
                            try:
                                p.stat_checks.append(StatCheck(**clean))
                            except Exception as e:
                                print(f"Warning: Skipping invalid stat check addition for section {sid}: {e}")
                                continue

    for p in out_portions:
        text = p.raw_text or html_to_text(p.raw_html or "")
        p.test_luck = ensure_test_luck(text, p.test_luck or [])

    for p in out_portions:
        claims: List[Dict[str, Any]] = []
        for idx, sc in enumerate(p.stat_checks or []):
            pass_section = sc.pass_section
            fail_section = sc.fail_section
            if pass_section:
                claims.append({
                    "target": str(pass_section),
                    "claim_type": "stat_check_pass",
                    "module_id": "extract_stat_checks_v1",
                    "evidence_path": f"/stat_checks/{idx}/pass_section",
                })
            if fail_section:
                claims.append({
                    "target": str(fail_section),
                    "claim_type": "stat_check_fail",
                    "module_id": "extract_stat_checks_v1",
                    "evidence_path": f"/stat_checks/{idx}/fail_section",
                })
        for idx, tl in enumerate(p.test_luck or []):
            lucky = tl.lucky_section
            unlucky = tl.unlucky_section
            if lucky:
                claims.append({
                    "target": str(lucky),
                    "claim_type": "test_luck_lucky",
                    "module_id": "extract_stat_checks_v1",
                    "evidence_path": f"/test_luck/{idx}/lucky_section",
                })
            if unlucky:
                claims.append({
                    "target": str(unlucky),
                    "claim_type": "test_luck_unlucky",
                    "module_id": "extract_stat_checks_v1",
                    "evidence_path": f"/test_luck/{idx}/unlucky_section",
                })
        p.turn_to_claims = merge_turn_to_claims(p.turn_to_claims, claims)
        p.turn_to_claims = [
            c if isinstance(c, TurnToLinkClaimInline) else TurnToLinkClaimInline(**c)
            for c in p.turn_to_claims or []
            if isinstance(c, (TurnToLinkClaimInline, dict))
        ]

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_stat_checks", "done", message=f"Extracted stat checks for {total_portions} portions. AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()
