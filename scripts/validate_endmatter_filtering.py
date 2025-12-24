#!/usr/bin/env python3
"""
Validation script to verify endmatter filtering in portionized sections.
Checks that sections near the end of the book don't contain endmatter content.
"""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Any

from modules.common.utils import read_jsonl


def detect_endmatter_in_html(html: str) -> List[str]:
    """Detect endmatter patterns in HTML content."""
    issues = []

    # Check for endmatter running heads (allow newlines within tags)
    if re.search(r'<p\s+class="running-head">\s*(?:more fighting fantasy|also available|coming soon)', html, re.IGNORECASE | re.DOTALL):
        issues.append("Found endmatter running head")

    # Check for book title headers (numbered all-caps, allow newlines)
    if re.search(r'<h[12]>\s*\d{1,2}\.\s+[A-Z][A-Z\s\-:]{5,}\s*</h[12]>', html, re.DOTALL):
        issues.append("Found book title header")

    # Check for author name patterns after headers (allow newlines)
    if re.search(r'<h[12]>[^<]*</h[12]>\s*<p>\s*[A-Z][a-z]+\s+(?:and\s+)?[A-Z][a-z]+\s*</p>', html, re.DOTALL):
        issues.append("Found author name pattern")

    return issues


def validate_portions(portions_path: str, check_last_n: int = 10) -> Dict[str, Any]:
    """
    Validate that the last N sections don't contain endmatter patterns.

    Args:
        portions_path: Path to enriched_portion_v1 JSONL file
        check_last_n: Number of sections at the end to check

    Returns:
        Validation report with findings
    """
    portions = list(read_jsonl(portions_path))

    # Sort by section ID (numeric sections should be at the end)
    numeric_portions = []
    for p in portions:
        section_id = p.get("section_id") or p.get("portion_id")
        if section_id and str(section_id).isdigit():
            numeric_portions.append(p)

    numeric_portions.sort(key=lambda p: int(p.get("section_id") or p.get("portion_id")))

    # Check the last N sections
    sections_to_check = numeric_portions[-check_last_n:] if len(numeric_portions) >= check_last_n else numeric_portions

    report = {
        "total_portions": len(portions),
        "numeric_portions": len(numeric_portions),
        "checked_sections": [],
        "issues_found": [],
        "clean_sections": 0,
    }

    for portion in sections_to_check:
        section_id = portion.get("section_id") or portion.get("portion_id")
        raw_html = portion.get("raw_html", "")

        issues = detect_endmatter_in_html(raw_html)

        section_report = {
            "section_id": section_id,
            "has_issues": len(issues) > 0,
            "issues": issues,
        }

        report["checked_sections"].append(section_report)

        if issues:
            report["issues_found"].append({
                "section_id": section_id,
                "issues": issues,
                "html_snippet": raw_html[:200] + "..." if len(raw_html) > 200 else raw_html
            })
        else:
            report["clean_sections"] += 1

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate endmatter filtering in portionized sections")
    parser.add_argument("portions", help="Path to enriched_portion_v1 JSONL file")
    parser.add_argument("--check-last-n", type=int, default=10, help="Number of sections at the end to check (default: 10)")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    args = parser.parse_args()

    if not Path(args.portions).exists():
        print(f"❌ File not found: {args.portions}")
        return 1

    report = validate_portions(args.portions, args.check_last_n)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n📊 Endmatter Filtering Validation Report")
        print(f"{'='*60}")
        print(f"Total portions: {report['total_portions']}")
        print(f"Numeric portions: {report['numeric_portions']}")
        print(f"Checked last {len(report['checked_sections'])} sections")
        print(f"Clean sections: {report['clean_sections']}/{len(report['checked_sections'])}")

        if report['issues_found']:
            print(f"\n⚠️  Issues Found ({len(report['issues_found'])} sections):")
            for issue in report['issues_found']:
                print(f"\n  Section {issue['section_id']}:")
                for i in issue['issues']:
                    print(f"    - {i}")
                print(f"    HTML: {issue['html_snippet']}")
        else:
            print(f"\n✅ No endmatter patterns found in the last {len(report['checked_sections'])} sections!")

    return 0 if not report['issues_found'] else 1


if __name__ == "__main__":
    exit(main())
