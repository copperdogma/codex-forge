import argparse
import json
import shutil
import sys
from pathlib import Path

from modules.common.utils import ensure_dir, read_jsonl, save_jsonl


def summarize(plan):
    return {
        "book_type": plan.get("book_type"),
        "type_confidence": plan.get("type_confidence"),
        "sections": plan.get("sections", []),
        "signals": plan.get("signals", []),
        "capability_gaps": plan.get("capability_gaps", []),
        "recommended_recipe": plan.get("recommended_recipe"),
        "warnings": plan.get("warnings", []),
    }


def main():
    parser = argparse.ArgumentParser(description="Confirm intake plan before running downstream recipe")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--auto-approve", "--auto_approve", dest="auto_approve", action="store_true", help="Skip prompt and approve plan")
    parser.add_argument("--state-file", dest="state_file", help="pipeline state file (ignored)", default=None)
    parser.add_argument("--progress-file", dest="progress_file", help="pipeline progress log (ignored)", default=None)
    parser.add_argument("--run-id", dest="run_id", help="run id (ignored)", default=None)
    args, _unknown = parser.parse_known_args()

    rows = list(read_jsonl(args.plan))
    plan = rows[0] if rows else {}

    summary = summarize(plan)
    print("=== Plan Summary ===")
    print(json.dumps(summary, indent=2))
    approved = args.auto_approve
    if not approved:
        resp = input("Proceed with this plan? [y/N]: ").strip().lower()
        approved = resp in {"y", "yes"}

    if not approved:
        print("Plan not approved. Exiting with code 2.")
        sys.exit(2)

    ensure_dir(Path(args.out).parent)
    save_jsonl(args.out, [plan])
    print(f"Plan confirmed. Written to {args.out}")


if __name__ == "__main__":
    main()
