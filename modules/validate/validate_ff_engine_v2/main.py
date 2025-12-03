import argparse
import json
import os
from typing import Dict, List, Any

from modules.common.utils import save_json, ensure_dir, ProgressLogger
from schemas import ValidationReport


def load_gamebook(path: str) -> Dict[str, Any]:
    """Load gamebook.json."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_gamebook(
    gamebook: Dict[str, Any],
    expected_range_start: int,
    expected_range_end: int
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
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    logger.log("validate", "running", current=0, total=1,
               message="Loading gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    gamebook = load_gamebook(args.gamebook)

    logger.log("validate", "running", current=0, total=1,
               message="Validating gamebook", artifact=args.out, module_id="validate_ff_engine_v2")

    report = validate_gamebook(gamebook, args.expected_range_start, args.expected_range_end)

    # Save report
    ensure_dir(os.path.dirname(args.out) or ".")
    save_json(args.out, report.dict(by_alias=True))

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
