import argparse
import json
import os
import re
from typing import Dict, List, Any, Optional

from modules.common.utils import save_json, ensure_dir, ProgressLogger, read_jsonl
from modules.common.page_numbers import validate_sequential_page_numbers
from schemas import ValidationReport


def load_optional_jsonl(path: str):
    if path and os.path.exists(path):
        try:
            return list(read_jsonl(path))
        except Exception:
            return []
    return []


def short_text(txt: str, limit: int = 160):
    if not txt:
        return None
    txt = " ".join(txt.split())
    return txt if len(txt) <= limit else txt[: limit - 3] + "..."


def find_hits(arr, sid: str, field="text", id_field="id", page_field="page"):
    hits = []
    if not arr:
        return hits
    pat = re.compile(rf"\\b{sid}\\b")
    for e in arr:
        txt = (e.get(field) or "").strip()
        if txt and pat.search(txt):
            hits.append({
                "id": e.get(id_field),
                "page": (e.get("page_number") or (e.get("metadata", {}).get("page_number") if isinstance(e.get("metadata"), dict) else None) or e.get(page_field)),
                "snippet": short_text(txt, 120),
            })
    return hits[:3]


def file_meta(path: str) -> Optional[Dict[str, Any]]:
    if path and os.path.exists(path):
        return {"path": path, "mtime": os.path.getmtime(path)}
    return None


def load_gamebook(path: str) -> Dict[str, Any]:
    """Load gamebook.json."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_gamebook(
    gamebook: Dict[str, Any],
    expected_range_start: int,
    expected_range_end: int,
    upstream: Optional[Dict[str, Any]] = None
) -> ValidationReport:
    """
    Validate a Fighting Fantasy Engine gamebook.

    Checks:
    - Missing sections in expected range (typically 1-400)
    - Duplicate sections (shouldn't happen but check anyway)
    - Sections with no text
    - Sections with no choices (potential dead ends)

    Returns ValidationReport with findings.
    """
    sections = gamebook.get("sections", {})

    # Collect section IDs
    section_ids = list(sections.keys())
    numeric_section_ids = [sid for sid in section_ids if sid.isdigit()]

    # Check for duplicates (shouldn't happen in a dict, but check for duplicates in source data)
    # In practice this checks if any section appears multiple times
    seen_ids = set()
    duplicate_sections = []
    for sid in section_ids:
        if sid in seen_ids:
            duplicate_sections.append(sid)
        seen_ids.add(sid)

    # Check for missing sections in expected range
    expected_sections = set(str(i) for i in range(expected_range_start, expected_range_end + 1))
    present_sections = set(numeric_section_ids)
    missing_sections = sorted(expected_sections - present_sections, key=lambda x: int(x))

    # Check for sections with no text
    sections_with_no_text = []
    for sid, section in sections.items():
        text = section.get("text", "").strip()
        if not text:
            sections_with_no_text.append(sid)

    # Check for sections with no choices (potential dead ends)
    # Exclude stubs, non-gameplay, and sections explicitly marked end_game
    sections_with_no_choices = []
    for sid, section in sections.items():
        # Skip if it's a stub
        if section.get("provenance", {}).get("stub"):
            continue

        # Skip non-gameplay sections
        if not section.get("isGameplaySection", False):
            continue

        if section.get("end_game"):
            continue

        # Check if section has any navigation
        nav_links = section.get("navigationLinks", [])
        combat = section.get("combat", {})
        test_luck = section.get("testYourLuck")
        items = section.get("items", [])

        has_navigation = (
            bool(nav_links) or
            bool(combat.get("winSection")) or
            bool(combat.get("loseSection")) or
            (test_luck and (test_luck.get("luckySection") or test_luck.get("unluckySection"))) or
            any(item.get("checkSuccessSection") or item.get("checkFailureSection") for item in items)
        )

        if not has_navigation:
            sections_with_no_choices.append(sid)

    # Build warnings and errors
    warnings = []
    errors = []

    if missing_sections:
        count = len(missing_sections)
        sample = missing_sections[:10]
        msg = f"Missing {count} sections in range {expected_range_start}-{expected_range_end}: {sample}"
        if count > 10:
            msg += f" (and {count - 10} more)"
        errors.append(msg)

    if duplicate_sections:
        errors.append(f"Duplicate sections found: {duplicate_sections}")

    if sections_with_no_text:
        count = len(sections_with_no_text)
        sample = sections_with_no_text[:10]
        msg = f"{count} sections have no text: {sample}"
        if count > 10:
            msg += f" (and {count - 10} more)"
        warnings.append(msg)

    if sections_with_no_choices:
        count = len(sections_with_no_choices)
        sample = sections_with_no_choices[:10]
        msg = f"{count} gameplay sections have no choices (potential dead ends): {sample}"
        if count > 10:
            msg += f" (and {count - 10} more)"
        warnings.append(msg)

    # Determine if valid (no critical errors)
    is_valid = len(errors) == 0

    report = ValidationReport(
        total_sections=len(sections),
        missing_sections=missing_sections,
        duplicate_sections=duplicate_sections,
        sections_with_no_text=sections_with_no_text,
        sections_with_no_choices=sections_with_no_choices,
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
    )

    # Attach provenance traces when upstream data provided
    if upstream:
        traces = {}
        elements = upstream.get("elements") or []
        elements_core = upstream.get("elements_core") or []
        boundaries = upstream.get("boundaries") or []
        portions = upstream.get("portions") or []

        bound_by_sid = {b.get("section_id"): b for b in boundaries}
        elem_by_id = {e.get("id"): e for e in elements_core or elements}
        portion_by_sid = {p.get("section_id") or p.get("portion_id"): p for p in portions}

        def span_meta(b):
            if not b:
                return None
            start = elem_by_id.get(b.get("start_element_id"))
            end = elem_by_id.get(b.get("end_element_id")) if b.get("end_element_id") else None
            def page_of(el):
                if not el:
                    return None
                md = el.get("metadata") or {}
                return el.get("page_number") or md.get("page_number") or el.get("page")
            return {
                "start_element_id": b.get("start_element_id"),
                "end_element_id": b.get("end_element_id"),
                "start_page": page_of(start),
                "end_page": page_of(end),
                "start_text": short_text(start.get("text")) if start else None,
                "end_text": short_text(end.get("text")) if end else None,
            }

        for sid in set(missing_sections + sections_with_no_text + sections_with_no_choices):
            b = bound_by_sid.get(sid)
            portion = portion_by_sid.get(sid)
            traces[sid] = {
                "boundary": span_meta(b),
                "portion_present": bool(portion),
                "portion_snippet": short_text((portion or {}).get("raw_text") or (portion or {}).get("text")),
                "portion_len": len(((portion or {}).get("raw_text") or (portion or {}).get("text") or "")),
                "elements_hits": find_hits(elements, sid),
                "elements_core_hits": find_hits(elements_core, sid),
                "artifact_paths": {
                    "boundaries": upstream.get("boundaries_path"),
                    "elements": upstream.get("elements_path"),
                    "elements_core": upstream.get("elements_core_path"),
                    "portions": upstream.get("portions_path"),
                }
            }
        if traces:
            report = report.model_copy(update={"forensics": traces})

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate Fighting Fantasy Engine gamebook output.")
    parser.add_argument("--gamebook", required=True, help="Path to gamebook.json")
    parser.add_argument("--out", required=True, help="Path to validation_report.json")
    parser.add_argument("--expected-range-start", "--expected_range_start", type=int, default=1, dest="expected_range_start", help="Expected first section number")
    parser.add_argument("--expected-range-end", "--expected_range_end", type=int, default=400, dest="expected_range_end", help="Expected last section number")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    parser.add_argument("--pages", help="(ignored; driver compatibility)")
    parser.add_argument("--forensics", action="store_true", help="Attach forensic traces for missing text/choices using sibling artifacts.")
    parser.add_argument("--unresolved_missing", help="Optional JSON list of section_ids that remained unresolved after escalation.")
    parser.add_argument("--boundaries", help="Optional path to section_boundaries.jsonl for tracing")
    parser.add_argument("--elements", help="Optional path to elements.jsonl for tracing")
    parser.add_argument("--elements-core", dest="elements_core", help="Optional path to elements_core.jsonl for tracing")
    parser.add_argument("--portions", help="Optional path to portions_enriched.jsonl for tracing")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    logger.log("validate", "running", current=0, total=1,
               message="Loading gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    gamebook = load_gamebook(args.gamebook)

    logger.log("validate", "running", current=0, total=1,
               message="Validating gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    upstream = None
    if args.forensics:
        upstream = {
            "elements": load_optional_jsonl(args.elements),
            "elements_core": load_optional_jsonl(args.elements_core),
            "boundaries": load_optional_jsonl(args.boundaries),
            "portions": load_optional_jsonl(args.portions),
            "boundaries_path": args.boundaries,
            "elements_path": args.elements,
            "elements_core_path": args.elements_core,
            "portions_path": args.portions,
        }
    report = validate_gamebook(gamebook, args.expected_range_start, args.expected_range_end, upstream=upstream)

    if args.forensics:
        base_dir = os.path.dirname(os.path.abspath(args.gamebook))
        boundaries_path = os.path.join(base_dir, "section_boundaries_merged.jsonl")
        elements_path = os.path.join(base_dir, "elements.jsonl")
        elements_core_path = os.path.join(base_dir, "elements_core.jsonl")
        portions_path = os.path.join(base_dir, "portions_enriched_choices.jsonl")
        pages_clean_path = os.path.join(base_dir, "pages_clean.jsonl")
        pages_raw_path = os.path.join(base_dir, "pages_raw.jsonl")
        unresolved_path = args.unresolved_missing or os.path.join(base_dir, "unresolved_missing.json")
        boundaries = load_optional_jsonl(boundaries_path)
        elements = load_optional_jsonl(elements_path)
        elements_core = load_optional_jsonl(elements_core_path)
        portions = load_optional_jsonl(portions_path)
        pages_clean = load_optional_jsonl(pages_clean_path)
        pages_raw = load_optional_jsonl(pages_raw_path)
        unresolved_ids = []
        if unresolved_path and os.path.exists(unresolved_path):
            try:
                with open(unresolved_path, "r", encoding="utf-8") as f:
                    maybe = json.load(f)
                    if isinstance(maybe, list):
                        unresolved_ids = [str(x) for x in maybe]
            except Exception:
                unresolved_ids = []

        page_number_trace = None
        if pages_raw:
            ok, missing = validate_sequential_page_numbers(pages_raw, field="page_number", allow_gaps=False)
            if not ok:
                msg = f"pages_raw page_number sequence has gaps: {missing[:10]}" + (f" (and {len(missing) - 10} more)" if len(missing) > 10 else "")
                errors = list(report.errors or [])
                errors.append(msg)
                report = report.model_copy(update={"errors": errors, "is_valid": False})
                page_number_trace = {"artifact": pages_raw_path, "missing": missing}
        elif pages_clean:
            ok, missing = validate_sequential_page_numbers(pages_clean, field="page_number", allow_gaps=False)
            if not ok:
                msg = f"pages_clean page_number sequence has gaps: {missing[:10]}" + (f" (and {len(missing) - 10} more)" if len(missing) > 10 else "")
                errors = list(report.errors or [])
                errors.append(msg)
                report = report.model_copy(update={"errors": errors, "is_valid": False})
                page_number_trace = {"artifact": pages_clean_path, "missing": missing}

        # Prefer elements_core (cleaner, seq/page aligned); fall back to full elements if missing
        elem_by_id = {e.get("id"): e for e in (elements_core or elements)}
        bound_by_sid = {b.get("section_id"): b for b in boundaries}
        portion_by_sid = {p.get("section_id") or p.get("portion_id"): p for p in portions}

        def short_text(txt: str, limit: int = 160):
            if not txt:
                return None
            txt = " ".join(txt.split())
            return txt if len(txt) <= limit else txt[: limit - 3] + "..."

        def span_meta(b):
            if not b:
                return None
            start_id = b.get("start_element_id")
            end_id = b.get("end_element_id")
            start = elem_by_id.get(start_id)
            end = elem_by_id.get(end_id) if end_id else None
            start_seq = start.get("seq") if start else None
            end_seq = end.get("seq") if end else None
            span_len = (end_seq - start_seq + 1) if start_seq is not None and end_seq is not None else None
            return {
                "start_seq": start_seq,
                "end_seq": end_seq,
                "start_page": (start.get("page_number") if start else None) or (start.get("metadata", {}).get("page_number") if start else None) or (start.get("page") if start else None),
                "end_page": (end.get("page_number") if end else None) or (end.get("metadata", {}).get("page_number") if end else None) or (end.get("page") if end else None),
                "span_length": span_len,
                "zero_length": span_len == 0 if span_len is not None else None,
                "start_element_id": start_id,
                "end_element_id": end_id,
                "end_element_text": short_text(end.get("text")) if end else None,
            }

        def portion_snippet(sid: str):
            p = portion_by_sid.get(sid)
            if not p:
                return None
            return short_text(p.get("raw_text") or p.get("text"))

        def portion_length(sid: str):
            p = portion_by_sid.get(sid)
            if not p:
                return None
            txt = (p.get("raw_text") or p.get("text") or "").strip()
            return len(txt) if txt else 0

        def page_for_boundary(b):
            if not b:
                return None
            start_elem = elem_by_id.get(b.get("start_element_id"))
            if start_elem:
                return start_elem.get("page_number") or (start_elem.get("metadata", {}).get("page_number") if start_elem.get("metadata") else None) or start_elem.get("page")
            return None

        def nearest_page_hint(sid_str: str):
            try:
                sid_int = int(sid_str)
            except Exception:
                return None
            lower = [int(k) for k in bound_by_sid.keys() if k.isdigit() and int(k) < sid_int]
            higher = [int(k) for k in bound_by_sid.keys() if k.isdigit() and int(k) > sid_int]
            prev_sid = str(max(lower)) if lower else None
            next_sid = str(min(higher)) if higher else None
            prev_page = page_for_boundary(bound_by_sid.get(prev_sid)) if prev_sid else None
            next_page = page_for_boundary(bound_by_sid.get(next_sid)) if next_sid else None
            return {
                "prev_sid": prev_sid,
                "prev_page": prev_page,
                "next_sid": next_sid,
                "next_page": next_page,
            }

        def suggested_action(kind: str, sid: str):
            if kind == "missing_sections":
                hint = nearest_page_hint(sid)
                return f"Re-run boundary detection / OCR around pages {hint['prev_page']}–{hint['next_page']} (neighbors {hint['prev_sid']}->{hint['next_sid']})" if hint else "Re-run boundary detection / OCR near neighboring sections"
            if kind == "no_text":
                return "Re-read portion (repair_portions) or widen boundary span; inspect start/end elements."
            if kind == "no_choices":
                return "Escalate choices_loop or run ending_guard to classify true endings."
            return None

        def search_sources(sid: str):
            """Search upstream artifacts to see where the section number appears."""
            def find_in_elements(arr):
                hits = []
                if not arr:
                    return hits
                pat = re.compile(rf"\\b{re.escape(sid)}\\b")
                for e in arr:
                    txt = (e.get("text") or "").strip()
                    if txt and pat.search(txt):
                        hits.append({
                            "id": e.get("id"),
                            "seq": e.get("seq"),
                            "page": e.get("page_number") or e.get("page") or e.get("metadata", {}).get("page_number"),
                            "text": short_text(txt),
                        })
                return hits[:3]  # cap for brevity

            def find_in_pages(arr):
                hits = []
                if not arr:
                    return hits
                pat = re.compile(rf"\\b{re.escape(sid)}\\b")
                for p in arr:
                    txt = (p.get("text") or "").strip()
                    if txt and pat.search(txt):
                        hits.append({
                            "page": p.get("page_number") or p.get("page"),
                            "text": short_text(txt),
                        })
                return hits[:3]

            return {
                "elements_core_hits": find_in_elements(elements_core),
                "elements_hits": find_in_elements(elements),
                "pages_clean_hits": find_in_pages(pages_clean),
                "pages_raw_hits": find_in_pages(pages_raw),
            }

        def make_trace(sid: str):
            b = bound_by_sid.get(sid)
            start_elem = elem_by_id.get(b.get("start_element_id")) if b else None
            trace = {
                "boundary_source": b.get("module_id") if b else None,
                "boundary_confidence": b.get("confidence") if b else None,
                "start_element_id": b.get("start_element_id") if b else None,
                "start_element_text": short_text(start_elem.get("text")) if start_elem else None,
                "start_element_page": (start_elem.get("page_number") if start_elem else None)
                or (start_elem.get("metadata", {}).get("page_number") if start_elem and start_elem.get("metadata") else None)
                or (start_elem.get("page") if start_elem else None),
                "span": span_meta(b),
                "portion_snippet": portion_snippet(sid),
                "portion_length": portion_length(sid),
                "evidence": b.get("evidence") if b else None,
                "artifact_paths": {
                    "boundaries": file_meta(boundaries_path),
                    "elements": file_meta(elements_path),
                    "elements_core": file_meta(elements_core_path),
                    "portions": file_meta(portions_path),
                    "pages_clean": file_meta(pages_clean_path),
                    "pages_raw": file_meta(pages_raw_path),
                }
            }
            trace.update(search_sources(sid))
            return trace

        traces = {}
        for sid in report.missing_sections:
            traces.setdefault("missing_sections", {})[sid] = make_trace(sid)
            traces["missing_sections"][sid]["suggested_action"] = suggested_action("missing_sections", sid)
        for sid in report.sections_with_no_text:
            traces.setdefault("no_text", {})[sid] = make_trace(sid)
            traces["no_text"][sid]["suggested_action"] = suggested_action("no_text", sid)
        for sid in report.sections_with_no_choices:
            traces.setdefault("no_choices", {})[sid] = make_trace(sid)
            traces["no_choices"][sid]["suggested_action"] = suggested_action("no_choices", sid)

        if page_number_trace:
            traces["page_number_sequence"] = page_number_trace

        # Mark unresolved-after-escalation
        if unresolved_ids:
            for sid in unresolved_ids:
                traces.setdefault("missing_sections", {})[sid] = traces.get("missing_sections", {}).get(sid, make_trace(sid))
                traces["missing_sections"][sid]["outcome"] = "resolved_bad_source_missing"
                traces["missing_sections"][sid]["suggested_action"] = "Source page missing/fused after OCR+vision escalation"
        report = report.model_copy(update={"forensics": traces})
        report = report.model_copy(update={"forensics": traces})

    # Save report
    ensure_dir(os.path.dirname(args.out) or ".")
    save_json(args.out, report.model_dump(by_alias=True))

    # Log completion
    status = "done" if report.is_valid else "failed"
    message = "Validation passed" if report.is_valid else f"Validation failed: {len(report.errors)} errors, {len(report.warnings)} warnings"

    logger.log("validate", status, current=1, total=1,
               message=message, artifact=args.out, module_id="validate_ff_engine_v2",
               schema_version="validation_report_v1")

    # Print summary
    print(f"Validation Report → {args.out}")
    print(f"Total sections: {report.total_sections}")
    print(f"Valid: {report.is_valid}")

    if report.errors:
        print(f"\nErrors ({len(report.errors)}):")
        for error in report.errors:
            print(f"  - {error}")

    if report.warnings:
        print(f"\nWarnings ({len(report.warnings)}):")
        for warning in report.warnings:
            print(f"  - {warning}")

    # Exit with error code if validation failed
    if not report.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
