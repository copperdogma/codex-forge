import argparse
import re
from typing import Dict, List, Set, Optional

from modules.common.utils import read_jsonl, save_jsonl, ProgressLogger


def load_portions(path: str, source_label: str) -> List[Dict]:
    portions = []
    for row in read_jsonl(path):
        src = set(row.get("source") or [])
        src.add(source_label)
        row["source"] = sorted(src)
        portions.append(row)
    return portions


def page_set(p: Dict) -> Set[int]:
    return set(range(p["page_start"], p["page_end"] + 1))


def dedupe_portions(portions: List[Dict]) -> List[Dict]:
    best = {}
    for p in portions:
        key = (p.get("portion_id"), p["page_start"], p["page_end"], p.get("title"), p.get("type"))
        if key not in best:
            best[key] = dict(p)
            continue

        current = best[key]
        if p.get("confidence", 0) > current.get("confidence", 0):
            # replace but keep unioned sources
            combined = set(current.get("source") or [])
            combined |= set(p.get("source") or [])
            best[key] = dict(p)
            best[key]["source"] = sorted(combined)
        else:
            # union sources even if lower confidence
            combined = set(current.get("source") or [])
            combined |= set(p.get("source") or [])
            current["source"] = sorted(combined)
            best[key] = current
    return list(best.values())


def collapse_duplicate_spans(portions: List[Dict]) -> List[Dict]:
    merged = {}
    for p in portions:
        key = (p["page_start"], p["page_end"], p.get("title"), p.get("type"))
        if key not in merged:
            merged[key] = dict(p)
            continue
        current = merged[key]
        if p.get("confidence", 0) > current.get("confidence", 0):
            merged[key] = dict(p)
            # ensure we keep unioned source info below
        merged[key]["source"] = sorted(set((current.get("source") or []) + (p.get("source") or [])))
        # keep highest continuation confidence
        if (p.get("continuation_confidence") or 0) > (current.get("continuation_confidence") or 0):
            merged[key]["continuation_of"] = p.get("continuation_of")
            merged[key]["continuation_confidence"] = p.get("continuation_confidence")
    return list(merged.values())


def title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    tok_a = set(re.findall(r"[A-Za-z0-9]+", a.lower()))
    tok_b = set(re.findall(r"[A-Za-z0-9]+", b.lower()))
    if not tok_a or not tok_b:
        return 0.0
    inter = len(tok_a & tok_b)
    union = len(tok_a | tok_b)
    return inter / union if union else 0.0


def attach_continuations(portions: List[Dict], gap: int, title_sim_thresh: float) -> List[Dict]:
    portions_sorted = sorted(portions, key=lambda p: (p["page_start"], p["page_end"]))
    for idx in range(len(portions_sorted) - 1):
        a = portions_sorted[idx]
        b = portions_sorted[idx + 1]
        gap_pages = b["page_start"] - a["page_end"] - 1
        if gap_pages > gap:
            continue
        if not a.get("portion_id"):
            continue

        score = 0.0
        if a.get("portion_id") == b.get("portion_id"):
            score += 0.6
        ts = title_similarity(a.get("title"), b.get("title"))
        if ts >= title_sim_thresh:
            score += 0.25 * (ts / max(title_sim_thresh, 0.01))
        if a.get("type") and a.get("type") == b.get("type"):
            score += 0.1
        score += 0.1 * min(a.get("confidence", 0.5), b.get("confidence", 0.5))

        if score >= 0.55:
            if not b.get("continuation_confidence") or score > b.get("continuation_confidence", 0):
                b["continuation_of"] = a.get("portion_id")
                b["continuation_confidence"] = round(min(1.0, score), 2)
    return portions_sorted


def merge_portions(fine: List[Dict], coarse: List[Dict], uncovered_thresh: float) -> List[Dict]:
    fine_cov: Set[int] = set()
    for p in fine:
        fine_cov |= page_set(p)

    merged: List[Dict] = []
    merged.extend(fine)

    for c in coarse:
        pages = page_set(c)
        if not pages:
            continue
        uncovered = pages - fine_cov
        ratio = len(uncovered) / len(pages)
        if ratio >= uncovered_thresh:
            merged.append(c)
    merged = dedupe_portions(merged)
    merged = collapse_duplicate_spans(merged)
    return merged


def main():
    parser = argparse.ArgumentParser(description="Merge coarse+fine portion hypotheses and add continuation links.")
    parser.add_argument("--coarse", help="Coarse portion hypotheses JSONL")
    parser.add_argument("--fine", help="Fine portion hypotheses JSONL")
    parser.add_argument("--inputs", nargs="+", help="Driver-provided inputs: expect [coarse fine]")
    parser.add_argument("--out", required=True, help="Merged portion hypotheses JSONL")
    parser.add_argument("--uncovered-threshold", "--uncovered_threshold", type=float, default=0.5, dest="uncovered_threshold")
    parser.add_argument("--continuation-gap", "--continuation_gap", type=int, default=1, help="Allowed gap (pages) between continuations.")
    parser.add_argument("--title-sim-threshold", "--title_sim_threshold", type=float, default=0.55, dest="title_sim_threshold")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    coarse_path: Optional[str] = args.coarse
    fine_path: Optional[str] = args.fine
    if args.inputs and len(args.inputs) >= 2:
        coarse_path = args.inputs[0]
        fine_path = args.inputs[1]
    if not coarse_path or not fine_path:
        raise SystemExit("merge_coarse_fine_v1 requires coarse and fine inputs (provide --coarse/--fine or --inputs coarse fine)")

    fine = load_portions(fine_path, "fine")
    coarse = load_portions(coarse_path, "coarse")

    logger.log("adapter", "running", current=0, total=len(fine) + len(coarse),
               message="Merging coarse+fine portion hypotheses", artifact=args.out,
               module_id="merge_coarse_fine_v1")

    merged = merge_portions(fine, coarse, uncovered_thresh=args.uncovered_threshold)
    merged = attach_continuations(merged, gap=args.continuation_gap, title_sim_thresh=args.title_sim_threshold)

    save_jsonl(args.out, merged)

    logger.log("adapter", "done", current=len(merged), total=len(merged),
               message=f"Merged portions → {len(merged)}", artifact=args.out,
               module_id="merge_coarse_fine_v1")
    print(f"[merge-coarse-fine] wrote {args.out} (fine={len(fine)}, coarse={len(coarse)}, merged={len(merged)})")


if __name__ == "__main__":
    main()
