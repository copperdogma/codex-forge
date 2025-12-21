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

from modules.common.utils import ensure_dir


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


def _collect_choice_orphans(run_dir: str) -> List[Dict]:
    issues: List[Dict] = []
    for path in _select_choice_stats_files(run_dir):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            data = None
        if not isinstance(data, dict):
            continue
        orphans = data.get("orphaned_sections") or []
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
    args = ap.parse_args()

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path))
    run_dir = args.run_dir or _run_dir_from_out(out_path)

    issues: List[Dict] = []
    issues.extend(_collect_missing_bundles(run_dir))
    issues.extend(_collect_choice_orphans(run_dir))

    summary = {
        "issue_count": len(issues),
        "missing_section_count": sum(1 for i in issues if i.get("type") == "missing_section"),
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


if __name__ == "__main__":
    main()
