import argparse
import json
import os
from pathlib import Path

from modules.common.utils import ensure_dir, save_jsonl, ProgressLogger


def join_lines(lines):
    return "\n".join([l.get("text", "") for l in lines])


def main():
    parser = argparse.ArgumentParser(description="Convert PageLines IR to clean_page_v1 JSONL.")
    parser.add_argument("--index", required=True, help="pagelines_index.json")
    parser.add_argument("--out", required=True, help="pages_clean.jsonl output path")
    parser.add_argument("--outdir", help=argparse.SUPPRESS)  # tolerate driver auto-flag
    parser.add_argument("--preserve-numeric-lines", action="store_true", default=True,
                        help="If set, keep standalone numeric lines (1-400) so headers survive cleaning.")
    parser.add_argument("--progress-file", help="pipeline_events.jsonl")
    parser.add_argument("--state-file", help="pipeline_state.json")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    index = json.load(open(args.index, "r", encoding="utf-8"))
    rows = []
    total = len(index)
    for i, (page_str, path) in enumerate(sorted(index.items(), key=lambda kv: int(kv[0]))):
        page_path = Path(path)
        data = json.load(open(page_path, "r", encoding="utf-8"))
        lines = data.get("lines", [])
        if not args.preserve_numeric_lines:
            text = join_lines(lines)
        else:
            filtered = []
            for l in lines:
                t = l.get("text", "")
                # Keep numeric-only lines (likely headers) so header detection sees them
                if t.strip().isdigit():
                    filtered.append(l)
                    continue
                filtered.append(l)
            text = "\n".join([l.get("text", "") for l in filtered])
        row = {
            "schema_version": "clean_page_v1",
            "module_id": "pagelines_to_clean_v1",
            "run_id": args.run_id,
            "page": int(data.get("page", page_str)),
            "image": data.get("image"),
            "raw_text": text,
            "clean_text": text,
            "confidence": 1.0,
        }
        rows.append(row)
        logger.log("pagelines_to_clean", "running", current=i+1, total=total,
                   message=f"page {row['page']}", artifact=args.out,
                   module_id="pagelines_to_clean_v1", schema_version="clean_page_v1")

    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, rows)
    logger.log("pagelines_to_clean", "done", current=total, total=total,
               message="pagelines → clean complete", artifact=args.out,
               module_id="pagelines_to_clean_v1", schema_version="clean_page_v1")
    print(f"Wrote {len(rows)} clean pages to {args.out}")


if __name__ == "__main__":
    main()
