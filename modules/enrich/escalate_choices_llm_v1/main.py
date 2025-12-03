import argparse
import json
from typing import List, Dict

from modules.common.utils import read_jsonl, save_jsonl, save_json


PROMPT = """You are extracting navigation choices from a gamebook section.

Input fields:
- section_id
- text: full section text

Task:
- If the section ends the game (death/victory) with no further choices, return end_game=true and choices=[].
- Otherwise, list each navigation choice with its target section number.
- Only include targets that are integers. Do not invent text.
- If this is an intro/background section that ends with “NOW TURN OVER” (or any similar non-numeric instruction to continue), treat it as a single navigation choice to section 1.

Return JSON:
{{
  "section_id": "<id>",
  "end_game": true/false,
  "choices": [{{"text": "<choice snippet>", "target": "<number>"}}]
}}
"""


def load_portions(path):
    if path.endswith(".jsonl"):
        return list(read_jsonl(path)), "jsonl"
    data = json.load(open(path, "r", encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.values()), "json"
    return data, "json"


def save_portions(rows: List[Dict], fmt: str, path: str):
    if fmt == "jsonl":
        save_jsonl(path, rows)
    else:
        obj = {str(r.get("section_id") or r.get("portion_id") or r.get("portion_id")): r for r in rows}
        save_json(path, obj)


def main():
    ap = argparse.ArgumentParser(description="Escalate missing-choice sections with LLM to extract choices or mark end_game.")
    ap.add_argument("--portions", required=True, help="portions json/jsonl")
    ap.add_argument("--missing", required=True, help="missing choices jsonl (section_id per line)")
    ap.add_argument("--out", required=True, help="output portions path")
    ap.add_argument("--model", default="gpt-4.1-mini")
    ap.add_argument("--max-sections", type=int, default=50)
    args = ap.parse_args()

    from openai import OpenAI
    client = OpenAI()

    rows, fmt = load_portions(args.portions)
    missing_ids = []
    for line in read_jsonl(args.missing):
        missing_ids.append(str(line["section_id"]))
        if len(missing_ids) >= args.max_sections:
            break

    missing_set = set(missing_ids)
    by_id = {str(r.get("section_id") or r.get("portion_id")): r for r in rows}

    for sid in missing_ids:
        r = by_id.get(sid)
        if not r:
            continue
        text = r.get("raw_text") or r.get("text") or ""
        msg = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": PROMPT + "\n\nsection_id: " + sid + "\ntext:\n" + text}],
            temperature=0,
            max_tokens=400,
        )
        try:
            parsed = json.loads(msg.choices[0].message.content)
            if parsed.get("end_game"):
                r["end_game"] = True
                r["choices"] = []
                r["targets"] = []
            else:
                choices = parsed.get("choices") or []
                r["choices"] = choices
                r["targets"] = [c["target"] for c in choices if "target" in c]
        except Exception:
            # leave unchanged on parse failure
            continue

    save_portions(rows, fmt, args.out)
    print(f"Escalated {len(missing_ids)} sections → {args.out}")


if __name__ == "__main__":
    main()
