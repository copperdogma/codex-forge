import argparse
import json
from typing import Dict, List, Tuple

from openai import OpenAI

from modules.common.utils import read_jsonl, save_jsonl, save_json, log_llm_usage

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
    usage = getattr(completion, "usage", None)
    if usage:
        log_llm_usage(
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
    return json.loads(completion.choices[0].message.content)


def main():
    parser = argparse.ArgumentParser(description="Mark no-choice sections as death/victory/open.")
    parser.add_argument("--portions", required=True, help="Input portions (json/jsonl).")
    parser.add_argument("--out", required=True, help="Output path; same format as input.")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--targets", nargs="*", help="Section IDs to check; if absent, auto-detect no-choice gameplay sections.")
    args = parser.parse_args()

    rows, fmt = load_portions(args.portions)
    by_id = {str(r.get("section_id") or r.get("portion_id")): r for r in rows}

    if args.targets:
        target_ids = set(args.targets)
    else:
        target_ids = set()
        for sid, r in by_id.items():
            if r.get("is_gameplay") and not r.get("choices"):
                target_ids.add(sid)

    client = OpenAI()
    for sid in target_ids:
        r = by_id.get(sid)
        if not r:
            continue
        text = r.get("raw_text") or r.get("text") or ""
        result = classify_ending(client, args.model, sid, text)
        r.setdefault("repair", {})["ending_guard"] = result
        if result.get("ending_type") in ("death", "victory"):
            r["ending"] = result["ending_type"]
            r["is_gameplay"] = True
        else:
            # leave as is; another pass (choice extractor) could run if needed
            pass

    save_portions(list(by_id.values()), fmt, args.out)
    print(f"Saved ending-marked portions → {args.out}")


if __name__ == "__main__":
    main()
