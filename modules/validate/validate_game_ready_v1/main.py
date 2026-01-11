#!/usr/bin/env python3
"""
Consolidated Game-Ready Validation Report.
Aggregates multiple validator outputs into a single pass/fail report.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Any

from modules.common.utils import save_json, ProgressLogger


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _safe_load_json(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        return _load_json(path)
    except Exception:
        return {}


def _run_dir_from_path(path: str) -> str:
    return str(Path(path).resolve().parent)


def _find_first(run_dir: str, filename: str) -> str | None:
    for root, _, files in os.walk(run_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None


def _find_choice_stats(run_dir: str) -> str | None:
    candidates: List[str] = []
    for root, _, files in os.walk(run_dir):
        for name in files:
            if not name.endswith("_stats.json"):
                continue
            if "portions_with_choices" not in name:
                continue
            candidates.append(os.path.join(root, name))
    if not candidates:
        return None
    preferred = [p for p in candidates if "validate_choice_links_v1" in p]
    return preferred[0] if preferred else candidates[0]


def _load_jsonl_first(path: str) -> Dict[str, Any]:
    with open(path, "r") as f:
        line = f.readline()
        return json.loads(line) if line else {}


def _parse_known_missing(raw: str) -> List[str]:
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _numeric_sections(sections: Dict[str, Any]) -> List[str]:
    return [sid for sid in sections.keys() if sid.isdigit()]


def _expected_range(start: int, end: int) -> List[str]:
    return [str(i) for i in range(start, end + 1)]


def _stubbed_sections(sections: Dict[str, Any]) -> List[str]:
    stubbed = []
    for sid, sec in sections.items():
        if not str(sid).isdigit():
            continue
        prov = sec.get("provenance") or {}
        if prov.get("stub") is True:
            stubbed.append(str(sid))
    return stubbed


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidated game-ready validation report")
    parser.add_argument("--gamebook", required=True, help="Path to gamebook.json")
    parser.add_argument("--choice-report", dest="choice_report", help="Choice completeness report JSON")
    parser.add_argument("--reachability-report", dest="reachability_report", help="Reachability report JSON")
    parser.add_argument("--engine-report", dest="engine_report", help="Engine validation report JSON")
    parser.add_argument("--issues-report", dest="issues_report", help="Pipeline issues report JSONL")
    parser.add_argument("--alignment-report", dest="alignment_report", help="Choice/text alignment report JSON")
    parser.add_argument("--orphan-trace-report", dest="orphan_trace_report", help="Orphan trace report JSON")
    parser.add_argument("--choice-links-stats", dest="choice_links_stats", help="Choice link repair stats JSON")
    parser.add_argument("--out", required=True, help="Output path for consolidated report JSON")
    parser.add_argument("--expected-range-start", dest="expected_range_start", type=int, default=1)
    parser.add_argument("--expected-range-end", dest="expected_range_end", type=int, default=400)
    parser.add_argument("--section-count", dest="section_count", help="Section range JSON (optional)")
    parser.add_argument("--known-missing", dest="known_missing", default="")
    parser.add_argument("--run-id", dest="run_id")
    parser.add_argument("--state-file", dest="state_file")
    parser.add_argument("--progress-file", dest="progress_file")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    gamebook = _load_json(args.gamebook)
    run_dir = _run_dir_from_path(args.gamebook)
    metadata = gamebook.get("metadata", {}) if isinstance(gamebook, dict) else {}
    if args.section_count:
        try:
            with open(args.section_count, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("max_section"), int):
                args.expected_range_end = data["max_section"]
        except Exception:
            pass
    elif isinstance(metadata, dict) and isinstance(metadata.get("sectionCount"), int):
        args.expected_range_end = metadata["sectionCount"]
    sections = gamebook.get("sections", {})
    present_sections = _numeric_sections(sections)
    stubbed_sections = _stubbed_sections(sections)
    expected = _expected_range(args.expected_range_start, args.expected_range_end)
    known_missing = _parse_known_missing(args.known_missing)
    missing = sorted(
        [s for s in expected if s not in present_sections and s not in known_missing],
        key=lambda x: int(x),
    )

    choice_report = _safe_load_json(args.choice_report)
    reachability_report = _safe_load_json(args.reachability_report)
    engine_report = _safe_load_json(args.engine_report)
    issues_report = _load_jsonl_first(args.issues_report) if args.issues_report else {}

    alignment_report_path = args.alignment_report or _find_first(run_dir, "choice_text_alignment_report.json")
    orphan_trace_path = args.orphan_trace_report or _find_first(run_dir, "orphan_trace_report.json")
    choice_links_stats_path = args.choice_links_stats or _find_choice_stats(run_dir)

    alignment_report = _safe_load_json(alignment_report_path)
    orphan_trace_report = _safe_load_json(orphan_trace_path)
    choice_links_stats = _safe_load_json(choice_links_stats_path)

    choice_flagged = choice_report.get("flagged_sections", [])
    reachability_forensics = reachability_report.get("forensics", {})
    reachability_orphans = reachability_forensics.get("orphans", []) or []
    reachability_broken = reachability_forensics.get("broken_links", []) or []
    def _filter_range(values: list) -> list:
        out = []
        for v in values or []:
            if isinstance(v, str) and v.isdigit():
                if args.expected_range_start <= int(v) <= args.expected_range_end:
                    out.append(v)
            else:
                out.append(v)
        return out
    reachability_orphans = _filter_range(reachability_orphans)
    reachability_broken = _filter_range(reachability_broken)
    engine_errors = engine_report.get("errors", []) or []
    engine_warnings = engine_report.get("warnings", []) or []

    issue_items = issues_report.get("issues", []) or []
    def _issue_in_expected(issue: dict) -> bool:
        sid = issue.get("section_id")
        if isinstance(sid, str) and sid.isdigit():
            return args.expected_range_start <= int(sid) <= args.expected_range_end
        return True
    issue_items = [i for i in issue_items if _issue_in_expected(i)]
    issue_types = [i.get("type") for i in issue_items if i.get("type")]
    issue_orphans = [i for i in issue_items if (i.get("type") or "").startswith("orphaned_section")]
    issue_missing = [i for i in issue_items if (i.get("type") == "missing_section")]
    issue_ordering = [i for i in issue_items if (i.get("type") == "boundary_ordering_conflict")]
    issue_duplicates = [i for i in issue_items if (i.get("type") == "boundary_duplicate_header")]
    missing_from_issues = [i.get("section_id") for i in issue_missing if i.get("section_id")]

    # Treat stubbed sections and missing_section issues as missing for game-ready status.
    missing_all = sorted(
        {s for s in (missing + stubbed_sections + missing_from_issues) if s not in known_missing},
        key=lambda x: int(x),
    )

    orphan_sources = orphan_trace_report.get("orphan_sources", {}) if isinstance(orphan_trace_report, dict) else {}
    issue_by_orphan = {}
    for issue in issue_items:
        sid = str(issue.get("section_id") or "")
        if sid:
            issue_by_orphan.setdefault(sid, []).append(issue)

    orphan_attempts = []
    for orphan_id in reachability_orphans:
        oid = str(orphan_id)
        orphan_attempts.append({
            "orphan_id": oid,
            "trace_sources": orphan_sources.get(oid, []),
            "issues": issue_by_orphan.get(oid, []),
        })

    broken_attempts = []
    for link in reachability_broken:
        broken_attempts.append({
            "broken_link": link,
            "notes": "No automated repair implemented; inspect source section text and choices.",
        })

    attempts = {
        "alignment_report": {
            "path": alignment_report_path,
            "flagged_count": alignment_report.get("flagged_count"),
        },
        "orphan_trace_report": {
            "path": orphan_trace_path,
            "orphan_count": orphan_trace_report.get("orphan_count"),
            "unreferenced_count": orphan_trace_report.get("unreferenced_count"),
        },
        "choice_links_stats": {
            "path": choice_links_stats_path,
            "repair_calls": choice_links_stats.get("repair_calls"),
            "repair_sources_examined": choice_links_stats.get("repair_sources_examined"),
            "alignment_added_choices": choice_links_stats.get("alignment_added_choices"),
            "orphan_trace_added_choices": choice_links_stats.get("orphan_trace_added_choices"),
        },
        "reachability_report": {
            "path": args.reachability_report,
            "orphan_count": len(reachability_orphans),
            "broken_link_count": len(reachability_broken),
        },
        "issues_report": {
            "path": args.issues_report,
            "issue_count": len(issue_items),
        },
    }

    unresolved = {
        "missing_sections": missing_all,
        "choice_missing_sections": choice_flagged,
        "reachability_orphans": reachability_orphans,
        "reachability_broken_links": reachability_broken,
        "engine_errors": engine_errors,
        "issues_orphans": [i.get("section_id") for i in issue_orphans],
        "issues_missing": missing_from_issues,
        "issues_ordering_conflicts": [i.get("section_id") for i in issue_ordering],
        "issues_duplicate_headers": [i.get("section_id") for i in issue_duplicates],
        "issue_types": issue_types,
    }

    status = "pass"
    fail_reasons = []
    if missing_all:
        status = "fail"
        fail_reasons.append("missing_sections")
    if choice_flagged:
        status = "fail"
        fail_reasons.append("choice_completeness")
    if reachability_orphans or reachability_broken:
        status = "fail"
        fail_reasons.append("reachability")
    if engine_errors:
        status = "fail"
        fail_reasons.append("engine_validation")
    if issue_orphans or issue_missing or issue_ordering:
        status = "fail"
        fail_reasons.append("issues_report")

    report = {
        "schema_version": "game_ready_validation_report_v1",
        "run_id": args.run_id,
        "status": status,
        "fail_reasons": fail_reasons,
        "known_missing_sections": known_missing,
        "section_counts": {
            "expected": len(expected),
            "present": len(present_sections),
            "missing": len(missing_all),
            "stubbed": len(stubbed_sections),
        },
        "choice_completeness": {
            "flagged_count": len(choice_flagged),
            "flagged_sections": choice_flagged,
        },
        "reachability": {
            "broken_links": reachability_broken,
            "orphans": reachability_orphans,
        },
        "engine_validation": {
            "errors": engine_errors,
            "warnings": engine_warnings,
        },
        "issues_report": {
            "issue_types": issue_types,
            "orphaned_sections": [i.get("section_id") for i in issue_orphans],
            "missing_sections": missing_from_issues,
            "ordering_conflicts": [i.get("section_id") for i in issue_ordering],
            "duplicate_headers": [i.get("section_id") for i in issue_duplicates],
        },
        "attempts": attempts,
        "orphan_attempts": orphan_attempts,
        "broken_link_attempts": broken_attempts,
        "unresolved": unresolved,
        "artifacts": {
            "gamebook": args.gamebook,
            "choice_report": args.choice_report,
            "reachability_report": args.reachability_report,
            "engine_report": args.engine_report,
            "issues_report": args.issues_report,
        },
        "manual_spot_checks": [],
    }

    save_json(args.out, report)
    logger.log("validate_game_ready", "done", message=f"Game-ready status: {status}", artifact=args.out)
    print(f"Game-ready report -> {args.out}")
    print(f"Status: {status}")
    if fail_reasons:
        print(f"Fail reasons: {', '.join(fail_reasons)}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
