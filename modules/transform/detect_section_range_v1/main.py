#!/usr/bin/env python3
import argparse
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from modules.common.utils import read_jsonl, save_json

SECTION_HEADER_RE = re.compile(r"<h2>\s*(\d+)\s*</h2>", re.IGNORECASE)


def _numeric_ids_from_portions(portions: Iterable[dict]) -> List[int]:
    numeric_ids: List[int] = []
    for row in portions:
        sid = row.get("section_id")
        if sid is None:
            continue
        sid_str = str(sid).strip()
        if sid_str.isdigit():
            numeric_ids.append(int(sid_str))
    return numeric_ids


def _collect_references(portions: Iterable[dict]) -> Set[int]:
    refs: Set[int] = set()
    for row in portions:
        # raw turn-to signals available immediately after portionize
        for key in ("turn_to_links", "turn_to_claims"):
            for target in row.get(key, []) or []:
                if target is not None and str(target).isdigit():
                    refs.add(int(str(target)))
        # choices
        for choice in row.get("choices", []) or []:
            target = choice.get("target")
            if target is not None and str(target).isdigit():
                refs.add(int(str(target)))
        # combat
        for combat in row.get("combat", []) or []:
            for key in ("win_section", "loss_section", "escape_section"):
                target = combat.get(key)
                if target is not None and str(target).isdigit():
                    refs.add(int(str(target)))
        # stat checks
        for check in row.get("stat_checks", []) or []:
            for key in ("pass_section", "fail_section"):
                target = check.get(key)
                if target is not None and str(target).isdigit():
                    refs.add(int(str(target)))
        # test luck
        for luck in row.get("test_luck", []) or []:
            for key in ("lucky_section", "unlucky_section"):
                target = luck.get(key)
                if target is not None and str(target).isdigit():
                    refs.add(int(str(target)))
        # inventory checks
        inv = row.get("inventory") or {}
        for check in inv.get("inventory_checks", []) or []:
            target = check.get("target_section")
            if target is not None and str(target).isdigit():
                refs.add(int(str(target)))
        # state checks with resolved targets
        for check in row.get("state_checks", []) or []:
            if not isinstance(check, dict):
                continue
            for key in ("has_target", "missing_target"):
                target = check.get(key)
                if target is not None and str(target).isdigit():
                    refs.add(int(str(target)))
    return refs


def _scan_back_pages(pages: Iterable[dict], max_pages: int = 12) -> Optional[int]:
    tail_headers: List[int] = []
    scanned = 0
    for page in reversed(list(pages)):
        html = page.get("html") or page.get("raw_html") or ""
        if html:
            for match in SECTION_HEADER_RE.finditer(html):
                val = int(match.group(1))
                tail_headers.append(val)
        scanned += 1
        if scanned >= max_pages and tail_headers:
            break
    if not tail_headers:
        return None
    return max(tail_headers)


def compute_section_range(portions: Iterable[dict], pages: Optional[Iterable[dict]] = None) -> Dict[str, object]:
    header_ids = _numeric_ids_from_portions(portions)
    ref_ids = sorted(_collect_references(portions))
    min_section = min(header_ids) if header_ids else 1
    max_header = max(header_ids) if header_ids else None
    max_ref = max(ref_ids) if ref_ids else None
    backscan_max = _scan_back_pages(pages or []) if pages is not None else None

    confidence = "low"
    flags: List[str] = []

    if max_header is None and max_ref is None and backscan_max is None:
        max_section = 1
    elif max_header is None:
        max_section = max_ref or backscan_max or 1
    else:
        max_section = max_header

    if backscan_max is not None:
        if max_header is None:
            max_section = backscan_max
        else:
            if max_header > backscan_max and (max_ref is None or max_ref <= backscan_max):
                # Prefer the backscan when references don't exceed it; headers beyond are likely noise.
                max_section = backscan_max
                flags.append("headers_exceed_backscan")
                confidence = "medium"
            elif backscan_max == max_header:
                confidence = "high"
            elif abs(backscan_max - max_header) <= 1:
                confidence = "medium"

    if max_ref is not None and max_section is not None and max_ref > max_section:
        flags.append("refs_exceed_headers")
        if confidence in {"high", "medium"}:
            confidence = "conflict"

    return {
        "schema_version": "section_range_v2",
        "min_section": min_section,
        "max_section": max_section,
        "numeric_section_count": len(header_ids),
        "max_ref_section": max_ref,
        "backscan_max_section": backscan_max,
        "confidence": confidence,
        "flags": flags,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect numeric section range from portions.")
    parser.add_argument("--portions", required=True, help="Input portions JSONL")
    parser.add_argument("--pages", help="Optional pages HTML JSONL")
    parser.add_argument("--out", required=True, help="Output JSON")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    portions = list(read_jsonl(args.portions))
    pages = list(read_jsonl(args.pages)) if args.pages else None
    result = compute_section_range(portions, pages)
    save_json(args.out, result)


if __name__ == "__main__":
    main()
