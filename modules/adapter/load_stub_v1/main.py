import argparse
import json
import os
from pathlib import Path

from modules.common.utils import ensure_dir, save_jsonl, read_jsonl, ProgressLogger, save_json


def main():
    ap = argparse.ArgumentParser(description="Copy stub JSON/JSONL to target, optionally overriding schema_version.")
    ap.add_argument("--stub", required=True, help="Path to source stub (json or jsonl)")
    ap.add_argument("--out", required=True, help="Destination path")
    ap.add_argument("--schema-version", dest="schema_version", help="If set, overwrite schema_version on each row (jsonl only)")
    ap.add_argument("--progress-file")
    ap.add_argument("--state-file")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    ensure_dir(os.path.dirname(args.out) or ".")

    if args.stub.endswith(".jsonl"):
        rows = list(read_jsonl(args.stub))
        if args.schema_version:
            for r in rows:
                r["schema_version"] = args.schema_version
        save_jsonl(args.out, rows)
        logger.log("adapter", "done", current=len(rows), total=len(rows),
                   message="Copied stub jsonl", artifact=args.out, module_id="load_stub_v1")
        print(f"[stub] copied {len(rows)} rows → {args.out}")
    else:
        data = json.load(open(args.stub, "r", encoding="utf-8"))
        if args.schema_version and isinstance(data, dict):
            data["schema_version"] = args.schema_version
        save_json(args.out, data)
        logger.log("adapter", "done", current=1, total=1,
                   message="Copied stub json", artifact=args.out, module_id="load_stub_v1")
        print(f"[stub] copied json → {args.out}")


if __name__ == "__main__":
    main()
