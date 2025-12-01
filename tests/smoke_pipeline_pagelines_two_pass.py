"""Local smoke test for pagelines two-pass recipe.

Not intended for CI; exercises the wired recipe end-to-end and asserts
missing headers are only 169,170 for the current source PDF.
Requires the referenced pagelines run to exist (gpt4v-iter-r5).
"""

import json
import subprocess
import sys
from pathlib import Path


RECIPE = "configs/recipes/recipe-pagelines-two-pass.yaml"
RUN_DIR = Path("output/runs/deathtrap-pagelines-two-pass-r5")
HEADERS = RUN_DIR / "window_hypotheses.jsonl"


def run_recipe():
    rc = subprocess.call([sys.executable, "driver.py", "--recipe", RECIPE])
    if rc != 0:
        raise SystemExit(f"recipe failed with code {rc}")


def read_headers(path):
    ids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            ids.add(int(row["portion_id"]))
    return ids


def main():
    run_recipe()
    ids = read_headers(HEADERS)
    missing = [i for i in range(1, 401) if i not in ids]
    assert missing == [169, 170], f"Unexpected missing IDs: {missing}"
    print("Smoke passed: missing IDs == [169, 170]")


if __name__ == "__main__":
    main()

