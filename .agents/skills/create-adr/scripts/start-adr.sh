#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: start-adr.sh <number> <short-name>" >&2
  echo "Example: start-adr.sh 001 normalization-framework" >&2
  exit 1
fi

NUM="$1"
NAME="$2"

if [[ ! "$NAME" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]]; then
  echo "ERROR: Invalid name '$NAME'. Use lowercase letters, numbers, and hyphens only." >&2
  exit 1
fi

PADDED=$(printf "%03d" "$((10#$NUM))")
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../" && pwd)"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TODAY=$(date +%Y-%m-%d)

ADR_DIR="$ROOT/docs/decisions/adr-${PADDED}-${NAME}"
RESEARCH_DIR="$ADR_DIR/research"

if [[ -d "$ADR_DIR" ]]; then
  echo "ERROR: $ADR_DIR already exists" >&2
  exit 1
fi

mkdir -p "$RESEARCH_DIR"

sed "s/NNN/$PADDED/g; s/TITLE/${NAME}/g" "$SKILL_DIR/templates/adr.md" > "$ADR_DIR/adr.md"
sed "s/TOPIC/${NAME}/g; s/CREATED_DATE/${TODAY}/g" "$SKILL_DIR/templates/research-prompt.md" > "$RESEARCH_DIR/research-prompt.md"
sed "s/TOPIC/${NAME}/g" "$SKILL_DIR/templates/final-synthesis.md" > "$RESEARCH_DIR/final-synthesis.md"

echo "Created:"
echo "  $ADR_DIR/adr.md"
echo "  $RESEARCH_DIR/research-prompt.md"
echo "  $RESEARCH_DIR/final-synthesis.md"
echo ""
echo "Next: Fill in adr.md, then write the research prompt, then run research."
