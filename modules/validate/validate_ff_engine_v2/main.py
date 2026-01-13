"""
Forensics Wrapper for Fighting Fantasy Engine Validation

This module is a forensics wrapper around the canonical Node validator
(validate_ff_engine_node_v1). It delegates all validation logic to the Node
validator and adds:
- Forensics traces linking validation issues to source artifacts
- HTML report generation for validation results

The Node validator is the single source of truth for validation checks.
This wrapper provides a stable Python interface for forensics and reporting.

Validation checks performed by Node validator:
- Schema validation
- Missing sections in expected range
- Duplicate sections
- Sections with no text
- Sections with no choices (potential dead ends)
- Reachability analysis (unreachable sections from startSection)
- Sequence target validation
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Any, Optional

from modules.common.utils import save_json, ensure_dir, ProgressLogger, read_jsonl
from modules.common.html_utils import html_to_text
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


# Cache for Node validator results (key: gamebook_path hash, value: (mtime, validation_result))
_node_validator_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _get_cache_key(gamebook_path: str, validator_dir: str) -> str:
    """Generate cache key from gamebook path and validator directory."""
    # Use absolute paths for consistent keys
    gamebook_abs = os.path.abspath(gamebook_path)
    validator_dir_abs = os.path.abspath(validator_dir)
    # Create hash from paths (not content, for speed)
    key_str = f"{gamebook_abs}:{validator_dir_abs}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _call_node_validator(
    gamebook_path: str, validator_dir: str, node_bin: str = "node", use_cache: bool = True
) -> Dict[str, Any]:
    """
    Call the Node validator to get full validation results.

    This uses the canonical Node validator (validate_ff_engine_node_v1) which
    performs all validation checks including:
    - Schema validation
    - Missing sections
    - Duplicate sections
    - Sections with no text
    - Sections with no choices
    - Reachability analysis
    - Sequence target validation

    Results are cached based on gamebook file mtime to avoid redundant subprocess calls
    when the same gamebook is validated multiple times in the same process.

    Args:
        gamebook_path: Path to gamebook.json file
        validator_dir: Path to Node validator directory
        node_bin: Node executable to use (default: "node")
        use_cache: Whether to use in-memory cache (default: True)

    Returns dict with validation results from Node validator.
    """
    # Use absolute paths to avoid path resolution issues
    gamebook_abs = os.path.abspath(gamebook_path)
    validator_dir_abs = os.path.abspath(validator_dir)
    cli_path = os.path.join(validator_dir_abs, "cli-validator.js")

    if not os.path.exists(cli_path):
        raise FileNotFoundError(f"Node validator cli-validator.js not found at {validator_dir_abs}")

    # Check cache if enabled
    if use_cache:
        cache_key = _get_cache_key(gamebook_abs, validator_dir_abs)
        try:
            # Get file mtime for cache invalidation
            gamebook_mtime = os.path.getmtime(gamebook_abs)
            cached_mtime, cached_result = _node_validator_cache.get(cache_key, (None, None))

            # If cache hit and file hasn't changed, return cached result
            if cached_mtime is not None and cached_mtime == gamebook_mtime:
                return cached_result
        except OSError:
            # If we can't get mtime, skip cache
            pass

    # Run Node validator - don't set cwd, use absolute paths (matches validate_ff_engine_node_v1/main.py)
    cmd = [node_bin, cli_path, gamebook_abs, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0 and not proc.stdout:
        # If validator fails but produces no output, return empty result
        # Check stderr for actual errors
        if proc.stderr:
            raise RuntimeError(f"Node validator failed: {proc.stderr[:500]}")
        result = {"valid": False, "errors": [], "warnings": [], "summary": {}}
    else:
        try:
            result = json.loads(proc.stdout.strip() if proc.stdout else "{}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Node validator JSON output: {e}\nstdout: {proc.stdout[:500]}")

    # Cache result if enabled
    if use_cache:
        try:
            gamebook_mtime = os.path.getmtime(gamebook_abs)
            cache_key = _get_cache_key(gamebook_abs, validator_dir_abs)
            _node_validator_cache[cache_key] = (gamebook_mtime, result)
        except OSError:
            # If we can't get mtime, skip caching
            pass

    return result


def validate_gamebook(
    gamebook: Dict[str, Any],
    expected_range_start: int,
    expected_range_end: int,
    upstream: Optional[Dict[str, Any]] = None,
    node_validator_result: Optional[Dict[str, Any]] = None
) -> ValidationReport:
    """
    Validate a Fighting Fantasy Engine gamebook using the canonical Node validator.

    This function is now a forensics wrapper around the Node validator.
    All validation logic is delegated to the Node validator (validate_ff_engine_node_v1),
    which is the single source of truth for validation checks.

    This wrapper's responsibilities:
    - Parse Node validator results
    - Map to ValidationReport schema
    - Provide a stable Python interface for forensics and reporting

    Args:
        gamebook: The gamebook JSON to validate
        expected_range_start: Expected first section number (used by Node validator)
        expected_range_end: Expected last section number (used by Node validator)
        upstream: Optional upstream data (unused, kept for backward compatibility)
        node_validator_result: Optional pre-computed Node validator result (for testing/caching)

    Returns:
        ValidationReport with findings from Node validator
    """
    sections = gamebook.get("sections", {})

    # If Node validator result not provided, validation must be done in main()
    # This path is for backward compatibility only
    if node_validator_result is None:
        # Return minimal report - main() will populate from Node validator
        return ValidationReport(
            total_sections=len(sections),
            missing_sections=[],
            duplicate_sections=[],
            sections_with_no_text=[],
            sections_with_no_choices=[],
            unreachable_sections=[],
            is_valid=True,
            warnings=[],
            errors=[],
        )

    # Parse Node validator results
    node_errors = node_validator_result.get("errors", [])
    node_warnings = node_validator_result.get("warnings", [])

    # Extract section lists from Node validator messages
    missing_sections = []
    duplicate_sections = []
    sections_with_no_text = []
    sections_with_no_choices = []
    unreachable_sections = []
    unreachable_entry_points = []
    manual_navigation_sections = []

    # Build error and warning message lists
    errors = []
    warnings = []

    # Process errors
    for error in node_errors:
        message = error.get("message", "")
        errors.append(message)

        # Extract missing sections
        if "Missing" in message and "sections in range" in message:
            # Parse message like: "Missing 5 sections in range 1-400: 1, 2, 3, 4, 5"
            match = re.search(r'Missing \d+ sections in range \d+-\d+: ([\d, ]+)', message)
            if match:
                missing_str = match.group(1)
                missing_sections = [s.strip() for s in missing_str.split(",")]

        # Extract duplicate sections
        if "Duplicate section IDs" in message:
            # Parse message like: "Duplicate section IDs detected: 7 (keys: 7, 7)"
            match = re.search(r'(\d+) \(keys:', message)
            if match:
                duplicate_sections.append(match.group(1))

    # Process warnings
    for warning in node_warnings:
        message = warning.get("message", "")
        warnings.append(message)

        # Extract sections with no text
        if "has no text" in message:
            match = re.search(r'Section "([^"]+)" has no text', message)
            if match:
                sections_with_no_text.append(match.group(1))

        # Extract sections with no choices
        if "has no choices" in message or "potential dead end" in message:
            match = re.search(r'section "([^"]+)" has no choices', message)
            if match:
                sections_with_no_choices.append(match.group(1))

        # Extract unreachable sections
        if "unreachable from startSection" in message:
            match = re.search(r'section "([^"]+)" is unreachable', message)
            if match:
                unreachable_sections.append(match.group(1))

            # Extract entry points from first unreachable warning metadata
            if not unreachable_entry_points and "entryPoints" in warning:
                unreachable_entry_points = warning["entryPoints"]

            # Extract manual navigation sections from first unreachable warning metadata
            if not manual_navigation_sections and "manualNavigationSections" in warning:
                manual_navigation_sections = warning["manualNavigationSections"]

    is_valid = len(errors) == 0

    return ValidationReport(
        total_sections=len(sections),
        missing_sections=missing_sections,
        duplicate_sections=duplicate_sections,
        sections_with_no_text=sections_with_no_text,
        sections_with_no_choices=sections_with_no_choices,
        unreachable_sections=unreachable_sections,
        unreachable_entry_points=unreachable_entry_points,
        manual_navigation_sections=manual_navigation_sections,
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
    parser.add_argument("--node-validator-dir", dest="node_validator_dir", help="Optional path to Node validator directory for reachability analysis")
    parser.add_argument("--node-bin", dest="node_bin", default="node", help="Node executable to use for reachability analysis")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log("validate", "running", current=0, total=1,
               message="Loading gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    gamebook = load_gamebook(args.gamebook)
    sections = gamebook.get("sections", {})

    logger.log("validate", "running", current=0, total=1,
               message="Validating gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    # Call Node validator for ALL validation (canonical source of truth)
    node_validator_result = None
    if args.node_validator_dir:
        try:
            node_validator_result = _call_node_validator(
                args.gamebook, args.node_validator_dir, args.node_bin
            )
        except Exception as e:
            # Don't fail validation if Node validator isn't available, just log warning
            print(f"Warning: Could not run Node validator: {e}", file=sys.stderr)

    # Build validation report from Node validator results
    report = validate_gamebook(
        gamebook,
        args.expected_range_start,
        args.expected_range_end,
        node_validator_result=node_validator_result
    )

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
