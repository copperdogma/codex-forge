#!/usr/bin/env python3
"""
Fail-fast guard for legacy EasyOCR runs: ensure arm64 Python with Metal (MPS) available.
Usage: python scripts/check_arm_mps.py
Exit code 0 if OK, 1 otherwise.
"""
import sys
import platform

def main():
    machine = platform.machine().lower()
    if machine != "arm64":
        print(f"[FAIL] platform.machine()={machine} (expected arm64). Activate codex-arm-mps env for legacy EasyOCR.")
        sys.exit(1)
    try:
        import torch  # noqa: WPS433
    except Exception as e:  # pragma: no cover
        print(f"[FAIL] torch not importable: {e}. Activate codex-arm-mps env for legacy EasyOCR.")
        sys.exit(1)
    mps_ok = torch.backends.mps.is_built() and torch.backends.mps.is_available()
    if not mps_ok:
        print("[FAIL] Torch MPS not available. Install Metal-enabled torch in codex-arm-mps env for legacy EasyOCR.")
        sys.exit(1)
    print("[OK] arm64 + MPS available.")

if __name__ == "__main__":
    main()
