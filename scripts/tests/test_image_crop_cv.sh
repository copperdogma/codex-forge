#!/usr/bin/env bash
# Manual integration check for image_crop_cv_v1 against the 12-page GT set.
# Requires: .venv active, PYTHONPATH=.

set -euo pipefail

PAGES=output/runs/image-crop-demo/pages.jsonl
OUT=output/runs/image-crop-demo/image_crops.jsonl
CROP=output/runs/image-crop-demo/crops

python modules/extract/image_crop_cv_v1/main.py \
  --pages "$PAGES" \
  --out "$OUT" \
  --crop-dir "$CROP" \
  --min-area-ratio 0.005 --max-area-ratio 0.99 --blur 3 --topk 5

python scripts/spikes/eval_detection.py \
  --gt configs/groundtruth/image_boxes_eval.jsonl \
  --detections "$OUT" \
  --iou 0.5
