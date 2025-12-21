#!/usr/bin/env python3
import argparse
import json
from typing import Dict, List, Set


def _load_gamebook(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_expected_range(rng: str) -> tuple[int, int]:
    try:
        lo, hi = rng.split("-", 1)
        return int(lo), int(hi)
    except Exception:
        return 1, 400


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight gamebook validation for smoke runs.")
    parser.add_argument("--gamebook", required=True, help="Path to gamebook.json")
    parser.add_argument("--out", required=True, help="Output validation report JSON")
    parser.add_argument("--state-file")
    parser.add_argument("--progress-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    gamebook = _load_gamebook(args.gamebook)
    sections: Dict[str, Dict] = gamebook.get("sections") or {}
    provenance = gamebook.get("provenance") or {}
    expected_range = provenance.get("expected_range") or "1-400"
    min_section, max_section = _parse_expected_range(expected_range)
    unresolved_missing = set(str(x) for x in (provenance.get("unresolved_missing") or []))
    stub_targets = set(str(x) for x in (provenance.get("stub_targets") or []))

    errors: List[str] = []
    warnings: List[str] = []

    if not sections:
        errors.append("gamebook.sections is empty")

    # Validate section IDs and gameplay content
    for sid, section in sections.items():
        if not str(sid).isdigit():
            errors.append(f"non-numeric section id: {sid}")
            continue
        n = int(sid)
        if not (min_section <= n <= max_section):
            warnings.append(f"section id {sid} outside expected range {expected_range}")
        if section.get("isGameplaySection") and not (section.get("text") or "").strip():
            if sid in stub_targets:
                warnings.append(f"empty text for stub target section {sid}")
            elif sid in unresolved_missing:
                warnings.append(f"empty text for unresolved-missing section {sid}")
            else:
                errors.append(f"empty text for gameplay section {sid}")

        # Validate navigation targets
        for link in section.get("navigationLinks") or []:
            tgt = link.get("targetSection")
            if tgt is None:
                errors.append(f"section {sid} has navigation link without targetSection")
                continue
            tgt_str = str(tgt)
            if not tgt_str.isdigit():
                errors.append(f"section {sid} has non-numeric target {tgt_str}")
                continue
            if tgt_str not in sections and tgt_str not in unresolved_missing:
                errors.append(f"section {sid} targets missing section {tgt_str} (not in unresolved_missing)")

    report = {
        "gamebook": args.gamebook,
        "expected_range": expected_range,
        "section_count": len(sections),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=True)

    if errors:
        raise SystemExit(f"Validation failed with {len(errors)} errors")
    print(f"Validation OK: {len(sections)} sections, {len(warnings)} warnings")


if __name__ == "__main__":
    main()
