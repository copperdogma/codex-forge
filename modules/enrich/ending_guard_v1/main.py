import argparse
import json
import re
from typing import Dict, List, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, save_json

SYSTEM_PROMPT = """You are checking if a Fighting Fantasy section is an ending.
Given section id and text, answer in JSON:
{ "ending_type": "death" | "victory" | "open", "reason": "<short>" }
Rules:
- If the text clearly ends the adventure (death or success), set ending_type accordingly.
- If the text instructs to turn to another section or otherwise continue, set ending_type="open".
- Do NOT invent targets; only classify the ending state."""


def load_portions(path: str) -> Tuple[List[Dict], str]:
    if path.endswith(".jsonl"):
        return list(read_jsonl(path)), "jsonl"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        rows = []
        for pid, val in data.items():
            if "portion_id" not in val:
                val["portion_id"] = pid
            rows.append(val)
        return rows, "json"
    if isinstance(data, list):
        return data, "json"
    raise ValueError("Unsupported portions format; expected JSON object, list, or JSONL")


def save_portions(rows: List[Dict], fmt: str, path: str):
    if fmt == "jsonl":
        save_jsonl(path, rows)
    else:
        obj = {str(r.get("portion_id")): r for r in rows}
        save_json(path, obj)


def classify_ending(client: OpenAI, model: str, section_id: str, text: str) -> Dict:
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Section {section_id}:\n{text}"},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(completion.choices[0].message.content)


def main():
    parser = argparse.ArgumentParser(description="Mark no-choice sections as death/victory/open.")
    parser.add_argument("--portions", required=True, help="Input portions (json/jsonl).")
    parser.add_argument("--out", required=True, help="Output path; same format as input.")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--targets", nargs="*", help="Section IDs to check; if absent, auto-detect no-choice gameplay sections.")
    parser.add_argument("--pages", help="Pages input (for driver compatibility; not used by this module).")
    parser.add_argument("--state-file", help="Pipeline state file (for driver compatibility).")
    parser.add_argument("--progress-file", help="Pipeline events file (for driver compatibility).")
    parser.add_argument("--run-id", help="Run ID (for driver compatibility).")
    parser.add_argument("--skip-ai", "--skip_ai", action="store_true", help="Skip AI calls; assume open for all.")
    args = parser.parse_args()

    rows, fmt = load_portions(args.portions)
    by_id = {str(r.get("section_id") or r.get("portion_id")): r for r in rows}

    if args.skip_ai:
        target_ids = set()
    elif args.targets:
        target_ids = set(args.targets)
    else:
        # Auto-detect no-choice sections
        # Check for sections with no choices that have numeric section_ids (gameplay sections)
        target_ids = set()
        for sid, r in by_id.items():
            section_id = r.get("section_id") or sid
            # Check if section has no choices
            has_choices = r.get("choices") and len(r.get("choices", [])) > 0
            # Check if it's a gameplay section (numeric ID 1-400) or has is_gameplay flag
            try:
                section_num = int(str(section_id))
                is_gameplay_section = 1 <= section_num <= 400
            except (ValueError, TypeError):
                is_gameplay_section = False

            # Include if: (is_gameplay flag OR numeric ID) AND no choices
            if not has_choices and (r.get("is_gameplay") or is_gameplay_section):
                target_ids.add(sid)

    client = OpenAI()
    print(f"Found {len(target_ids)} no-choice sections to classify")
    for sid in target_ids:
        r = by_id.get(sid)
        if not r:
            print(f"Warning: section {sid} not found in by_id map")
            continue
        # Get text from raw_text, text, or raw_html (AI OCR pipeline uses HTML)
        text = r.get("raw_text") or r.get("text") or ""
        if not text and r.get("raw_html"):
            # Strip HTML tags to get plain text
            text = re.sub(r'<[^>]+>', ' ', r.get("raw_html", ""))
            text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            print(f"Warning: section {sid} has no text, skipping")
            continue
        result = classify_ending(client, args.model, sid, text)
        if "repair" not in r or r["repair"] is None:
            r["repair"] = {}
        r["repair"]["ending_guard"] = result
        ending_type = result.get("ending_type")
        print(f"DEBUG: Section {sid} ending_type='{ending_type}' in ('death','victory')={ending_type in ('death', 'victory')}")
        if ending_type in ("death", "victory"):
            r["ending"] = ending_type
            r["end_game"] = True  # Used by build stage to mark terminal sections
            r["is_gameplay"] = True
            print(f"DEBUG: Section {sid} SET ending={r.get('ending')}, end_game={r.get('end_game')}")
        print(f"Section {sid}: {ending_type} - {result.get('reason')[:50] if result.get('reason') else 'no reason'}")

    save_portions(list(by_id.values()), fmt, args.out)
    print(f"Saved ending-marked portions → {args.out}")


if __name__ == "__main__":
    main()