import argparse
import json
from pathlib import Path

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir


def load_portions(path):
    if path.endswith(".jsonl"):
        return list(read_jsonl(path))
    data = json.load(open(path, "r", encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.values())
    return data


def main():
    ap = argparse.ArgumentParser(description="Validate choices coverage/targets; emit missing/invalid choice report.")
    ap.add_argument("--portions", required=True, help="portions json/jsonl")
    ap.add_argument("--out-missing", required=True, help="jsonl of sections with no choices (gameplay only).")
    ap.add_argument("--out-invalid", required=True, help="jsonl of sections with out-of-range targets.")
    ap.add_argument("--min-target", type=int, default=1)
    ap.add_argument("--max-target", type=int, default=400)
    ap.add_argument("--include-text", action="store_true", default=True, help="Include raw_text snippet in findings (default on).")
    args = ap.parse_args()

    rows = load_portions(args.portions)
    missing = []
    invalid = []
    for r in rows:
        sid = str(r.get("section_id") or r.get("portion_id"))
        is_gameplay = r.get("is_gameplay", True)
        choices = r.get("choices") or []
        targets = r.get("targets") or []
        any_choices = bool(choices or targets)
        text = r.get("raw_text") or r.get("text") or ""
        if is_gameplay and not any_choices:
            row = {"section_id": sid, "reason": "no_choices"}
            if args.include_text:
                row["text"] = text[:500]
            missing.append(row)
        all_targets = []
        for c in choices:
            tgt = c.get("target")
            if tgt is not None:
                all_targets.append(str(tgt))
        for t in targets:
            all_targets.append(str(t))
        bad = [t for t in all_targets if not (args.min_target <= int(t) <= args.max_target)]
        if bad:
            row = {"section_id": sid, "invalid_targets": bad}
            if args.include_text:
                row["text"] = text[:500]
            invalid.append(row)

    ensure_dir(Path(args.out_missing).parent)
    save_jsonl(args.out_missing, missing)
    save_jsonl(args.out_invalid, invalid)
    print(f"Missing choices: {len(missing)}, invalid targets: {len(invalid)}")


if __name__ == "__main__":
    main()
