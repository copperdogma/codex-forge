import argparse
import json
import re
from pathlib import Path
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


def find_targets(text: str, min_target: int, max_target: int) -> List[Tuple[str, str]]:
    targets: List[Tuple[str, str]] = []
    if not text:
        return targets
    pattern = re.compile(r"turn to\s+(\d{1,3})", re.IGNORECASE)
    for m in pattern.finditer(text):
        tgt = m.group(1)
        try:
            num = int(tgt)
        except ValueError:
            continue
        if num < min_target or num > max_target:
            continue
        # Build a short snippet for choice text (surrounding words).
        start = max(0, m.start() - 60)
        end = min(len(text), m.end() + 20)
        snippet = text[start:end].strip()
        targets.append((snippet, tgt))
    return targets


def main():
    parser = argparse.ArgumentParser(description="Infer navigation choices from raw_text using simple 'turn to N' regex.")
    parser.add_argument("--portions", required=True, help="Input portions (json/jsonl).")
    parser.add_argument("--out", required=True, help="Output path; format follows input.")
    parser.add_argument("--min-target", type=int, default=1)
    parser.add_argument("--max-target", type=int, default=400)
    parser.add_argument("--pages", help="Optional pages input (unused; accepted for driver compatibility).")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    rows, fmt = load_portions(args.portions)
    for row in rows:
        existing = row.get("choices") or []
        if existing:
            continue  # keep authored choices
        text = row.get("raw_text") or row.get("text") or ""
        inferred = find_targets(text, args.min_target, args.max_target)
        if not inferred:
            continue
        seen = set()
        choices = []
        for snippet, tgt in inferred:
            if tgt in seen:
                continue
            seen.add(tgt)
            choices.append({"text": snippet, "target": tgt})
        if choices:
            row["choices"] = choices
            row.setdefault("targets", [c["target"] for c in choices])
            row.setdefault("repair", {})
            row["repair"]["choices_inferred"] = True

    save_portions(rows, fmt, args.out)
    print(f"Saved portions with inferred choices → {args.out}")


if __name__ == "__main__":
    main()
