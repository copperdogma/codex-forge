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
    pat = re.compile(rf"\b{sid}\b")
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
    sections_with_no_choices = []
    for sid, section in sections.items():
        if section.get("provenance", {}).get("stub"):
            continue
        if not section.get("isGameplaySection", False):
            continue
        if section.get("end_game"):
            continue

        nav_links = section.get("navigationLinks", [])
        combat = section.get("combat") or [] # In ff_engine_v2 combat is a list
        if not isinstance(combat, list): combat = [combat]
        
        test_luck = section.get("testYourLuck") or []
        if not isinstance(test_luck, list): test_luck = [test_luck]
        
        items = section.get("items", [])

        has_navigation = (
            bool(nav_links) or
            any(c.get("win_section") or c.get("loss_section") for c in combat if isinstance(c, dict)) or
            any(l.get("luckySection") or l.get("unluckySection") for l in test_luck if isinstance(l, dict)) or
            any(item.get("checkSuccessSection") or item.get("checkFailureSection") for item in items if isinstance(item, dict))
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

    is_valid = len(errors) == 0

    return ValidationReport(
        total_sections=len(sections),
        missing_sections=missing_sections,
        duplicate_sections=duplicate_sections,
        sections_with_no_text=sections_with_no_text,
        sections_with_no_choices=sections_with_no_choices,
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
    )


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
    parser.add_argument("--reachability-report", dest="reachability_report", help="Optional path to reachability_report.json to include broken links and orphans.")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("validate", "running", current=0, total=1,
               message="Loading gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    gamebook = load_gamebook(args.gamebook)
    sections = gamebook.get("sections", {})

    logger.log("validate", "running", current=0, total=1,
               message="Validating gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    report = validate_gamebook(gamebook, args.expected_range_start, args.expected_range_end)

    if args.forensics:
        base_dir = os.path.dirname(os.path.abspath(args.gamebook))
        boundaries_path = args.boundaries or os.path.join(base_dir, "section_boundaries_merged.jsonl")
        elements_path = args.elements or os.path.join(base_dir, "elements.jsonl")
        elements_core_path = args.elements_core or os.path.join(base_dir, "elements_core.jsonl")
        portions_path = args.portions or os.path.join(base_dir, "portions_enriched_choices.jsonl")
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

        flattened_elements = []
        for row in (elements_core or elements):
            if "blocks" in row and isinstance(row["blocks"], list):
                page_num = row.get("page_number") or row.get("page")
                for block in row["blocks"]:
                    order = block.get("order") or 0
                    flattened_elements.append({
                        "id": f"p{page_num:03d}-b{order}",
                        "text": block.get("text"),
                        "page_number": page_num,
                        "metadata": row.get("metadata"),
                        "seq": order,
                    })
            else:
                flattened_elements.append(row)

        elem_by_id = {e.get("id"): e for e in flattened_elements}
        bound_by_sid = {b.get("section_id"): b for b in boundaries}
        portion_by_sid = {str(p.get("section_id") or p.get("portion_id")): p for p in portions}

        def span_meta(b):
            if not b: return None
            
            # Find all elements associated with this section by searching flattened_elements
            # This is more robust than a seq range which fails across page boundaries
            sid = b.get("section_id")
            
            # Get pages from boundary
            start_page = b.get("start_page")
            end_page = b.get("end_page")
            
            # Count elements that belong to this section ID
            section_elements = [e for e in flattened_elements if e.get("section_id") == sid]
            element_count = len(section_elements)
            
            return {
                "start_page": start_page,
                "end_page": end_page,
                "element_count": element_count,
                "start_element_id": b.get("start_element_id"),
                "end_element_id": b.get("end_element_id")
            }

        def make_trace(sid: str):
            b = bound_by_sid.get(sid)
            p = portion_by_sid.get(sid)
            s = sections.get(sid)
            
            # Extract ending info from portion
            ending_info = None
            if p:
                if p.get("ending"):
                    ending_info = {"ending_type": p.get("ending")}
                else:
                    eg = (p.get("repair") or {}).get("ending_guard")
                    if eg:
                        ending_info = eg

            trace = {
                "boundary_source": b.get("module_id") if b else None,
                "boundary_confidence": b.get("confidence") if b else None,
                "span": span_meta(b),
                "portion_snippet": short_text((p or {}).get("raw_text") or (p or {}).get("text")),
                "portion_html": (p or {}).get("raw_html"),
                "presentation_html": (s or {}).get("presentation_html") or (s or {}).get("html"),
                "portion_length": len(((p or {}).get("raw_text") or (p or {}).get("text") or "").strip()),
                "ending_info": ending_info,
                "elements_hits": find_hits(elements, sid),
                "elements_core_hits": find_hits(flattened_elements, sid),
            }
            return trace

        traces = {}
        for sid in report.missing_sections:
            traces.setdefault("missing_sections", {})[sid] = make_trace(sid)
        for sid in report.sections_with_no_text:
            traces.setdefault("no_text", {})[sid] = make_trace(sid)
        for sid in report.sections_with_no_choices:
            traces.setdefault("no_choices", {})[sid] = make_trace(sid)

        if args.reachability_report and os.path.exists(args.reachability_report):
            try:
                with open(args.reachability_report, "r", encoding="utf-8") as f:
                    reach = json.load(f)
                    reach_forensics = reach.get("forensics") or {}
                    for sid in reach_forensics.get("broken_links", []):
                        traces.setdefault("broken_links", {})[sid] = make_trace(sid)
                    for sid in reach_forensics.get("orphans", []):
                        traces.setdefault("orphans", {})[sid] = make_trace(sid)
            except Exception as e:
                print(f"Warning: Failed to merge reachability report: {e}")

        report = report.model_copy(update={"forensics": traces})

    ensure_dir(os.path.dirname(args.out) or ".")
    save_json(args.out, report.model_dump(by_alias=True))

    if args.forensics:
        try:
            import subprocess
            html_out = args.out.replace(".json", ".html")
            subprocess.run(["python3", "tools/generate_forensic_html.py", args.out, "--out", html_out], check=False)
        except Exception as e:
            print(f"Warning: Failed to generate HTML forensic report: {e}")

    logger.log("validate", "done", message="Validation passed", artifact=args.out, module_id="validate_ff_engine_v2")
    print(f"Validation Report \u2192 {args.out}")


if __name__ == "__main__":
    main()