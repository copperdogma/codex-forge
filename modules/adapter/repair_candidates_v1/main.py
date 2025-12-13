import argparse
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from modules.common.utils import ensure_dir, ProgressLogger, read_jsonl, save_jsonl


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _normalize_page_numbers(pages: Sequence[Any]) -> Set[int]:
    normalized: Set[int] = set()
    for val in pages:
        if isinstance(val, (str, int)):
            page = _int_or_none(val)
            if page is not None:
                normalized.add(page)
    return normalized


def _load_pagelines(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise SystemExit(f"Pagelines input not found: {path}")
    return list(read_jsonl(path))


def _load_portions(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise SystemExit(f"Portions input not found: {path}")
    return list(read_jsonl(path))


def _portion_pages(portion: Dict[str, Any]) -> Set[int]:
    pages = set()
    for key in ("source_pages",):
        for val in portion.get(key) or []:
            page = _int_or_none(val)
            if page is not None:
                pages.add(page)
    start = _int_or_none(portion.get("page_start"))
    end = _int_or_none(portion.get("page_end"))
    if start is not None:
        pages.add(start)
        if end is not None and end >= start:
            pages.update(range(start, end + 1))
    elif end is not None:
        pages.add(end)
    return pages


def select_candidates(
    pagelines: List[Dict[str, Any]],
    portions: List[Dict[str, Any]],
    *,
    char_confusion_threshold: float,
    dictionary_oov_threshold: float,
    include_escalation_reasons: bool,
    forced_pages: Set[int],
    forced_portions: Set[str],
    max_candidates: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    page_metrics: Dict[int, Dict[str, Any]] = {}
    flagged_pages: Set[int] = set(forced_pages)
    for row in pagelines:
        page = _int_or_none(row.get("page"))
        if page is None:
            continue
        qm = row.get("quality_metrics") or {}
        char_conf = float(qm.get("char_confusion_score") or 0.0)
        dict_oov = float(qm.get("dictionary_oov_ratio") or 0.0)
        reasons = row.get("escalation_reasons") or row.get("prev_escalation_reasons") or []
        metric = {
            "char_confusion_score": char_conf,
            "dictionary_oov_ratio": dict_oov,
            "escalation_reasons": reasons,
        }
        page_metrics[page] = metric
        if char_conf >= char_confusion_threshold or dict_oov >= dictionary_oov_threshold:
            flagged_pages.add(page)
        if include_escalation_reasons and reasons:
            if "char_confusion" in reasons:
                flagged_pages.add(page)

    annotated: List[Dict[str, Any]] = []
    stats = {
        "pages_scanned": len(pagelines),
        "portions_scanned": len(portions),
        "flagged_pages": sorted(flagged_pages),
    }
    flagged_so_far = 0
    for portion in portions:
        portion_id = str(portion.get("portion_id") or portion.get("section_id") or "")
        section_pages = _portion_pages(portion)
        intersect = section_pages & flagged_pages
        should_flag = bool(intersect) or portion_id in forced_portions
        hints: Dict[str, Any] = {
            "flagged_pages": sorted(intersect) if intersect else [],
            "pages": sorted(section_pages),
            "char_confusion_score": None,
            "dictionary_oov_ratio": None,
            "escalation_reasons": [],
        }
        if intersect:
            scores = [page_metrics[p] for p in intersect if p in page_metrics]
            if scores:
                hints["char_confusion_score"] = max(s["char_confusion_score"] for s in scores)
                hints["dictionary_oov_ratio"] = max(s["dictionary_oov_ratio"] for s in scores)
                hints["escalation_reasons"] = sorted({r for s in scores for r in s.get("escalation_reasons") or []})
        can_flag = not max_candidates or flagged_so_far < max_candidates
        if should_flag and can_flag:
            portion["repair_hints"] = hints
            flagged_so_far += 1
        else:
            portion.setdefault("repair_hints", hints)
        annotated.append(portion)
    stats["candidate_count"] = flagged_so_far
    return annotated, stats


def main():
    parser = argparse.ArgumentParser(description="Find portions that should be sent through the repair loop.")
    parser.add_argument("--pages", help="Unused; accepted for compatibility.", default=None)
    parser.add_argument("--portions", required=True, help="Input enriched portions (jsonl).")
    parser.add_argument("--out", required=True, help="Candidate portions artifact (jsonl).")
    parser.add_argument("--pagelines", help="Path to pagelines_final.jsonl (relative to run dir).", default="pagelines_final.jsonl")
    parser.add_argument("--char-confusion-threshold", "--char_confusion_threshold", type=float, default=0.25)
    parser.add_argument("--dictionary-oov-threshold", "--dictionary_oov_threshold", type=float, default=0.35)
    parser.add_argument("--include-escalation-reasons", "--include_escalation_reasons", action="store_true")
    parser.add_argument("--force-pages", "--force_pages", type=str, default="")
    parser.add_argument("--force-portions", "--force_portions", type=str, default="")
    parser.add_argument("--max-candidates", "--max_candidates", type=int, default=40)
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    pagelines_path = args.pagelines
    if not os.path.isabs(pagelines_path):
        pagelines_path = os.path.join(base_dir, pagelines_path)

    forced_pages = _normalize_page_numbers(args.force_pages.split(",")) if args.force_pages else set()
    forced_portions = {p.strip() for p in (args.force_portions or "").split(",") if p.strip()}

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("repair_candidates", "running", current=0, total=0,
               message="Selecting candidate portions", artifact=args.out,
               module_id="repair_candidates_v1", schema_version="enriched_portion_v1")

    pagelines = _load_pagelines(pagelines_path)
    portions = _load_portions(args.portions)
    candidates, stats = select_candidates(
        pagelines,
        portions,
        char_confusion_threshold=args.char_confusion_threshold,
        dictionary_oov_threshold=args.dictionary_oov_threshold,
        include_escalation_reasons=args.include_escalation_reasons,
        forced_pages=forced_pages,
        forced_portions=forced_portions,
        max_candidates=args.max_candidates,
    )

    ensure_dir(os.path.dirname(args.out) or ".")
    save_jsonl(args.out, candidates)

    logger.log("repair_candidates", "done", current=len(portions), total=len(portions),
               message=f"Candidates: {len(candidates)} portions flagged", artifact=args.out,
               module_id="repair_candidates_v1", schema_version="enriched_portion_v1")

    flagged = stats.get("candidate_count", 0)
    print(f"Flagged {flagged} portions (from {len(portions)} scanned)")
    print(f"Flagged pages: {stats['flagged_pages']}")


if __name__ == "__main__":
    main()
