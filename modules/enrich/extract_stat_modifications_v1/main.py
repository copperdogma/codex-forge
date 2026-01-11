import argparse
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger
from modules.common.html_utils import html_to_text
from schemas import EnrichedPortion, StatModification

# --- Patterns ---

# Loose patterns to detect potential stat changes and trigger AI
MOD_KEYWORDS = ["lose", "gain", "reduce", "increase", "restore", "add", "deduct", "subtract", "SKILL", "STAMINA", "LUCK"]

# Specific regex for common deterministic cases
REDUCE_PATTERN = re.compile(r"\b(?:reduce|reduces|deduct|subtract)\s+(?:your\s+)?(.*?)\s+by\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", re.IGNORECASE)
LOSE_PATTERN = re.compile(r"\b(?:lose|deduct)\s+(\d+)\s+(skill|stamina|luck)\b", re.IGNORECASE)
GAIN_PATTERN = re.compile(r"\b(?:gain|increase|restore|add)\s+(?:your\s+)?(.*?)\s+by\s+(\d+)\b", re.IGNORECASE)
GAIN_VAL_PATTERN = re.compile(r"\b(?:gain|restore|add)\s+(\d+)\s+(skill|stamina|luck)\b", re.IGNORECASE)
SENTENCE_MOD_PATTERN = re.compile(
    r"\b(?:(lose|deduct|reduce|reduces|subtract|gain|increase|restore|add)\s+(\d+)\s+(skill|stamina|luck)|and\s+(\d+)\s+(skill|stamina|luck))\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are an expert at parsing Fighting Fantasy gamebook sections.
Extract stat modifications (SKILL, STAMINA, LUCK) from the provided text into a JSON object.

Detect:
- stat: \"skill\", \"stamina\", or \"luck\" (normalized to lowercase).
- amount: The integer amount of change (positive for gains/restoration, negative for losses).
- scope: \"permanent\", \"section\", \"combat\", or \"round\".
  - Use \"permanent\" when the text changes INITIAL or MAX values (e.g., \"reduce your initial Skill\").
  - Use \"section\" for one-off changes outside combat.
  - Use \"combat\" for changes that apply for the duration of the combat.
  - Use \"round\" for changes that apply only for a single attack round.

Rules:
- Ignore narrative mentions that aren't modifications (e.g., \"Your Skill is 12\").
- \"Restore\" or \"Gain\" are positive. \"Lose\" or \"Reduce\" are negative.
- Handle implicit amounts (e.g., \"Lose a Luck point\" -> amount: -1).

Example output:
{
  \"stat_modifications\": [
    { \"stat\": \"skill\", \"amount\": -1, \"scope\": \"section\" },
    { \"stat\": \"stamina\", \"amount\": 4, \"scope\": \"section\" }
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
    { \"section_id\": \"16\", \"item_index\": 0, \"data\": { \"stat\": \"stamina\", \"amount\": \"-(1d6+1)\", \"scope\": \"section\" } }
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

def _filter_combat_modifier_mods(text: str, mods: List[StatModification]) -> List[StatModification]:
    if not mods:
        return mods
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
    combat_sentences = [s for s in sentences if _is_combat_modifier(s)]
    if not combat_sentences:
        return mods
    filtered = []
    for m in mods:
        stat = str(m.stat).lower()
        if any(stat in s.lower() for s in combat_sentences):
            continue
        filtered.append(m)
    return filtered


def _is_combat_modifier(sentence: str) -> bool:
    lower = sentence.lower()
    return (
        "attack strength" in lower
        or "attack round" in lower
        or "during this combat" in lower
        or "during the combat" in lower
        or "for this combat" in lower
        or "duration of the combat" in lower
        or "duration of combat" in lower
    )


def extract_stat_modifications_regex(text: str) -> List[StatModification]:
    mods = []
    seen = set()
    word_numbers = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    def _to_int(raw: str) -> Optional[int]:
        if raw is None:
            return None
        raw = str(raw).strip().lower()
        if raw.isdigit():
            return int(raw)
        return word_numbers.get(raw)

    def _scope_from_sentence(sentence: str) -> str:
        lower = sentence.lower()
        if "initial" in lower or "permanent" in lower or "maximum" in lower or "max" in lower:
            return "permanent"
        return "section"

    def _append(stat: Optional[str], amount: int, sentence: str = "") -> None:
        if not stat:
            return
        scope = _scope_from_sentence(sentence)
        key = (stat, amount, scope)
        if key in seen:
            return
        seen.add(key)
        mods.append(StatModification(stat=stat, amount=amount, scope=scope, confidence=0.7))

    def _append_expr(stat: Optional[str], expr: str, sentence: str = "") -> None:
        if not stat:
            return
        scope = _scope_from_sentence(sentence)
        key = (stat, expr, scope)
        if key in seen:
            return
        seen.add(key)
        mods.append(StatModification(stat=stat, amount=expr, scope=scope, confidence=0.7))

    def _dice_count(raw: str) -> Optional[int]:
        if raw is None:
            return None
        raw = str(raw).strip().lower()
        if raw.isdigit():
            return int(raw)
        return word_numbers.get(raw)

    def _sentence_for(span_start: int, span_end: int) -> str:
        start = max(text.rfind(".", 0, span_start), text.rfind("!", 0, span_start), text.rfind("?", 0, span_start))
        end_candidates = [text.find(".", span_end), text.find("!", span_end), text.find("?", span_end)]
        end_candidates = [c for c in end_candidates if c != -1]
        end = min(end_candidates) if end_candidates else len(text)
        return text[start + 1:end]

    def _is_conditional(sentence: str) -> bool:
        """
        Stat mods that are conditional ("if you are shot... reduce SKILL") cannot be represented
        as unconditional events. Prefer dropping them rather than emitting incorrect unconditional changes.
        """
        lower = (sentence or "").strip().lower()
        return lower.startswith("if ") or " if " in lower or " unless " in lower


    roll_each_pattern = re.compile(
        r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die|dice)"
        r".{0,200}?(?:lose|loses|reduces|reduce)"
        r"\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(skill|stamina|luck)\s+points?\s+for\s+each",
        re.IGNORECASE | re.DOTALL,
    )
    each_one_pattern = re.compile(
        r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die|dice)"
        r".{0,200}?each\s+one\s+reduces?\s+your\s+"
        r"(skill|stamina|luck)\s+by\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)",
        re.IGNORECASE | re.DOTALL,
    )
    each_stats_pattern = re.compile(
        r"\b(?:add|increase)\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+to\s+each\s+of\s+your\s+"
        r"(skill|stamina|luck)"
        r"(?:\s*,\s*|\s+and\s+)(skill|stamina|luck)"
        r"(?:\s*,\s*|\s+and\s+)?(skill|stamina|luck)?"
        r"(?:\s+scores?)?\b",
        re.IGNORECASE,
    )
    roll_add_each_pattern = re.compile(
        r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die|dice)\s+and\s+add\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(?:to\s+the\s+total|to\s+this\s+total)?"
        r".{0,220}?(?:lose|loses|reduces|reduce)\s+(?:your\s+)?"
        r"(skill|stamina|luck)\s+by\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+for\s+each",
        re.IGNORECASE | re.DOTALL,
    )
    roll_reduce_total_pattern = re.compile(
        r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die|dice)"
        r"(?:\s*,?\s*(?:and\s+)?add\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+to\s+the\s+number)?"
        r".{0,220}?(?:lose|loses|reduces|reduce|deduct|subtract)\s+(?:your\s+)?"
        r"(skill|stamina|luck)\s+(?:score\s+)?by\s+(?:the\s+)?(?:total|number|amount)",
        re.IGNORECASE | re.DOTALL,
    )
    roll_deduct_number_pattern = re.compile(
        r"roll\s+(one|two|three|four|five|six|\d+)\s+(?:die|dice)"
        r"(?:\s*,?\s*(?:and\s+)?add\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+to\s+the\s+number)?"
        r".{0,200}?(?:deduct|subtract)\s+(?:the\s+)?(?:number|total|amount)\s+from\s+(?:your\s+)?"
        r"(skill|stamina|luck)\s*(?:score)?",
        re.IGNORECASE | re.DOTALL,
    )

    dice_spans: List[Tuple[int, int]] = []
    for match in roll_each_pattern.finditer(text):
        dice_raw = match.group(1)
        loss_raw = match.group(2)
        stat = normalize_stat(match.group(3))
        dice_count = _dice_count(dice_raw) or 1
        loss_val = _to_int(loss_raw)
        if stat and loss_val is not None:
            expr = f"-({dice_count}d6)" if loss_val == 1 else f"-({dice_count}d6*{loss_val})"
            _append_expr(stat, expr, _sentence_for(match.start(), match.end()))
            dice_spans.append((match.start(), match.end()))

    for match in each_one_pattern.finditer(text):
        dice_raw = match.group(1)
        stat = normalize_stat(match.group(2))
        loss_raw = match.group(3)
        dice_count = _dice_count(dice_raw) or 1
        loss_val = _to_int(loss_raw)
        if stat and loss_val is not None:
            expr = f"-({dice_count}d6)" if loss_val == 1 else f"-({dice_count}d6*{loss_val})"
            _append_expr(stat, expr, _sentence_for(match.start(), match.end()))
            dice_spans.append((match.start(), match.end()))

    for match in each_stats_pattern.finditer(text):
        amount = _to_int(match.group(1))
        if amount is None:
            continue
        for stat_raw in match.groups()[1:]:
            stat = normalize_stat(stat_raw)
            if stat:
                _append(stat, amount, _sentence_for(match.start(), match.end()))

    for match in roll_add_each_pattern.finditer(text):
        dice_raw = match.group(1)
        add_raw = match.group(2)
        stat = normalize_stat(match.group(3))
        loss_raw = match.group(4)
        dice_count = _dice_count(dice_raw) or 1
        add_val = _to_int(add_raw)
        loss_val = _to_int(loss_raw)
        if stat and add_val is not None and loss_val is not None:
            expr = f"-({dice_count}d6+{add_val})" if loss_val == 1 else f"-(({dice_count}d6+{add_val})*{loss_val})"
            _append_expr(stat, expr, _sentence_for(match.start(), match.end()))
            dice_spans.append((match.start(), match.end()))

    for match in roll_reduce_total_pattern.finditer(text):
        dice_raw = match.group(1)
        add_raw = match.group(2)
        stat = normalize_stat(match.group(3))
        dice_count = _dice_count(dice_raw) or 1
        add_val = _to_int(add_raw) if add_raw else 0
        if stat:
            expr = f"-({dice_count}d6+{add_val})" if add_val else f"-({dice_count}d6)"
            _append_expr(stat, expr, _sentence_for(match.start(), match.end()))
            dice_spans.append((match.start(), match.end()))

    for match in roll_deduct_number_pattern.finditer(text):
        dice_raw = match.group(1)
        add_raw = match.group(2)
        stat = normalize_stat(match.group(3))
        dice_count = _dice_count(dice_raw) or 1
        add_val = _to_int(add_raw) if add_raw else 0
        if stat:
            expr = f"-({dice_count}d6+{add_val})" if add_val else f"-({dice_count}d6)"
            _append_expr(stat, expr, _sentence_for(match.start(), match.end()))
            dice_spans.append((match.start(), match.end()))

    # Very simple regex attempt; most extraction will rely on AI due to phrasing variety
    def _in_dice_span(start: int, end: int) -> bool:
        return any(start >= s and end <= e for s, e in dice_spans)

    for match in REDUCE_PATTERN.finditer(text):
        if _in_dice_span(match.start(), match.end()):
            continue
        sentence = _sentence_for(match.start(), match.end())
        if _is_combat_modifier(sentence):
            continue
        if _is_conditional(sentence):
            continue
        stat = normalize_stat(match.group(1))
        amount = _to_int(match.group(2))
        if stat and amount is not None:
            _append(stat, -amount, sentence)

    for match in LOSE_PATTERN.finditer(text):
        if _in_dice_span(match.start(), match.end()):
            continue
        sentence = _sentence_for(match.start(), match.end())
        if _is_combat_modifier(sentence):
            continue
        if _is_conditional(sentence):
            continue
        stat = normalize_stat(match.group(2))
        if stat:
            _append(stat, -int(match.group(1)), sentence)

    for match in GAIN_PATTERN.finditer(text):
        sentence = _sentence_for(match.start(), match.end())
        if _is_combat_modifier(sentence):
            continue
        if _is_conditional(sentence):
            continue
        stat = normalize_stat(match.group(1))
        amount = _to_int(match.group(2))
        if stat and amount is not None:
            _append(stat, amount, sentence)

    for match in GAIN_VAL_PATTERN.finditer(text):
        sentence = _sentence_for(match.start(), match.end())
        if _is_combat_modifier(sentence):
            continue
        if _is_conditional(sentence):
            continue
        stat = normalize_stat(match.group(2))
        if stat:
            _append(stat, int(match.group(1)), sentence)

    for sentence in re.split(r"[.!?]", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if _is_combat_modifier(sentence):
            continue
        if _is_conditional(sentence):
            continue
        current_sign: Optional[int] = None
        for match in SENTENCE_MOD_PATTERN.finditer(sentence):
            if match.group(1):
                keyword = match.group(1).lower()
                amount = int(match.group(2))
                stat = normalize_stat(match.group(3))
                if keyword in ("lose", "deduct", "reduce", "subtract"):
                    current_sign = -1
                else:
                    current_sign = 1
                _append(stat, current_sign * amount, sentence)
            else:
                amount = int(match.group(4))
                stat = normalize_stat(match.group(5))
                if current_sign is None:
                    continue
                _append(stat, current_sign * amount, sentence)
            
    lower_text = text.lower()
    if "for each" in lower_text or "each one" in lower_text:
        dice_stats = {m.stat for m in mods if isinstance(m.amount, str) and "d6" in m.amount}
        if dice_stats:
            mods = [m for m in mods if not (m.stat in dice_stats and isinstance(m.amount, (int, float)))]

    return _filter_combat_modifier_mods(text, mods)


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
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Global stat modification audit error: {e}")
        return {"removals": [], "corrections": [], "additions": []}


def _build_audit_maps(removals: list, corrections: list, additions: list) -> tuple[dict, dict, dict]:
    removals_map = {}
    for r in removals or []:
        sid_r = str(r.get("section_id"))
        idx = r.get("item_index")
        if idx is None:
            continue
        try:
            idx_int = int(idx)
        except (TypeError, ValueError):
            continue
        removals_map.setdefault(sid_r, set()).add(idx_int)

    corrections_map = {}
    for c in corrections or []:
        sid_c = str(c.get("section_id"))
        idx = c.get("item_index")
        if idx is None:
            continue
        try:
            idx_int = int(idx)
        except (TypeError, ValueError):
            continue
        corrections_map.setdefault(sid_c, {})[idx_int] = c.get("data")

    additions_map = {}
    for a in additions or []:
        sid_a = str(a.get("section_id"))
        additions_map.setdefault(sid_a, []).append(a.get("data"))

    return removals_map, corrections_map, additions_map

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
            if m_ai:
                mods = m_ai
        
        if mods:
            mods = _filter_combat_modifier_mods(text, mods)
        
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
            removals_map, corrections_map, additions_map = _build_audit_maps(removals, corrections, additions)

            for p in out_portions:
                sid = str(p.section_id or p.portion_id)
                # Apply corrections
                if sid in corrections_map:
                    for idx, new_data in corrections_map[sid].items():
                        if idx < len(p.stat_modifications):
                            if not isinstance(new_data, dict):
                                continue
                            p.stat_modifications[idx] = StatModification(**new_data)
                
                # Apply removals
                if sid in removals_map:
                    p.stat_modifications = [m for i, m in enumerate(p.stat_modifications) if i not in removals_map[sid]]
                
                # Apply additions
                if sid in additions_map:
                    if not p.stat_modifications:
                        p.stat_modifications = []
                    for a_data in additions_map[sid]:
                        if not isinstance(a_data, dict):
                            print(f"Warning: Skipping invalid stat modification addition for section {sid}: {a_data}")
                            continue
                        try:
                            p.stat_modifications.append(StatModification(**a_data))
                        except Exception as e:
                            print(f"Warning: Skipping invalid stat modification addition for section {sid}: {e}")
                            continue

    final_rows = [p.model_dump(exclude_none=True) for p in out_portions]
    save_jsonl(args.out, final_rows)
    logger.log("extract_stat_modifications", "done", message=f"Extracted stat modifications for {total_portions} portions. AI calls: {ai_calls} + 1 audit.", artifact=args.out)

if __name__ == "__main__":
    main()
