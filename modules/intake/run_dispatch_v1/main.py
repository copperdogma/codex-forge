import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Dispatch downstream recipe based on dispatch_hint.json")
    parser.add_argument("--dispatch_hint", required=True)
    parser.add_argument("--default_recipe", default=None)
    parser.add_argument("--run_id", default=None)
    parser.add_argument("--dry_run", action="store_true", help="Print command without executing")
    args = parser.parse_args()

    with open(args.dispatch_hint, "r", encoding="utf-8") as f:
        hint = json.load(f)

    recipe = hint.get("recommended_recipe") or args.default_recipe
    if not recipe:
        print("No recommended recipe found and no default provided; aborting.")
        sys.exit(3)

    cmd = ["python", "driver.py", "--recipe", recipe]
    if args.run_id:
        cmd += ["--run-id", args.run_id]
    print("Dispatching:", " ".join(cmd))
    if args.dry_run:
        print("Dry run: not executing downstream recipe")
        sys.exit(0)
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
