import argparse
import json
import os
from typing import List


def read_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def concat_dedupe(inputs: List[str], output: str, key_field: str = "portion_id"):
    seen = set()
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as out_f:
        for path in inputs:
            if not os.path.exists(path):
                raise SystemExit(f"Missing input file: {path}")
            for obj in read_jsonl(path):
                key = obj.get(key_field) or json.dumps(obj, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                out_f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Merge portion hypotheses JSONL files with de-duplication.")
    parser.add_argument("--inputs", nargs="+", required=True, help="Input JSONL files")
    parser.add_argument("--out", required=True, help="Output JSONL file")
    parser.add_argument("--dedupe_field", default="portion_id", help="Field to de-duplicate on")
    args = parser.parse_args()

    concat_dedupe(args.inputs, args.out, key_field=args.dedupe_field)
    print(f"[merge] wrote {args.out} from {len(args.inputs)} inputs")


if __name__ == "__main__":
    main()
