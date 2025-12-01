import argparse
import re
import json
import os
from typing import List, Dict

from modules.common.utils import read_jsonl, append_jsonl, ProgressLogger
from schemas import PortionHypothesis

SECTION_RE = re.compile(r"^\s*(\d{1,3})\s*$")


def main():
    parser = argparse.ArgumentParser(description="Detect numbered Fighting Fantasy sections from clean pages (rule-based).")
    parser.add_argument("--pages", required=True, help="pages_clean.jsonl")
    parser.add_argument("--out", required=True, help="portion_hyp.jsonl")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    # reset output
    out_path = args.out
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(out_path):
        os.remove(out_path)

    pages = list(read_jsonl(args.pages))
    pages.sort(key=lambda p: p.get("page", 0))

    # collect line tuples
    markers: List[Dict] = []
    seen_ids = set()
    for p in pages:
        page_num = p["page"]
        lines = (p.get("clean_text") or p.get("raw_text") or "").splitlines()
        for idx, line in enumerate(lines):
            m = SECTION_RE.match(line)
            if not m:
                continue
            sid = m.group(1)
            if 1 <= int(sid) <= 400:
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                markers.append({"section_id": sid, "page": page_num, "line_idx": idx})

    markers.sort(key=lambda m: (m["page"], m["line_idx"]))
    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    for i, m in enumerate(markers):
        start_page = m["page"]
        end_page = pages[-1]["page"] if i == len(markers) - 1 else markers[i + 1]["page"]
        # gather text from start marker to just before next marker
        text_parts = []
        for p in pages:
            if p["page"] < start_page or p["page"] > end_page:
                continue
            lines = (p.get("clean_text") or p.get("raw_text") or "").splitlines()
            for line in lines:
                if SECTION_RE.match(line):
                    if p["page"] == start_page and SECTION_RE.match(line).group(1) == m["section_id"]:
                        continue  # skip the marker line
                    else:
                        break
                text_parts.append(line)
            else:
                continue
            if p["page"] == start_page:
                continue
            break

        hypo = PortionHypothesis(
            portion_id=m["section_id"],
            page_start=start_page,
            page_end=end_page,
            title=None,
            type="section",
            confidence=0.8,
            raw_text="\n".join(text_parts).strip(),
            source_window=[start_page, end_page],
            source_pages=list(range(start_page, end_page + 1)),
            source=["rule_section_detect"],
        )
        append_jsonl(args.out, hypo.dict())
        logger.log("portionize", "running", current=i + 1, total=len(markers),
                   message=f"section {m['section_id']} pages {start_page}-{end_page}",
                   artifact=args.out, module_id="portionize_detect_sections_v1")

    logger.log("portionize", "done", current=len(markers), total=len(markers),
               message=f"Detected {len(markers)} sections", artifact=args.out,
               module_id="portionize_detect_sections_v1")
    print(f"Detected {len(markers)} sections → {args.out}")


if __name__ == "__main__":
    main()
