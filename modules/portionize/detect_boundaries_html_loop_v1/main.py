#!/usr/bin/env python3
"""
Coverage guard + HTML-only repair loop for missing section headers.

Pattern: detect -> validate -> repair -> re-detect until coverage met or retries exhausted.
"""
import argparse
import base64
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from modules.common.openai_client import OpenAI
except Exception as exc:  # pragma: no cover
    OpenAI = None
    _OPENAI_IMPORT_ERROR = exc
else:
    _OPENAI_IMPORT_ERROR = None

from modules.common.utils import read_jsonl, save_jsonl, ensure_dir, ProgressLogger
from modules.adapter.html_to_blocks_v1.main import parse_blocks
from modules.portionize.detect_boundaries_html_v1.main import (
    build_candidates,
    dedupe_candidates,
    build_boundaries,
    apply_macro_section,
    filter_pages_to_gameplay,
    load_coarse_segments,
)
from modules.extract.ocr_ai_gpt51_v1.main import sanitize_html


SYSTEM_PROMPT = (
    "You are repairing HTML for a single book page. "
    "Preserve all content and tags; only adjust tags to correctly mark section numbers. "
    "Return HTML only, no commentary."
)
SYSTEM_PROMPT_IMAGE = (
    "You are repairing HTML for a single book page using the image as ground truth. "
    "Preserve all content and tags; only adjust tags to correctly mark section numbers. "
    "Return HTML only, no commentary."
)


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _coerce_int(val: Any) -> Optional[int]:
    if isinstance(val, int):
        return val
    if val is None:
        return None
    digits = ""
    for ch in str(val):
        if ch.isdigit():
            digits += ch
        else:
            break
    if digits:
        return int(digits)
    return None


def _extract_html(text: str) -> str:
    if not text:
        return ""
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return text.strip()


def _code_repair_html(html: str, expected_ids: List[int]) -> Tuple[str, bool]:
    repaired = html or ""
    changed = False
    for sec in expected_ids:
        for pattern in (
            rf"<p class=\"page-number\">\\s*{sec}\\s*</p>",
            rf"<p>\\s*{sec}\\s*</p>",
        ):
            repl = f"<h2>{sec}</h2>"
            repaired, count = re.subn(pattern, repl, repaired, flags=re.IGNORECASE)
            if count:
                changed = True
    return repaired, changed


def _prompt_for_expected(expected_ids: List[int]) -> str:
    expected = ", ".join(str(x) for x in expected_ids)
    return (
        "This page is from a numbered gamebook. "
        "Section numbers are standalone and should be wrapped in <h2> tags. "
        "Expected section IDs on this page may include: "
        f"{expected}. "
        "Only wrap numbers that appear as standalone numeric text (no other words). "
        "Do NOT wrap numbers inside tables, lists, or phrases like 'Turn to 16'. "
        "If a standalone expected number appears in <p class=\"page-number\">, "
        "it may actually be a section header; convert it to <h2>. "
        "Preserve running heads and page numbers otherwise "
        "(they are often marked as <p class=\"running-head\"> or <p class=\"page-number\">). "
        "Return the full corrected HTML for this page only."
    )


def _hash_prompt(system: str, user: str, model: str, mode: str) -> str:
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\n")
    h.update(user.encode("utf-8"))
    h.update(b"\n")
    h.update(model.encode("utf-8"))
    h.update(b"\n")
    h.update(mode.encode("utf-8"))
    return h.hexdigest()


def _repair_html(
    client: OpenAI,
    html: str,
    expected_ids: List[int],
    model: str,
    max_output_tokens: int,
    image_path: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    user_prompt = _prompt_for_expected(expected_ids)
    system = SYSTEM_PROMPT_IMAGE if image_path else SYSTEM_PROMPT
    mode = "image" if image_path else "html"
    if hasattr(client, "responses"):
        content = [
            {"type": "input_text", "text": user_prompt},
            {"type": "input_text", "text": html},
        ]
        if image_path:
            mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
            b64 = Path(image_path).read_bytes()
            content.append({
                "type": "input_image",
                "image_url": f"data:{mime};base64,{base64.b64encode(b64).decode('utf-8')}",
            })
        resp = client.responses.create(
            model=model,
            temperature=0,
            max_output_tokens=max_output_tokens,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {"role": "user", "content": content},
            ],
        )
        raw = resp.output_text or ""
        usage = getattr(resp, "usage", None)
        request_id = getattr(resp, "id", None)
    else:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
            {"role": "user", "content": html},
        ]
        if image_path:
            mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
            b64 = Path(image_path).read_bytes()
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(b64).decode('utf-8')}"}}
                ],
            })
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_completion_tokens=max_output_tokens,
            messages=messages,
        )
        raw = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        request_id = getattr(resp, "id", None)

    cleaned = sanitize_html(_extract_html(raw))
    return cleaned, {
        "usage": getattr(usage, "dict", lambda: usage)() if usage is not None else None,
        "request_id": request_id,
        "mode": mode,
    }


def _build_blocks(pages_html: List[Dict[str, Any]], drop_empty: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for page in pages_html:
        blocks = parse_blocks(page.get("html") or "", drop_empty=drop_empty)
        rows.append({
            "schema_version": "page_html_blocks_v1",
            "module_id": "html_to_blocks_v1",
            "run_id": page.get("run_id"),
            "created_at": _utc(),
            "page": page.get("page"),
            "page_number": page.get("page_number"),
            "original_page_number": page.get("original_page_number"),
            "image": page.get("image"),
            "spread_side": page.get("spread_side"),
            "is_blank": len(blocks) == 0,
            "blocks": blocks,
        })
    return rows


def _compute_missing(boundaries: List[Dict[str, Any]], min_section: int, max_section: int) -> List[int]:
    found = set()
    for b in boundaries:
        sec = _coerce_int(b.get("section_id"))
        if sec is not None:
            found.add(sec)
    return [i for i in range(min_section, max_section + 1) if i not in found]


def _extract_running_head(html: str) -> Optional[str]:
    if not html:
        return None
    match = re.search(r"<p class=\"running-head\">\\s*([^<]+)\\s*</p>", html)
    return match.group(1).strip() if match else None


def _build_missing_bundles(
    out_dir: str,
    missing_ids: List[int],
    boundaries: List[Dict[str, Any]],
    pages_html: List[Dict[str, Any]],
    page_map: Dict[int, List[int]],
) -> str:
    bundle_dir = os.path.join(out_dir, "missing_bundles")
    ensure_dir(bundle_dir)
    page_lookup = {(_coerce_int(p.get("page_number"))): p for p in pages_html}
    section_pages = _build_section_page_map(boundaries)
    for sec in missing_ids:
        prev = max([s for s in section_pages if s < sec], default=None)
        nxt = min([s for s in section_pages if s > sec], default=None)
        prev_page = section_pages.get(prev) if prev is not None else None
        next_page = section_pages.get(nxt) if nxt is not None else None
        candidate_pages = sorted(page_map.keys())
        page_summaries = []
        for p in candidate_pages:
            if p not in page_lookup:
                continue
            html = page_lookup[p].get("html") or ""
            page_summaries.append({
                "page_number": p,
                "running_head": _extract_running_head(html),
                "html_head": html[:400],
            })
        bundle = {
            "section_id": str(sec),
            "prev_section": str(prev) if prev is not None else None,
            "next_section": str(nxt) if nxt is not None else None,
            "prev_page": prev_page,
            "next_page": next_page,
            "candidate_pages": candidate_pages,
            "page_summaries": page_summaries,
            "note": "Missing after escalation; likely absent from source or unresolvable from page HTML.",
        }
        out_path = os.path.join(bundle_dir, f"missing_section_{sec}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=True, indent=2)
    return bundle_dir


def _build_section_page_map(boundaries: List[Dict[str, Any]]) -> Dict[int, int]:
    mapping: Dict[int, int] = {}
    for b in boundaries:
        sec = _coerce_int(b.get("section_id"))
        page = _coerce_int(b.get("start_page"))
        if sec is None or page is None:
            continue
        mapping[sec] = page
    return mapping


def _suspected_pages_for_missing(
    missing_ids: List[int],
    section_pages: Dict[int, int],
    page_numbers: List[int],
    adjacent_window: int,
) -> Dict[int, List[int]]:
    if not page_numbers:
        return {}
    page_numbers = sorted(page_numbers)
    min_page = page_numbers[0]
    max_page = page_numbers[-1]
    existing = sorted(section_pages.keys())
    if not existing:
        return {p: missing_ids[:] for p in page_numbers}

    page_to_missing: Dict[int, List[int]] = {p: [] for p in page_numbers}

    for miss in missing_ids:
        prev = max([s for s in existing if s < miss], default=None)
        nxt = min([s for s in existing if s > miss], default=None)
        if prev is None and nxt is None:
            start_page, end_page = min_page, max_page
        elif prev is None:
            end_page = section_pages.get(nxt, max_page)
            start_page = max(min_page, end_page - (1 + adjacent_window))
        elif nxt is None:
            start_page = section_pages.get(prev, min_page)
            end_page = min(max_page, start_page + (1 + adjacent_window))
        else:
            start_page = max(min_page, section_pages.get(prev, min_page) - adjacent_window)
            end_page = min(max_page, section_pages.get(nxt, max_page) + adjacent_window)
            if end_page < start_page:
                start_page, end_page = end_page, start_page
        for page in page_numbers:
            if start_page <= page <= end_page:
                page_to_missing[page].append(miss)

    return {p: ids for p, ids in page_to_missing.items() if ids}


def main() -> None:
    parser = argparse.ArgumentParser(description="Coverage guard + HTML-only repair loop for section headers", allow_abbrev=False)
    parser.add_argument("--inputs", nargs="*", help="Driver inputs")
    parser.add_argument("--pages", dest="pages_html", help="page_html_v1 JSONL path")
    parser.add_argument("--pages-html", dest="pages_html", help="page_html_v1 JSONL path")
    parser.add_argument("--pages_html", dest="pages_html", help="page_html_v1 JSONL path")
    parser.add_argument("--out", required=True, help="Output repaired pages HTML JSONL path")
    parser.add_argument("--boundaries-out", dest="boundaries_out", default="section_boundaries.jsonl")
    parser.add_argument("--boundaries_out", dest="boundaries_out", default="section_boundaries.jsonl")
    parser.add_argument("--out-blocks", dest="out_blocks", default="page_blocks_repaired.jsonl")
    parser.add_argument("--missing-out", dest="missing_out", default="missing_sections.json")
    parser.add_argument("--missing_out", dest="missing_out", default="missing_sections.json")
    parser.add_argument("--coarse-segments", dest="coarse_segments", help="coarse_segments.json path")
    parser.add_argument("--coarse_segments", dest="coarse_segments", help="coarse_segments.json path")
    parser.add_argument("--min-section", dest="min_section", type=int, default=1)
    parser.add_argument("--min_section", dest="min_section", type=int, default=1)
    parser.add_argument("--max-section", dest="max_section", type=int, default=400)
    parser.add_argument("--max_section", dest="max_section", type=int, default=400)
    parser.add_argument("--require-text-between", dest="require_text_between", action="store_true")
    parser.add_argument("--require_text_between", dest="require_text_between", action="store_true")
    parser.add_argument("--allow-empty-between", dest="require_text_between", action="store_false")
    parser.add_argument("--allow_empty_between", dest="require_text_between", action="store_false")
    parser.set_defaults(require_text_between=True)
    parser.add_argument("--include-background", dest="include_background", action="store_true")
    parser.add_argument("--include_background", dest="include_background", action="store_true")
    parser.add_argument("--exclude-background", dest="include_background", action="store_false")
    parser.add_argument("--exclude_background", dest="include_background", action="store_false")
    parser.set_defaults(include_background=True)
    parser.add_argument("--max-retries", dest="max_retries", type=int, default=3)
    parser.add_argument("--max_retries", dest="max_retries", type=int, default=3)
    parser.add_argument("--html-only-retries", dest="html_only_retries", type=int, default=1)
    parser.add_argument("--html_only_retries", dest="html_only_retries", type=int, default=1)
    parser.add_argument("--adjacent-scan-window", dest="adjacent_window", type=int, default=1)
    parser.add_argument("--adjacent_scan_window", dest="adjacent_window", type=int, default=1)
    parser.add_argument("--allow-missing", dest="allow_missing", action="store_true")
    parser.add_argument("--allow_missing", dest="allow_missing", action="store_true")
    parser.add_argument("--repair-model", dest="repair_model", default="gpt-5.1")
    parser.add_argument("--repair_model", dest="repair_model", default="gpt-5.1")
    parser.add_argument("--repair-cache-dir", dest="repair_cache_dir", default="html_repair_cache")
    parser.add_argument("--repair_cache_dir", dest="repair_cache_dir", default="html_repair_cache")
    parser.add_argument("--max-output-tokens", dest="max_output_tokens", type=int, default=2048)
    parser.add_argument("--max_output_tokens", dest="max_output_tokens", type=int, default=2048)
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    pages_path = args.pages_html or (args.inputs[0] if args.inputs else None)
    if not pages_path:
        raise SystemExit("Missing --pages-html or --inputs")
    pages_path = os.path.abspath(pages_path)
    if not os.path.exists(pages_path):
        raise SystemExit(f"Missing pages_html file: {pages_path}")

    out_pages_path = os.path.abspath(args.out)
    out_dir = os.path.dirname(out_pages_path)
    ensure_dir(out_dir)

    pages_html = list(read_jsonl(pages_path))
    if not pages_html:
        raise SystemExit(f"Input is empty: {pages_path}")

    coarse = load_coarse_segments(args.coarse_segments)

    cache_dir = Path(out_dir) / args.repair_cache_dir
    ensure_dir(cache_dir)

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    if OpenAI is None:  # pragma: no cover
        raise RuntimeError("openai package required") from _OPENAI_IMPORT_ERROR
    client = OpenAI()

    total_blocks_repaired = 0
    for attempt in range(args.max_retries + 1):
        logger.log(
            "portionize",
            "running",
            current=attempt,
            total=args.max_retries,
            message=f"Detecting HTML boundaries (attempt {attempt})",
            artifact=out_pages_path,
            module_id="detect_boundaries_html_loop_v1",
            schema_version="page_html_v1",
        )

        # Build blocks from current HTML
        blocks_rows = _build_blocks(pages_html, drop_empty=True)
        pages_for_detection = filter_pages_to_gameplay(blocks_rows, coarse)

        candidates = build_candidates(
            pages_for_detection,
            args.min_section,
            args.max_section,
            args.require_text_between,
            args.include_background,
        )
        deduped = dedupe_candidates(candidates)
        boundaries = build_boundaries(deduped)
        apply_macro_section(boundaries, coarse)

        missing = _compute_missing(boundaries, args.min_section, args.max_section)
        expected_total = args.max_section - args.min_section + 1
        boundaries_out_path = os.path.join(out_dir, args.boundaries_out)
        missing_path = os.path.join(out_dir, args.missing_out)
        with open(missing_path, "w", encoding="utf-8") as f:
            for sec in missing:
                f.write(json.dumps({"section_id": str(sec)}) + "\n")

        if not missing:
            save_jsonl(boundaries_out_path, boundaries)
            save_jsonl(out_pages_path, pages_html)
            save_jsonl(os.path.join(out_dir, args.out_blocks), blocks_rows)
            summary_msg = f"Coverage: {len(boundaries)}/{expected_total} sections; missing 0"
            logger.log(
                "html_repair_loop",
                "done",
                current=len(boundaries),
                total=len(boundaries),
                message=summary_msg,
                artifact=out_pages_path,
                module_id="detect_boundaries_html_loop_v1",
                schema_version="page_html_v1",
                extra={"summary_metrics": {"blocks_repaired_count": total_blocks_repaired, "sections_found": len(boundaries), "missing_count": 0}},
            )
            print(f"[summary] detect_boundaries_html_loop_v1: {summary_msg}")
            return

        if attempt >= args.max_retries:
            save_jsonl(boundaries_out_path, boundaries)
            save_jsonl(out_pages_path, pages_html)
            save_jsonl(os.path.join(out_dir, args.out_blocks), blocks_rows)
            page_numbers = [p.get("page_number") for p in pages_for_detection if p.get("page_number") is not None]
            section_pages = _build_section_page_map(boundaries)
            page_map = _suspected_pages_for_missing(missing, section_pages, page_numbers, args.adjacent_window)
            bundle_dir = _build_missing_bundles(out_dir, missing, boundaries, pages_html, page_map)
            summary_msg = f"Missing sections: {len(missing)}/{expected_total}; missing list: {missing_path}; bundles: {bundle_dir}"
            metrics = {"blocks_repaired_count": total_blocks_repaired, "sections_found": len(boundaries), "missing_count": len(missing)}
            if args.allow_missing:
                logger.log(
                    "html_repair_loop",
                    "warning",
                    current=len(boundaries),
                    total=len(boundaries),
                    message=f"Missing sections after {args.max_retries} retries. {summary_msg}",
                    artifact=bundle_dir,
                    module_id="detect_boundaries_html_loop_v1",
                    schema_version="page_html_v1",
                    extra={"summary_metrics": metrics},
                )
                print(f"[summary] detect_boundaries_html_loop_v1: {summary_msg}")
                return
            else:
                logger.log(
                    "html_repair_loop",
                    "failed",
                    current=len(boundaries),
                    total=len(boundaries),
                    message=f"Missing sections after {args.max_retries} retries. {summary_msg}",
                    artifact=bundle_dir,
                    module_id="detect_boundaries_html_loop_v1",
                    schema_version="page_html_v1",
                    extra={"summary_metrics": metrics},
                )
                print(f"[summary] detect_boundaries_html_loop_v1: {summary_msg}")
                raise SystemExit(
                    f"Missing sections after {args.max_retries} retries: {len(missing)} missing"
                )

        # Build suspect pages for repair
        section_pages = _build_section_page_map(boundaries)
        page_numbers = [p.get("page_number") for p in pages_for_detection if p.get("page_number") is not None]
        page_map = _suspected_pages_for_missing(missing, section_pages, page_numbers, args.adjacent_window)
        if not page_map:
            raise SystemExit("Missing sections detected but no suspect pages identified")

        # Repair pages
        use_image = attempt >= args.html_only_retries
        repaired = 0
        for page in pages_html:
            page_number = _coerce_int(page.get("page_number"))
            if page_number is None or page_number not in page_map:
                continue
            expected_ids = sorted(set(page_map[page_number]))
            if not expected_ids:
                continue

            repaired_html, changed = _code_repair_html(page.get("html") or "", expected_ids)
            if changed:
                page["html"] = repaired_html
                repaired += 1
                continue

            user_prompt = _prompt_for_expected(expected_ids)
            mode = "image" if use_image else "html"
            system = SYSTEM_PROMPT_IMAGE if use_image else SYSTEM_PROMPT
            prompt_hash = _hash_prompt(system, user_prompt, args.repair_model, mode)
            cache_path = cache_dir / f"page_{page_number:03d}.json"

            cached_html = None
            if cache_path.exists():
                try:
                    cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
                    if (
                        cache_data.get("prompt_hash") == prompt_hash
                        and cache_data.get("expected_ids") == expected_ids
                        and cache_data.get("model") == args.repair_model
                        and cache_data.get("mode") == mode
                    ):
                        cached_html = cache_data.get("html")
                except Exception:
                    cached_html = None

            if cached_html:
                page["html"] = cached_html
                repaired += 1
                continue

            repaired_html, meta = _repair_html(
                client=client,
                html=page.get("html") or "",
                expected_ids=expected_ids,
                model=args.repair_model,
                max_output_tokens=args.max_output_tokens,
                image_path=page.get("image") if use_image else None,
            )
            if repaired_html:
                page["html"] = repaired_html
            cache_path.write_text(
                json.dumps({
                    "page_number": page_number,
                    "expected_ids": expected_ids,
                    "prompt_hash": prompt_hash,
                    "model": args.repair_model,
                    "mode": mode,
                    "image": page.get("image") if use_image else None,
                    "html": page.get("html") or "",
                    "meta": meta,
                }, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            repaired += 1

        total_blocks_repaired += repaired
        logger.log(
            "portionize",
            "running",
            current=attempt + 1,
            total=args.max_retries,
            message=f"Repaired {repaired} pages; re-running detection",
            artifact=out_pages_path,
            module_id="detect_boundaries_html_loop_v1",
            schema_version="page_html_v1",
        )


if __name__ == "__main__":
    main()
