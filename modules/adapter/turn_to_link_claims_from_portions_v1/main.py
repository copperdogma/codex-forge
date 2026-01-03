#!/usr/bin/env python3
"""Emit turn-to link claims from enriched portions."""
import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.common.utils import ensure_dir, ProgressLogger


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _walk_targets(obj: Any, prefix: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            if key in {"targetSection", "target_section", "target"} and value is not None:
                yield (str(value), path)
            else:
                yield from _walk_targets(value, path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            path = f"{prefix}/{idx}" if prefix else f"/{idx}"
            yield from _walk_targets(item, path)


def _emit_claim(rows: List[Dict[str, Any]], *, portion: Dict[str, Any], target: str, claim_type: str, evidence_path: str, module_id: str, run_id: Optional[str], seen: set) -> None:
    section_id = portion.get("section_id")
    portion_id = portion.get("portion_id")
    if not section_id and not portion_id:
        return
    key = (str(section_id or portion_id), str(target), str(claim_type), str(evidence_path))
    if key in seen:
        return
    seen.add(key)
    rows.append({
        "schema_version": "turn_to_link_claims_v1",
        "module_id": module_id,
        "run_id": run_id,
        "created_at": _utc(),
        "section_id": str(section_id) if section_id is not None else str(portion_id),
        "portion_id": str(portion_id) if portion_id is not None else None,
        "target": str(target),
        "claim_type": claim_type,
        "evidence_path": evidence_path,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit turn-to link claims from enriched portions.")
    parser.add_argument("--input", help="Portions JSONL")
    parser.add_argument("--inputs", nargs="*", help="Driver adapter input list")
    parser.add_argument("--out", required=True, help="Output claims JSONL")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    portions_path = args.input
    if not portions_path and args.inputs:
        portions_path = args.inputs[0]
    if not portions_path:
        raise SystemExit("turn_to_link_claims_from_portions_v1 requires --input or --inputs")

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path))

    portions = _load_jsonl(portions_path)
    rows: List[Dict[str, Any]] = []
    seen = set()

    for portion in portions:
        if not isinstance(portion, dict):
            continue

        explicit_claims = portion.get("turn_to_claims") or []
        if isinstance(explicit_claims, list) and explicit_claims:
            for idx, claim in enumerate(explicit_claims):
                if not isinstance(claim, dict):
                    continue
                target = claim.get("target")
                if not target:
                    continue
                claim_type = claim.get("claim_type") or "explicit"
                module_id = claim.get("module_id") or "turn_to_link_claims_from_portions_v1"
                evidence_path = claim.get("evidence_path") or f"/turn_to_claims/{idx}"
                _emit_claim(
                    rows,
                    portion=portion,
                    target=str(target),
                    claim_type=str(claim_type),
                    evidence_path=str(evidence_path),
                    module_id=str(module_id),
                    run_id=args.run_id,
                    seen=seen,
                )
            continue

        # Choices
        for idx, choice in enumerate(portion.get("choices") or []):
            target = choice.get("target") if isinstance(choice, dict) else None
            if target:
                _emit_claim(rows, portion=portion, target=str(target), claim_type="choice", evidence_path=f"/choices/{idx}", module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)

        # Test luck
        for idx, tl in enumerate(portion.get("test_luck") or []):
            if not isinstance(tl, dict):
                continue
            lucky = tl.get("lucky_section")
            unlucky = tl.get("unlucky_section")
            if lucky:
                _emit_claim(rows, portion=portion, target=str(lucky), claim_type="test_luck_lucky", evidence_path=f"/test_luck/{idx}/lucky_section", module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)
            if unlucky:
                _emit_claim(rows, portion=portion, target=str(unlucky), claim_type="test_luck_unlucky", evidence_path=f"/test_luck/{idx}/unlucky_section", module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)

        # Stat checks
        for idx, sc in enumerate(portion.get("stat_checks") or []):
            if not isinstance(sc, dict):
                continue
            pass_section = sc.get("pass_section")
            fail_section = sc.get("fail_section")
            if pass_section:
                _emit_claim(rows, portion=portion, target=str(pass_section), claim_type="stat_check_pass", evidence_path=f"/stat_checks/{idx}/pass_section", module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)
            if fail_section:
                _emit_claim(rows, portion=portion, target=str(fail_section), claim_type="stat_check_fail", evidence_path=f"/stat_checks/{idx}/fail_section", module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)

        # Inventory checks
        inventory = portion.get("inventory") or {}
        checks = inventory.get("inventory_checks") if isinstance(inventory, dict) else []
        for idx, chk in enumerate(checks or []):
            if not isinstance(chk, dict):
                continue
            target = chk.get("target_section")
            if target:
                _emit_claim(rows, portion=portion, target=str(target), claim_type="inventory_check", evidence_path=f"/inventory/inventory_checks/{idx}/target_section", module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)

        # Combat: walk for targetSection/target_section/target in combat structures
        for idx, combat in enumerate(portion.get("combat") or []):
            if not isinstance(combat, dict):
                continue
            for target, path in _walk_targets(combat, f"/combat/{idx}"):
                _emit_claim(rows, portion=portion, target=str(target), claim_type="combat", evidence_path=path, module_id="turn_to_link_claims_from_portions_v1", run_id=args.run_id, seen=seen)

    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "turn_to_link_claims",
        "done",
        current=len(rows),
        total=len(rows),
        message=f"Emitted {len(rows)} turn-to claims from portions",
        artifact=out_path,
        module_id="turn_to_link_claims_from_portions_v1",
        schema_version="turn_to_link_claims_v1",
    )
    print(f"[summary] turn_to_link_claims_from_portions_v1: {len(rows)} claims → {out_path}")


if __name__ == "__main__":
    main()
