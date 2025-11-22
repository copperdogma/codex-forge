import argparse
from typing import List, Dict

from modules.common.utils import read_jsonl, append_jsonl, ProgressLogger
from schemas import PortionHypothesis


def group_pages(pages: List[Dict], group_size: int) -> List[List[Dict]]:
    grouped = []
    batch = []
    for page in pages:
        batch.append(page)
        if len(batch) == group_size:
            grouped.append(batch)
            batch = []
    if batch:
        grouped.append(batch)
    return grouped


def main():
    parser = argparse.ArgumentParser(description="Deterministic page-based portionizer (no LLM).")
    parser.add_argument("--pages", required=True, help="Path to pages_clean.jsonl")
    parser.add_argument("--out", required=True, help="Output hypotheses JSONL path")
    parser.add_argument("--group_size", type=int, default=1, help="Number of pages per portion")
    parser.add_argument("--confidence", type=float, default=0.4, help="Assigned confidence per portion")
    parser.add_argument("--pstart", type=int, help="First page to include (1-based)")
    parser.add_argument("--pend", type=int, help="Last page to include (inclusive)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    pages = [p for p in read_jsonl(args.pages)]
    if args.pstart or args.pend:
        start = args.pstart or pages[0]["page"]
        end = args.pend or pages[-1]["page"]
        pages = [p for p in pages if start <= p["page"] <= end]
    if not pages:
        raise SystemExit("No pages to process.")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    grouped = group_pages(pages, args.group_size)
    total = len(grouped)
    portion_idx = 1

    for idx, batch in enumerate(grouped, start=1):
        page_start = batch[0]["page"]
        page_end = batch[-1]["page"]
        portion = PortionHypothesis(
            portion_id=f"G{portion_idx:03d}",
            page_start=page_start,
            page_end=page_end,
            title=None,
            type=None,
            confidence=args.confidence,
            notes="deterministic page grouping",
            source_window=[b["page"] for b in batch],
            source_pages=list(range(page_start, page_end + 1))
        )
        append_jsonl(args.out, portion.dict())
        portion_idx += 1
        logger.log("portionize", "running", current=idx, total=total,
                   message=f"group {idx}/{total} pages {page_start}-{page_end}",
                   artifact=args.out)

    logger.log("portionize", "done", current=total, total=total,
               message=f"Wrote {total} grouped portions", artifact=args.out)
    print(f"Wrote {total} portion hypotheses to {args.out}")


if __name__ == "__main__":
    main()
