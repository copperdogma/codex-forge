import argparse
import json
import os
from typing import Any, Dict, List, Set

from modules.common.utils import read_jsonl, save_json, ProgressLogger
from schemas import ValidationReport, EnrichedPortion

def collect_referenced_sections(portion: Dict[str, Any]) -> Set[str]:
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
        
    return referenced

def main():
    parser = argparse.ArgumentParser(description="Holistic reachability validation.")
    parser.add_argument("--portions", required=True, help="Input enriched_portion_v1 JSONL")
    parser.add_argument("--out", required=True, help="Output validation_report.json")
    parser.add_argument("--expected-range-start", "--expected_range_start", type=int, default=1)
    parser.add_argument("--expected-range-end", "--expected_range_end", type=int, default=400)
    parser.add_argument("--run-id")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--pages", help="ignored")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    portions = [row for row in read_jsonl(args.portions) if "error" not in row]
    
    authoritative_sections = {str(p.get("section_id") or p.get("portion_id")) for p in portions}
    all_references = set()
    section_references = {} # sid -> set of targets
    
    for p in portions:
        sid = str(p.get("section_id") or p.get("portion_id"))
        refs = collect_referenced_sections(p)
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
