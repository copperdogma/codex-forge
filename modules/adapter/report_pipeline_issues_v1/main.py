#!/usr/bin/env python3
"""Collect pipeline issues into a single JSONL report.

Scans the run directory for known issue artifacts (e.g., missing_bundles).
Writes one JSONL row with summary + detailed issues.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from modules.common.utils import ensure_dir, ProgressLogger


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _run_dir_from_out(out_path: str) -> str:
    # out_path => .../output/runs/<run_id>/<ordinal_module>/issues_report.jsonl
    # run dir is parent of module folder
    return str(Path(out_path).resolve().parents[1])


def _collect_missing_bundles(run_dir: str) -> List[Dict]:
    issues = []
    for root, dirs, files in os.walk(run_dir):
        if os.path.basename(root) != "missing_bundles":
            continue
        for name in files:
            if not name.startswith("missing_section_") or not name.endswith(".json"):
                continue
            path = os.path.join(root, name)
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                data = None
            issues.append({
                "type": "missing_section",
                "severity": "error",
                "section_id": data.get("section_id") if isinstance(data, dict) else None,
                "note": data.get("note") if isinstance(data, dict) else None,
                "evidence_path": path,
            })
    return issues


def _collect_ordering_conflicts(run_dir: str) -> List[Dict]:
    issues: List[Dict] = []
    for root, dirs, files in os.walk(run_dir):
        for name in files:
            if name != "ordering_conflicts.json":
                continue
            path = os.path.join(root, name)
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                data = None
            conflicts = data.get("ordering_conflicts") if isinstance(data, dict) else None
            if not isinstance(conflicts, list):
                continue
            for conflict in conflicts:
                issues.append({
                    "type": "boundary_ordering_conflict",
                    "severity": "error",
                    "section_id": str(conflict.get("section_id")) if conflict.get("section_id") is not None else None,
                    "note": "Section ordering conflict detected; boundary spans may be inverted.",
                    "details": conflict,
                    "evidence_path": path,
                })
    return issues


def _collect_duplicate_headers(run_dir: str) -> List[Dict]:
    issues: List[Dict] = []
    for root, dirs, files in os.walk(run_dir):
        for name in files:
            if name != "duplicate_headers.json":
                continue
            path = os.path.join(root, name)
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                data = None
            duplicates = data.get("duplicate_headers") if isinstance(data, dict) else None
            if not isinstance(duplicates, list):
                continue
            for dup in duplicates:
                issues.append({
                    "type": "boundary_duplicate_header",
                    "severity": "error",
                    "section_id": str(dup.get("section_id")) if dup.get("section_id") is not None else None,
                    "note": "Multiple candidate headers detected for same section id; dedupe may be wrong.",
                    "details": dup,
                    "evidence_path": path,
                })
    return issues


def _select_choice_stats_files(run_dir: str) -> List[str]:
    stats_files = []
    for root, dirs, files in os.walk(run_dir):
        for name in files:
            if not name.endswith("_stats.json"):
                continue
            if "portions_with_choices" not in name:
                continue
            stats_files.append(os.path.join(root, name))
    if not stats_files:
        return []
    preferred = [p for p in stats_files if "choices_repair_relaxed_v1" in p]
    if preferred:
        return preferred
    relaxed = [p for p in stats_files if "extract_choices_relaxed_v1" in p]
    return relaxed or stats_files


def _load_reachability_orphans(run_dir: str) -> Optional[List[str]]:
    report_path = os.path.join(run_dir, "18_validate_holistic_reachability_v1", "reachability_report.json")
    if not os.path.exists(report_path):
        return None
    try:
        data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    orphans = data.get("forensics", {}).get("orphans")
    if isinstance(orphans, list):
        return [str(o) for o in orphans]
    return None


def _collect_choice_orphans(run_dir: str) -> List[Dict]:
    issues: List[Dict] = []
    true_orphans = _load_reachability_orphans(run_dir)
    for path in _select_choice_stats_files(run_dir):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            data = None
        if not isinstance(data, dict):
            continue
        orphans = data.get("orphaned_sections") or []
        if true_orphans is not None:
            orphans = [str(o) for o in orphans if str(o) in set(true_orphans)]
        repair_no_sources = data.get("repair_no_sources")
        repair_sources_examined = data.get("repair_sources_examined")
        relaxed_index = data.get("relaxed_reference_index") or {}
        for sec in orphans:
            relaxed_sources = relaxed_index.get(str(sec)) or relaxed_index.get(int(sec)) if str(sec).isdigit() else None
            if relaxed_sources:
                issues.append({
                    "type": "orphaned_section_relaxed_hit",
                    "severity": "warning",
                    "section_id": str(sec),
                    "note": "Relaxed scan found references; investigate source sections.",
                    "sources": relaxed_sources,
                    "evidence_path": path,
                })
            else:
                issue_type = "orphaned_section"
                note = "Section has no incoming choices; may indicate missing choices."
                if repair_no_sources or (repair_sources_examined == 0):
                    issue_type = "orphaned_section_no_sources"
                    note = "No relaxed sources found to repair this orphan; escalation exhausted. Requires manual review."
                issues.append({
                    "type": issue_type,
                    "severity": "warning",
                    "section_id": str(sec),
                    "note": note,
                    "evidence_path": path,
                })
    return issues


def _write_unresolved_missing(run_dir: str, issues: List[Dict]) -> Optional[str]:
    missing = sorted({i.get("section_id") for i in issues if i.get("type") == "missing_section" and i.get("section_id")})
    if not missing:
        return None
    out_path = os.path.join(run_dir, "unresolved_missing.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(missing, f, ensure_ascii=True, indent=2)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect pipeline issues into a report JSONL")
    ap.add_argument("--inputs", nargs="*", help="(ignored) driver compatibility")
    ap.add_argument("--out", required=True, help="Output JSONL report path")
    ap.add_argument("--run-dir", dest="run_dir", help="Optional run directory override")
    ap.add_argument("--progress-file")
    ap.add_argument("--state-file")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path))
    run_dir = args.run_dir or _run_dir_from_out(out_path)

    issues: List[Dict] = []
    issues.extend(_collect_missing_bundles(run_dir))
    issues.extend(_collect_ordering_conflicts(run_dir))
    issues.extend(_collect_duplicate_headers(run_dir))
    issues.extend(_collect_choice_orphans(run_dir))

    summary = {
        "issue_count": len(issues),
        "missing_section_count": sum(1 for i in issues if i.get("type") == "missing_section"),
        "boundary_ordering_conflict_count": sum(1 for i in issues if i.get("type") == "boundary_ordering_conflict"),
        "boundary_duplicate_header_count": sum(1 for i in issues if i.get("type") == "boundary_duplicate_header"),
        "orphaned_section_count": sum(1 for i in issues if i.get("type") == "orphaned_section"),
        "orphaned_section_no_sources_count": sum(1 for i in issues if i.get("type") == "orphaned_section_no_sources"),
        "orphaned_section_relaxed_hit_count": sum(1 for i in issues if i.get("type") == "orphaned_section_relaxed_hit"),
    }

    row = {
        "schema_version": "pipeline_issues_v1",
        "module_id": "report_pipeline_issues_v1",
        "run_id": os.path.basename(run_dir),
        "created_at": _utc(),
        "summary": summary,
        "issues": issues,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=True) + "\n")

    _write_unresolved_missing(run_dir, issues)

    progress_path = args.progress_file or os.path.join(run_dir, "pipeline_events.jsonl")
    run_id = args.run_id or os.path.basename(run_dir)
    logger = ProgressLogger(state_path=args.state_file, progress_path=progress_path, run_id=run_id)
    summary_msg = (
        f"Issues: missing {summary['missing_section_count']}, "
        f"ordering_conflicts {summary['boundary_ordering_conflict_count']}, "
        f"duplicate_headers {summary['boundary_duplicate_header_count']}, "
        f"orphans {summary['orphaned_section_count']}, "
        f"orphans_no_sources {summary['orphaned_section_no_sources_count']} → {out_path}"
    )
    status = "warning" if summary["issue_count"] else "done"
    logger.log(
        "report_pipeline_issues",
        status,
        current=summary["issue_count"],
        total=summary["issue_count"],
        message=summary_msg,
        artifact=out_path,
        module_id="report_pipeline_issues_v1",
        schema_version="pipeline_issues_v1",
        extra={"summary_metrics": {
            "missing_section_count": summary["missing_section_count"],
            "orphaned_section_count": summary["orphaned_section_count"],
            "orphaned_section_no_sources_count": summary["orphaned_section_no_sources_count"],
            "issue_count": summary["issue_count"],
        }},
    )
    print(f"[summary] report_pipeline_issues_v1: {summary_msg}")


if __name__ == "__main__":
    main()
