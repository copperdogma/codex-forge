#!/usr/bin/env python3
"""
Validate Choice Links Module

Detects orphaned sections and verifies/repairs suspicious incoming links using AI.
Focuses on potential OCR misreads (e.g., 303 read as 103).
"""

import argparse
import json
import os
import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text

try:
    from modules.common.openai_client import OpenAI
except ImportError:
    OpenAI = None


@dataclass
class SuspectLink:
    source_section_id: str
    target_section_id: str
    choice_index: int
    reason: str
    context_text: str


def get_suspect_targets(orphan_id: int) -> Set[int]:
    """
    Generate suspect target numbers that might be misreads of the orphan ID.
    E.g., for 303, suspect 103, 203, 313, 323, 333, 343, 353, 363, 373, 383, 393.
    Also 300-309 (last digit confusion) and maybe 30-39 (dropped digit).
    """
    suspects = set()
    s_orphan = str(orphan_id)
    
    # 1. Single digit changes (classic OCR/typo)
    for i, digit in enumerate(s_orphan):
        for d in "0123456789":
            if d == digit:
                continue
            new_s = s_orphan[:i] + d + s_orphan[i+1:]
            if new_s != "0" and not new_s.startswith("0"): # simple check, gamebooks usually 1-400
                 suspects.add(int(new_s))

    # 2. Dropped digits (e.g. 303 -> 33, 303 -> 30) - less likely but possible
    if len(s_orphan) > 1:
        for i in range(len(s_orphan)):
            new_s = s_orphan[:i] + s_orphan[i+1:]
            if new_s != "0" and not new_s.startswith("0"):
                suspects.add(int(new_s))
                
    return suspects


def find_orphans(portions: List[Dict], expected_range: Tuple[int, int] = (1, 400)) -> Set[str]:
    referenced = set()
    existing = set()
    
    for p in portions:
        sid = p.get('section_id')
        if sid:
            existing.add(sid)
        
        for choice in p.get('choices', []):
            target = choice.get('target')
            if target:
                referenced.add(str(target))
                
    # Section 1 is allowed to be an orphan (start)
    orphans = {sid for sid in existing if sid != '1' and sid not in referenced}
    
    # Filter by expected range if needed, but string IDs are safer
    return orphans


def validate_link_with_ai(
    client, 
    model: str, 
    source_text: str, 
    source_id: str, 
    target_id: str, 
    orphan_id: str,
    orphan_text: str
) -> Tuple[float, str, Optional[any]]:
    """
    Ask AI if the link from source to target makes sense, or if it should likely be the orphan_id.
    Returns (confidence, explanation, usage).
    """
    prompt = f"""You are validating a Fighting Fantasy gamebook.
I suspect a link in Section {source_id} might be an OCR error.
The text currently links to Section {target_id}, but I suspect it should link to Section {orphan_id}.

Section {source_id} text:
"{source_text}"

Candidate Target (Orphan) Section {orphan_id} text:
"{orphan_text}"

Task:
1. Analyze the text context of BOTH sections.
2. Does the content of Section {orphan_id} follow logically from Section {source_id}?
   - CRITICAL: Does Section {source_id} mention the specific items, actions, or context required by Section {orphan_id}?
   - Example: If Orphan says "you pour the acid", Source MUST mention "acid".
   - If Source mentions "door labeled 103" and Orphan mentions "pouring acid", this is NOT a match unless Source also mentions acid.
3. Does the text of Section {source_id} EXPLICITLY and CLEARLY write "{target_id}"? 
   - Even if it clearly says "{target_id}", could it be an OCR error?
   - Common errors: 1 vs 7, 3 vs 8, 1 vs 3 (if 3 is cut off), 5 vs S.
   - Example: "turn to 103" vs "turn to 303". If the text says "use acid" and Section 303 is about using acid, then "103" is likely a misread of "303".
4. Decision:
   - If Narrative Match is STRONG and Visual Similarity is PLAUSIBLE -> Suggest {orphan_id} (Low Confidence in {target_id}).
   - If Narrative Match is WEAK -> Stick with {target_id} (High Confidence).

Output JSON only:
{{
  "confidence_link_is_correct": <float 0.0 to 1.0>,
  "suggested_target": <string, "{target_id}" or "{orphan_id}" or "unsure">,
  "reasoning": "<short explanation>"
}}

SCORING GUIDE:
- 1.0: "I am certain {target_id} is correct."
- 0.9: "Text clearly says {target_id} and context matches."
- 0.5: "Ambiguous."
- 0.1: "I am certain {target_id} is WRONG and {orphan_id} is correct."
- 0.0: "Definite OCR error, {orphan_id} is the correct link."

IF you suggest {orphan_id} as the target, "confidence_link_is_correct" MUST be less than 0.5.
"""
    try:
        if hasattr(client, "responses"):
             # Mock client or different interface
             pass 
             
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        usage = response.usage
        
        try:
            data = json.loads(content)
            confidence = data.get("confidence_link_is_correct", 1.0)
            reasoning = data.get("reasoning", "")
            return confidence, reasoning, usage
        except json.JSONDecodeError:
            return 0.5, "Failed to parse JSON", usage
            
    except Exception as e:
        print(f"AI Error: {e}")
        return 1.0, f"AI Error: {e}", None


def validate_link_general(
    client, 
    model: str, 
    source_text: str, 
    source_id: str, 
    target_id: str,
    target_text: str
) -> Tuple[float, str, Optional[any]]:
    """
    Ask AI if the link from source to target makes sense given the content of both.
    """
    prompt = f"""You are validating a Fighting Fantasy gamebook.
I am verifying a link from Section {source_id} to Section {target_id}.

Section {source_id} text:
"{source_text}"

Target Section {target_id} text:
"{target_text}"

Task:
1. Analyze the text context of BOTH sections.
2. Does the content of Section {target_id} follow logically from Section {source_id}?
   - CRITICAL: Does Section {source_id} mention items/actions required by {target_id}?
   - Example: If Target says "you pour the acid", Source MUST mention "acid".
3. Does the text of Section {source_id} EXPLICITLY and CLEARLY write "{target_id}"?
4. Is it possible the number is an OCR error pointing to a WRONG section?
   - If the narrative flow is completely wrong (e.g. Source: "fight goblin", Target: "peaceful shop"), verify if the number is clear.

Output JSON only:
{{
  "confidence_link_is_correct": <float 0.0 to 1.0>,
  "reasoning": "<short explanation>"
}}

SCORING:
- 1.0: Link is definitely correct (numbers match, narrative flows).
- 0.8: Link is likely correct (numbers match, narrative neutral).
- 0.2: Link is suspicious (numbers match but narrative mismatches strongly).
- 0.0: Link is definitely WRONG (narrative impossible).
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        usage = response.usage
        data = json.loads(content)
        return data.get("confidence_link_is_correct", 1.0), data.get("reasoning", ""), usage
    except Exception as e:
        print(f"AI Error: {e}")
        return 1.0, f"AI Error: {e}", None

def main():
    parser = argparse.ArgumentParser(description='Validate Choice Links')
    parser.add_argument('--input', '--inputs', '--portions', dest='inputs', help='Input portions JSONL')
    parser.add_argument('--pages', help='Ignored (driver enrich-stage compatibility)')
    parser.add_argument('--out', help='Output portions JSONL')
    parser.add_argument('--confidence-threshold', '--confidence_threshold', type=float, default=0.6)
    parser.add_argument('--max-ai-calls', '--max_ai_calls', type=int, default=50)
    parser.add_argument('--model', default='gpt-4.1-mini')
    parser.add_argument('--state-file', help='Driver state file')
    parser.add_argument('--progress-file', help='Driver progress file')
    parser.add_argument('--run-id', help='Run ID')
    parser.add_argument('--check-multi-links', '--check_multi_links', action='store_true', default=True, help='Check sections with multiple incoming links')
    args = parser.parse_args()

    if not args.inputs:
        raise SystemExit("Missing --inputs")
    
    portions = list(read_jsonl(args.inputs))
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    section_map = {p.get('section_id'): p for p in portions}

    # 1. Detect Orphans
    orphans = find_orphans(portions)
    
    # 2. Build map of Incoming Links: target -> list of (source_id, choice_index)
    incoming_map = defaultdict(list)
    for p in portions:
        sid = p.get('section_id')
        if not sid: continue
        for idx, choice in enumerate(p.get('choices', [])):
            target = str(choice.get('target'))
            incoming_map[target].append((sid, idx))

    suspects = [] 
    
    # 3a. Orphan Suspects
    if orphans:
        print(f"Found {len(orphans)} orphans: {sorted(list(orphans))[:10]}...")
        for orphan in orphans:
            try:
                oid = int(orphan)
            except ValueError:
                continue
            suspect_targets = get_suspect_targets(oid)
            for st in suspect_targets:
                st_str = str(st)
                if st_str in incoming_map:
                    sources = incoming_map[st_str]
                    for src_id, choice_idx in sources:
                        suspects.append({
                            "type": "orphan_repair",
                            "source_id": src_id,
                            "target_id": st_str,
                            "orphan_id": str(oid),
                            "choice_idx": choice_idx
                        })

    # 3b. Multi-Link Collisions (General Check)
    if args.check_multi_links:
        multi_links = {tgt: srcs for tgt, srcs in incoming_map.items() if len(srcs) > 1}
        print(f"Found {len(multi_links)} sections with multiple incoming links.")
        for tgt, srcs in multi_links.items():
            for src_id, choice_idx in srcs:
                # Avoid adding if already in orphan suspects (orphan check is more specific/powerful)
                if any(s['source_id'] == src_id and s['target_id'] == tgt for s in suspects):
                    continue
                suspects.append({
                    "type": "multi_link_check",
                    "source_id": src_id,
                    "target_id": tgt,
                    "choice_idx": choice_idx
                })

    print(f"Total links to verify: {len(suspects)}")
    
    # 4. Validate with AI
    client = None
    if suspects and OpenAI:
        try:
            client = OpenAI()
        except Exception as e:
            print(f"Failed to init OpenAI: {e}")

    ai_calls = 0
    modifications = 0
    
    if client:
        # Prioritize orphan repairs first? 
        suspects.sort(key=lambda x: x['type'] == 'multi_link_check') # False (orphan) comes first

        for suspect in suspects:
            if ai_calls >= args.max_ai_calls:
                break
                
            src_p = section_map.get(suspect['source_id'])
            if not src_p: continue
            
            # Get text context
            html = src_p.get('raw_html', '')
            text = html_to_text(html)
            
            if suspect['type'] == 'orphan_repair':
                orphan_p = section_map.get(suspect['orphan_id'])
                orphan_text = html_to_text(orphan_p.get('raw_html', '')) if orphan_p else ""
                
                conf, reason, usage = validate_link_with_ai(
                    client, args.model, text, suspect['source_id'], suspect['target_id'], suspect['orphan_id'], orphan_text
                )
                ai_calls += 1

                print(f"[Orphan Check] {suspect['source_id']}->{suspect['target_id']} (orphan {suspect['orphan_id']}): Conf={conf}")

                if conf < args.confidence_threshold:
                    print(f"--> REPAIRING: Changing target {suspect['target_id']} to {suspect['orphan_id']}")
                    choices = src_p.get('choices', [])
                    if len(choices) > suspect['choice_idx']:
                        old_choice = choices[suspect['choice_idx']]
                        if str(old_choice.get('target')) == suspect['target_id']:
                            old_choice['target'] = str(suspect['orphan_id'])
                            old_choice['confidence'] = 0.99
                            old_choice['extraction_method'] = 'ai_repair_orphan_logic'
                            old_choice['original_target'] = str(suspect['target_id'])
                            old_choice['repair_reason'] = reason
                            modifications += 1

            elif suspect['type'] == 'multi_link_check':
                tgt_p = section_map.get(suspect['target_id'])
                tgt_text = html_to_text(tgt_p.get('raw_html', '')) if tgt_p else ""
                
                conf, reason, usage = validate_link_general(
                    client, args.model, text, suspect['source_id'], suspect['target_id'], tgt_text
                )
                ai_calls += 1
                
                print(f"[Collision Check] {suspect['source_id']}->{suspect['target_id']}: Conf={conf}")
                
                if conf < 0.3: # Strict threshold for flagging
                     print(f"--> FLAGGING: Suspicious link {suspect['source_id']}->{suspect['target_id']} (Reason: {reason})")
                     choices = src_p.get('choices', [])
                     if len(choices) > suspect['choice_idx']:
                         choices[suspect['choice_idx']]['flagged_suspicious'] = True
                         choices[suspect['choice_idx']]['suspicion_reason'] = reason
    
    # Save output
    save_jsonl(args.out or 'portions_validated.jsonl', portions)
    
    logger.log(
        "validate_choice_links",
        "done",
        current=len(portions),
        total=len(portions),
        message=f"Validated choices. Checked {ai_calls} links, repaired {modifications}.",
        artifact=args.out or 'portions_validated.jsonl',
        module_id="validate_choice_links_v1",
    )

    # Explicitly exit with success code
    import sys
    sys.exit(0)

if __name__ == '__main__':
    main()