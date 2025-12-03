import argparse
import json
from typing import Dict, List, Tuple

from modules.common.utils import read_jsonl, save_jsonl, save_json


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


def main():
    parser = argparse.ArgumentParser(description="Phase smoother: enforce frontmatter → gameplay → endmatter based on order/IDs.")
    parser.add_argument("--portions", required=True, help="Input portions (json/jsonl).")
    parser.add_argument("--out", required=True, help="Output path; same format as input.")
    parser.add_argument("--frontmatter_cap", type=int, default=12, help="(Legacy) kept for compatibility; not used in pivot detection.")
    parser.add_argument("--endmatter_hint", type=int, default=380, help="IDs >= this tilt to endmatter if non-choice (default 380).")
    parser.add_argument("--macro", help="Optional macro sections JSON from macro_section_detector_ff_v1.")
    args = parser.parse_args()

    rows, fmt = load_portions(args.portions)

    def key_fn(r):
        sid = str(r.get("section_id") or r.get("portion_id"))
        return int(sid) if sid.isdigit() else 10**9

    rows.sort(key=key_fn)

    # Optional macro sections input
    macro_front = 1
    macro_main = None
    macro_end = None
    if args.macro:
        macro = json.load(open(args.macro, "r"))
        for sec in macro.get("sections", []):
            if sec.get("section_name") == "frontmatter":
                macro_front = sec.get("page", 1)
            elif sec.get("section_name") == "main_content":
                macro_main = sec.get("page")
            elif sec.get("section_name") == "endmatter":
                macro_end = sec.get("page")

    # Step 1: find BACKGROUND pivot or first gameplay cue
    bg_idx = None
    gameplay_pivot = None
    for idx, r in enumerate(rows):
        text = (r.get("raw_text") or "").lower()
        if bg_idx is None and (text.strip().startswith("background") or text.strip().startswith("background:")):
            bg_idx = idx
        has_choices = bool(r.get("choices"))
        has_turnto = "turn to" in text
        gameplay_cue = has_choices or has_turnto
        if gameplay_pivot is None and gameplay_cue:
            gameplay_pivot = idx

    # Step 2: assign phases deterministically
    phase = "front"
    for idx, r in enumerate(rows):
        sid = str(r.get("section_id") or r.get("portion_id"))
        sid_num = int(sid) if sid.isdigit() else None
        has_choices = bool(r.get("choices"))

        page_start = r.get("page_start") or r.get("page") or 0
        if macro_main:
            # Use macro cutpoints
            if page_start < macro_main:
                phase = "front"
            elif macro_end and page_start >= macro_end:
                phase = "end"
            else:
                phase = "game"
        elif bg_idx is not None:
            phase = "front" if idx < bg_idx else "game"
        elif gameplay_pivot is not None:
            phase = "front" if idx < gameplay_pivot else "game"
        else:
            phase = "front"

        # Endmatter switch: after gameplay has started, if we see non-numeric or very late id with no choices
        if phase == "game" and sid_num is not None and sid_num >= args.endmatter_hint and not has_choices:
            phase = "end"

        if phase == "front":
            r["section_type"] = r.get("section_type") or "front_matter"
            r["is_gameplay"] = False
        elif phase == "game":
            r["section_type"] = r.get("section_type") or "gameplay"
            r["is_gameplay"] = True
            text = (r.get("raw_text") or "").strip().lower()
            if text.startswith("background") and not r.get("choices"):
                r["choices"] = [{"text": "Turn to 1", "target": "1"}]
        else:
            r["section_type"] = "endmatter"
            r["is_gameplay"] = False

    save_portions(rows, fmt, args.out)
    print(f"Saved phase-smoothed portions → {args.out}")


if __name__ == "__main__":
    main()
