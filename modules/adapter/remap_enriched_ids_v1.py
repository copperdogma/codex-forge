import argparse
import os
import sys
import re
from typing import Dict, Any, List, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.common.utils import read_jsonl, save_jsonl  # noqa: E402


def detect_id(raw_text: str) -> str:
    """
    Heuristic: if text starts with an integer token (e.g., '123 '), return that number.
    """
    if not raw_text:
        return None
    m = re.match(r"\s*(\d{1,4})\b", raw_text)
    if not m:
        return None
    return m.group(1)


def remap(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mapping: Dict[str, str] = {}
    seen_new: Set[str] = set()
    remapped = []
    for row in rows:
        new_id = detect_id(row.get("raw_text", ""))
        old_id = row.get("portion_id")
        if new_id and new_id not in seen_new:
            mapping[old_id] = new_id
            seen_new.add(new_id)
            row = dict(row)
            row["portion_id"] = new_id
        remapped.append(row)

    # optional: adjust choices targets if they match old ids
    for row in remapped:
        choices = row.get("choices") or []
        new_choices = []
        for ch in choices:
            if not isinstance(ch, dict):
                new_choices.append(ch); continue
            tgt = ch.get("target")
            new_tgt = mapping.get(tgt) or tgt
            ch = dict(ch)
            ch["target"] = str(new_tgt) if new_tgt is not None else new_tgt
            new_choices.append(ch)
        row["choices"] = new_choices
    return remapped


def main():
    parser = argparse.ArgumentParser(description="Remap enriched_portion IDs using numeric heading heuristic.")
    parser.add_argument("--input", required=True, help="Input enriched_portion JSONL")
    parser.add_argument("--out", required=True, help="Output enriched_portion JSONL with remapped ids")
    args = parser.parse_args()

    rows = list(read_jsonl(args.input))
    out_rows = remap(rows)
    save_jsonl(args.out, out_rows)
    print(f"Remapped {len(out_rows)} rows → {args.out}")


if __name__ == "__main__":
    main()
