import argparse
import json
import string
from pathlib import Path
from typing import Any, Dict, Iterable, List

from modules.common.utils import ProgressLogger, read_jsonl, save_jsonl

PUNCTUATION = set(".!?;""'")


def iter_lines_from_pagelines(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            yield json.loads(line)


def detect_truncated_lines(lines: List[str], min_len: int) -> List[str]:
    warnings: List[str] = []
    for text in lines:
        stripped = text.strip()
        if len(stripped) < min_len:
            continue
        last_char = stripped[-1]
        if stripped.endswith("..."):
            continue
        if last_char not in PUNCTUATION and not last_char.isupper():
            warnings.append(stripped)
    return warnings


def main():
    parser = argparse.ArgumentParser(description="Detect truncated sentences in pagelines_final.jsonl.")
    parser.add_argument("--pagelines", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-len", type=int, default=50)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    warnings: List[Dict[str, Any]] = []
    pagelines = list(iter_lines_from_pagelines(args.pagelines))
    logger.log("truncation", "running", current=0, total=len(pagelines),
               artifact=args.out, module_id="truncation_detector_v1", message="Scanning for truncated text")
    for idx, page in enumerate(pagelines, start=1):
        lines = [ln.get("text") or "" for ln in page.get("lines", []) if isinstance(ln, dict)]
        truncated = detect_truncated_lines(lines, args.min_len)
        for snippet in truncated:
            warnings.append({
                "page": page.get("page"),
                "snippet": snippet[:100],
                "line_count": len(lines),
            })
        if idx % 25 == 0:
            logger.log("truncation", "running", current=idx, total=len(pagelines),
                       artifact=args.out, module_id="truncation_detector_v1",
                       message=f"Scanned {idx}/{len(pagelines)} pages")
    save_jsonl(args.out, warnings)
    logger.log("truncation", "done", current=len(pagelines), total=len(pagelines),
               artifact=args.out, module_id="truncation_detector_v1", message=f"Found {len(warnings)} truncated lines")

if __name__ == "__main__":
    main()
