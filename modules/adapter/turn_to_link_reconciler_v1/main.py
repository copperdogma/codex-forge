#!/usr/bin/env python3
"""Reconcile turn-to links against claims and report unclaimed targets."""
import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from modules.common.utils import ensure_dir, ProgressLogger


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _claim_key(row: Dict[str, Any]) -> Optional[str]:
    section_id = row.get("section_id")
    if section_id:
        return str(section_id)
    portion_id = row.get("portion_id")
    if portion_id:
        return str(portion_id)
    return None


def _build_claim_index(claims: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    claimed: Set[Tuple[str, str]] = set()
    for claim in claims:
        sid = _claim_key(claim) or ""
        target = str(claim.get("target") or "")
        if sid and target:
            claimed.add((sid, target))
    return claimed


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile turn-to links against claims.")
    parser.add_argument("--links", help="turn_to_links.jsonl or portions.jsonl")
    parser.add_argument("--claims", help="turn_to_link_claims.jsonl")
    parser.add_argument("--inputs", nargs="*", help="Driver adapter inputs (links, claims)")
    parser.add_argument("--out", required=True, help="Output JSONL report")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path))

    links_path = args.links
    claims_path = args.claims
    if args.inputs:
        if not links_path:
            links_path = args.inputs[0]
        if len(args.inputs) > 1 and not claims_path:
            claims_path = args.inputs[1]

    if not links_path:
        raise SystemExit("turn_to_link_reconciler_v1 requires --links or --inputs")

    link_rows = _load_jsonl(links_path)
    claim_rows = _load_jsonl(claims_path) if claims_path else []
    claimed = _build_claim_index(claim_rows)

    issues: List[Dict[str, Any]] = []
    total_links = 0
    for row in link_rows:
        section_id = _claim_key(row) or ""
        if not section_id:
            continue
        page_start = row.get("pageStart")
        page_end = row.get("pageEnd")
        links = row.get("links") or row.get("turn_to_links") or []
        for link in links:
            if isinstance(link, dict):
                target = str(link.get("target") or "")
            else:
                target = str(link)
            if not target:
                continue
            total_links += 1
            if (section_id, target) in claimed:
                continue
            issues.append({
                "section_id": section_id,
                "target": target,
                "pageStart": page_start,
                "pageEnd": page_end,
                "reason_code": "unclaimed_turn_to",
            })

    summary = {
        "sections": len(link_rows),
        "links_total": total_links,
        "claims_total": len(claimed),
        "unclaimed_total": len(issues),
    }

    report = {
        "schema_version": "turn_to_unclaimed_v1",
        "module_id": "turn_to_link_reconciler_v1",
        "run_id": args.run_id,
        "created_at": _utc(),
        "summary": summary,
        "issues": issues,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=True) + "\n")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "turn_to_link_reconciler",
        "done",
        current=summary["unclaimed_total"],
        total=summary["links_total"],
        message=f"Unclaimed links: {summary['unclaimed_total']} of {summary['links_total']}",
        artifact=out_path,
        module_id="turn_to_link_reconciler_v1",
        schema_version="turn_to_unclaimed_v1",
        extra={"summary_metrics": summary},
    )
    print(f"[summary] turn_to_link_reconciler_v1: {summary['unclaimed_total']} unclaimed → {out_path}")


if __name__ == "__main__":
    main()
