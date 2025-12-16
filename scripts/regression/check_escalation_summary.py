#!/usr/bin/env python
"""
Check escalation coverage for an OCR run.

Given a run directory (e.g. /private/tmp/ff-full-070-center-bias-test or output/runs/ff-canonical-...),
this script will:

- Locate the extract_ocr_ensemble_v1 ocr_ensemble outputs
- Read `ocr_escalation_summary.json` written by `modules/extract/extract_ocr_ensemble_v1/main.py`
- Optionally read the ocr_escalate_gpt4v adapter summary (`adapter_out.jsonl`)
- Print a concise summary of:
    * total quality rows
    * total pages needing escalation
    * total pages escalated inline
    * total pages escalated by the GPT‑4V adapter
    * total pages still marked as needing escalation after both passes
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_escalation_summary(run_dir: Path) -> Optional[Path]:
    """
    Find ocr_escalation_summary.json under the extract_ocr_ensemble_v1 outdir.
    We look for any */ocr_ensemble/ocr_escalation_summary.json to be robust to
    different stage ordinals.
    """
    for p in run_dir.rglob("ocr_escalation_summary.json"):
        return p
    return None


def find_escalate_adapter_summary(run_dir: Path) -> Optional[Path]:
    """
    Find the adapter summary JSONL produced by ocr_escalate_gpt4v_v1.
    This is typically named `adapter_out.jsonl` under the `*_ocr_ensemble_v1`
    merge/escalate adapter outdir (e.g. 06_ocr_ensemble_v1/adapter_out.jsonl).

    We search for any adapter_out.jsonl whose first JSON line has
    `"module_id": "ocr_escalate_gpt4v_v1"`.
    """
    for p in run_dir.rglob("adapter_out.jsonl"):
        try:
            with p.open("r", encoding="utf-8") as f:
                line = f.readline().strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("module_id") == "ocr_escalate_gpt4v_v1":
                return p
        except Exception:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Report OCR escalation coverage for a run")
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to the run directory (e.g. output/runs/ff-canonical-... or /tmp/...)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory does not exist: {run_dir}")

    # Load inline escalation summary from extract_ocr_ensemble_v1
    summary_path = find_escalation_summary(run_dir)
    if not summary_path:
        print(f"No ocr_escalation_summary.json found under {run_dir}")
        return

    esc = load_json(summary_path)
    total_quality = esc.get("total_quality_rows", 0)
    total_needing = esc.get("total_needing_escalation", 0)
    total_inline = esc.get("total_inline_escalated", 0)
    total_outstanding_after_inline = esc.get("total_escalation_outstanding", max(0, total_needing - total_inline))
    inline_budget = esc.get("escalation_budget_pages", None)
    inline_used = esc.get("escalated_pages_within_budget", None)

    # Load second-pass adapter summary if present
    adapter_path = find_escalate_adapter_summary(run_dir)
    adapter_escalated: int = 0
    adapter_pages: List[Any] = []
    if adapter_path is not None:
        try:
            with adapter_path.open("r", encoding="utf-8") as f:
                line = f.readline().strip()
            if line:
                data = json.loads(line)
                pages = data.get("escalated_pages") or []
                if isinstance(pages, list):
                    adapter_pages = pages
                    adapter_escalated = len(pages)
        except Exception as e:
            print(f"Warning: failed to read adapter summary {adapter_path}: {e}")

    total_after_adapter = max(0, total_needing - total_inline - adapter_escalated)

    print("=== OCR Escalation Summary ===")
    print(f"Run directory: {run_dir}")
    print(f"Inline summary: {summary_path}")
    print()
    print("Inline extract_ocr_ensemble_v1 escalation:")
    print(f"  total_quality_rows          : {total_quality}")
    print(f"  total_needing_escalation    : {total_needing}")
    print(f"  total_inline_escalated      : {total_inline}")
    print(f"  total_escalation_outstanding (after inline) : {total_outstanding_after_inline}")
    if inline_budget is not None:
        print(f"  inline_budget_pages         : {inline_budget}")
    if inline_used is not None:
        print(f"  inline_escalations_used     : {inline_used}")
    print()
    if adapter_path is not None:
        print(f"GPT-4V adapter summary        : {adapter_path}")
        print(f"  second_pass_escalated_pages : {adapter_escalated}")
        print(f"  second_pass_page_keys       : {adapter_pages[:20]}")
    else:
        print("GPT-4V adapter summary        : not found (stage may not have run)")
        adapter_escalated = 0

    print()
    print("Overall escalation (both passes):")
    print(f"  total_needing_escalation    : {total_needing}")
    print(f"  total_escalated (inline+2nd): {total_inline + adapter_escalated}")
    print(f"  total_outstanding           : {max(0, total_needing - total_inline - adapter_escalated)}")


if __name__ == "__main__":
    main()



