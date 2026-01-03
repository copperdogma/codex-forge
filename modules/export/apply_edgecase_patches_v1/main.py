#!/usr/bin/env python3
"""Apply edge-case patch JSONL to a gamebook.json."""
import argparse
import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from modules.common.utils import ProgressLogger


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_patches(path: str) -> List[Dict[str, Any]]:
    patches: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            patches.append(json.loads(line))
    return patches


def _parse_pointer(pointer: str) -> List[str]:
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {pointer}")
    parts = pointer.lstrip("/").split("/")
    return [p.replace("~1", "/").replace("~0", "~") for p in parts]


def _get_target(container: Any, pointer: str) -> Tuple[Any, str]:
    parts = _parse_pointer(pointer)
    if not parts:
        raise ValueError(f"Pointer resolves to root: {pointer}")
    current = container
    for key in parts[:-1]:
        if isinstance(current, list):
            idx = int(key)
            current = current[idx]
        else:
            current = current[key]
    return current, parts[-1]


def _apply_patch(gamebook: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    op = patch.get("op")
    pointer = patch.get("path")
    value = patch.get("value")
    if op not in {"add", "replace", "remove"}:
        raise ValueError(f"Unsupported op: {op}")
    if not pointer:
        raise ValueError("Patch missing path")

    target, last = _get_target(gamebook, pointer)
    before = None
    if isinstance(target, list):
        idx = int(last)
        before = target[idx] if idx < len(target) else None
        if op == "remove":
            target.pop(idx)
        elif op == "replace":
            target[idx] = value
        elif op == "add":
            if idx == len(target):
                target.append(value)
            else:
                target.insert(idx, value)
    else:
        before = target.get(last) if isinstance(target, dict) else None
        if op == "remove":
            if isinstance(target, dict):
                target.pop(last, None)
        elif op in {"replace", "add"}:
            if isinstance(target, dict):
                target[last] = value
    return {"before": before, "after": value if op != "remove" else None}


def _is_idempotent(gamebook: Dict[str, Any], patch: Dict[str, Any]) -> bool:
    op = patch.get("op")
    pointer = patch.get("path")
    value = patch.get("value")
    try:
        target, last = _get_target(gamebook, pointer)
    except Exception:
        return False
    if isinstance(target, list):
        idx = int(last)
        current = target[idx] if idx < len(target) else None
    else:
        current = target.get(last) if isinstance(target, dict) else None
    if op == "remove":
        return current is None
    return current == value


def apply_patches(gamebook: Dict[str, Any], patches: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    report: List[Dict[str, Any]] = []
    applied = 0
    for idx, patch in enumerate(patches):
        record = {
            "patch_index": idx,
            "section_id": patch.get("section_id"),
            "reason_code": patch.get("reason_code"),
            "path": patch.get("path"),
            "op": patch.get("op"),
        }
        if _is_idempotent(gamebook, patch):
            record["status"] = "already_applied"
            report.append(record)
            continue
        snapshot = deepcopy(gamebook)
        try:
            change = _apply_patch(gamebook, patch)
            record["status"] = "applied"
            record["before"] = change.get("before")
            record["after"] = change.get("after")
            applied += 1
        except Exception as exc:
            gamebook = snapshot
            record["status"] = "failed"
            record["error"] = str(exc)
        report.append(record)
    return gamebook, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply edge-case patch JSONL to gamebook.json")
    parser.add_argument("--input", required=True, help="Input gamebook.json")
    parser.add_argument("--patches", help="Patch JSONL file")
    parser.add_argument("--allow-missing", action="store_true", help="Allow missing patch file and pass through")
    parser.add_argument("--out", required=True, help="Output patched gamebook.json")
    parser.add_argument("--report-out", required=True, help="Output patch report JSONL")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        gamebook = json.load(f)
    if not isinstance(gamebook, dict) or "sections" not in gamebook:
        run_dir = os.path.abspath(os.path.join(os.path.dirname(args.out), ".."))
        fallback = os.path.join(run_dir, "gamebook.json")
        if os.path.exists(fallback):
            with open(fallback, "r", encoding="utf-8") as f:
                gamebook = json.load(f)
    if not args.patches:
        if not args.allow_missing:
            raise SystemExit("--patches is required unless --allow-missing is set")
        patches = []
    else:
        patches_path = args.patches
        if not os.path.isabs(patches_path):
            run_dir = os.path.abspath(os.path.join(os.path.dirname(args.out), ".."))
            candidate = os.path.join(run_dir, "03_edgecase_ai_patch_v1", patches_path)
            if os.path.exists(candidate):
                patches_path = candidate
        if not os.path.exists(patches_path):
            if args.allow_missing:
                patches = []
            else:
                raise FileNotFoundError(f"Patches file not found: {patches_path}")
        else:
            patches = _load_patches(patches_path)

    patched, report = apply_patches(gamebook, patches)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(patched, f, indent=2, ensure_ascii=False)

    report_path = args.report_out
    if not os.path.isabs(report_path):
        report_path = os.path.join(os.path.dirname(args.out), report_path)
    with open(report_path, "w", encoding="utf-8") as f:
        row = {
            "schema_version": "edgecase_patch_report_v1",
            "module_id": "apply_edgecase_patches_v1",
            "run_id": args.run_id,
            "created_at": _utc(),
            "summary": {
                "patch_count": len(patches),
                "applied_count": sum(1 for r in report if r.get("status") == "applied"),
                "failed_count": sum(1 for r in report if r.get("status") == "failed"),
                "already_applied_count": sum(1 for r in report if r.get("status") == "already_applied"),
            },
            "patches": report,
        }
        f.write(json.dumps(row, ensure_ascii=True) + "\n")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "apply_edgecase_patches",
        "done",
        message=f"Applied {len(patches)} patches → {args.out}",
        artifact=report_path,
        module_id="apply_edgecase_patches_v1",
        schema_version="edgecase_patch_report_v1",
    )
    print(f"[summary] apply_edgecase_patches_v1: {len(patches)} patches → {args.out}")


if __name__ == "__main__":
    main()
