"""
Lightweight regression guard to ensure continuation metadata survives the pipeline.

Usage:
  python scripts/regression/check_continuation_propagation.py \\
    --hypotheses output/runs/deathtrap-ocr-dag/adapter_out.jsonl \\
    --locked output/runs/deathtrap-ocr-dag/portions_locked_merged.jsonl \\
    --resolved output/runs/deathtrap-ocr-dag/portions_resolved.jsonl

Checks:
- Schemas can be parsed.
- If any hypothesis has continuation_of set, at least one locked or resolved
  record also carries continuation_of (i.e., metadata not completely dropped).
- Coverage sanity: locked/resolved page ranges are non-empty and ordered.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict


def read_jsonl(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Check continuation propagation through pipeline outputs.")
    parser.add_argument("--hypotheses", required=True, help="adapter_out.jsonl (portion_hyp_v1)")
    parser.add_argument("--locked", required=True, help="portions_locked_merged.jsonl")
    parser.add_argument("--resolved", required=True, help="portions_resolved.jsonl")
    args = parser.parse_args()

    hypo_path = Path(args.hypotheses)
    locked_path = Path(args.locked)
    resolved_path = Path(args.resolved)

    if not hypo_path.exists() or not locked_path.exists() or not resolved_path.exists():
        sys.exit("One or more input files do not exist.")

    hypos = read_jsonl(hypo_path)
    locked = read_jsonl(locked_path)
    resolved = read_jsonl(resolved_path)

    hypo_cont = sum(1 for h in hypos if h.get("continuation_of"))
    locked_cont = sum(1 for h in locked if h.get("continuation_of"))
    resolved_cont = sum(1 for h in resolved if h.get("continuation_of"))

    if hypo_cont and (locked_cont + resolved_cont) == 0:
        sys.exit("FAIL: continuation metadata present in hypotheses but absent from locked/resolved outputs.")

    # basic monotonicity/coverage sanity
    for name, rows in (("locked", locked), ("resolved", resolved)):
        for r in rows:
            ps, pe = r["page_start"], r["page_end"]
            if pe < ps:
                sys.exit(f"FAIL: {name} row has negative span {ps}-{pe}")

    print("PASS: continuation propagation and ordering look good.")


if __name__ == "__main__":
    main()
