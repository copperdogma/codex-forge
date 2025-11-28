#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[ff-engine smoke] ensuring Node >=18..."
node -e "const v=process.versions.node.split('.')[0]; if (v<18) { console.error('Need node >=18'); process.exit(1); }"

echo "[ff-engine smoke] running mock pipeline..."
python driver.py --recipe configs/recipes/recipe-ff-engine.yaml --mock --instrument --end-at validate_ff_engine

echo "[ff-engine smoke] done. Validation report:"
cat output/runs/deathtrap-ff-engine/gamebook_validation_node.json | sed -n '1,40p'
