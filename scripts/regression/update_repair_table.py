#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import shorten


def _load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _snippet(text: str, width: int = 90) -> str:
    return shorten((text or "").replace("\n", " "), width, placeholder="...")


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh repair table + rerun suspicious-token regression.")
    ap.add_argument("--run-dir", required=True, help="Path to the canonical run directory.")
    ap.add_argument("--table-out", help="Path to write the markdown table (default: <run-dir>/repair_table.md).")
    ap.add_argument("--check-file", help="Artifact to feed into check_suspicious_tokens.py; defaults to pagelines_final.jsonl in run dir.")
    ap.add_argument("--min-len", type=int, default=4, help="Minimum token length for the regression check.")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"ERROR: run directory not found: {run_dir}", file=sys.stderr)
        return 2

    repaired_path = run_dir / "repaired_portions.jsonl"
    repaired = []
    if repaired_path.exists():
        repaired = _load_jsonl(repaired_path)
    table_rows = []
    for row in repaired:
        portion_id = str(row.get("portion_id") or row.get("section_id") or "?")
        repair = row.get("repair") or {}
        attempted = repair.get("attempted")
        if not attempted:
            continue
        raw = row.get("raw_text_original") or row.get("raw_text") or ""
        clean = row.get("raw_text") or ""
        reasons = repair.get("reason") or []
        confidence = repair.get("confidence")
        context = row.get("context_correction") or {}
        trigger = context.get("trigger_scores") or {}
        dict_score = trigger.get("dictionary_score")
        char_score = trigger.get("char_confusion_score")
        table_rows.append(
            {
                "portion": portion_id,
                "raw": _snippet(raw),
                "reason": ", ".join(reasons) if reasons else "(none)",
                "confidence": f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "-",
                "clean": _snippet(clean),
                "dict": f"{dict_score:.3f}" if isinstance(dict_score, (int, float)) else "-",
                "char": f"{char_score:.3f}" if isinstance(char_score, (int, float)) else "-",
            }
        )
    table_lines = [
        "| Portion | Raw snippet | Repair reason | Confidence | Clean snippet | Dict score | Char score |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(table_rows, key=lambda r: int(r["portion"] if r["portion"].isdigit() else 999)):
        table_lines.append(
            "| "
            + " | ".join(
                [row["portion"], row["raw"], row["reason"], row["confidence"], row["clean"], row["dict"], row["char"]]
            )
            + " |"
        )
    out_path = Path(args.table_out) if args.table_out else run_dir / "repair_table.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Repair Table\n\n")
        if table_rows:
            f.write("\n".join(table_lines) + "\n")
        else:
            f.write("No repairs recorded for this run.\n")
    print(f"Wrote repair table to {out_path}")

    check_file = Path(args.check_file) if args.check_file else run_dir / "pagelines_final.jsonl"
    if not check_file.exists():
        print(f"WARNING: suspicious token check file missing: {check_file}", file=sys.stderr)
        return 1
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, str(repo_root / "scripts" / "regression" / "check_suspicious_tokens.py"),
           "--file", str(check_file), "--min-len", str(args.min_len)]
    proc = subprocess.run(cmd, cwd=repo_root)
    print(f"check_suspicious_tokens.py exit code: {proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
