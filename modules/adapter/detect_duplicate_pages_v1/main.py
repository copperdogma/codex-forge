#!/usr/bin/env python3
"""
Detect and drop near-duplicate pages using whole-page text similarity.
Intended for early pipeline use (pre-section parsing).
"""
import argparse
import json
import os
import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger
from modules.common.html_utils import html_to_text


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _filter_lines(text: str) -> str:
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    kept: List[str] = []
    for ln in lines:
        if re.fullmatch(r"\d+\s*-\s*\d+", ln):
            continue
        if re.fullmatch(r"\d+", ln):
            continue
        if re.fullmatch(r"page\s+\d+", ln):
            continue
        if len(ln) < 3:
            continue
        kept.append(ln)
    return " ".join(kept)


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    tokens = [t for t in text.split() if len(t) >= 2]
    return tokens


def _similarity(tokens_a: List[str], tokens_b: List[str], text_a: str, text_b: str) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    jaccard = inter / max(1, union)
    seq_ratio = SequenceMatcher(None, text_a, text_b).ratio() if text_a and text_b else 0.0
    return max(jaccard, seq_ratio)


def _page_key(page: Dict[str, Any]) -> Tuple[int, int]:
    page_number = page.get("page_number")
    original_page = page.get("original_page_number")
    try:
        page_number = int(page_number)
    except Exception:
        page_number = 0
    try:
        original_page = int(original_page)
    except Exception:
        original_page = 0
    return (page_number, original_page)


def _build_page_text(page: Dict[str, Any]) -> str:
    html = page.get("html") or ""
    text = html_to_text(html)
    text = _normalize_text(_filter_lines(text))
    return text


def _extract_header_numbers(html: str) -> List[str]:
    if not html:
        return []
    return re.findall(r"<h2>\s*(\d+)\s*</h2>", html, flags=re.IGNORECASE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect and drop near-duplicate pages")
    parser.add_argument("--inputs", nargs="*", help="Driver inputs")
    parser.add_argument("--pages", help="Path to page_html_v1 JSONL")
    parser.add_argument("--out", required=True, help="Output JSONL path for deduped pages")
    parser.add_argument("--report-out", dest="report_out", default="duplicate_pages.json", help="Output report JSON")
    parser.add_argument("--similarity-threshold", dest="similarity_threshold", type=float, default=0.95)
    parser.add_argument("--similarity_threshold", dest="similarity_threshold", type=float, default=0.95)
    parser.add_argument("--min-tokens", dest="min_tokens", type=int, default=120)
    parser.add_argument("--min_tokens", dest="min_tokens", type=int, default=120)
    parser.add_argument("--max-lookback", dest="max_lookback", type=int, default=3)
    parser.add_argument("--max_lookback", dest="max_lookback", type=int, default=3)
    parser.add_argument("--max-page-gap", dest="max_page_gap", type=int, default=3)
    parser.add_argument("--max_page_gap", dest="max_page_gap", type=int, default=3)
    parser.add_argument("--header-overlap-threshold", dest="header_overlap_threshold", type=float, default=0.88)
    parser.add_argument("--header_overlap_threshold", dest="header_overlap_threshold", type=float, default=0.88)
    parser.add_argument("--require-header-overlap", dest="require_header_overlap", action="store_true")
    parser.add_argument("--require_header_overlap", dest="require_header_overlap", action="store_true")
    parser.add_argument("--allow-frontmatter-dedupe", dest="allow_frontmatter_dedupe", action="store_true")
    parser.add_argument("--allow_frontmatter_dedupe", dest="allow_frontmatter_dedupe", action="store_true")
    parser.add_argument("--frontmatter-max-page", dest="frontmatter_max_page", type=int, default=0)
    parser.add_argument("--frontmatter_max_page", dest="frontmatter_max_page", type=int, default=0)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages_path = args.pages or (args.inputs[0] if args.inputs else None)
    if not pages_path:
        raise SystemExit("Missing --pages or --inputs")
    if not os.path.exists(pages_path):
        raise SystemExit(f"Missing pages file: {pages_path}")

    out_path = os.path.abspath(args.out)
    out_dir = os.path.dirname(out_path)
    ensure_dir(out_dir)
    report_path = args.report_out
    if not os.path.isabs(report_path):
        report_path = os.path.join(out_dir, report_path)

    pages = list(read_jsonl(pages_path))
    if not pages:
        raise SystemExit(f"Input is empty: {pages_path}")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "adapter",
        "running",
        current=0,
        total=len(pages),
        message="Detecting duplicate pages",
        artifact=out_path,
        module_id="detect_duplicate_pages_v1",
        schema_version="page_html_v1",
    )

    kept_pages: List[Dict[str, Any]] = []
    kept_texts: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []

    for idx, page in enumerate(pages, start=1):
        text = _build_page_text(page)
        tokens = _tokenize(text)
        headers = _extract_header_numbers(page.get("html") or "")
        page_number = page.get("page_number") or 0
        best_match: Optional[Dict[str, Any]] = None
        best_score = 0.0

        # Compare to recent kept pages only.
        for prev in kept_texts[-args.max_lookback:]:
            gap = abs(prev["page_number"] - page.get("page_number", 0))
            if gap > args.max_page_gap:
                continue
            score = _similarity(tokens, prev["tokens"], text, prev["text"])
            header_overlap = bool(set(headers) & set(prev["headers"]))
            if score > best_score:
                best_score = score
                best_match = {**prev, "header_overlap": header_overlap}

        is_duplicate = False
        if best_match:
            threshold = args.similarity_threshold
            if best_match.get("header_overlap"):
                threshold = min(threshold, args.header_overlap_threshold)
            if best_score >= threshold:
                if len(tokens) >= args.min_tokens and len(best_match["tokens"]) >= args.min_tokens:
                    if args.require_header_overlap and not best_match.get("header_overlap"):
                        is_duplicate = False
                    else:
                        if args.allow_frontmatter_dedupe:
                            is_duplicate = True
                        else:
                            if args.frontmatter_max_page and page_number and page_number <= args.frontmatter_max_page:
                                is_duplicate = False
                            else:
                                is_duplicate = True

        if is_duplicate:
            duplicates.append({
                "page_number": page.get("page_number"),
                "original_page_number": page.get("original_page_number"),
                "duplicate_of_page": best_match["page_number"],
                "duplicate_of_original_page": best_match["original_page_number"],
                "similarity": round(best_score, 4),
                "header_overlap": bool(best_match.get("header_overlap")),
                "threshold_used": round(min(args.similarity_threshold, args.header_overlap_threshold) if best_match.get("header_overlap") else args.similarity_threshold, 4),
                "token_count": len(tokens),
                "matched_token_count": len(best_match["tokens"]),
                "text_excerpt": text[:240],
            })
            continue

        kept_pages.append(page)
        kept_texts.append({
            "page_number": page.get("page_number"),
            "original_page_number": page.get("original_page_number"),
            "tokens": tokens,
            "text": text,
            "headers": headers,
        })

        logger.log(
            "adapter",
            "running",
            current=idx,
            total=len(pages),
            message=f"Processed page {page.get('page_number')}",
            artifact=out_path,
            module_id="detect_duplicate_pages_v1",
            schema_version="page_html_v1",
        )

    save_jsonl(out_path, kept_pages)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "schema_version": "duplicate_page_report_v1",
            "total_pages": len(pages),
            "kept_pages": len(kept_pages),
            "duplicate_pages": len(duplicates),
            "duplicates": duplicates,
        }, f, ensure_ascii=True, indent=2)

    logger.log(
        "adapter",
        "done",
        current=len(kept_pages),
        total=len(pages),
        message=f"Deduped pages: {len(duplicates)} dropped",
        artifact=out_path,
        module_id="detect_duplicate_pages_v1",
        schema_version="page_html_v1",
    )


if __name__ == "__main__":
    main()
