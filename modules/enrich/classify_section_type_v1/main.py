import argparse
import json
from typing import Dict, List, Tuple

from modules.common.openai_client import OpenAI
from modules.common.utils import read_jsonl, save_jsonl, save_json, ProgressLogger


FRONT_PROMPT = """You are classifying a FRONT-MATTER page of a Fighting Fantasy–style gamebook.
Allowed labels: front_cover, back_cover, title_page, publishing_info, toc, intro, rules, adventure_sheet, adverts, other.
Return JSON: { "section_type": "<label>", "is_gameplay": false }."""

GAMEPLAY_PROMPT = """You are classifying a GAMEPLAY section of a Fighting Fantasy–style gamebook.
Allowed labels: gameplay, death, victory, other.
Return JSON: { "section_type": "<label>", "is_gameplay": true }.
If this text clearly ends the adventure, use death or victory; otherwise gameplay."""

END_PROMPT = """You are classifying an ENDMATTER page of a Fighting Fantasy–style gamebook.
Allowed labels: endmatter, adverts, back_cover, other.
Return JSON: { "section_type": "<label>", "is_gameplay": false }."""


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


def classify_snippet(client: OpenAI, model: str, section_id: str, text: str, max_chars: int, phase: str) -> Dict:
    snippet = (text or "")[:max_chars]
    if phase == "front":
        prompt = FRONT_PROMPT
    elif phase == "end":
        prompt = END_PROMPT
    else:
        prompt = GAMEPLAY_PROMPT
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Section {section_id}: {snippet}"},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(completion.choices[0].message.content)
    return {
        "section_type": data.get("section_type"),
        "is_gameplay": bool(data.get("is_gameplay", False)),
    }


def main():
    parser = argparse.ArgumentParser(description="Classify sections into front_matter/intro/rules/adventure_sheet/gameplay/other.")
    parser.add_argument("--portions", required=True, help="Input portions (json/jsonl).")
    parser.add_argument("--out", required=True, help="Output path; same format as input.")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-chars", type=int, default=200, help="Snippet length from raw_text.")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    rows, fmt = load_portions(args.portions)
    client = OpenAI()
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    total = len(rows)
    for idx, row in enumerate(rows, start=1):
        text = row.get("raw_text") or row.get("text") or ""
        section_id = str(row.get("section_id") or row.get("portion_id") or idx)
        # Determine phase hint from existing flags
        if row.get("section_type") in ("front_matter", "front_cover", "title_page", "publishing_info", "toc", "intro", "rules", "adventure_sheet"):
            phase = "front"
        elif row.get("section_type") in ("endmatter", "back_cover"):
            phase = "end"
        elif row.get("is_gameplay"):
            phase = "game"
        else:
            phase = "front"

        result = classify_snippet(client, args.model, section_id, text, args.max_chars, phase)
        row["section_type"] = result.get("section_type") or row.get("section_type")
        row["is_gameplay"] = result.get("is_gameplay", row.get("is_gameplay"))
        if idx % 25 == 0 or idx == total:
            logger.log("classify", "running", current=idx, total=total,
                       message=f"Classified {idx}/{total}", artifact=args.out,
                       module_id="classify_section_type_v1")

    save_portions(rows, fmt, args.out)
    logger.log("classify", "done", current=total, total=total,
               message="Classification complete", artifact=args.out,
               module_id="classify_section_type_v1")
    print(f"Saved classified portions → {args.out}")


if __name__ == "__main__":
    main()