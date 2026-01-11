#!/usr/bin/env python3
"""
Orphan Re-OCR Candidate Selector

Flags source sections for image re-OCR when orphan IDs are similar to
highly-linked targets (e.g., 307 vs 397 due to OCR digit-shape confusion).
Outputs the full portions JSONL with repair_hints annotations.
"""

import argparse
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from modules.common.utils import ProgressLogger, read_jsonl, save_jsonl


DEFAULT_CONFUSIONS: Dict[str, List[str]] = {
    "0": ["9"],
    "9": ["0"],
    "6": ["8"],
    "8": ["6", "3"],
    "3": ["8"],
    "1": ["7"],
    "7": ["1"],
    "5": ["6"],
    "2": ["7"],
}


def _digits_only(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s if s.isdigit() else None


def _shape_candidates(orphan_id: str, *, confusion_map: Dict[str, List[str]]) -> Set[str]:
    candidates: Set[str] = set()
    for i, ch in enumerate(orphan_id):
        for repl in confusion_map.get(ch, []):
            cand = orphan_id[:i] + repl + orphan_id[i + 1:]
            if cand.isdigit() and not cand.startswith("0"):
                candidates.add(cand)
    return candidates


def _choice_targets(portion: Dict[str, Any]) -> Set[str]:
    targets: Set[str] = set()
    for choice in portion.get("choices", []) or []:
        target = _digits_only(choice.get("target"))
        if target:
            targets.add(target)
    return targets


def _incoming_map(portions: List[Dict[str, Any]]) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    incoming: Dict[str, List[str]] = {}
    counts: Dict[str, int] = {}
    for p in portions:
        sid = _digits_only(p.get("section_id") or p.get("portion_id"))
        if not sid:
            continue
        for tgt in _choice_targets(p):
            incoming.setdefault(tgt, []).append(sid)
            counts[tgt] = counts.get(tgt, 0) + 1
    return incoming, counts


def _compute_orphans(portions: List[Dict[str, Any]]) -> Set[str]:
    existing: Set[str] = set()
    referenced: Set[str] = set()
    for p in portions:
        sid = _digits_only(p.get("section_id") or p.get("portion_id"))
        if sid:
            existing.add(sid)
        referenced.update(_choice_targets(p))
    return {sid for sid in existing if sid not in referenced and sid != "1"}


def _parse_confusions(arg: str) -> Dict[str, List[str]]:
    if not arg:
        return DEFAULT_CONFUSIONS
    out: Dict[str, List[str]] = {}
    pairs = [p.strip() for p in arg.split(",") if p.strip()]
    for pair in pairs:
        if ":" not in pair:
            continue
        src, dsts = pair.split(":", 1)
        src = src.strip()
        dst_list = [d.strip() for d in dsts.split("|") if d.strip()]
        if src and dst_list:
            out[src] = dst_list
    return out or DEFAULT_CONFUSIONS


def _apply_hint(portion: Dict[str, Any], *, orphan_id: str, suspect_target: str, inbound: int) -> None:
    hints = portion.get("repair_hints") or {}
    reasons = list(hints.get("escalation_reasons") or [])
    if "orphan_similar_target" not in reasons:
        reasons.append("orphan_similar_target")
    hints["escalation_reasons"] = reasons
    details = list(hints.get("orphan_similar_target") or [])
    details.append({
        "orphan_id": orphan_id,
        "suspect_target": suspect_target,
        "inbound": inbound,
    })
    hints["orphan_similar_target"] = details
    portion["repair_hints"] = hints


def main() -> None:
    ap = argparse.ArgumentParser(description="Flag orphan-related OCR-shape candidates for re-OCR.")
    ap.add_argument("--portions", help="Input enriched_portion_v1 JSONL")
    ap.add_argument("--inputs", help="Input portions JSONL (driver compatibility)")
    ap.add_argument("--pages", help="Input portions JSONL (driver compatibility)")
    ap.add_argument("--out", required=True, help="Output JSONL with repair_hints annotations")
    ap.add_argument("--min-target", "--min_target", type=int, default=1)
    ap.add_argument("--max-target", "--max_target", type=int, default=400)
    ap.add_argument("--min-inbound", "--min_inbound", type=int, default=2, help="Min inbound links for a suspect target to be considered")
    ap.add_argument("--max-candidates", "--max_candidates", type=int, default=80, help="Cap total flagged source sections")
    ap.add_argument("--confusions", type=str, default="", help="Digit confusion map (e.g., 0:9,9:0,6:8,8:6|3)")
    ap.add_argument("--state-file")
    ap.add_argument("--progress-file")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    portions_path = args.portions or args.inputs or args.pages
    if not portions_path:
        raise SystemExit("Missing --portions/--inputs/--pages")
    portions = list(read_jsonl(portions_path))
    incoming, counts = _incoming_map(portions)
    orphans = sorted(_compute_orphans(portions), key=lambda x: int(x))
    confusion_map = _parse_confusions(args.confusions)

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "orphan_reocr_candidates",
        "running",
        current=0,
        total=len(portions),
        message=f"Scanning {len(orphans)} orphans for shape-confusion candidates",
        artifact=args.out,
        module_id="orphan_reocr_candidates_v1",
    )

    flagged_sources: Set[str] = set()
    flagged_count = 0
    for orphan in orphans:
        candidates = _shape_candidates(orphan, confusion_map=confusion_map)
        for cand in candidates:
            if not cand.isdigit():
                continue
            cand_int = int(cand)
            if cand_int < args.min_target or cand_int > args.max_target:
                continue
            inbound = counts.get(cand, 0)
            if inbound < args.min_inbound:
                continue
            for source in incoming.get(cand, []):
                if flagged_count >= args.max_candidates:
                    break
                if source in flagged_sources:
                    continue
                # Apply repair hint to source portion
                for portion in portions:
                    sid = _digits_only(portion.get("section_id") or portion.get("portion_id"))
                    if sid == source:
                        _apply_hint(portion, orphan_id=orphan, suspect_target=cand, inbound=inbound)
                        flagged_sources.add(source)
                        flagged_count += 1
                        break
            if flagged_count >= args.max_candidates:
                break
        if flagged_count >= args.max_candidates:
            break

    save_jsonl(args.out, portions)

    logger.log(
        "orphan_reocr_candidates",
        "done",
        current=len(portions),
        total=len(portions),
        message=f"Flagged {flagged_count} sources across {len(orphans)} orphans",
        artifact=args.out,
        module_id="orphan_reocr_candidates_v1",
    )
    print(f"Flagged {flagged_count} source sections for re-OCR")


if __name__ == "__main__":
    main()
