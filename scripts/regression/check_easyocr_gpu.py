"""
Regression check: ensure EasyOCR ran on GPU (MPS) when available.

Usage:
  python scripts/regression/check_easyocr_gpu.py --debug-file <path/to/easyocr_debug.jsonl>

Behavior:
  - If torch MPS is unavailable on this host, exits 0 (nothing to enforce).
  - Otherwise, fails (exit 1) if:
      * The debug file is missing/empty, or
      * Any EasyOCR event reports gpu=false, or
      * No EasyOCR events were recorded.
  - Prints a short summary to stdout.
"""

import argparse
import json
import sys
from pathlib import Path


def mps_available() -> bool:
    try:
        import torch
        return bool(torch.backends.mps.is_available() and torch.backends.mps.is_built())
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-file", required=True, help="Path to easyocr_debug.jsonl")
    args = parser.parse_args()

    debug_path = Path(args.debug_file)
    if not debug_path.exists():
        print(f"[FAIL] Missing easyocr debug file: {debug_path}")
        sys.exit(1)

    if not mps_available():
        print("[SKIP] MPS not available on this host; no GPU expectation enforced.")
        sys.exit(0)

    lines = debug_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        print(f"[FAIL] easyocr debug file is empty: {debug_path}")
        sys.exit(1)

    events = []
    gpu_false = 0
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        events.append(obj)
        if obj.get("event", "").startswith("easyocr_") and obj.get("gpu") is False:
            gpu_false += 1

    if not events:
        print(f"[FAIL] No parseable EasyOCR events in {debug_path}")
        sys.exit(1)

    if gpu_false > 0:
        print(f"[FAIL] Found {gpu_false} EasyOCR events with gpu=false (expected true on MPS host).")
        sys.exit(1)

    print(f"[OK] EasyOCR debug shows GPU=true on MPS host ({len(events)} events checked).")


if __name__ == "__main__":
    main()
