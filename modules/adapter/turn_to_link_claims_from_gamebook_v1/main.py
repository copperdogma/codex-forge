#!/usr/bin/env python3
"""Emit turn-to link claims based on gamebook sequence targets."""
import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from modules.common.utils import ensure_dir, ProgressLogger


def _utc() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _load_gamebook(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _walk_targets(obj: Any, prefix: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}/{key}" if prefix else f"/{key}"
            if key == "targetSection" and value is not None:
                yield (str(value), path)
            else:
                yield from _walk_targets(value, path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            path = f"{prefix}/{idx}" if prefix else f"/{idx}"
            yield from _walk_targets(item, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit turn-to link claims from gamebook.json")
    parser.add_argument("--input", help="Path to gamebook.json")
    parser.add_argument("--gamebook", help="Alias for --input")
    parser.add_argument("--inputs", nargs="*", help="Driver adapter input list")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--progress-file")
    parser.add_argument("--state-file")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    gamebook_path = args.input or args.gamebook
    if not gamebook_path and args.inputs:
        gamebook_path = args.inputs[0]
    if not gamebook_path:
        raise SystemExit("turn_to_link_claims_from_gamebook_v1 requires --input or --gamebook")

    out_path = os.path.abspath(args.out)
    ensure_dir(os.path.dirname(out_path))

    gamebook = _load_gamebook(gamebook_path)
    sections = gamebook.get("sections") or {}

    rows: List[Dict[str, Any]] = []
    for section_id, section in sections.items():
        if not isinstance(section, dict):
            continue
        sequence = section.get("sequence") or []
        for target, evidence_path in _walk_targets(sequence, ""):
            row = {
                "schema_version": "turn_to_link_claims_v1",
                "module_id": "turn_to_link_claims_from_gamebook_v1",
                "run_id": args.run_id,
                "created_at": _utc(),
                "section_id": str(section_id),
                "target": str(target),
                "claim_type": "gamebook_ref",
                "evidence_path": f"/sections/{section_id}/sequence{evidence_path}",
            }
            rows.append(row)

    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)
    logger.log(
        "turn_to_link_claims",
        "done",
        current=len(rows),
        total=len(rows),
        message=f"Emitted {len(rows)} turn-to claims from gamebook",
        artifact=out_path,
        module_id="turn_to_link_claims_from_gamebook_v1",
        schema_version="turn_to_link_claims_v1",
    )
    print(f"[summary] turn_to_link_claims_from_gamebook_v1: {len(rows)} claims → {out_path}")


if __name__ == "__main__":
    main()
