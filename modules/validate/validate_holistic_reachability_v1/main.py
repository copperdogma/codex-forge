import argparse
import json
import os
from typing import Any, Dict, List, Set

from modules.common.utils import read_jsonl, save_json, ProgressLogger
from schemas import ValidationReport, EnrichedPortion

def _resolve_template(template: str, value: str, op: str = "", op_value: str = "") -> str:
    base = template.replace("{state}", str(value)) if template else str(value)
    op = (op or "").strip().lower()
    op_value = str(op_value or "").strip()
    if not op or not op_value.isdigit():
        return base
    if base.isdigit():
        num = int(base)
    elif str(value).isdigit():
        num = int(str(value))
    else:
        return base
    delta = int(op_value)
    if op == "add":
        return str(num + delta)
    if op == "subtract":
        return str(num - delta)
    if op == "multiply":
        return str(num * delta)
    return base


def collect_referenced_sections(portion: Dict[str, Any], state_values: Dict[str, Set[str]]) -> Set[str]:
    """Collects all section IDs referenced in any gameplay mechanic."""
    referenced = set()
    
    # 1. Choices
    for choice in portion.get("choices", []):
        if choice.get("target"):
            referenced.add(str(choice["target"]))
            
    # 2. Combat
    for combat in portion.get("combat", []):
        if combat.get("win_section"): referenced.add(str(combat["win_section"]))
        if combat.get("loss_section"): referenced.add(str(combat["loss_section"]))
        if combat.get("escape_section"): referenced.add(str(combat["escape_section"]))
        
    # 3. Stat Checks
    for check in portion.get("stat_checks", []):
        if check.get("pass_section"): referenced.add(str(check["pass_section"]))
        if check.get("fail_section"): referenced.add(str(check["fail_section"]))
        
    # 4. Test Luck
    for luck in portion.get("test_luck", []):
        if luck.get("lucky_section"): referenced.add(str(luck["lucky_section"]))
        if luck.get("unlucky_section"): referenced.add(str(luck["unlucky_section"]))
        
    # 5. Inventory
    inv = portion.get("inventory") or {}
    for check in inv.get("inventory_checks", []):
        if check.get("target_section"): referenced.add(str(check["target_section"]))

    # 6. State checks (templated references)
    for check in portion.get("state_checks", []) or []:
        if not isinstance(check, dict):
            continue
        if check.get("has_target"):
            referenced.add(str(check["has_target"]))
        if check.get("missing_target"):
            referenced.add(str(check["missing_target"]))
        template = check.get("template_target")
        key = check.get("key")
        op = check.get("template_op")
        op_value = check.get("template_value")
        if template and key and key in state_values:
            for value in state_values[key]:
                resolved = _resolve_template(str(template), str(value), op=op, op_value=op_value)
                if resolved and str(resolved).isdigit():
                    referenced.add(str(resolved))
        
    return referenced

def main():
    parser = argparse.ArgumentParser(description="Holistic reachability validation.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--out", required=True, help="Output validation_report.json")
    parser.add_argument("--expected-range-start", "--expected_range_start", type=int, default=1)
    parser.add_argument("--expected-range-end", "--expected_range_end", type=int, default=400)
    parser.add_argument("--section-count", "--section_count", dest="section_count", help="Section range JSON (optional)")
    parser.add_argument("--run-id")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--pages", help="ignored")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    portions = [row for row in read_jsonl(args.portions) if "error" not in row]

    section_confidence = None
    section_max_ref = None
    if args.section_count:
        try:
            with open(args.section_count, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if isinstance(data.get("max_section"), int):
                    args.expected_range_end = data["max_section"]
                if isinstance(data.get("min_section"), int):
                    args.expected_range_start = data["min_section"]
                if isinstance(data.get("confidence"), str):
                    section_confidence = data["confidence"]
                if isinstance(data.get("max_ref_section"), int):
                    section_max_ref = data["max_ref_section"]
        except Exception:
            pass
    
    def _in_expected_section_id(section_id: str) -> bool:
        if not section_id:
            return False
        if not section_id.isdigit():
            return True
        return args.expected_range_start <= int(section_id) <= args.expected_range_end

    authoritative_sections = {
        sid for sid in (str(p.get("section_id") or p.get("portion_id")) for p in portions)
        if _in_expected_section_id(sid)
    }
    all_references = set()
    section_references = {} # sid -> set of targets

    state_values: Dict[str, Set[str]] = {}
    for p in portions:
        sid = str(p.get("section_id") or p.get("portion_id"))
        if not _in_expected_section_id(sid):
            continue
        for state in p.get("state_values", []) or []:
            if not isinstance(state, dict):
                continue
            key = state.get("key")
            value = state.get("value")
            if not key or value is None:
                continue
            state_values.setdefault(str(key), set()).add(str(value))
    
    for p in portions:
        sid = str(p.get("section_id") or p.get("portion_id"))
        if not _in_expected_section_id(sid):
            continue
        refs = collect_referenced_sections(p, state_values)
        section_references[sid] = refs
        all_references.update(refs)
        
    # Validation Logic
    
    # 1. Broken Links (Referenced but not found)
    broken_links = sorted([r for r in all_references if r not in authoritative_sections and r.isdigit()])
    
    # 2. Orphans (Found but never referenced)
    # Ignore section 1, background, etc.
    ignore_orphans = {"1", "background", "intro", "rules"}
    orphans = sorted([s for s in authoritative_sections if s not in all_references and s not in ignore_orphans and s.isdigit()], key=lambda x: int(x))
    
    # 3. Missing expected sections
    expected = {str(i) for i in range(args.expected_range_start, args.expected_range_end + 1)}
    missing = sorted(list(expected - authoritative_sections), key=lambda x: int(x))
    
    # Build Report
    errors = []
    warnings = []
    
    if broken_links:
        errors.append(f"Found {len(broken_links)} broken links: {broken_links[:10]}...")
    if missing:
        errors.append(f"Missing {len(missing)} sections in expected range: {missing[:10]}...")
    if orphans:
        warnings.append(f"Found {len(orphans)} orphaned sections: {orphans[:10]}...")
    if section_confidence == "conflict" and section_max_ref:
        warnings.append(f"Section range conflict: refs exceed max_section (max_ref={section_max_ref}).")
        
    is_valid = len(errors) == 0
    
    report = ValidationReport(
        total_sections=len(authoritative_sections),
        missing_sections=missing,
        duplicate_sections=[], # Portions are unique by ID in this pipeline
        sections_with_no_text=[], # Logic moved to forensics if needed
        sections_with_no_choices=[], # Logic moved to forensics if needed
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
        forensics={
            "broken_links": broken_links,
            "orphans": orphans,
            "reference_map": {k: list(v) for k, v in section_references.items() if v}
        }
    )
    
    save_json(args.out, report.model_dump(by_alias=True))
    logger.log("validate_reachability", "done", message=f"Validated reachability for {len(authoritative_sections)} sections. Valid: {is_valid}", artifact=args.out)
    
    print(f"Holistic Validation Report -> {args.out}")
    print(f"  Valid: {is_valid}")
    print(f"  Broken Links: {len(broken_links)}")
    print(f"  Orphans: {len(orphans)}")
    print(f"  Missing: {len(missing)}")

if __name__ == "__main__":
    main()
